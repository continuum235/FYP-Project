import pytest

from app.domain.models import SchedulingState
from app.intelligence.constraints import must_force_run
from app.domain.enums import Action
from app.intelligence.defaults import GREEDY_PAUSE_THRESHOLD, GREEDY_RUN_THRESHOLD
from app.intelligence.policies.constraint_lexicographic import ConstraintLexicographicPolicy
from app.intelligence.policies.forecast import ForecastPolicy
from app.intelligence.policies.greedy import GreedyPolicy


@pytest.fixture
def policy():
    return GreedyPolicy(
        run_threshold=GREEDY_RUN_THRESHOLD,
        pause_threshold=GREEDY_PAUSE_THRESHOLD,
    )


def test_run_when_clean_grid(policy):
    state = SchedulingState(
        is_currently_running=False,
        carbon_intensity=400.0,
        total_epochs=2,
    )
    assert policy.decide(state) == Action.RUN


def test_wait_when_dirty_grid(policy):
    state = SchedulingState(
        is_currently_running=False,
        carbon_intensity=600.0,
        total_epochs=2,
    )
    assert policy.decide(state) == Action.WAIT


def test_pause_when_running_and_dirty(policy):
    state = SchedulingState(
        is_currently_running=True,
        carbon_intensity=750.0,
        total_epochs=2,
    )
    assert policy.decide(state) == Action.WAIT


def test_hold_band_running_keeps_job(policy):
    state = SchedulingState(
        is_currently_running=True,
        carbon_intensity=620.0,
        total_epochs=2,
    )
    assert policy.decide(state) == Action.RUN


def test_high_carbon_waits_despite_performance_target(policy):
    state = SchedulingState(
        is_currently_running=False,
        carbon_intensity=700.0,
        current_epoch=0,
        performance_target=2,
        total_epochs=2,
    )
    assert policy.decide(state) == Action.WAIT


def test_deadline_pressure_forces_run(policy):
    state = SchedulingState(
        is_currently_running=False,
        carbon_intensity=700.0,
        current_epoch=0,
        total_epochs=4,
        time_to_deadline_hours=0.1,
        time_running_hours=2.0,
        time_waiting_hours=0.0,
    )
    assert policy.decide(state) == Action.RUN


def test_hysteresis_running_stays_on_clean(policy):
    state = SchedulingState(
        is_currently_running=True,
        carbon_intensity=500.0,
        total_epochs=2,
    )
    assert policy.decide(state) == Action.RUN


def test_force_run_only_on_deadline_and_max_pause():
    state = SchedulingState(
        is_currently_running=False,
        carbon_intensity=700.0,
        pause_count=10,
        max_pause_count=10,
        total_epochs=2,
    )
    assert must_force_run(state) is True

    state2 = SchedulingState(
        is_currently_running=False,
        carbon_intensity=700.0,
        time_to_deadline_hours=0.5,
        total_epochs=2,
    )
    assert must_force_run(state2, deadline_critical_hours=1.0) is True

    state3 = SchedulingState(
        is_currently_running=False,
        carbon_intensity=700.0,
        current_epoch=0,
        performance_target=2,
        total_epochs=2,
    )
    assert must_force_run(state3) is False


def test_forecast_policy_waits_when_carbon_is_high_but_falling():
    policy = ForecastPolicy(run_threshold=550.0, pause_threshold=700.0)
    state = SchedulingState(
        is_currently_running=False,
        carbon_intensity=750.0,
        carbon_forecast=[700.0, 650.0, 600.0, 500.0],
        total_epochs=2,
    )
    assert policy.decide(state) == Action.WAIT


def test_forecast_policy_runs_when_forecast_stays_clean():
    policy = ForecastPolicy(run_threshold=550.0, pause_threshold=700.0)
    state = SchedulingState(
        is_currently_running=False,
        carbon_intensity=400.0,
        carbon_forecast=[420.0, 410.0, 430.0, 450.0],
        total_epochs=2,
    )
    assert policy.decide(state) == Action.RUN


def test_constraint_lexicographic_policy_prioritizes_deadline_then_target_then_carbon():
    policy = ConstraintLexicographicPolicy(run_threshold=550.0, pause_threshold=700.0)

    deadline_state = SchedulingState(
        is_currently_running=False,
        carbon_intensity=800.0,
        time_to_deadline_hours=0.5,
        total_epochs=2,
    )
    assert policy.decide(deadline_state) == Action.RUN

    target_state = SchedulingState(
        is_currently_running=False,
        carbon_intensity=600.0,
        current_epoch=1,
        performance_target=3,
        total_epochs=3,
    )
    assert policy.decide(target_state) == Action.RUN

    carbon_state = SchedulingState(
        is_currently_running=False,
        carbon_intensity=500.0,
        current_epoch=3,
        performance_target=3,
        total_epochs=3,
    )
    assert policy.decide(carbon_state) == Action.RUN

    wait_state = SchedulingState(
        is_currently_running=False,
        carbon_intensity=650.0,
        current_epoch=3,
        performance_target=3,
        total_epochs=3,
    )
    assert policy.decide(wait_state) == Action.WAIT
