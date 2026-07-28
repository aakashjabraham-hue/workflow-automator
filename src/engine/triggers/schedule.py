from datetime import datetime

from croniter import croniter

from src.engine.triggers.base import BaseTrigger


class ScheduleTrigger(BaseTrigger):
    """Cron-based schedule trigger.

    Supports standard cron expressions (minute hour day month weekday)
    as well as shortcuts like @daily, @hourly, and @every N minutes.
    """

    def __init__(self, cron_expr: str, workflow_id: int, config: dict | None = None):
        self.cron_expr = cron_expr
        self.workflow_id = workflow_id
        self.config = config or {}
        self._croniter = croniter(cron_expr, datetime.now())
        self._next_run = self._croniter.get_next(datetime)

    def name(self) -> str:
        return "schedule"

    def get_event_types(self) -> list[str]:
        return ["schedule.poll"]

    def check(self) -> bool:
        """Return True when the cron expression indicates it is time to fire."""
        now = datetime.now()
        if now >= self._next_run:
            # Advance to the next scheduled time so subsequent checks
            # don't fire again for the same interval.
            self._next_run = self._croniter.get_next(datetime)
            return True
        return False

    def get_next_run(self) -> datetime:
        """Return the next scheduled fire time (always in the future)."""
        return self._next_run