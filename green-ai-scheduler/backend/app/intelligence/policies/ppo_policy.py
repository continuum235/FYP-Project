import numpy as np
from stable_baselines3 import PPO

from app.domain.enums import Action
from app.domain.models import SchedulingState
from app.intelligence.constraints import must_force_run
from app.intelligence.policies.greedy import GreedyPolicy
from app.intelligence.policies.base import SchedulingPolicy

CARBON_MIN = 329.0
CARBON_MAX = 706.0
OBS_SIZE = 12
CLEAN_WINDOW_SENTINEL_HOURS = 48.0


def _forecast_stats(state: SchedulingState) -> tuple[float, float]:
    if not state.carbon_forecast:
        return state.carbon_intensity, state.carbon_intensity
    return (
        sum(state.carbon_forecast) / len(state.carbon_forecast),
        min(state.carbon_forecast),
    )


def state_to_obs(state: SchedulingState, *, run_threshold: float = 450.0) -> np.ndarray:
    carbon_norm = (state.carbon_intensity - CARBON_MIN) / (CARBON_MAX - CARBON_MIN)
    forecast_avg, forecast_min = _forecast_stats(state)
    forecast_avg_norm = (forecast_avg - CARBON_MIN) / (CARBON_MAX - CARBON_MIN)
    forecast_min_norm = (forecast_min - CARBON_MIN) / (CARBON_MAX - CARBON_MIN)

    clean_hours = state.time_to_clean_window_hours
    if clean_hours is None:
        clean_hours = CLEAN_WINDOW_SENTINEL_HOURS
    clean_window_norm = min(1.0, max(0.0, clean_hours / CLEAN_WINDOW_SENTINEL_HOURS))

    time_feature = state.time_running_hours if state.is_currently_running else state.time_waiting_hours
    deadline_norm = 1.0
    if state.time_to_deadline_hours is not None:
        deadline_norm = min(1.0, max(0.0, state.time_to_deadline_hours / 48.0))

    progress_ratio = state.progress_ratio
    if progress_ratio is None and state.total_epochs > 0:
        progress_ratio = state.current_epoch / state.total_epochs
    progress_ratio = progress_ratio if progress_ratio is not None else 0.0

    perf_ratio = 1.0
    if state.performance_target and state.performance_target > 0:
        perf_ratio = min(1.0, state.current_epoch / state.performance_target)

    pause_ratio = state.pause_count / max(state.max_pause_count, 1)
    priority_norm = min(1.0, max(0.0, state.priority / 10.0))
    queue_norm = min(1.0, max(0.0, state.queue_length / 20.0))

    obs = np.array(
        [
            float(state.is_currently_running),
            carbon_norm,
            forecast_avg_norm,
            forecast_min_norm,
            clean_window_norm,
            max(0.0, time_feature) / 24.0,
            deadline_norm,
            priority_norm,
            pause_ratio,
            perf_ratio,
            progress_ratio,
            queue_norm,
        ],
        dtype=np.float32,
    )
    return np.clip(obs, 0.0, 1.0)


class PPOPolicy(SchedulingPolicy):
    ACTION_MAP = {0: Action.RUN, 1: Action.WAIT, 2: Action.PAUSE}

    def __init__(
        self,
        model: PPO | None = None,
        fallback: SchedulingPolicy | None = None,
        deadline_critical_hours: float = 1.0,
    ) -> None:
        self._model = model
        self._fallback = fallback or GreedyPolicy(run_threshold=450.0, pause_threshold=550.0)
        self._deadline_critical_hours = deadline_critical_hours

    def decide(self, state: SchedulingState) -> Action:
        if self._model is None:
            return self._fallback.decide(state)
        if must_force_run(state, deadline_critical_hours=self._deadline_critical_hours):
            return Action.RUN
        obs = state_to_obs(state)
        action_idx, _ = self._model.predict(obs, deterministic=True)
        action = self.ACTION_MAP.get(int(action_idx), Action.WAIT)

        if state.is_currently_running and action == Action.WAIT:
            return Action.PAUSE
        if not state.is_currently_running and action == Action.PAUSE:
            return Action.WAIT
        if state.is_currently_running and action not in (Action.RUN, Action.PAUSE):
            return Action.RUN
        if not state.is_currently_running and action not in (Action.RUN, Action.WAIT):
            return Action.WAIT
        return action
