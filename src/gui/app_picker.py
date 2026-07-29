"""Desktop application scanner — reads .desktop files to populate the Launch App picker."""

import configparser
import os
import subprocess
from collections import namedtuple

AppInfo = namedtuple("AppInfo", ["name", "exec_cmd", "icon", "categories", "filename"])

# Standard paths where .desktop files live
_DESKTOP_DIRS = [
    "/usr/share/applications",
    "/usr/local/share/applications",
    os.path.expanduser("~/.local/share/applications"),
    "/var/lib/snapd/desktop/applications",
    "/var/lib/flatpak/exports/share/applications",
    "/var/lib/flatpak/exports/share/applications",
]

# Cache so we don't re-parse every time
_cache = None


def _read_desktop_file(full_path: str) -> AppInfo | None:
    """Parse a single .desktop file and return an AppInfo, or None if invalid."""
    try:
        cp = configparser.ConfigParser()
        cp.read(full_path, encoding="utf-8")
        if not cp.has_section("Desktop Entry"):
            return None

        name = cp.get("Desktop Entry", "Name", fallback="")
        exec_cmd = cp.get("Desktop Entry", "Exec", fallback="")
        icon = cp.get("Desktop Entry", "Icon", fallback="")
        categories = cp.get("Desktop Entry", "Categories", fallback="")
        no_display = cp.get("Desktop Entry", "NoDisplay", fallback="false")
        hidden = cp.get("Desktop Entry", "Hidden", fallback="false")
        terminal = cp.get("Desktop Entry", "Terminal", fallback="false")

        # Skip hidden / no-display apps
        if no_display.lower() == "true" or hidden.lower() == "true":
            return None

        if not name or not exec_cmd:
            return None

        # Clean up the Exec field — strip field codes like %f, %F, %u, %U
        exec_clean = exec_cmd.split("%")[0].strip()
        # Remove quotes around the executable if needed
        exec_clean = exec_clean.strip('"').strip("'")

        # Get just the command path
        exec_parts = exec_clean.split()
        exec_cmd_clean = exec_parts[0] if exec_parts else exec_clean

        return AppInfo(
            name=name,
            exec_cmd=exec_cmd_clean,
            icon=icon,
            categories=categories,
            filename=os.path.basename(full_path),
        )
    except (configparser.Error, OSError, UnicodeDecodeError):
        return None


def get_installed_apps(force_refresh: bool = False) -> list[AppInfo]:
    """Scan all .desktop directories and return a list of AppInfo objects."""
    global _cache
    if _cache is not None and not force_refresh:
        return _cache

    seen = set()
    apps: list[AppInfo] = []

    for directory in _DESKTOP_DIRS:
        if not os.path.isdir(directory):
            continue
        try:
            for entry in os.listdir(directory):
                if not entry.endswith(".desktop"):
                    continue
                full_path = os.path.join(directory, entry)
                # Skip duplicates (user overrides system)
                if full_path in seen:
                    continue
                seen.add(full_path)
                info = _read_desktop_file(full_path)
                if info is not None:
                    apps.append(info)
        except OSError:
            continue

    # Sort by name (case-insensitive)
    apps.sort(key=lambda a: a.name.lower())
    _cache = apps
    return apps


def search_apps(query: str, max_results: int = 20) -> list[AppInfo]:
    """Filter installed apps by name match."""
    apps = get_installed_apps()
    q = query.lower().strip()
    if not q:
        return apps[:max_results]
    return [a for a in apps if q in a.name.lower()][:max_results]


def get_app_store() -> tuple[list[str], list[AppInfo]]:
    """Return (names list, app list) suitable for Gtk.StringList."""
    apps = get_installed_apps()
    names = [a.name for a in apps]
    return names, apps
