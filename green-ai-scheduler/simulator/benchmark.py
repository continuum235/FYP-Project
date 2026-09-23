import copy
import json
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

from app.domain.enums import Action
from app.domain.models import SchedulingState
from app.intelligence.defaults import GREEDY_PAUSE_THRESHOLD, GREEDY_RUN_THRESHOLD
from app.intelligence.policies.constraint_lexicographic import ConstraintLexicographicPolicy
from app.intelligence.policies.forecast import ForecastPolicy
from app.intelligence.policies.greedy import GreedyPolicy
from app.intelligence.state_builder import (
    forecast_avg_and_min,
    progress_ratio,
    time_to_clean_window_hours,
)
from simulator.metrics import BenchmarkMetrics
from simulator.scoring import ScoreConfig, score_results
from simulator.workload_generator import WorkloadJob, generate_workload, workload_to_dicts

SIM_TICK_HOURS = 1.0 / 12.0


@dataclass
class SimJob:
    job_id: int
    priority: int
    total_epochs: int
    performance_target: int
    current_epoch: int = 0
    pause_count: int = 0
    status: str = "QUEUED"
    carbon_used_g: float = 0.0
    baseline_carbon_g: float = 50.0
    deadline_tick: int = 1000
    arrival_tick: int = 0
    completion_tick: int | None = None
    carbon_intensities: list[float] = field(default_factory=list)


@dataclass
class SimMetrics:
    total_carbon_g: float = 0.0
    carbon_saved_g: float = 0.0
    deadline_misses: int = 0
    performance_violations: int = 0
    pause_count_total: int = 0
    jobs_completed: int = 0
    clean_window_finishes: int = 0


