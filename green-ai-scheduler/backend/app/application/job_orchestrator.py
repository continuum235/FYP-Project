"""
Status machine (QUEUED -> WAITING -> RUNNING -> PAUSED/COMPLETED):

- POST /jobs sets status QUEUED.
- First tick where GreedyPolicy returns WAIT for a start-candidate sets WAITING.
- RUN verdict on start-candidate dispatches to ExecutionEngine -> RUNNING once worker confirms.
- WAIT verdict on RUNNING job triggers cooperative pause -> PAUSED (system-initiated).
- POST /jobs/{id}/pause sets MANUALLY_PAUSED (never auto-resumed by tick).
- POST /jobs/{id}/resume clears MANUALLY_PAUSED back to QUEUED.

Deadline proximity (GreedyPolicy):
  time_remaining = deadline - now
  estimated_remaining = (remaining_epochs / total_epochs) * observed_duration_so_far
  RUN-forcing when time_remaining <= estimated_remaining + safety_margin_hours
"""

import asyncio
import logging
from datetime import datetime
from typing import Optional

from app.domain.enums import Action, JobStatus, JobType
from app.domain.models import GridStatus, JobCreate, SchedulingState, SessionReport, StatsResponse
from app.infrastructure.execution_engine import ExecutionEngine
from app.infrastructure.jobs.registry import get_train_fn, train_kwargs_for
from app.infrastructure.persistent_store import JobRow, PersistentJobStore
from app.intelligence.carbon_estimator import CarbonEstimator
from app.intelligence.decision_engine import DecisionEngine
from app.intelligence.gaiq_engine import GaiQEngine, ProfileData

logger = logging.getLogger(__name__)

ELIGIBLE_START = {JobStatus.QUEUED, JobStatus.WAITING, JobStatus.PAUSED}


