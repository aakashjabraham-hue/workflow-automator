"""Bluetooth device scanner — scans for paired Bluetooth devices for the device picker."""

import subprocess
import re

PairedDevice = tuple  # (name: str, mac: str)

_cache = None


def _parse_bluetoothctl() -> list[PairedDevice]:
    """Run bluetoothctl devices Paired and parse the output.

    Supports both bluetoothctl 5.85+ (``devices Paired``) and older
    versions (``paired-devices``).
    """
    candidates = [
        ["bluetoothctl", "devices", "Paired"],
        ["bluetoothctl", "paired-devices"],
    ]
    output = ""
    for cmd in candidates:
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=10,
            )
            # Accept successful run OR a partial stdout with "Device" lines
            if result.returncode == 0 or "Device" in result.stdout:
                output = result.stdout
                break
        except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
            continue

    if not output:
        return []

    devices: list[PairedDevice] = []
    for line in output.strip().split("\n"):
        line = line.strip()
        # Format: "Device XX:XX:XX:XX:XX:XX Device Name"
        match = re.match(r"^Device\s+([0-9A-Fa-f:]+)\s+(.+)$", line)
        if match:
            mac = match.group(1).upper()
            name = match.group(2).strip()
            if name:
                devices.append((name, mac))

    # Sort by name
    devices.sort(key=lambda d: d[0].lower())
    return devices


def _parse_bluetoothctl_via_dbus() -> list[PairedDevice]:
    """Fallback: use D-Bus to list adapters and paired devices."""
    try:
        result = subprocess.run(
            ["busctl", "call", "org.bluez", "/", "org.freedesktop.DBus.ObjectManager", "GetManagedObjects"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        output = result.stdout
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return []

    devices: list[PairedDevice] = []
    current_mac = ""
    current_name = ""
    paired = False

    for line in output.split("\n"):
        mac_match = re.search(r'"/org/bluez/hci(\d+)/dev_([^"]+)"', line)
        if mac_match:
            # Save previous device
            if current_mac and current_name and paired:
                devices.append((current_name, current_mac))
            # Parse new device MAC
            raw = mac_match.group(2)
            mac = ":".join(raw[i : i + 2] for i in range(0, len(raw), 2)).upper()
            current_mac = mac
            current_name = ""
            paired = False
            continue

        name_match = re.search(r'string\s+"([^"]+)"', line)
        if name_match and current_mac:
            current_name = name_match.group(1)

        if "boolean true" in line and "Paired" in line:
            paired = True

    # Last device
    if current_mac and current_name and paired:
        devices.append((current_name, current_mac))

    devices.sort(key=lambda d: d[0].lower())
    return devices


def get_paired_devices(force_refresh: bool = False) -> list[PairedDevice]:
    """Return a list of (name, MAC) tuples for all paired Bluetooth devices."""
    global _cache
    if _cache is not None and not force_refresh:
        return _cache

    devices = _parse_bluetoothctl()
    if not devices:
        devices = _parse_bluetoothctl_via_dbus()

    _cache = devices
    return devices


def get_device_store() -> tuple[list[str], list[PairedDevice]]:
    """Return (names list, devices list) for a Gtk.StringList."""
    devices = get_paired_devices()
    names = [f"{d[0]} ({d[1]})" for d in devices]
    if not names:
        names = ["No paired devices found"]
    return names, devices
