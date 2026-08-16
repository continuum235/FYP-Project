import pytest

from app.intelligence.gaiq_engine import GaiQEngine, ProfileData
from app.domain.enums import JobType


def test_baseline_computed_from_profile():
    engine = GaiQEngine()
    profile = ProfileData(JobType.SIMULATED, 0.1, 1.0, 0)
    baseline = engine.estimate_baseline(profile, carbon_intensity=500.0)
    assert baseline == pytest.approx(50.0)


def test_update_profile_rolling_average():
    engine = GaiQEngine()
    profile = ProfileData(JobType.SIMULATED, 0.1, 1.0, 1)
    updated = engine.update_profile(profile, actual_power_kw=0.2, actual_duration_hours=2.0)
    assert updated.expected_power_draw_kw == pytest.approx(0.15)
    assert updated.expected_duration_hours == pytest.approx(1.5)
    assert updated.sample_count == 2


def test_grade_thresholds():
    engine = GaiQEngine()
    assert engine.grade(50, 100) == "A"
    assert engine.grade(85, 100) == "B"
    assert engine.grade(110, 100) == "D"