@dataclass
class SchedulingSimulator:
    carbon_series: np.ndarray
    policy: object
    run_threshold: float = 550.0
    jobs: list[SimJob] = field(default_factory=list)
    current_tick: int = 0
    running_job: SimJob | None = None
    metrics: SimMetrics = field(default_factory=SimMetrics)
    rng: np.random.Generator = field(default_factory=lambda: np.random.default_rng(42))

    def add_poisson_arrivals(self, rate: float, horizon: int) -> None:
        t = 0
        jid = 0
        created = 0
        while t < horizon:
            t += int(self.rng.exponential(1.0 / rate)) + 1
            if t >= horizon:
                break
            self.jobs.append(
                SimJob(
                    job_id=jid,
                    priority=self.rng.integers(0, 3),
                    total_epochs=self.rng.integers(1, 3),
                    performance_target=1,
                    deadline_tick=t + self.rng.integers(50, 200),
                    arrival_tick=t,
                    baseline_carbon_g=40.0 + self.rng.random() * 20,
                )
            )
            jid += 1
            created += 1

        if created == 0 and horizon > 0:
            fallback_count = min(5, max(2, horizon // 4))
            step = max(1, horizon // max(1, fallback_count))
            for i in range(fallback_count):
                tick = min(horizon - 1, max(1, (i + 1) * step))
                self.jobs.append(
                    SimJob(
                        job_id=jid,
                        priority=i % 3,
                        total_epochs=2,
                        performance_target=1,
                        deadline_tick=min(horizon + 20, tick + 20),
                        arrival_tick=tick,
                        baseline_carbon_g=50.0 + i * 5,
                    )
                )
                jid += 1

    def add_workload(self, workload: list[WorkloadJob]) -> None:
        self.jobs = [
            SimJob(
                job_id=job.job_id,
                priority=job.priority,
                total_epochs=job.total_epochs,
                performance_target=job.performance_target,
                deadline_tick=job.deadline_tick,
                arrival_tick=job.arrival_tick,
                baseline_carbon_g=job.baseline_carbon_g,
            )
            for job in workload
        ]

    def _intensity_at(self, tick: int) -> float:
        idx = min(tick, len(self.carbon_series) - 1)
        return float(self.carbon_series[idx])

    def _build_state(self, job: SimJob) -> SchedulingState:
        intensity = self._intensity_at(self.current_tick)
        forecast = [
            self._intensity_at(self.current_tick + i)
            for i in range(1, 13)
        ]
        f_avg, f_min = forecast_avg_and_min(forecast)
        clean_window = time_to_clean_window_hours(
            forecast, self.run_threshold, step_hours=SIM_TICK_HOURS
        )
        queue_len = sum(
            1
            for j in self.jobs
            if j.status in ("QUEUED", "WAITING", "PAUSED")
            and j.arrival_tick <= self.current_tick
        )
        prog = progress_ratio(job.current_epoch, job.total_epochs)
        return SchedulingState(
            is_currently_running=job is self.running_job,
            carbon_intensity=intensity,
            carbon_forecast=forecast,
            forecast_avg=f_avg,
            forecast_min=f_min,
            time_to_clean_window_hours=clean_window,
            time_waiting_hours=max(0.0, (self.current_tick - job.arrival_tick) * SIM_TICK_HOURS),
            time_running_hours=0.5 if self.running_job else 0.0,
            time_to_deadline_hours=max(0, (job.deadline_tick - self.current_tick) * SIM_TICK_HOURS),
            priority=job.priority,
            pause_count=job.pause_count,
            max_pause_count=10,
            current_epoch=job.current_epoch,
            performance_target=job.performance_target,
            total_epochs=job.total_epochs,
            progress_ratio=prog,
            queue_length=queue_len,
        )

    def _select_candidate(self) -> SimJob | None:
        if self.running_job:
            return self.running_job
        eligible = [
            j
            for j in self.jobs
            if j.status in ("QUEUED", "WAITING", "PAUSED") and j.arrival_tick <= self.current_tick
        ]
        if not eligible:
            return None
        eligible.sort(key=lambda j: (-j.priority, j.arrival_tick))
        return eligible[0]

    def tick(self) -> None:
        for j in self.jobs:
            if j.arrival_tick == self.current_tick and j.status == "QUEUED":
                pass

        job = self._select_candidate()
        if job is None:
            self.current_tick += 1
            return

        action = self.policy.decide(self._build_state(job))

        if self.running_job:
            if action in (Action.WAIT, Action.PAUSE):
                job.pause_count += 1
                self.metrics.pause_count_total += 1
                if job.current_epoch < job.performance_target:
                    self.metrics.performance_violations += 1
                job.status = "PAUSED"
                self.running_job = None
            else:
                job.current_epoch += 1
                intensity = self._intensity_at(self.current_tick)
                job.carbon_intensities.append(intensity)
                session_carbon = 0.05 * intensity / 500
                job.carbon_used_g += session_carbon
                if job.current_epoch >= job.total_epochs:
                    job.status = "COMPLETED"
                    job.completion_tick = self.current_tick
                    self.metrics.jobs_completed += 1
                    self.metrics.total_carbon_g += job.carbon_used_g
                    self.metrics.carbon_saved_g += max(0, job.baseline_carbon_g - job.carbon_used_g)
                    if intensity < self.run_threshold:
                        self.metrics.clean_window_finishes += 1
                    self.running_job = None
        else:
            if action == Action.RUN:
                job.status = "RUNNING"
                self.running_job = job
            else:
                job.status = "WAITING"

        if self.current_tick > 0:
            for j in self.jobs:
                if (
                    j.status not in ("COMPLETED", "FAILED")
                    and self.current_tick > j.deadline_tick
                ):
                    if j.status != "FAILED":
                        self.metrics.deadline_misses += 1
                        j.completion_tick = self.current_tick
                    j.status = "FAILED"

        self.current_tick += 1

    def run(self, horizon: int) -> SimMetrics:
        for _ in range(horizon):
            self.tick()
        return self.metrics


def load_carbon_csv(path: Path, validation_only: bool = True) -> np.ndarray:
    rng = np.random.default_rng(0)
    if not path.exists():
        return rng.uniform(329, 706, size=5000)

    try:
        df = pd.read_csv(path)
    except Exception:
        return rng.uniform(329, 706, size=5000)

    if df.empty:
        return rng.uniform(329, 706, size=5000)

    normalized = {str(c).lower().strip(): c for c in df.columns}
    candidates = [
        "carbon intensity gco₂eq/kwh (direct)",
        "carbon intensity gco2eq/kwh (direct)",
        "carbon intensity",
        "carbon_intensity",
        "carbon intensity gco2eq/kwh",
        "carbon intensity gco₂eq/kwh",
    ]
    col = next((normalized[c] for c in candidates if c in normalized), None)
    if col is None:
        for c in df.columns:
            label = str(c).lower()
            if "carbon" in label and "intensity" in label:
                col = c
                break
    if col is None:
        return rng.uniform(329, 706, size=5000)

    try:
        series = df[col].astype(float).dropna().to_numpy()
    except Exception:
        return rng.uniform(329, 706, size=5000)

    if len(series) == 0:
        return rng.uniform(329, 706, size=5000)
    if validation_only:
        split = int(len(series) * 10 / 12)
        series = series[split:]
    return series.astype(float)


def run_benchmark(
    csv_path: Path,
    policies: list[str],
    horizon: int = 2000,
    output_path: Path | None = None,
) -> dict:
    carbon = load_carbon_csv(csv_path)
    workload = generate_workload(seed=42, horizon=horizon)
    results = {}
    for name in policies:
        key = (name or "").strip().lower().replace("-", "_").replace(" ", "_")
        if key in {"greedy"}:
            policy = GreedyPolicy(
                run_threshold=GREEDY_RUN_THRESHOLD,
                pause_threshold=GREEDY_PAUSE_THRESHOLD,
            )
        elif key in {"forecast", "forecast_based", "forecast_policy"}:
            policy = ForecastPolicy(
                run_threshold=GREEDY_RUN_THRESHOLD,
                pause_threshold=GREEDY_PAUSE_THRESHOLD,
            )
        elif key in {"constraint_lexicographic", "constraintlexicographic", "constraint_lexicographic_policy"}:
            policy = ConstraintLexicographicPolicy(
                run_threshold=GREEDY_RUN_THRESHOLD,
                pause_threshold=GREEDY_PAUSE_THRESHOLD,
            )
        else:
            from app.intelligence.policies.ppo_policy import PPOPolicy
            from stable_baselines3 import PPO

            model_path = Path(__file__).parent / "models" / "ppo_scheduler.zip"
            if model_path.exists():
                policy = PPOPolicy(model=PPO.load(str(model_path)))
            else:
                policy = GreedyPolicy(
                    run_threshold=GREEDY_RUN_THRESHOLD,
                    pause_threshold=GREEDY_PAUSE_THRESHOLD,
                )

        sim = SchedulingSimulator(carbon_series=carbon, policy=policy)
        sim.add_workload(copy.deepcopy(workload))
        metrics = sim.run(horizon)
        results[name] = {
            "total_carbon_g": metrics.total_carbon_g,
            "carbon_saved_g": metrics.carbon_saved_g,
            "deadline_misses": metrics.deadline_misses,
            "performance_violations": metrics.performance_violations,
            "avg_pause_count": metrics.pause_count_total / max(metrics.jobs_completed, 1),
            "jobs_completed": metrics.jobs_completed,
            "clean_window_finishes": metrics.clean_window_finishes,
        }

    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(results, indent=2))
    return results


SUPPORTED_POLICIES = ("greedy", "forecast", "constraint_lexicographic", "ppo")


def _policy_for_comparison(name: str):
    from app.intelligence.policies.ppo_policy import PPOPolicy

    key = name.strip().lower().replace("-", "_").replace(" ", "_")
    if key == "greedy":
        return GreedyPolicy(GREEDY_RUN_THRESHOLD, GREEDY_PAUSE_THRESHOLD)
    if key == "forecast":
        return ForecastPolicy(GREEDY_RUN_THRESHOLD, GREEDY_PAUSE_THRESHOLD)
    if key == "constraint_lexicographic":
        return ConstraintLexicographicPolicy(GREEDY_RUN_THRESHOLD, GREEDY_PAUSE_THRESHOLD)
    if key == "ppo":
        model_path = Path(__file__).parent / "models" / "ppo_scheduler.zip"
        if model_path.exists():
            from stable_baselines3 import PPO

            return PPOPolicy(model=PPO.load(str(model_path)))
        return PPOPolicy(model=None)
    raise ValueError(f"unsupported policy: {name}")


def _metrics_for_simulation(sim: SchedulingSimulator, workload: list[WorkloadJob]) -> BenchmarkMetrics:
    submitted = len(sim.jobs)
    completed = [job for job in sim.jobs if job.status == "COMPLETED"]
    failed = [job for job in sim.jobs if job.status == "FAILED"]
    baseline = sum(job.baseline_carbon_g for job in workload)
    intensities = [intensity for job in completed for intensity in job.carbon_intensities]
    waiting_ticks = [
        max(0, (job.completion_tick or sim.current_tick) - job.arrival_tick - len(job.carbon_intensities))
        for job in completed
    ]
    completion_hours = [
        max(0, (job.completion_tick or sim.current_tick) - job.arrival_tick) * SIM_TICK_HOURS
        for job in completed
    ]
    deadline_satisfaction = (len(completed) / max(len(completed) + len(failed), 1)) * 100
    clean_finishes = sim.metrics.clean_window_finishes
    total_carbon = sim.metrics.total_carbon_g
    return BenchmarkMetrics(
        total_carbon_g=total_carbon,
        baseline_carbon_g=baseline,
        carbon_saved_g=max(0.0, baseline - total_carbon),
        carbon_reduction_percent=(max(0.0, baseline - total_carbon) / baseline * 100) if baseline else 0.0,
        average_carbon_intensity=(sum(intensities) / len(intensities)) if intensities else None,
        carbon_per_completed_job_g=(total_carbon / len(completed)) if completed else None,
        jobs_submitted=submitted,
        jobs_completed=len(completed),
        jobs_failed=len(failed),
        deadline_misses=sim.metrics.deadline_misses,
        deadline_satisfaction_percent=deadline_satisfaction,
        total_pause_count=sim.metrics.pause_count_total,
        average_pause_count=sim.metrics.pause_count_total / max(len(completed), 1),
        total_waiting_time_hours=sum(waiting_ticks) * SIM_TICK_HOURS,
        average_waiting_time_hours=(sum(waiting_ticks) * SIM_TICK_HOURS / len(completed)) if completed else None,
        average_completion_time_hours=(sum(completion_hours) / len(completed)) if completed else None,
        performance_violations=sim.metrics.performance_violations,
        jobs_affected_by_performance_constraints=sum(
            1 for job in sim.jobs if job.pause_count and job.current_epoch < job.performance_target
        ),
        clean_window_finishes=clean_finishes,
        clean_window_completion_percent=(clean_finishes / len(completed) * 100) if completed else 0.0,
    )


def run_comparison(
    csv_path: Path,
    policies: list[str] | None = None,
    horizon: int = 2000,
    seed: int = 42,
    scoring: dict[str, float] | None = None,
) -> dict:
    selected = policies or list(SUPPORTED_POLICIES)
    normalized = [name.strip().lower().replace("-", "_").replace(" ", "_") for name in selected]
    invalid = [name for name in normalized if name not in SUPPORTED_POLICIES]
    if invalid:
        raise ValueError(f"unsupported policies: {', '.join(invalid)}")
    if horizon < 1 or horizon > 100000:
        raise ValueError("horizon must be between 1 and 100000")

    carbon = load_carbon_csv(csv_path)
    workload = generate_workload(seed=seed, horizon=horizon)
    result_rows: dict[str, dict] = {}
    for name in normalized:
        sim = SchedulingSimulator(carbon_series=carbon.copy(), policy=_policy_for_comparison(name))
        sim.add_workload(copy.deepcopy(workload))
        sim.run(horizon)
        result_rows[name] = _metrics_for_simulation(sim, workload).to_dict()

    score_config = ScoreConfig.from_dict(scoring)
    return {
        "config": {
            "seed": seed,
            "horizon": horizon,
            "dataset": str(csv_path),
            "policies": normalized,
            "workload": workload_to_dicts(workload),
            "scoring": score_config.weights if score_config else None,
        },
        "policies": result_rows,
        "score": score_results(result_rows, score_config),
    }


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", default=str(Path(__file__).parent / "data" / "snapshots_2026-02-10_IN-2025-5_minute.csv"))
    parser.add_argument("--policies", default="greedy,forecast,constraint_lexicographic,ppo")
    parser.add_argument("--horizon", type=int, default=2000)
    parser.add_argument("--output", default=str(Path(__file__).parent / "logs" / "benchmark_results.json"))
    args = parser.parse_args()
    out = run_benchmark(
        Path(args.csv),
        args.policies.split(","),
        args.horizon,
        Path(args.output),
    )
    print(json.dumps(out, indent=2))
