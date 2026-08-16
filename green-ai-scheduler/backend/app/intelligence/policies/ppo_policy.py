import numpy as np
from stable_baselines3 import PPO

from app.domain.enums import Action
from app.domain.models import SchedulingState
from app.intelligence.policies.greedy import GreedyPolicy
from app.intelligence.policies.base import SchedulingPolicy

CARBON_MIN = 329.0
CARBON_MAX = 706.0


def state_to_obs(state: SchedulingState) -> np.ndarray:
    carbon_norm = (state.carbon_intensity - CARBON_MIN) / (CARBON_MAX - CARBON_MIN)
    forecast_norm = 0.5
    if state.carbon_forecast:
        avg = sum(state.carbon_forecast) / len(state.carbon_forecast)
        forecast_norm = (avg - CARBON_MIN) / (CARBON_MAX - CARBON_MIN)

    time_feature = state.time_running_hours if state.is_currently_running else state.time_waiting_hours
    deadline_norm = 1.0
    if state.time_to_deadline_hours is not None:
        deadline_norm = min(1.0, max(0.0, state.time_to_deadline_hours / 48.0))

    perf_ratio = 1.0
    if state.performance_target and state.performance_target > 0:
        perf_ratio = min(1.0, state.current_epoch / state.performance_target)

    pause_ratio = state.pause_count / max(state.max_pause_count, 1)
    priority_norm = min(1.0, max(0.0, state.priority / 10.0))

    obs = np.array(
        [
            float(state.is_currently_running),
            carbon_norm,
            forecast_norm,
            max(0.0, time_feature) / 24.0,
            deadline_norm,
            priority_norm,
            pause_ratio,
            perf_ratio,
        ],
        dtype=np.float32,
    )
    return np.clip(obs, 0.0, 1.0)


class PPOPolicy(SchedulingPolicy):
  ACTION_MAP = {0: Action.RUN, 1: Action.WAIT, 2: Action.PAUSE}

  def __init__(self, model: PPO | None = None, fallback: SchedulingPolicy | None = None) -> None:
      self._model = model
      self._fallback = fallback or GreedyPolicy(run_threshold=450.0, pause_threshold=550.0)

  def _force_run(self, state: SchedulingState) -> bool:
      if state.performance_target is not None and state.current_epoch < state.performance_target:
          return True
      if state.pause_count >= state.max_pause_count:
          return True
      if state.time_to_deadline_hours is not None and state.time_to_deadline_hours <= 1.0:
          return True
      return False

  def decide(self, state: SchedulingState) -> Action:
      if self._model is None:
          return self._fallback.decide(state)
      if self._force_run(state):
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
