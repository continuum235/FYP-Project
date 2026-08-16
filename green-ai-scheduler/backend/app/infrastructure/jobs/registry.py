"""Dispatch job_type → training function (lazy imports for heavy deps)."""

from __future__ import annotations

from app.domain.enums import JobType
from app.infrastructure.execution_engine import TrainFn
from app.infrastructure.jobs.simulated import run_simulated_job


def get_train_fn(job_type: JobType) -> TrainFn:
    if job_type == JobType.SIMULATED:
        return run_simulated_job
    if job_type == JobType.RESNET50_CIFAR:
        from app.infrastructure.jobs.resnet50_cifar import run_resnet50_cifar_job

        return run_resnet50_cifar_job
    if job_type == JobType.BERT_IMDB:
        from app.infrastructure.jobs.bert_imdb import run_bert_imdb_job

        return run_bert_imdb_job
    raise ValueError(f"No training function for job_type={job_type}")


def train_kwargs_for(job_type: JobType, job_id: int, start_epoch: int, total_epochs: int, checkpoint_path: str) -> dict:
    base = {
        "job_id": job_id,
        "start_epoch": start_epoch,
        "total_epochs": total_epochs,
        "checkpoint_path": checkpoint_path,
    }
    if job_type == JobType.SIMULATED:
        base["batch_sleep_s"] = 0.02
        base["batches_per_epoch"] = 10
        base["power_kw"] = 0.05
    return base
