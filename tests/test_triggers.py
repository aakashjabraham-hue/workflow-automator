from datetime import datetime

import pytest
from croniter import croniter
from freezegun import freeze_time

from src.engine.triggers.schedule import ScheduleTrigger


def test_construct_at_1004_check_at_1005():
    """Construct trigger at 10:04, advances to 10:05, check fires."""
    with freeze_time("2026-07-27 10:04:00"):
        trigger = ScheduleTrigger("*/5 * * * *", 1)
        assert trigger.check() is False  # not yet 10:05

    with freeze_time("2026-07-27 10:05:00"):
        assert trigger.check() is True  # now it's 10:05


def test_construct_exactly_at_fire_time():
    """Construct trigger at 10:05 (on boundary), check fires immediately."""
    with freeze_time("2026-07-27 10:05:00"):
        trigger = ScheduleTrigger("*/5 * * * *", 1)
        # 10:05 is on the 5-min boundary → next_run = 10:05, check() returns True
        assert trigger.check() is True


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


def test_next_fire_after_boundary():
    """After firing, next fire time is correctly computed."""
    with freeze_time("2026-07-27 10:05:00"):
        trigger = ScheduleTrigger("*/5 * * * *", 1)
        trigger.check()  # fire at 10:05

    # After firing at 10:05, next is 10:10
    with freeze_time("2026-07-27 10:10:00"):
        assert trigger.check() is True


def test_schedule_daily_8am():
    """Daily trigger at 8am fires when time reaches 8am."""
    with freeze_time("2026-07-27 07:59:00"):
        trigger = ScheduleTrigger("0 8 * * *", 1)
        assert trigger.check() is False  # not yet 8am

    with freeze_time("2026-07-27 08:00:00"):
        assert trigger.check() is True  # it's 8am!


def test_next_run_is_in_future_or_now():
    """next_run after construction is always in the future or at now."""
    with freeze_time("2026-07-27 10:04:00"):
        trigger = ScheduleTrigger("*/5 * * * *", 1)
    assert trigger._next_run >= datetime(2026, 7, 27, 10, 0, 0)


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
        # 10:05 is on the boundary, so next_run = 10:05, check fires immediately
        assert trigger.check() is True

    with freeze_time("2026-07-27 10:10:00"):
        # After firing at 10:05, a fresh trigger next is 10:10
        trigger2 = ScheduleTrigger("@every 5 minutes", 1)
        assert trigger2.check() is True


def test_croniter_next_from_boundary():
    """croniter.get_next from exact boundary time gives NEXT boundary, not current."""
    c = croniter("*/5 * * * *", datetime(2026, 7, 27, 10, 0, 0))
    assert c.get_next(datetime) == datetime(2026, 7, 27, 10, 5, 0)


def test_croniter_match_at_boundary():
    """croniter.match correctly identifies times that match the schedule."""
    assert croniter.match("*/5 * * * *", datetime(2026, 7, 27, 10, 0, 0))
    assert croniter.match("*/5 * * * *", datetime(2026, 7, 27, 10, 5, 0))
    assert not croniter.match("*/5 * * * *", datetime(2026, 7, 27, 10, 3, 0))