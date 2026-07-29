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

    def name(self) -> str:
        state = self._config.get("state", "unknown")
        return f"Power: {state}"

    def _read_ac_online(self) -> bool:
        """Read the current AC online state from sysfs."""
        try:
            with open("/sys/class/power_supply/AC/online", "r") as f:
                return f.read().strip() == "1"
        except (FileNotFoundError, PermissionError):
            return False

        # Also try alternative paths
        import glob
        for path in glob.glob("/sys/class/power_supply/*/type"):
            try:
                with open(path) as f:
                    if f.read().strip() == "Mains":
                        dir_path = os.path.dirname(path)
                        with open(os.path.join(dir_path, "online")) as f2:
                            return f2.read().strip() == "1"
            except (FileNotFoundError, PermissionError, OSError):
                continue
        return False

    def _state_matches(self, is_plugged: bool) -> bool:
        target = self._config.get("state", "plugged")
        if target == "plugged":
            return is_plugged
        return not is_plugged

    def poll(self) -> Optional[dict]:
        """Poll the AC power state. Returns an event dict if state changed."""
        current = self._read_ac_online()
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
        """Check if the event's power state matches this trigger's config state.

        The event_data may contain:
            - 'online' key (bool or int) directly at top level
            - 'changed_properties' dict with 'Online' or 'Capacity' key
        """
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

        return self._state_matches(online)

    def get_event_types(self) -> list[str]:
        return ["PropertiesChanged", "power_changed"]