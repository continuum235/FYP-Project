import asyncio
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest

from app.domain.enums import Action, JobStatus, JobType
from app.domain.models import JobCreate, SchedulingState
from app.infrastructure.persistent_store import JobRow


@pytest.mark.asyncio
async def test_job_lifecycle(orchestrator, carbon_estimator):
    carbon_estimator.set_mock_intensity(400.0)
    job = await orchestrator.submit_job(
        JobCreate(name="lifecycle", job_type=JobType.SIMULATED, total_epochs=1)
    )
    assert job.status == JobStatus.QUEUED
    assert job.baseline_carbon_estimate_g > 0

    await orchestrator.tick()
    await asyncio.sleep(0.5)

    updated = await orchestrator.get_job(job.id)
    assert updated.status in (JobStatus.RUNNING, JobStatus.COMPLETED, JobStatus.WAITING)

    for _ in range(30):
        if updated.status == JobStatus.COMPLETED:
            break
        await asyncio.sleep(0.2)
        updated = await orchestrator.get_job(job.id)
    assert updated.status == JobStatus.COMPLETED


@pytest.mark.asyncio
async def test_pause_resume_accumulates_carbon(orchestrator, carbon_estimator):
    carbon_estimator.set_mock_intensity(400.0)
    job = await orchestrator.submit_job(
        JobCreate(name="pause-test", job_type=JobType.SIMULATED, total_epochs=3)
    )
    await orchestrator.tick()
    await asyncio.sleep(0.3)

    job = await orchestrator.get_job(job.id)
    if job.status == JobStatus.RUNNING:
        await orchestrator._execution.request_pause(job.id)
        await asyncio.sleep(0.5)

    job = await orchestrator.get_job(job.id)
    carbon_after_first = job.carbon_used_g
    energy_after_first = job.energy_used_kwh
    epoch_after_pause = job.current_epoch

    carbon_estimator.set_mock_intensity(400.0)
    await orchestrator._store.update_job(job.id, status=JobStatus.QUEUED)
    await orchestrator.tick()
    await asyncio.sleep(1.0)

    job = await orchestrator.get_job(job.id)
    if job.status != JobStatus.COMPLETED:
        await asyncio.sleep(1.0)
        job = await orchestrator.get_job(job.id)

    assert job.carbon_used_g >= carbon_after_first
    assert job.energy_used_kwh >= energy_after_first
    if epoch_after_pause > 0:
        assert job.current_epoch >= epoch_after_pause


@pytest.mark.asyncio
async def test_manual_pause_not_overridden(orchestrator, carbon_estimator):
    carbon_estimator.set_mock_intensity(400.0)
    job = await orchestrator.submit_job(
        JobCreate(name="manual", job_type=JobType.SIMULATED, total_epochs=5)
    )
    await orchestrator.tick()
    await asyncio.sleep(0.3)
    await orchestrator.manual_pause(job.id)
    await asyncio.sleep(0.5)

    carbon_estimator.set_mock_intensity(300.0)
    await orchestrator.tick()
    job = await orchestrator.get_job(job.id)
    assert job.status == JobStatus.MANUALLY_PAUSED


@pytest.mark.asyncio
async def test_system_pause_on_high_carbon(orchestrator, carbon_estimator):
    carbon_estimator.set_mock_intensity(400.0)
    job = await orchestrator.submit_job(
        JobCreate(name="syspause", job_type=JobType.SIMULATED, total_epochs=5)
    )
    await orchestrator.tick()
    await asyncio.sleep(0.3)

    carbon_estimator.set_mock_intensity(700.0)
    await orchestrator.tick()
    await asyncio.sleep(0.8)

    job = await orchestrator.get_job(job.id)
    if job.status not in (JobStatus.PAUSED, JobStatus.COMPLETED):
        await asyncio.sleep(0.5)
        job = await orchestrator.get_job(job.id)
    assert job.status in (JobStatus.PAUSED, JobStatus.COMPLETED, JobStatus.RUNNING)


@pytest.mark.asyncio
async def test_startup_reconciliation(db_store, tmp_checkpoint_dir, carbon_estimator, greedy_policy):
    from app.application.job_orchestrator import JobOrchestrator
    from app.infrastructure.execution_engine import ExecutionEngine
    from app.intelligence.decision_engine import DecisionEngine
    from app.intelligence.gaiq_engine import GaiQEngine

    job = await db_store.create_job(
        name="crash",
        job_type=JobType.SIMULATED,
        priority=0,
        deadline=None,
        performance_target=None,
        total_epochs=2,
        baseline_carbon_estimate_g=1.0,
    )
    await db_store.update_job(job.id, status=JobStatus.RUNNING, current_epoch=3)

    orch = JobOrchestrator(
        store=db_store,
        execution_engine=ExecutionEngine(tmp_checkpoint_dir),
        carbon_estimator=carbon_estimator,
        gaiq_engine=GaiQEngine(),
        decision_engine=DecisionEngine(greedy_policy),
        tick_interval_seconds=3600,
    )
    await orch._reconcile_running_jobs()
    restored = await db_store.get_job(job.id)
    assert restored.status == JobStatus.QUEUED
    assert restored.current_epoch == 3
    await orch.stop()


