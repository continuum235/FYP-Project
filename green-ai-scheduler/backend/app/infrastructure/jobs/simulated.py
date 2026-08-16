"""Fast simulated training loop (tests + quick scheduler demos)."""

from __future__ import annotations

import os
import threading
import time

from app.infrastructure.jobs.carbon_session import carbon_training_session


def run_simulated_job(
    *,
    cancel_event: threading.Event,
    job_id: int,
    start_epoch: int,
    total_epochs: int,
    checkpoint_path: str,
    batch_sleep_s: float = 0.05,
    batches_per_epoch: int = 10,
    power_kw: float = 0.05,
) -> dict:
    import torch

    current_epoch = start_epoch
    state = {"epoch": current_epoch, "loss": 1.0}

    if os.path.exists(checkpoint_path):
        state = torch.load(checkpoint_path, weights_only=False)
        current_epoch = int(state.get("epoch", start_epoch))

    paused = False
    completed = False

    with carbon_training_session(job_id, power_kw_fallback=power_kw) as carbon:
        while current_epoch < total_epochs:
            for _ in range(batches_per_epoch):
                if cancel_event.is_set():
                    paused = True
                    break
                state["loss"] = max(0.01, float(state["loss"]) * 0.95)
                time.sleep(batch_sleep_s)
            if paused:
                break
            current_epoch += 1
            state["epoch"] = current_epoch

        if not paused and current_epoch >= total_epochs:
            completed = True

        os.makedirs(os.path.dirname(checkpoint_path) or ".", exist_ok=True)
        torch.save(state, checkpoint_path)

    return {
        "session_carbon_g": carbon.session_carbon_g,
        "session_energy_kwh": carbon.session_energy_kwh,
        "session_duration_hours": carbon.session_duration_hours,
        "current_epoch": current_epoch,
        "completed": completed,
        "paused": paused,
        "checkpoint_path": checkpoint_path,
    }
