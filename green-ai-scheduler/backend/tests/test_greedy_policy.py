import pytest

from app.domain.models import SchedulingState
from app.intelligence.policies.greedy import GreedyPolicy
from app.domain.enums import Action


@pytest.fixture
def policy():
    return GreedyPolicy(run_threshold=450.0, pause_threshold=550.0)


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
        carbon_intensity=600.0,
        total_epochs=2,
    )
    assert policy.decide(state) == Action.WAIT


def test_performance_floor_forces_run(policy):
    state = SchedulingState(
        is_currently_running=True,
        carbon_intensity=700.0,
        current_epoch=0,
        performance_target=2,
        total_epochs=2,
    )
    assert policy.decide(state) == Action.RUN


def test_hysteresis_running_stays_on_clean(policy):
    state = SchedulingState(
        is_currently_running=True,
        carbon_intensity=500.0,
        total_epochs=2,
    )
    assert policy.decide(state) == Action.RUN
