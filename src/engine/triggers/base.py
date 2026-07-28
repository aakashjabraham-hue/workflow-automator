from abc import ABC, abstractmethod


class BaseTrigger(ABC):
    """Abstract base class for all workflow trigger types."""

    @abstractmethod
    def name(self) -> str:
        """Return a human-readable name for this trigger."""
        raise NotImplementedError

    @abstractmethod
    def get_event_types(self) -> list[str]:
        """Return the D-Bus signal names this trigger listens for."""
        raise NotImplementedError

    @abstractmethod
    def match(self, event_data: dict) -> bool:
        """Check whether this trigger fires for the given event data."""
        raise NotImplementedError


# Backward-compatible alias for existing code that uses TriggerBase
TriggerBase = BaseTrigger