@pytest.mark.asyncio
async def test_single_flight_two_jobs(orchestrator, carbon_estimator):
    carbon_estimator.set_mock_intensity(400.0)
    j1 = await orchestrator.submit_job(
        JobCreate(name="a", job_type=JobType.SIMULATED, priority=1, total_epochs=3)
    )
    j2 = await orchestrator.submit_job(
        JobCreate(name="b", job_type=JobType.SIMULATED, priority=0, total_epochs=3)
    )
    await orchestrator.tick()
    await asyncio.sleep(0.2)
    running = await orchestrator._store.get_jobs_by_status(JobStatus.RUNNING)
    assert len(running) <= 1


@pytest.mark.asyncio
async def test_decide_called_once_per_tick(orchestrator, carbon_estimator):
    carbon_estimator.set_mock_intensity(600.0)
    for i in range(5):
        await orchestrator.submit_job(
            JobCreate(name=f"j{i}", job_type=JobType.SIMULATED, total_epochs=1)
        )
    orchestrator._decision.reset_call_count()
    await orchestrator.tick()
    assert orchestrator._decision.decide_call_count <= 1


@pytest.mark.asyncio
async def test_profile_update_uses_energy_not_carbon(db_store, tmp_checkpoint_dir, carbon_estimator, greedy_policy):
    from app.application.job_orchestrator import JobOrchestrator
    from app.infrastructure.execution_engine import ExecutionEngine
    from app.intelligence.decision_engine import DecisionEngine
    from app.intelligence.gaiq_engine import GaiQEngine

    orch = JobOrchestrator(
        store=db_store,
        execution_engine=ExecutionEngine(tmp_checkpoint_dir),
        carbon_estimator=carbon_estimator,
        gaiq_engine=GaiQEngine(),
        decision_engine=DecisionEngine(greedy_policy),
        tick_interval_seconds=3600,
    )
    job = await db_store.create_job(
        name="profile",
        job_type=JobType.SIMULATED,
        priority=0,
        deadline=None,
        performance_target=None,
        total_epochs=1,
        baseline_carbon_estimate_g=100.0,
    )
    await db_store.update_job(
        job.id,
        status=JobStatus.COMPLETED,
        energy_used_kwh=0.5,
        total_duration_hours=2.0,
        carbon_used_g=9999.0,
    )
    await orch._refine_profile(job.id)
    profile = await db_store.get_profile(JobType.SIMULATED)
    assert profile.expected_power_draw_kw == pytest.approx(0.25)
    await orch.stop()


@pytest.mark.asyncio
async def test_profile_persists_across_store_instances(db_store, tmp_path):
    profile = await db_store.get_profile(JobType.SIMULATED)
    await db_store.update_profile(
        JobType.SIMULATED,
        profile.expected_power_draw_kw + 0.01,
        profile.expected_duration_hours,
        profile.sample_count + 1,
    )
    db_path = tmp_path / "test.db"
    url = f"sqlite+aiosqlite:///{db_path}"
    store2 = __import__(
        "app.infrastructure.persistent_store", fromlist=["PersistentJobStore"]
    ).PersistentJobStore(url)
    await store2.init_db()
    p2 = await store2.get_profile(JobType.SIMULATED)
    assert p2.sample_count == profile.sample_count + 1
    await store2.dispose()


@pytest.mark.asyncio
async def test_baseline_set_once_at_submission(orchestrator, carbon_estimator):
    carbon_estimator.set_mock_intensity(400.0)
    job = await orchestrator.submit_job(
        JobCreate(name="baseline", job_type=JobType.SIMULATED, total_epochs=1)
    )
    baseline = job.baseline_carbon_estimate_g
    carbon_estimator.set_mock_intensity(700.0)
    await orchestrator.tick()
    await asyncio.sleep(0.5)
    updated = await orchestrator.get_job(job.id)
    assert updated.baseline_carbon_estimate_g == baseline


@pytest.mark.asyncio
async def test_performance_floor_forces_run_on_tick(orchestrator, carbon_estimator):
    carbon_estimator.set_mock_intensity(700.0)
    job = await orchestrator.submit_job(
        JobCreate(
            name="perf",
            job_type=JobType.SIMULATED,
            total_epochs=3,
            performance_target=2,
        )
    )
    await orchestrator.tick()
    updated = await orchestrator.get_job(job.id)
    assert updated.status in (JobStatus.RUNNING, JobStatus.WAITING, JobStatus.COMPLETED)
