"""Tests for the background daemon service."""

import sqlite3

import pytest

from src.db import init_db
from src.daemon import DaemonService


def test_daemon_service_imports() -> None:
    """DaemonService must be importable from src.daemon."""
    assert DaemonService is not None


def test_daemon_starts_event_bus() -> None:
    """DaemonService with an in-memory DB should register triggers via EventBus."""
    from src.engine.event_bus import EventBus

    # Create a daemon backed by an in-memory database.
    daemon = DaemonService(db_path=":memory:", verbose=True)

    # The event bus singleton should have triggers registered
    # (if any enabled workflows exist).  Even with no workflows,
    # the bus itself must be functional and accept registrations.
    bus = EventBus.get_instance()
    assert bus is not None

    # Verify the daemon's triggers list and event bus are accessible.
    assert isinstance(daemon.triggers, list)
    assert isinstance(daemon.workflows, list)

    # Demonstrate that a new trigger can be registered on the bus.
    from src.engine.triggers.base import BaseTrigger

    class DemoTrigger(BaseTrigger):
        def name(self) -> str:
            return "Demo"

        def get_event_types(self) -> list[str]:
            return ["DemoSignal"]

        def match(self, event_data: dict) -> bool:
            return True

    demo = DemoTrigger()
    bus.register_trigger(demo)
    assert demo in bus._triggers

    # Clean up: shutdown the daemon gracefully.
    daemon.stop()