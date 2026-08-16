from typing import Optional

from app.domain.enums import Action
from app.domain.models import SchedulingState
from app.intelligence.policies.base import SchedulingPolicy
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
    if name == "ppo":
        if ppo is None:
            return PPOPolicy(model=None)
        return ppo
    if greedy is None:
        greedy = GreedyPolicy(run_threshold=450.0, pause_threshold=550.0)
    return greedy
