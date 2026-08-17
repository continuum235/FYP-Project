import asyncio
import os
import tempfile
from pathlib import Path

import pytest
import pytest_asyncio

from app.application.job_orchestrator import JobOrchestrator
from app.config import settings
from app.domain.enums import JobType
from app.domain.models import JobCreate
from app.infrastructure.execution_engine import ExecutionEngine
from app.infrastructure.persistent_store import PersistentJobStore
from app.intelligence.carbon_estimator import CarbonEstimator
from app.intelligence.decision_engine import DecisionEngine
from app.intelligence.gaiq_engine import GaiQEngine
from app.intelligence.policies.greedy import GreedyPolicy
from app.intelligence.policies.ppo_policy import PPOPolicy


@pytest.fixture
def tmp_checkpoint_dir(tmp_path):
    d = tmp_path / "checkpoints"
    d.mkdir()
    return str(d)


@pytest_asyncio.fixture
async def db_store(tmp_path):
    db_path = tmp_path / "test.db"
    url = f"sqlite+aiosqlite:///{db_path}"
    store = PersistentJobStore(url)
    await store.init_db()
    yield store
    await store.dispose()


@pytest.fixture
def carbon_estimator():
    ce = CarbonEstimator(api_key="", zone="IN")
    ce.set_mock_intensity(400.0)
    return ce


@pytest.fixture
def greedy_policy():
    return GreedyPolicy(
        run_threshold=450.0,
        pause_threshold=550.0,
        max_pause_count=10,
        deadline_safety_margin_hours=0.5,
    )


@pytest.fixture
def ppo_policy():
    return PPOPolicy(model=None)


@pytest.fixture(params=["greedy", "ppo"])
def policy(request, greedy_policy, ppo_policy):
    if request.param == "greedy":
        return greedy_policy
    return ppo_policy


@pytest_asyncio.fixture
async def orchestrator(db_store, tmp_checkpoint_dir, carbon_estimator, policy):
    decision = DecisionEngine(policy)
    execution = ExecutionEngine(tmp_checkpoint_dir, max_workers=1)
    gaiq = GaiQEngine()
    orch = JobOrchestrator(
        store=db_store,
        execution_engine=execution,
        carbon_estimator=carbon_estimator,
        gaiq_engine=gaiq,
        decision_engine=decision,
        tick_interval_seconds=3600,
        max_pause_count=10,
        run_threshold=450.0,
    )
    yield orch
    await orch.stop()
    await execution.shutdown()
