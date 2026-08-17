import os
from pathlib import Path

from fastapi import FastAPI
from stable_baselines3 import PPO

from app.application.job_orchestrator import JobOrchestrator
from app.config import settings
from app.infrastructure.execution_engine import ExecutionEngine
from app.infrastructure.persistent_store import PersistentJobStore
from app.intelligence.carbon_estimator import CarbonEstimator
from app.intelligence.decision_engine import DecisionEngine, build_policy
from app.intelligence.gaiq_engine import GaiQEngine
from app.intelligence.policies.greedy import GreedyPolicy
from app.intelligence.policies.ppo_policy import PPOPolicy

_orchestrator: JobOrchestrator | None = None


def _load_ppo() -> PPOPolicy | None:
    path = Path(settings.ppo_model_path)
    if path.exists():
        model = PPO.load(str(path))
        return PPOPolicy(
            model=model,
            deadline_critical_hours=settings.deadline_critical_hours,
        )
    return None


def switch_policy(app: FastAPI, name: str) -> None:
    orch: JobOrchestrator = app.state.orchestrator
    greedy = GreedyPolicy(
        run_threshold=settings.greedy_run_threshold,
        pause_threshold=settings.greedy_pause_threshold,
        max_pause_count=settings.greedy_max_pause_count,
        deadline_safety_margin_hours=settings.greedy_deadline_safety_margin_hours,
    )
    ppo = _load_ppo()
    policy = build_policy(name, greedy=greedy, ppo=ppo)
    orch._decision.set_policy(policy)


async def init_app_state(app: FastAPI) -> None:
    global _orchestrator
    os.makedirs(settings.checkpoint_dir, exist_ok=True)
    store = PersistentJobStore(settings.database_url)
    await store.init_db()
    carbon = CarbonEstimator(
        api_key=settings.electricity_maps_api_key,
        zone=settings.electricity_maps_zone,
        cache_ttl_seconds=settings.carbon_cache_ttl_seconds,
    )
    greedy = GreedyPolicy(
        run_threshold=settings.greedy_run_threshold,
        pause_threshold=settings.greedy_pause_threshold,
        max_pause_count=settings.greedy_max_pause_count,
        deadline_safety_margin_hours=settings.greedy_deadline_safety_margin_hours,
    )
    ppo = _load_ppo()
    policy = build_policy(settings.scheduling_policy, greedy=greedy, ppo=ppo)
    decision = DecisionEngine(policy)
    execution = ExecutionEngine(settings.checkpoint_dir, max_workers=1)
    gaiq = GaiQEngine()
    orch = JobOrchestrator(
        store=store,
        execution_engine=execution,
        carbon_estimator=carbon,
        gaiq_engine=gaiq,
        decision_engine=decision,
        tick_interval_seconds=settings.tick_interval_seconds,
        max_pause_count=settings.greedy_max_pause_count,
        run_threshold=settings.greedy_run_threshold,
    )
    await orch.start()
    app.state.orchestrator = orch
    app.state.store = store
    _orchestrator = orch


async def shutdown_app_state(app: FastAPI) -> None:
    orch: JobOrchestrator = app.state.orchestrator
    await orch.stop()
    await orch._execution.shutdown()
    await app.state.store.dispose()


def get_orchestrator(app: FastAPI) -> JobOrchestrator:
    return app.state.orchestrator
