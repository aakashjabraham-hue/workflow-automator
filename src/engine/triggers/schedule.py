from datetime import datetime

from croniter import croniter

from src.engine.triggers.base import BaseTrigger

# Map non-standard shortcuts to 5-field equivalents for croniter.
# croniter handles @hourly, @daily, @weekly etc. natively but
# does not understand the "@every N minutes/hours/days" syntax.
_SHORTCUT_ALIASES = {
    "@midnight": "0 0 * * *",
    "@hourly": "0 * * * *",
    "@daily": "0 0 * * *",
    "@weekly": "0 0 * * 0",
    "@monthly": "0 0 1 * *",
    "@yearly": "0 0 1 1 *",
    "@annually": "0 0 1 1 *",
}


def _normalize_cron(expr: str) -> str:
    """Expand user-friendly shortcuts to standard 5-field cron."""
    lowered = expr.strip().lower()
    if lowered in _SHORTCUT_ALIASES:
        return _SHORTCUT_ALIASES[lowered]
    # @every N minutes / hours / days
    if lowered.startswith("@every"):
        parts = lowered.split()
        if len(parts) == 3 and parts[1].isdigit():
            n = int(parts[1])
            unit = parts[2].rstrip("s")
            if unit == "minute":
                return f"*/{n} * * * *"
            elif unit == "hour":
                return f"0 */{n} * * *"
            elif unit == "day":
                return f"0 0 */{n} * *"
            elif unit == "week":
                return f"0 0 * * */{n}"
    return expr


class ScheduleTrigger(BaseTrigger):
    """Cron-based schedule trigger.

    Supports standard 5-field cron expressions (minute hour day month
    weekday) as well as shortcuts like @daily, @hourly, and @every N
    minutes.
    """

    def __init__(self, cron_expr: str, workflow_id: int, config: dict | None = None):
        self.cron_expr = cron_expr
        self.workflow_id = workflow_id
        self.config = config or {}
        self._normalized = _normalize_cron(cron_expr)
        now = datetime.now()
        self._croniter = croniter(self._normalized, now)
        # If the current time already matches the cron, fire immediately
        # on the first check. Otherwise, compute the next scheduled time.
        if croniter.match(self._normalized, now):
            self._next_run = now
        else:
            self._next_run = self._croniter.get_next(datetime)

    def name(self) -> str:
        return "schedule"

    def get_event_types(self) -> list[str]:
        return ["schedule.poll"]

    def match(self, event_data: dict) -> bool:
        """ScheduleTrigger ignores event data; delegates to check()."""
        return self.check()

    def check(self) -> bool:
        """Return True when the cron schedule has reached its fire time."""
        now = datetime.now()
        if now >= self._next_run:
            self._next_run = self._croniter.get_next(datetime)
            return True
        return False

    def get_next_run(self) -> datetime:
        """Return the next scheduled fire time (always in the future or now)."""
        return self._next_run