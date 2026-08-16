import pytest
import pytest_asyncio

from app.domain.enums import JobStatus, JobType
from app.domain.models import JobCreate
from app.infrastructure.persistent_store import PersistentJobStore


@pytest.mark.asyncio
async def test_create_job_has_job_type_and_duration_fields(db_store):
    job = await db_store.create_job(
        name="test",
        job_type=JobType.SIMULATED,
        priority=1,
        deadline=None,
        performance_target=1,
        total_epochs=2,
        baseline_carbon_estimate_g=10.0,
    )
    assert job.job_type == JobType.SIMULATED
    assert job.total_duration_hours == 0.0
    assert job.status == JobStatus.QUEUED


@pytest.mark.asyncio
async def test_fresh_db_per_test(db_store, tmp_path):
    """Each test gets isolated store via conftest fixture."""
    jobs = await db_store.list_jobs()
    assert jobs == []


@pytest.mark.asyncio
async def test_profile_seeded(db_store):
    profile = await db_store.get_profile(JobType.SIMULATED)
    assert profile is not None
    assert profile.expected_power_draw_kw > 0
