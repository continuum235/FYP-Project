from app.domain.enums import Action
from app.domain.models import SchedulingState
from app.intelligence.constraints import must_force_run
from app.intelligence.policies.base import SchedulingPolicy


class GreedyPolicy(SchedulingPolicy):
    def __init__(
        self,
        run_threshold: float,
        pause_threshold: float,
        max_pause_count: int = 10,
        deadline_safety_margin_hours: float = 0.5,
    ) -> None:
        if pause_threshold <= run_threshold:
            raise ValueError("pause_threshold must be strictly greater than run_threshold")
        self.run_threshold = run_threshold
        self.pause_threshold = pause_threshold
        self.max_pause_count = max_pause_count
        self.deadline_safety_margin_hours = deadline_safety_margin_hours

    def _deadline_pressure(self, state: SchedulingState) -> bool:
        if state.time_to_deadline_hours is None:
            return False
        remaining_epochs = max(0, state.total_epochs - state.current_epoch)
        if state.total_epochs <= 0:
            return False
        epoch_fraction_remaining = remaining_epochs / state.total_epochs
        estimated_remaining_hours = epoch_fraction_remaining * max(
            state.time_running_hours + state.time_waiting_hours, 0.05
        )
        return state.time_to_deadline_hours <= (
            estimated_remaining_hours + self.deadline_safety_margin_hours
        )

    def _force_run(self, state: SchedulingState) -> bool:
        return must_force_run(state) or self._deadline_pressure(state)

    def decide(self, state: SchedulingState) -> Action:
        if self._force_run(state):
            return Action.RUN

        if state.is_currently_running:
            if state.carbon_intensity > self.pause_threshold:
                return Action.WAIT
            return Action.RUN

        if state.carbon_intensity < self.run_threshold:
            return Action.RUN
        return Action.WAIT
