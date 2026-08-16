import asyncio
import os
import time

import pytest

from app.infrastructure.execution_engine import ExecutionEngine, run_simulated_job


@pytest.mark.asyncio
async def test_execution_reports_session(tmp_checkpoint_dir):
    engine = ExecutionEngine(tmp_checkpoint_dir)
    reports = []

    async def on_complete(report):
        reports.append(report)

    await engine.run_job(
        job_id=1,
        job_type=None,
        train_fn=run_simulated_job,
        train_kwargs={
            "job_id": 1,
            "start_epoch": 0,
            "total_epochs": 1,
            "checkpoint_path": f"{tmp_checkpoint_dir}/job_1.pt",
            "batch_sleep_s": 0.01,
            "batches_per_epoch": 5,
        },
        on_complete=on_complete,
    )
    assert len(reports) == 1
    assert reports[0].session_carbon_g > 0
    assert reports[0].session_energy_kwh > 0
    assert reports[0].session_duration_hours > 0
    await engine.shutdown()


@pytest.mark.asyncio
async def test_cooperative_pause_mid_epoch(tmp_checkpoint_dir):
    engine = ExecutionEngine(tmp_checkpoint_dir)
    reports = []

    async def on_complete(report):
        reports.append(report)

    cancel_holder = {}

    def slow_train(**kwargs):
        cancel_event = kwargs["cancel_event"]
        cancel_holder["event"] = cancel_event
        kwargs["batches_per_epoch"] = 50
        kwargs["batch_sleep_s"] = 0.05
        return run_simulated_job(**kwargs)

    task = asyncio.create_task(
        engine.run_job(
            job_id=2,
            job_type=None,
            train_fn=slow_train,
            train_kwargs={
                "job_id": 2,
                "start_epoch": 0,
                "total_epochs": 3,
                "checkpoint_path": f"{tmp_checkpoint_dir}/job_2.pt",
            },
            on_complete=on_complete,
        )
    )
    await asyncio.sleep(0.15)
    await engine.request_pause(2)
    await task

    assert reports[0].paused
    assert reports[0].current_epoch >= 0
    assert os.path.exists(f"{tmp_checkpoint_dir}/job_2.pt")
    await engine.shutdown()


@pytest.mark.asyncio
async def test_event_loop_not_blocked(tmp_checkpoint_dir):
    engine = ExecutionEngine(tmp_checkpoint_dir)
    done = asyncio.Event()

    async def on_complete(_):
        done.set()

    asyncio.create_task(
        engine.run_job(
            job_id=3,
            job_type=None,
            train_fn=run_simulated_job,
            train_kwargs={
                "job_id": 3,
                "start_epoch": 0,
                "total_epochs": 2,
                "checkpoint_path": f"{tmp_checkpoint_dir}/job_3.pt",
                "batch_sleep_s": 0.1,
                "batches_per_epoch": 20,
            },
            on_complete=on_complete,
        )
    )
    await asyncio.sleep(0.05)
    start = time.time()
    await asyncio.sleep(0)  # yield to event loop
    elapsed = time.time() - start
    assert elapsed < 0.05
    await done.wait()
    await engine.shutdown()
