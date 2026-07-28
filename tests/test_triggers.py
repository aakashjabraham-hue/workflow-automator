import pytest
from unittest.mock import MagicMock

from src.engine.triggers.base import TriggerBase
from src.engine.event_bus import EventBus
from src.engine.triggers.bluetooth import BluetoothTrigger
from src.engine.triggers.power import PowerTrigger


class ConcreteTrigger(TriggerBase):
    """Minimal concrete TriggerBase for testing the base class interface."""

    def name(self) -> str:
        return "Test Trigger"

    def match(self, event_data: dict) -> bool:
        return True

    def get_event_types(self) -> list[str]:
        return ["TestSignal"]


# --- BluetoothTrigger tests ---


def test_bluetooth_trigger_match_connected():
    """A Bluetooth device that is Connected and matches the configured name should fire."""
    trigger = BluetoothTrigger({"device_name": "MyHeadphones"})
    event = {
        "device": "MyHeadphones",
        "changed_properties": {"Connected": True},
    }
    assert trigger.match(event) is True


def test_bluetooth_trigger_no_match_disconnected():
    """A Bluetooth device that is not Connected should not fire."""
    trigger = BluetoothTrigger({"device_name": "MyHeadphones"})
    event = {
        "device": "MyHeadphones",
        "changed_properties": {"Connected": False},
    }
    assert trigger.match(event) is False


def test_bluetooth_trigger_no_match_different_device():
    """A Bluetooth device with a different name should not fire."""
    trigger = BluetoothTrigger({"device_name": "MyHeadphones"})
    event = {
        "device": "OtherDevice",
        "changed_properties": {"Connected": True},
    }
    assert trigger.match(event) is False


# --- PowerTrigger tests ---


def test_power_trigger_match_unplugged():
    """When AC is offline and trigger config is 'unplugged', match returns True."""
    trigger = PowerTrigger({"state": "unplugged"})
    event = {
        "changed_properties": {"Online": False},
    }
    assert trigger.match(event) is True


def test_power_trigger_no_match_plugged():
    """When AC is online and trigger config is 'unplugged', match returns False."""
    trigger = PowerTrigger({"state": "unplugged"})
    event = {
        "changed_properties": {"Online": True},
    }
    assert trigger.match(event) is False


# --- EventBus tests ---


def test_event_bus_register_and_dispatch():
    """Register a trigger and dispatch an event; trigger.match should be called."""
    bus = EventBus()
    mock_trigger = MagicMock()
    mock_trigger.get_event_types.return_value = ["TestSignal"]
    mock_trigger.match.return_value = True

    bus.register_trigger(mock_trigger)
    bus.dispatch("TestSignal", {"foo": "bar"})

    mock_trigger.match.assert_called_once_with({"foo": "bar"})


# --- TriggerBase tests ---


def test_trigger_base_name():
    """A concrete TriggerBase subclass should return a descriptive name() string."""
    trigger = ConcreteTrigger()
    assert trigger.name() == "Test Trigger"
    assert isinstance(trigger.name(), str)


# --- Singleton / D-Bus integration tests ---


def test_event_bus_singleton():
    """EventBus.get_instance() returns the same object across calls."""
    a = EventBus.get_instance()
    b = EventBus.get_instance()
    assert a is b


def test_event_bus_singleton_reset():
    """After clearing the singleton, a new instance is created."""
    EventBus._instance = None
    a = EventBus.get_instance()
    b = EventBus.get_instance()
    assert a is b
    EventBus._instance = None


def test_event_bus_unregister_trigger():
    """After unregistering, a trigger should no longer receive dispatch."""
    bus = EventBus()
    mock_trigger = MagicMock()
    mock_trigger.get_event_types.return_value = ["TestSignal"]

    bus.register_trigger(mock_trigger)
    bus.unregister_trigger(mock_trigger)
    bus.dispatch("TestSignal", {})

    mock_trigger.match.assert_not_called()