from typing import Optional

from app.domain.enums import Action
from app.domain.models import SchedulingState
from app.intelligence.policies.base import SchedulingPolicy
from app.intelligence.defaults import GREEDY_PAUSE_THRESHOLD, GREEDY_RUN_THRESHOLD
from app.intelligence.policies.constraint_lexicographic import ConstraintLexicographicPolicy
from app.intelligence.policies.forecast import ForecastPolicy
from app.intelligence.policies.greedy import GreedyPolicy
from app.intelligence.policies.ppo_policy import PPOPolicy


class DecisionEngine:
    def __init__(self, policy: SchedulingPolicy) -> None:
        self._policy = policy
        self.decide_call_count = 0

    @property
    def policy(self) -> SchedulingPolicy:
        return self._policy

    def set_policy(self, policy: SchedulingPolicy) -> None:
        self._policy = policy

    def decide(self, state: SchedulingState) -> Action:
        self.decide_call_count += 1
        return self._policy.decide(state)

    def reset_call_count(self) -> None:
        self.decide_call_count = 0


def build_policy(
    name: str,
    greedy: Optional[GreedyPolicy] = None,
    ppo: Optional[PPOPolicy] = None,
) -> SchedulingPolicy:
    key = (name or "").strip().lower().replace("-", "_").replace(" ", "_")

    if key in {"ppo", "ppo_policy"}:
        if ppo is None:
            return PPOPolicy(model=None)
        return ppo

    if key in {"forecast", "forecast_based", "forecast_policy"}:
        return ForecastPolicy(
            run_threshold=GREEDY_RUN_THRESHOLD,
            pause_threshold=GREEDY_PAUSE_THRESHOLD,
        )

    if key in {"constraint_lexicographic", "constraint_lexicographic_policy", "constraintlexicographic"}:
        return ConstraintLexicographicPolicy(
            run_threshold=GREEDY_RUN_THRESHOLD,
            pause_threshold=GREEDY_PAUSE_THRESHOLD,
        )

    if greedy is None:
        greedy = GreedyPolicy(
            run_threshold=GREEDY_RUN_THRESHOLD,
            pause_threshold=GREEDY_PAUSE_THRESHOLD,
        )
    return greedy
