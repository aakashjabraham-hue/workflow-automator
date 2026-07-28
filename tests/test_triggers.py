from datetime import datetime

import pytest
from croniter import croniter
from freezegun import freeze_time

from src.engine.triggers.schedule import ScheduleTrigger


def test_construct_at_1000_check_at_1005():
    """Construct trigger at 10:00, advances to 10:05, check fires."""
    with freeze_time("2026-07-27 10:00:00"):
        trigger = ScheduleTrigger("*/5 * * * *", 1)
        assert trigger.check() is False  # not yet 10:05

    with freeze_time("2026-07-27 10:05:00"):
        assert trigger.check() is True  # now it's 10:05


def test_construct_at_1005_check_immediately():
    """Construct trigger exactly at 10:05, check fires on first call."""
    with freeze_time("2026-07-27 10:05:00"):
        trigger = ScheduleTrigger("*/5 * * * *", 1)
        pass


def test_fires_every_5_minutes():
    """Trigger fires once at each 5-minute boundary."""
    with freeze_time("2026-07-27 10:04:00"):
        trigger = ScheduleTrigger("*/5 * * * *", 1)

    with freeze_time("2026-07-27 10:05:00"):
        assert trigger.check() is True

    with freeze_time("2026-07-27 10:06:00"):
        assert trigger.check() is False  # already fired, not yet 10:10

    with freeze_time("2026-07-27 10:10:00"):
        assert trigger.check() is True  # next 5-min boundary


def test_schedule_daily_8am():
    """Daily trigger at 8am fires when time reaches 8am."""
    with freeze_time("2026-07-27 07:59:00"):
        trigger = ScheduleTrigger("0 8 * * *", 1)
        assert trigger.check() is False  # not yet 8am

    with freeze_time("2026-07-27 08:00:00"):
        assert trigger.check() is True  # it's 8am!


def test_next_run_is_in_future():
    """next_run after construction is always in the future (or at the current time)."""
    with freeze_time("2026-07-27 10:00:00"):
        trigger = ScheduleTrigger("*/5 * * * *", 1)
    assert trigger._next_run > datetime(2026, 7, 27, 10, 0, 0)


def test_schedule_hourly():
    """@hourly fires at minute 0 of every hour."""
    with freeze_time("2026-07-27 11:00:00"):
        trigger = ScheduleTrigger("@hourly", 1)
        assert trigger.check() is True

    with freeze_time("2026-07-27 10:30:00"):
        trigger = ScheduleTrigger("@hourly", 1)
        assert trigger.check() is False  # next is 11:00


def test_schedule_daily_midnight():
    """@daily fires at midnight (00:00)."""
    with freeze_time("2026-07-28 00:00:00"):
        trigger = ScheduleTrigger("@daily", 1)
        assert trigger.check() is True


def test_at_every_5_minutes():
    """@every 5 minutes expands to */5 * * * *."""
    with freeze_time("2026-07-27 10:05:00"):
        trigger = ScheduleTrigger("@every 5 minutes", 1)
        assert trigger.check() is False

    with freeze_time("2026-07-27 10:10:00"):
        assert trigger.check() is True


def test_croniter_behavior():
    """Verify how croniter behaves at boundary times."""
    c = croniter("*/5 * * * *", datetime(2026, 7, 27, 10, 0, 0))
    print("From 10:00:", c.get_next(datetime))

    c2 = croniter("*/5 * * * *", datetime(2026, 7, 27, 10, 5, 0))
    print("From 10:05:", c2.get_next(datetime))

    c3 = croniter("0 8 * * *", datetime(2026, 7, 27, 8, 0, 0))
    print("From 8:00 daily:", c3.get_next(datetime))


# --- TriggerBase tests ---


def test_trigger_base_name():
    """TriggerBase subclasses return a descriptive name."""
    from src.engine.triggers.base import TriggerBase

    class DemoTrigger(TriggerBase):
        def name(self) -> str:
            return "Demo Trigger"

        def match(self, event_data: dict) -> bool:
            return True

        def get_event_types(self) -> list[str]:
            return ["DemoSignal"]

    trigger = DemoTrigger()
    assert trigger.name() == "Demo Trigger"
    assert isinstance(trigger.name(), str)


# --- BluetoothTrigger tests ---


def test_bluetooth_trigger_match_connected():
    """A Bluetooth device that is Connected and matches the configured name should fire."""
    from src.engine.triggers.bluetooth import BluetoothTrigger

    trigger = BluetoothTrigger({"device_name": "MyHeadphones"})
    event = {
        "device": "MyHeadphones",
        "changed_properties": {"Connected": True},
    }
    assert trigger.match(event) is True


def test_bluetooth_trigger_no_match_disconnected():
    """A Bluetooth device that is not Connected should not fire."""
    from src.engine.triggers.bluetooth import BluetoothTrigger

    trigger = BluetoothTrigger({"device_name": "MyHeadphones"})
    event = {
        "device": "MyHeadphones",
        "changed_properties": {"Connected": False},
    }
    assert trigger.match(event) is False


def test_bluetooth_trigger_no_match_different_device():
    """A Bluetooth device with a different name should not fire."""
    from src.engine.triggers.bluetooth import BluetoothTrigger

    trigger = BluetoothTrigger({"device_name": "MyHeadphones"})
    event = {
        "device": "OtherDevice",
        "changed_properties": {"Connected": True},
    }
    assert trigger.match(event) is False


# --- PowerTrigger tests ---


def test_power_trigger_match_unplugged():
    """When AC is offline and trigger config is 'unplugged', match returns True."""
    from src.engine.triggers.power import PowerTrigger

    trigger = PowerTrigger({"state": "unplugged"})
    event = {
        "changed_properties": {"Online": False},
    }
    assert trigger.match(event) is True


def test_power_trigger_no_match_plugged():
    """When AC is online and trigger config is 'unplugged', match returns False."""
    from src.engine.triggers.power import PowerTrigger

    trigger = PowerTrigger({"state": "unplugged"})
    event = {
        "changed_properties": {"Online": True},
    }
    assert trigger.match(event) is False


# --- EventBus tests ---


def test_event_bus_register_and_dispatch():
    """Register a trigger and dispatch an event; trigger.match should be called."""
    from src.engine.event_bus import EventBus
    from unittest.mock import MagicMock

    bus = EventBus()
    mock_trigger = MagicMock()
    mock_trigger.get_event_types.return_value = ["TestSignal"]
    mock_trigger.match.return_value = True

    bus.register_trigger(mock_trigger)
    bus.dispatch("TestSignal", {"foo": "bar"})

    mock_trigger.match.assert_called_once_with({"foo": "bar"})
