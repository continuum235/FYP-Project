from app.domain.models import SchedulingState


def must_force_run(
    state: SchedulingState,
    *,
    deadline_critical_hours: float = 1.0,
) -> bool:
    """Hard overrides: max pauses exhausted or deadline in critical window."""
    if state.pause_count >= state.max_pause_count:
        return True
    if (
        state.time_to_deadline_hours is not None
        and state.time_to_deadline_hours <= deadline_critical_hours
    ):
        return True
    return False
