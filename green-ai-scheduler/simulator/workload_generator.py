from dataclasses import asdict, dataclass

import numpy as np


@dataclass(frozen=True)
class WorkloadJob:
    job_id: int
    priority: int
    total_epochs: int
    performance_target: int
    deadline_tick: int
    arrival_tick: int
    baseline_carbon_g: float


def generate_workload(seed: int, horizon: int, rate: float = 0.02) -> list[WorkloadJob]:
    rng = np.random.default_rng(seed)
    jobs: list[WorkloadJob] = []
    tick = 0
    job_id = 0
    while tick < horizon:
        tick += int(rng.exponential(1.0 / rate)) + 1
        if tick >= horizon:
            break
        jobs.append(
            WorkloadJob(
                job_id=job_id,
                priority=int(rng.integers(0, 3)),
                total_epochs=int(rng.integers(1, 3)),
                performance_target=1,
                deadline_tick=tick + int(rng.integers(50, 200)),
                arrival_tick=tick,
                baseline_carbon_g=float(40.0 + rng.random() * 20),
            )
        )
        job_id += 1

    if not jobs and horizon > 0:
        fallback_count = min(5, max(2, horizon // 4))
        step = max(1, horizon // max(1, fallback_count))
        for index in range(fallback_count):
            arrival = min(horizon - 1, max(1, (index + 1) * step))
            jobs.append(
                WorkloadJob(
                    job_id=job_id,
                    priority=index % 3,
                    total_epochs=2,
                    performance_target=1,
                    deadline_tick=min(horizon + 20, arrival + 20),
                    arrival_tick=arrival,
                    baseline_carbon_g=50.0 + index * 5,
                )
            )
            job_id += 1
    return jobs


def workload_to_dicts(workload: list[WorkloadJob]) -> list[dict]:
    return [asdict(job) for job in workload]