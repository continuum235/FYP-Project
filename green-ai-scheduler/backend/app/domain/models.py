from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from app.domain.enums import Action, JobStatus, JobType


class JobCreate(BaseModel):
    name: str
    job_type: JobType
    priority: int = 0
    deadline: Optional[datetime] = None
    performance_target: Optional[int] = None
    total_epochs: int = 2


class JobRead(BaseModel):
    id: int
    name: str
    job_type: JobType
    status: JobStatus
    priority: int
    created_at: datetime
    deadline: Optional[datetime]
    checkpoint_path: Optional[str]
    carbon_used_g: float
    energy_used_kwh: float
    baseline_carbon_estimate_g: float
    pause_count: int
    current_epoch: int
    performance_target: Optional[int]
    total_epochs: int
    total_duration_hours: float

    model_config = {"from_attributes": True}


class JobTypeProfile(BaseModel):
    job_type: JobType
    expected_power_draw_kw: float
    expected_duration_hours: float
    sample_count: int

    model_config = {"from_attributes": True}


class SchedulingState(BaseModel):
    is_currently_running: bool
    carbon_intensity: float
    carbon_forecast: Optional[list[float]] = None
    forecast_avg: Optional[float] = None
    forecast_min: Optional[float] = None
    time_to_clean_window_hours: Optional[float] = None
    time_waiting_hours: float = 0.0
    time_running_hours: float = 0.0
    time_to_deadline_hours: Optional[float] = None
    priority: int = 0
    pause_count: int = 0
    max_pause_count: int = 10
    current_epoch: int = 0
    performance_target: Optional[int] = None
    total_epochs: int = 1
    progress_ratio: Optional[float] = None
    queue_length: int = 0


class SessionReport(BaseModel):
    job_id: int
    session_carbon_g: float
    session_energy_kwh: float
    session_duration_hours: float
    current_epoch: int
    completed: bool
    paused: bool
    checkpoint_path: Optional[str] = None
    error: Optional[str] = None


class GridStatus(BaseModel):
    carbon_intensity_g_per_kwh: float
    source: str
    zone: str
    cached: bool = False


class StatsResponse(BaseModel):
    jobs_waiting: int
    jobs_running: int
    jobs_completed: int
    total_carbon_saved_g: float
    policy: str


class PolicyAction(BaseModel):
    action: Action


class BulkJobCreate(BaseModel):
    count: int = Field(default=3, ge=1, le=20)
    name_prefix: str = "batch-job"
    job_type: JobType = JobType.SIMULATED
    total_epochs: int = 2
    performance_target: Optional[int] = None
    priority: int = 0
