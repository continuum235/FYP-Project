from app.domain.enums import Action
from app.domain.models import SchedulingState
from app.intelligence.constraints import must_force_run
from app.intelligence.policies.base import SchedulingPolicy


class ConstraintLexicographicPolicy(SchedulingPolicy):
    """Priority-based rule order: deadline -> target attainment -> carbon threshold -> wait."""

    def __init__(
        self,
        run_threshold: float,
        pause_threshold: float,
        deadline_critical_hours: float = 1.0,
    ) -> None:
        self.run_threshold = run_threshold
        self.pause_threshold = pause_threshold
        self.deadline_critical_hours = deadline_critical_hours

    def _performance_target_not_met(self, state: SchedulingState) -> bool:
        if state.performance_target is None or state.performance_target <= 0:
            return False
        return state.current_epoch < state.performance_target

    def decide(self, state: SchedulingState) -> Action:
        if must_force_run(state, deadline_critical_hours=self.deadline_critical_hours):
            return Action.RUN

        if state.is_currently_running:
            if state.carbon_intensity > self.pause_threshold:
                return Action.WAIT
            return Action.RUN

        if self._performance_target_not_met(state) and state.carbon_intensity <= self.pause_threshold:
            return Action.RUN

        if state.carbon_intensity <= self.run_threshold:
            return Action.RUN

        return Action.WAIT
