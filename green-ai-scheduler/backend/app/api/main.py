from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI, HTTPException, Query

from app.api.deps import get_orchestrator, init_app_state, shutdown_app_state
from app.domain.models import BulkJobCreate, GridStatus, JobCreate, JobRead, StatsResponse


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    await init_app_state(app)
    yield
    await shutdown_app_state(app)


def create_app() -> FastAPI:
    app = FastAPI(title="Green Hours Scheduler", lifespan=lifespan)

    @app.get("/")
    async def root() -> dict:
        return {
            "service": "Green Hours Scheduler",
            "docs": "/docs",
            "health": "/health",
        }

    @app.get("/health")
    async def health() -> dict:
        return {"status": "ok"}

    @app.post("/jobs", response_model=JobRead)
    async def submit_job(payload: JobCreate) -> JobRead:
        orch = get_orchestrator(app)
        job = await orch.submit_job(payload)
        return JobRead.model_validate(job)

    @app.post("/jobs/bulk", response_model=list[JobRead])
    async def submit_jobs_bulk(payload: BulkJobCreate) -> list[JobRead]:
        orch = get_orchestrator(app)
        created = []
        for i in range(payload.count):
            job = await orch.submit_job(
                JobCreate(
                    name=f"{payload.name_prefix}-{i + 1}",
                    job_type=payload.job_type,
                    priority=payload.priority + (payload.count - i),
                    total_epochs=payload.total_epochs,
                    performance_target=payload.performance_target,
                )
            )
            created.append(JobRead.model_validate(job))
        return created

    @app.get("/jobs", response_model=list[JobRead])
    async def list_jobs() -> list[JobRead]:
        orch = get_orchestrator(app)
        jobs = await orch.list_jobs()
        return [JobRead.model_validate(j) for j in jobs]

    @app.get("/jobs/{job_id}", response_model=JobRead)
    async def get_job(job_id: int) -> JobRead:
        orch = get_orchestrator(app)
        job = await orch.get_job(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="Job not found")
        return JobRead.model_validate(job)

    @app.post("/jobs/{job_id}/pause", response_model=JobRead)
    async def pause_job(job_id: int) -> JobRead:
        orch = get_orchestrator(app)
        job = await orch.manual_pause(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="Job not found")
        return JobRead.model_validate(job)

    @app.post("/jobs/{job_id}/resume", response_model=JobRead)
    async def resume_job(job_id: int) -> JobRead:
        orch = get_orchestrator(app)
        job = await orch.manual_resume(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="Job not found")
        return JobRead.model_validate(job)

    @app.get("/grid/status", response_model=GridStatus)
    async def grid_status() -> GridStatus:
        orch = get_orchestrator(app)
        return await orch.get_grid_status()

    @app.get("/stats", response_model=StatsResponse)
    async def stats(policy: str | None = Query(default=None)) -> StatsResponse:
        orch = get_orchestrator(app)
        if policy:
            from app.api.deps import switch_policy

            switch_policy(app, policy)
        return await orch.get_stats()

    return app


app = create_app()
