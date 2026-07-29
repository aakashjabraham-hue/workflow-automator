from typing import Any, Optional

import os

from src.engine.triggers.base import TriggerBase


class PowerTrigger(TriggerBase):
    """Trigger that fires when AC power is plugged in or unplugged.

    Config keys:
        state: str - either 'plugged' or 'unplugged'

    On Linux, polls /sys/class/power_supply/AC/online as a fallback when
    no D-Bus signal arrives. A value of '1' means plugged in, '0' means
    unplugged.
    """

    def __init__(self, config: dict):
        self._config = config
        self._last_state: Optional[bool] = None
        self._ac_path = None

    def name(self) -> str:
        state = self._config.get("state", "unknown")
        return f"Power: {state}"

    def _find_ac_path(self) -> str | None:
        """Find the sysfs path for AC power online status."""
        for common_path in [
            "/sys/class/power_supply/AC/online",
            "/sys/class/power_supply/ACAD/online",
            "/sys/class/power_supply/ADP0/online",
            "/sys/class/power_supply/ADP1/online",
        ]:
            if os.path.exists(common_path):
                return common_path
        # Fallback: scan all power supply dirs for "Mains" type
        import glob
        for path in glob.glob("/sys/class/power_supply/*/type"):
            try:
                with open(path) as f:
                    if f.read().strip() == "Mains":
                        return os.path.join(os.path.dirname(path), "online")
            except (FileNotFoundError, PermissionError, OSError):
                continue
        return None

    def _read_ac_online(self) -> bool:
        """Read the current AC online state from sysfs."""
        if self._ac_path is None:
            self._ac_path = self._find_ac_path()
        if self._ac_path is None:
            return False
        try:
            with open(self._ac_path, "r") as f:
                val = f.read().strip()
                return val == "1"
        except (FileNotFoundError, PermissionError):
            return False

    def _state_matches(self, is_plugged: bool) -> bool:
        target = self._config.get("state", "plugged")
        if target == "plugged":
            return is_plugged
        return not is_plugged

    def poll(self) -> Optional[dict]:
        """Poll the AC power state. Returns an event dict if state changed."""
        current = self._read_ac_online()
        import logging as _lg
        _lg.getLogger("workflow-automator.daemon").debug(
            "PowerTrigger poll: current=%s last=%s path=%s",
            current, self._last_state, self._ac_path,
        )
        if self._last_state is not None and current != self._last_state:
            self._last_state = current
            return {
                "type": "power_changed",
                "online": current,
            }
        if self._last_state is None:
            self._last_state = current
        return None

    def match(self, event_data: dict) -> bool:
        """Check if the event's power state matches this trigger's config state."""
        import logging as _lg
        changed = event_data.get("changed_properties", {})

        # Check for direct online indicator in event data
        online: Optional[bool] = None
        if "online" in event_data:
            online = bool(event_data["online"])
        elif "Online" in changed:
            online = bool(changed["Online"])
        else:
            # Fall back to reading sysfs directly
            online = self._read_ac_online()

        result = self._state_matches(online)
        _lg.getLogger("workflow-automator.daemon").debug(
            "PowerTrigger match: online=%s target=%s result=%s",
            online, self._config.get("state"), result,
        )
        return result

    def get_event_types(self) -> list[str]:
        return ["PropertiesChanged", "power_changed"]