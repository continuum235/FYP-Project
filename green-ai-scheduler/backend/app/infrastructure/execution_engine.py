import asyncio
import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Awaitable, Callable, Optional

from app.domain.enums import JobType
from app.domain.models import SessionReport


@dataclass
class RunningJobContext:
    job_id: int
    job_type: JobType
    cancel_event: threading.Event
    future: asyncio.Future


TrainFn = Callable[..., dict]


class ExecutionEngine:
    """Runs blocking training in a single-worker thread pool; reports sessions to orchestrator."""

    def __init__(self, checkpoint_dir: str, max_workers: int = 1) -> None:
        self._checkpoint_dir = Path(checkpoint_dir)
        self._checkpoint_dir.mkdir(parents=True, exist_ok=True)
        self._thread_pool = ThreadPoolExecutor(max_workers=max_workers)
        self._running: Optional[RunningJobContext] = None
        self._lock = asyncio.Lock()

    @property
    def is_busy(self) -> bool:
        return self._running is not None

    @property
    def running_job_id(self) -> Optional[int]:
        return self._running.job_id if self._running else None

    async def run_job(
        self,
        job_id: int,
        job_type: JobType,
        train_fn: TrainFn,
        train_kwargs: dict,
        on_complete: Callable[[SessionReport], Awaitable[None]],
    ) -> None:
        async with self._lock:
            if self._running is not None:
                raise RuntimeError("ExecutionEngine worker slot is already occupied")
            cancel_event = threading.Event()
            loop = asyncio.get_running_loop()

            def _execute() -> dict:
                return train_fn(cancel_event=cancel_event, **train_kwargs)

            future = loop.run_in_executor(self._thread_pool, _execute)
            self._running = RunningJobContext(
                job_id=job_id,
                job_type=job_type,
                cancel_event=cancel_event,
                future=future,
            )

        try:
            result = await future
            report = SessionReport(
                job_id=job_id,
                session_carbon_g=result.get("session_carbon_g", 0.0),
                session_energy_kwh=result.get("session_energy_kwh", 0.0),
                session_duration_hours=result.get("session_duration_hours", 0.0),
                current_epoch=result.get("current_epoch", 0),
                completed=result.get("completed", False),
                paused=result.get("paused", False),
                checkpoint_path=result.get("checkpoint_path"),
                error=result.get("error"),
            )
            await on_complete(report)
        except Exception as exc:
            report = SessionReport(
                job_id=job_id,
                session_carbon_g=0.0,
                session_energy_kwh=0.0,
                session_duration_hours=0.0,
                current_epoch=train_kwargs.get("start_epoch", 0),
                completed=False,
                paused=False,
                error=str(exc),
            )
            await on_complete(report)
        finally:
            async with self._lock:
                self._running = None

    async def request_pause(self, job_id: int) -> bool:
        async with self._lock:
            if self._running is None or self._running.job_id != job_id:
                return False
            self._running.cancel_event.set()
            return True

    def checkpoint_path_for(self, job_id: int) -> str:
        path = self._checkpoint_dir / f"job_{job_id}.pt"
        return str(path)

    async def shutdown(self) -> None:
        self._thread_pool.shutdown(wait=False, cancel_futures=True)


from app.infrastructure.jobs.simulated import run_simulated_job  # re-export for tests

__all__ = ["ExecutionEngine", "TrainFn", "run_simulated_job"]
