from abc import ABC, abstractmethod

from app.domain.enums import Action
from app.domain.models import SchedulingState


class SchedulingPolicy(ABC):
    @abstractmethod
    def decide(self, state: SchedulingState) -> Action:
        """Return scheduling action for the single job under evaluation this tick."""
