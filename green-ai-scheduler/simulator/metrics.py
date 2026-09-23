from dataclasses import asdict, dataclass


@dataclass
class BenchmarkMetrics:
    total_carbon_g: float
    baseline_carbon_g: float
    carbon_saved_g: float
    carbon_reduction_percent: float
    average_carbon_intensity: float | None
    carbon_per_completed_job_g: float | None
    jobs_submitted: int
    jobs_completed: int
    jobs_failed: int
    deadline_misses: int
    deadline_satisfaction_percent: float
    total_pause_count: int
    average_pause_count: float
    total_waiting_time_hours: float
    average_waiting_time_hours: float
    average_completion_time_hours: float | None
    performance_violations: int
    jobs_affected_by_performance_constraints: int
    clean_window_finishes: int
    clean_window_completion_percent: float

    def to_dict(self) -> dict:
        return asdict(self)