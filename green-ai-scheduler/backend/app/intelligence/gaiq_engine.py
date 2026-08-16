from dataclasses import dataclass
from typing import Optional

from app.domain.enums import JobType


@dataclass
class ProfileData:
    job_type: JobType
    expected_power_draw_kw: float
    expected_duration_hours: float
    sample_count: int


@dataclass
class GradeThresholds:
    grade_a: float = 0.75
    grade_b: float = 0.90
    grade_c: float = 1.05


class GaiQEngine:
    """Pure intelligence: baseline estimation and profile refinement. No DB access."""

    def __init__(self, thresholds: Optional[GradeThresholds] = None) -> None:
        self._thresholds = thresholds or GradeThresholds()

    def estimate_baseline(
        self,
        profile: ProfileData,
        carbon_intensity: float,
        forecast: Optional[list[float]] = None,
    ) -> float:
        duration = profile.expected_duration_hours
        if forecast and duration >= 1.0:
            window = forecast[: max(1, int(duration * 12))]
            avg_intensity = sum(window) / len(window)
        else:
            avg_intensity = carbon_intensity
        return profile.expected_power_draw_kw * duration * avg_intensity

    def update_profile(
        self,
        profile: ProfileData,
        actual_power_kw: float,
        actual_duration_hours: float,
    ) -> ProfileData:
        n = profile.sample_count
        new_n = n + 1
        new_power = (profile.expected_power_draw_kw * n + actual_power_kw) / new_n
        new_duration = (profile.expected_duration_hours * n + actual_duration_hours) / new_n
        return ProfileData(
            job_type=profile.job_type,
            expected_power_draw_kw=new_power,
            expected_duration_hours=new_duration,
            sample_count=new_n,
        )

    def grade(self, carbon_used_g: float, baseline_carbon_estimate_g: float) -> str:
        if baseline_carbon_estimate_g <= 0:
            return "N/A"
        ratio = carbon_used_g / baseline_carbon_estimate_g
        t = self._thresholds
        if ratio <= t.grade_a:
            return "A"
        if ratio <= t.grade_b:
            return "B"
        if ratio <= t.grade_c:
            return "C"
        return "D"
