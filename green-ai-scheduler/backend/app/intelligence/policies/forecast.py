from app.domain.enums import Action
from app.domain.models import SchedulingState
from app.intelligence.constraints import must_force_run
from app.intelligence.policies.base import SchedulingPolicy


class ForecastPolicy(SchedulingPolicy):
    """Rule-based policy that prioritizes forecasted carbon improvements over current grid intensity."""

    def __init__(
        self,
        run_threshold: float,
        pause_threshold: float,
        deadline_critical_hours: float = 1.0,
    ) -> None:
        self.run_threshold = run_threshold
        self.pause_threshold = pause_threshold
        self.deadline_critical_hours = deadline_critical_hours

    def _forecast_is_improving(self, state: SchedulingState) -> bool:
        if not state.carbon_forecast:
            return False
        if len(state.carbon_forecast) < 2:
            return False
        current = state.carbon_intensity
        next_window = state.carbon_forecast[: max(1, min(3, len(state.carbon_forecast)))]
        if not next_window:
            return False
        return min(next_window) < current and min(next_window) <= self.run_threshold

    def _forecast_stays_clean(self, state: SchedulingState) -> bool:
        if not state.carbon_forecast:
            return state.carbon_intensity <= self.run_threshold
        forecast = state.carbon_forecast[: max(1, min(4, len(state.carbon_forecast)))]
        return float(max(forecast)) <= self.pause_threshold and float(sum(forecast) / len(forecast)) <= self.run_threshold

    def decide(self, state: SchedulingState) -> Action:
        if must_force_run(state, deadline_critical_hours=self.deadline_critical_hours):
            return Action.RUN

        if state.is_currently_running:
            if state.carbon_intensity > self.pause_threshold:
                if self._forecast_is_improving(state):
                    return Action.WAIT
                return Action.WAIT
            return Action.RUN

        if self._forecast_stays_clean(state):
            return Action.RUN
        if state.carbon_intensity <= self.run_threshold:
            return Action.RUN
        if self._forecast_is_improving(state):
            return Action.WAIT
        return Action.WAIT
