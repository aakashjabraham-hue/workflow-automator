import re
from src.engine.triggers.base import TriggerBase


class BluetoothTrigger(TriggerBase):
    """Trigger that fires when a Bluetooth device connects or disconnects.

    Config keys:
        device_name: str - exact name of the device to match (optional)
        mac_pattern: str - substring to match against the device MAC address (optional)

    Either device_name or mac_pattern must be provided in config.
    """

    def __init__(self, config: dict):
        self._config = config

    def name(self) -> str:
        device = self._config.get("device_name") or self._config.get("mac_pattern", "unknown")
        return f"Bluetooth: {device}"

    def match(self, event_data: dict) -> bool:
        """Check if the event indicates a Bluetooth device connection.

        The event_data may contain:
            - 'changed_properties' dict with 'Connected' key (from D-Bus PropertiesChanged)
            - 'Connected' key directly at top level
            - 'device' or 'device_name' key to match against config
            - 'mac_address' or 'object_path' for MAC-based matching
        """
        changed = event_data.get("changed_properties", {})
        connected = changed.get("Connected")

        if connected is None:
            connected = event_data.get("Connected")

        if connected is not True:
            return False

        device_name = event_data.get("device") or event_data.get("device_name", "")
        mac_address = event_data.get("mac_address", "")

        # Extract MAC from D-Bus object_path if available
        # e.g. /org/bluez/hci0/dev_XX_XX_XX_XX_XX_XX
        object_path = event_data.get("object_path", "")
        if not mac_address and object_path:
            mac_match_path = re.search(r'dev_([0-9A-Fa-f_]+)', object_path)
            if mac_match_path:
                raw = mac_match_path.group(1)
                mac_address = ":".join(raw.split("_")).upper()

        device_name_match = (
            self._config.get("device_name") is not None
            and device_name == self._config.get("device_name")
        )
        mac_match = (
            self._config.get("mac_pattern") is not None
            and mac_address
            and self._config.get("mac_pattern") in mac_address
        )

        return device_name_match or mac_match

    def get_event_types(self) -> list[str]:
        return ["PropertiesChanged"]