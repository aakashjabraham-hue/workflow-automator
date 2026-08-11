"""Platform-aware paths for workflow-automator (Linux, macOS, Windows).

Every path resolves through a module-level ``_PLATFORM`` marker so tests can
patch ``src.paths._PLATFORM`` to simulate other operating systems without
changing ``sys.platform`` (which some libs cache at import time).
"""

import os
import sys

_PLATFORM = sys.platform

IS_WINDOWS = _PLATFORM == "win32"
IS_MACOS = _PLATFORM == "darwin"


def _localappdata() -> str:
    return os.environ.get("LOCALAPPDATA") or os.path.expanduser(r"~\AppData\Local")


def _appdata() -> str:
    return os.environ.get("APPDATA") or os.path.expanduser(r"~\AppData\Roaming")


def app_base_dir() -> str:
    """Where installed copies of the app live (versioned `current/` tree)."""
    if IS_WINDOWS:
        return os.path.join(_localappdata(), "workflow-automator")
    if IS_MACOS:
        return os.path.join(os.path.expanduser("~/Library/Application Support"), "workflow-automator")
    return os.path.join(
        os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share"),
        "workflow-automator",
    )


def current_dir() -> str:
    """The directory holding the currently installed app tree."""
    return os.path.join(app_base_dir(), "current")


def config_dir() -> str:
    """Per-user config and credentials directory."""
    if IS_WINDOWS:
        return os.path.join(_appdata(), "workflow-automator")
    if IS_MACOS:
        return os.path.join(os.path.expanduser("~/Library/Application Support"), "workflow-automator")
    return os.path.join(
        os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config"),
        "workflow-automator",
    )


def bin_dir() -> str:
    """Directory where the `workflow-automator` shim is installed."""
    if IS_WINDOWS:
        return os.path.join(_localappdata(), "workflow-automator", "bin")
    return os.path.expanduser("~/.local/bin")


def shim_path() -> str:
    """Path to the `workflow-automator` executable shim."""
    if IS_WINDOWS:
        return os.path.join(bin_dir(), "workflow-automator.cmd")
    return os.path.join(bin_dir(), "workflow-automator")


def default_db_path() -> str:
    """Default SQLite database location.

    Linux keeps the historical ``~/.workflow-automator/workflows.db`` so
    existing installations keep their data untouched.
    """
    if IS_WINDOWS:
        return os.path.join(config_dir(), "workflows.db")
    if IS_MACOS:
        return os.path.join(
            os.path.expanduser("~/Library/Application Support"),
            "workflow-automator",
            "workflows.db",
        )
    return os.path.join(os.path.expanduser("~/.workflow-automator"), "workflows.db")