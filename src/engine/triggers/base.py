from abc import ABC, abstractmethod
from datetime import datetime


class BaseTrigger(ABC):
    """Abstract base class for all workflow trigger types."""

    @abstractmethod
    def name(self) -> str:
        """Return the trigger type name."""
        raise NotImplementedError

    @abstractmethod
    def get_event_types(self) -> list[str]:
        """Return the list of event types this trigger produces."""
        raise NotImplementedError

    @abstractmethod
    def check(self) -> bool:
        """Return True when the trigger should fire."""
        raise NotImplementedError

    def get_next_run(self) -> datetime:
        """Return the next scheduled fire time (override in subclasses)."""
        raise NotImplementedError