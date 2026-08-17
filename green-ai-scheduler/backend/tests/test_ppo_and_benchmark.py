import pytest

from app.domain.enums import Action
from app.domain.models import SchedulingState
from app.intelligence.policies.ppo_policy import PPOPolicy, state_to_obs


def test_ppo_without_model_uses_fallback():
    policy = PPOPolicy(model=None)
    state = SchedulingState(is_currently_running=False, carbon_intensity=400.0, total_epochs=1)
    assert policy.decide(state) == Action.RUN


def test_ppo_waits_at_high_carbon_without_deadline():
    policy = PPOPolicy(model=None)
    state = SchedulingState(
        is_currently_running=False,
        carbon_intensity=605.0,
        total_epochs=2,
        performance_target=1,
        current_epoch=0,
    )
    assert policy.decide(state) == Action.WAIT


def test_ppo_force_run_on_critical_deadline():
    policy = PPOPolicy(model=None, deadline_critical_hours=1.0)
    state = SchedulingState(
        is_currently_running=False,
        carbon_intensity=605.0,
        total_epochs=2,
        time_to_deadline_hours=0.5,
    )
    assert policy.decide(state) == Action.RUN


def test_state_to_obs_shape():
    state = SchedulingState(
        is_currently_running=True,
        carbon_intensity=500.0,
        carbon_forecast=[480, 490],
        current_epoch=1,
        performance_target=2,
        total_epochs=2,
        queue_length=3,
        progress_ratio=0.5,
        time_to_clean_window_hours=2.0,
    )
    obs = state_to_obs(state)
    assert obs.shape == (12,)


@pytest.mark.benchmark
def test_benchmark_runs():
    from pathlib import Path
    from simulator.benchmark import run_benchmark

    results = run_benchmark(
        Path(__file__).parent.parent / "simulator" / "data" / "snapshots.csv",
        policies=["greedy"],
        horizon=100,
    )
    assert "greedy" in results