class JobOrchestrator:
    def __init__(
        self,
        store: PersistentJobStore,
        execution_engine: ExecutionEngine,
        carbon_estimator: CarbonEstimator,
        gaiq_engine: GaiQEngine,
        decision_engine: DecisionEngine,
        tick_interval_seconds: int = 60,
        max_pause_count: int = 10,
    ) -> None:
        self._store = store
        self._execution = execution_engine
        self._carbon = carbon_estimator
        self._gaiq = gaiq_engine
        self._decision = decision_engine
        self._tick_interval = tick_interval_seconds
        self._max_pause_count = max_pause_count
        self._tick_task: Optional[asyncio.Task] = None
        self._job_start_times: dict[int, datetime] = {}
        self._job_wait_start: dict[int, datetime] = {}

    async def start(self) -> None:
        await self._reconcile_running_jobs()
        if self._tick_task is None or self._tick_task.done():
            self._tick_task = asyncio.create_task(self._tick_loop())

    async def stop(self) -> None:
        if self._tick_task:
            self._tick_task.cancel()
            try:
                await self._tick_task
            except asyncio.CancelledError:
                pass
            self._tick_task = None

    async def _reconcile_running_jobs(self) -> None:
        running = await self._store.get_jobs_by_status(JobStatus.RUNNING)
        for job in running:
            await self._store.update_job(job.id, status=JobStatus.QUEUED)

    async def submit_job(self, payload: JobCreate) -> JobRow:
        grid = await self._carbon.get_current_intensity()
        forecast = await self._carbon.get_forecast()
        profile_row = await self._store.get_profile(payload.job_type)
        profile = ProfileData(
            job_type=payload.job_type,
            expected_power_draw_kw=profile_row.expected_power_draw_kw,
            expected_duration_hours=profile_row.expected_duration_hours,
            sample_count=profile_row.sample_count,
        )
        baseline = self._gaiq.estimate_baseline(profile, grid.carbon_intensity_g_per_kwh, forecast)
        job = await self._store.create_job(
            name=payload.name,
            job_type=payload.job_type,
            priority=payload.priority,
            deadline=payload.deadline,
            performance_target=payload.performance_target,
            total_epochs=payload.total_epochs,
            baseline_carbon_estimate_g=baseline,
        )
        self._job_wait_start[job.id] = datetime.utcnow()
        return job

    async def get_job(self, job_id: int) -> Optional[JobRow]:
        return await self._store.get_job(job_id)

    async def list_jobs(self) -> list[JobRow]:
        return await self._store.list_jobs()

    async def manual_pause(self, job_id: int) -> Optional[JobRow]:
        job = await self._store.get_job(job_id)
        if job is None:
            return None
        if job.status == JobStatus.RUNNING:
            await self._execution.request_pause(job_id)
        if job.status not in (JobStatus.COMPLETED, JobStatus.FAILED):
            return await self._store.update_job(job_id, status=JobStatus.MANUALLY_PAUSED)
        return job

    async def manual_resume(self, job_id: int) -> Optional[JobRow]:
        job = await self._store.get_job(job_id)
        if job is None or job.status != JobStatus.MANUALLY_PAUSED:
            return job
        self._job_wait_start[job_id] = datetime.utcnow()
        return await self._store.update_job(job_id, status=JobStatus.QUEUED)

    async def get_grid_status(self) -> GridStatus:
        return await self._carbon.get_current_intensity()

    async def get_stats(self) -> StatsResponse:
        counts = await self._store.count_by_status()
        policy_name = "greedy"
        if hasattr(self._decision.policy, "_model"):
            policy_name = "ppo" if getattr(self._decision.policy, "_model", None) else "greedy"
        return StatsResponse(
            jobs_waiting=counts.get(JobStatus.WAITING.value, 0)
            + counts.get(JobStatus.QUEUED.value, 0)
            + counts.get(JobStatus.PAUSED.value, 0),
            jobs_running=counts.get(JobStatus.RUNNING.value, 0),
            jobs_completed=counts.get(JobStatus.COMPLETED.value, 0),
            total_carbon_saved_g=await self._store.total_carbon_saved(),
            policy=policy_name,
        )

    def _build_state(self, job: JobRow, intensity: float, forecast: Optional[list[float]]) -> SchedulingState:
        now = datetime.utcnow()
        is_running = job.status == JobStatus.RUNNING
        time_running = 0.0
        time_waiting = 0.0
        if is_running and job.id in self._job_start_times:
            time_running = (now - self._job_start_times[job.id]).total_seconds() / 3600.0
        elif job.id in self._job_wait_start:
            time_waiting = (now - self._job_wait_start[job.id]).total_seconds() / 3600.0

        time_to_deadline = None
        if job.deadline:
            time_to_deadline = max(0.0, (job.deadline - now).total_seconds() / 3600.0)

        return SchedulingState(
            is_currently_running=is_running,
            carbon_intensity=intensity,
            carbon_forecast=forecast,
            time_waiting_hours=time_waiting,
            time_running_hours=time_running,
            time_to_deadline_hours=time_to_deadline,
            priority=job.priority,
            pause_count=job.pause_count,
            max_pause_count=self._max_pause_count,
            current_epoch=job.current_epoch,
            performance_target=job.performance_target,
            total_epochs=job.total_epochs,
        )

    async def _select_job_for_tick(self) -> Optional[JobRow]:
        running = await self._store.get_jobs_by_status(JobStatus.RUNNING)
        if running:
            return running[0]
        candidates = await self._store.list_jobs()
        eligible = [
            j
            for j in candidates
            if j.status in ELIGIBLE_START and j.status != JobStatus.MANUALLY_PAUSED
        ]
        if not eligible:
            return None
        eligible.sort(key=lambda j: (-j.priority, j.created_at))
        return eligible[0]

    async def tick(self) -> None:
        if self._execution.is_busy:
            job = await self._store.get_job(self._execution.running_job_id)
            if job and job.status == JobStatus.MANUALLY_PAUSED:
                return
        else:
            job = await self._select_job_for_tick()

        if job is None:
            return
        if job.status == JobStatus.MANUALLY_PAUSED:
            return

        self._decision.reset_call_count()
        grid = await self._carbon.get_current_intensity()
        forecast = await self._carbon.get_forecast()
        state = self._build_state(job, grid.carbon_intensity_g_per_kwh, forecast)
        action = self._decision.decide(state)

        if job.status == JobStatus.RUNNING:
            if action in (Action.WAIT, Action.PAUSE):
                await self._execution.request_pause(job.id)
            return

        if action == Action.RUN and not self._execution.is_busy:
            other_running = await self._store.get_jobs_by_status(JobStatus.RUNNING)
            if other_running:
                raise RuntimeError("Single-flight violation: another job is RUNNING")
            await self._dispatch_job(job)

        elif action == Action.WAIT:
            if job.status in (JobStatus.QUEUED, JobStatus.PAUSED):
                self._job_wait_start[job.id] = datetime.utcnow()
                await self._store.update_job(job.id, status=JobStatus.WAITING)

    async def _dispatch_job(self, job: JobRow) -> None:
        checkpoint = job.checkpoint_path or self._execution.checkpoint_path_for(job.id)
        await self._store.update_job(
            job.id,
            status=JobStatus.RUNNING,
            checkpoint_path=checkpoint,
        )
        self._job_start_times[job.id] = datetime.utcnow()

        async def on_complete(report: SessionReport) -> None:
            await self._handle_session_report(report)

        train_fn = get_train_fn(job.job_type)
        kwargs = train_kwargs_for(
            job.job_type,
            job_id=job.id,
            start_epoch=job.current_epoch,
            total_epochs=job.total_epochs,
            checkpoint_path=checkpoint,
        )

        asyncio.create_task(
            self._execution.run_job(
                job_id=job.id,
                job_type=job.job_type,
                train_fn=train_fn,
                train_kwargs=kwargs,
                on_complete=on_complete,
            )
        )

    async def _handle_session_report(self, report: SessionReport) -> None:
        job = await self._store.get_job(report.job_id)
        if job is None:
            return

        updates = {
            "carbon_used_g": job.carbon_used_g + report.session_carbon_g,
            "energy_used_kwh": job.energy_used_kwh + report.session_energy_kwh,
            "total_duration_hours": job.total_duration_hours + report.session_duration_hours,
            "current_epoch": report.current_epoch,
        }
        if report.checkpoint_path:
            updates["checkpoint_path"] = report.checkpoint_path

        if report.error:
            updates["status"] = JobStatus.FAILED
        elif report.completed:
            updates["status"] = JobStatus.COMPLETED
            await self._refine_profile(job.id)
        elif report.paused:
            updates["status"] = (
                JobStatus.MANUALLY_PAUSED
                if job.status == JobStatus.MANUALLY_PAUSED
                else JobStatus.PAUSED
            )
            updates["pause_count"] = job.pause_count + 1

        await self._store.update_job(report.job_id, **updates)

    async def _refine_profile(self, job_id: int) -> None:
        job = await self._store.get_job(job_id)
        if job is None or job.total_duration_hours <= 0:
            return
        actual_power_kw = job.energy_used_kwh / job.total_duration_hours
        profile_row = await self._store.get_profile(job.job_type)
        profile = ProfileData(
            job_type=job.job_type,
            expected_power_draw_kw=profile_row.expected_power_draw_kw,
            expected_duration_hours=profile_row.expected_duration_hours,
            sample_count=profile_row.sample_count,
        )
        updated = self._gaiq.update_profile(
            profile, actual_power_kw, job.total_duration_hours
        )
        await self._store.update_profile(
            job.job_type,
            updated.expected_power_draw_kw,
            updated.expected_duration_hours,
            updated.sample_count,
        )

    async def _tick_loop(self) -> None:
        while True:
            try:
                await self.tick()
            except Exception:
                logger.exception("Tick loop error")
            await asyncio.sleep(self._tick_interval)
