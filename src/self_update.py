"""Self-management for the workflow-automator CLI.

Provides ``install``, ``update``, ``uninstall`` and ``version`` commands, the
platform-aware daemon registration (systemd / launchd / Task Scheduler), and
the colorful interactive wizard.  Follows the established self-update pattern:

* ``install`` ALWAYS downloads the latest from GitHub (never copies the
  running tree), so an installed copy is never older than the release.
* ``update`` downloads to a temp tree, compares versions, and only swaps
  ``current/`` when the remote is actually newer.
* GitHub raw/codeload URLs always carry a timestamp cache-buster plus a
  ``Cache-Control: no-cache`` header.

Every state-changing step is factored as a small function so tests can
monkeypatch downloads / subprocesses without touching the network.
"""

import json
import logging
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time
from pathlib import Path

from src.paths import (
    app_base_dir,
    bin_dir,
    current_dir,
    default_db_path,
    shim_path,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Repo metadata
# ---------------------------------------------------------------------------

REPO = "aakashjabraham-hue/workflow-automator"
BRANCH = "master"
TARBALL_URL = f"https://codeload.github.com/{REPO}/tar.gz/refs/heads/{BRANCH}"
ZIP_URL = f"https://codeload.github.com/{REPO}/zip/refs/heads/{BRANCH}"
RAW_URL = f"https://raw.githubusercontent.com/{REPO}/{BRANCH}"

SERVICE_NAME = "workflow-automator"          # systemd unit / launchd label base
LAUNCHD_LABEL = "com.workflow.automator"
SCHTASKS_NAME = "WorkflowAutomator"

IS_WINDOWS = sys.platform == "win32"
IS_MACOS = sys.platform == "darwin"


# ---------------------------------------------------------------------------
# Output styling (colorful feedback, per user preference)
# ---------------------------------------------------------------------------

class Style:
    BOLD = "\033[1m"
    GREEN = "\033[92m"
    CYAN = "\033[96m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    MAGENTA = "\033[95m"
    DIM = "\033[2m"
    RESET = "\033[0m"


def c(text: str, *styles: str) -> str:
    """Colorize *text* (no-op when output is not a tty)."""
    if not sys.stdout.isatty():
        return text
    return "".join(styles) + text + Style.RESET


def banner() -> None:
    print(c("╭──────────────────────────────────────────────╮", Style.CYAN))
    print(c("│   ⚙️   WORKFLOW AUTOMATOR  —  v" + current_version() + "        │", Style.CYAN, Style.BOLD))
    print(c("╰──────────────────────────────────────────────╯", Style.CYAN))


def _ask(prompt: str, default: bool) -> bool:
    """Ask a yes/no question, returning *default* when stdin is unavailable.

    ``curl | bash`` one-liners close stdin once curl finishes, so a plain
    ``input()`` would raise EOFError and kill the wizard mid-install.  When
    stdin is not a tty (or reading fails) we fall back to the prompt's
    default instead of crashing — the same result as pressing Enter.
    """
    suffix = "Y/n" if default else "y/N"
    if not sys.stdin.isatty():
        print(c("  ℹ️   Non-interactive install — using the default.", Style.DIM))
        print(c(f"       ({'enabled' if default else 'skipped'} — run `workflow-automator install` to change)", Style.DIM))
        return default
    try:
        answer = input(c(f"  {prompt} ({suffix}): ", Style.YELLOW)).strip().lower()
    except (EOFError, OSError):
        print(c("  ℹ️   No input available — using the default.", Style.DIM))
        return default
    if not answer:
        return default
    return answer in ("y", "yes")


# ---------------------------------------------------------------------------
# Version helpers
# ---------------------------------------------------------------------------

_RE_VERSION = re.compile(r'__version__\s*=\s*["\']([^"\']+)["\']')
_RE_PYPROJECT_VERSION = re.compile(r'^version\s*=\s*["\']([^"\']+)["\']', re.M)


def read_version(tree_dir: str) -> str:
    """Read the version from a source tree (src/__init__.py, pyproject fallback)."""
    init = os.path.join(tree_dir, "src", "__init__.py")
    try:
        with open(init, encoding="utf-8") as f:
            m = _RE_VERSION.search(f.read())
        if m:
            return m.group(1)
    except OSError:
        pass
    pyproject = os.path.join(tree_dir, "pyproject.toml")
    try:
        with open(pyproject, encoding="utf-8") as f:
            m = _RE_PYPROJECT_VERSION.search(f.read())
        if m:
            return m.group(1)
    except OSError:
        pass
    return "0.0.0"


def current_version() -> str:
    """Version of the currently installed / running tree, or '?' if unknown."""
    try:
        from src import __version__  # noqa: PLC0415

        return __version__
    except Exception:
        return "?"


def version_key(version: str) -> tuple:
    """'1.2.3' -> (1, 2, 3).  Non-numeric segments are treated as 0."""
    parts = []
    for seg in str(version).split("."):
        try:
            parts.append(int(re.sub(r"\D", "", seg) or 0))
        except ValueError:
            parts.append(0)
    return tuple(parts)


def is_newer(remote: str, local: str) -> bool:
    """True when *remote* is strictly newer than *local*."""
    return version_key(remote) > version_key(local)


# ---------------------------------------------------------------------------
# Download / extract (cache-busted, platform-aware)
# ---------------------------------------------------------------------------

def _download(url: str, dest: str) -> bool:
    """Download *url* to *dest* showing a progress bar. Returns True on success."""
    bumped = url + ("" if "?" in url else "?v=") + f"{int(time.time())}"
    if IS_WINDOWS:
        cmd = [
            "powershell", "-NoProfile", "-Command",
            f"$ProgressPreference='Continue'; Invoke-WebRequest -UseBasicParsing "
            f"-Uri '{bumped}' -OutFile '{dest}'",
        ]
    else:
        cmd = [
            "curl", "-#", "-fL", "-H", "Cache-Control: no-cache",
            "-o", dest, bumped,
        ]
    try:
        result = subprocess.run(cmd, timeout=120)
        return result.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def _extract_tarball(tarball: str, dest: str) -> None:
    """Extract a GitHub tarball into *dest*, stripping the top-level dir."""
    os.makedirs(dest, exist_ok=True)
    with tarfile.open(tarball, "r:gz") as tf:
        members = tf.getmembers()
        top = ""
        if members:
            top = members[0].name.split("/", 1)[0]
        cleaned = []
        for m in members:
            if m.name == top:
                continue
            if m.name.startswith(top + "/"):
                m.name = m.name[len(top) + 1:]
            cleaned.append(m)
        tf.extractall(dest, members=cleaned)


def _seed_tree(new_dir: str) -> str:
    """Install a freshly extracted tree as ``current``. Returns its version."""
    base = app_base_dir()
    os.makedirs(base, exist_ok=True)
    version = read_version(new_dir)
    old = os.path.join(base, "old")
    cur = current_dir()
    shutil.rmtree(old, ignore_errors=True)
    if os.path.isdir(cur) and not os.path.samefile(cur, new_dir):
        shutil.move(cur, old)
    shutil.rmtree(cur, ignore_errors=True)  # stray partials
    shutil.move(new_dir, cur)
    shutil.rmtree(old, ignore_errors=True)
    return version


def _write_shim() -> str:
    """Write the platform executable that launches the installed tree."""
    cur = current_dir()
    path = shim_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if IS_WINDOWS:
        content = (
            "@echo off\r\n"
            f'py -3 "{cur}\\launcher.py" %*\r\n'
            "if errorlevel 1 pause\r\n"
        )
        with open(path, "w", newline="", encoding="ascii") as f:
            f.write(content)
    else:
        content = (
            "#!/usr/bin/env python3\n"
            "import os, sys\n"
            f"sys.path.insert(0, {cur!r})\n"
            "from src.main import main\n"
            "sys.exit(main())\n"
        )
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        os.chmod(path, 0o755)
    return path


def _fetch_and_seed() -> str | None:
    """Download latest tarball, extract, swap in as ``current``. Returns version."""
    base = app_base_dir()
    os.makedirs(base, exist_ok=True)
    tmp = tempfile.mkdtemp(prefix="wa-update-", dir=base)
    tarball = os.path.join(tmp, "wa.tgz")
    extracted = os.path.join(tmp, "tree")
    try:
        print(c("  ⬇️   Downloading latest from GitHub…", Style.CYAN))
        if not _download(TARBALL_URL, tarball):
            print(c("  ✗  Download failed. Check your connection and try again.", Style.RED))
            return None
        print(c("  📦  Extracting…", Style.CYAN))
        _extract_tarball(tarball, extracted)
        return _seed_tree(extracted)
    except Exception as exc:  # noqa: BLE001
        print(c(f"  ✗  Install failed: {exc}", Style.RED))
        return None
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ---------------------------------------------------------------------------
# Checkout detection (dev mode)
# ---------------------------------------------------------------------------

def running_from_checkout() -> str | None:
    """Return the git work-tree path when running from a dev checkout, else None."""
    here = Path(__file__).resolve()
    for parent in (here.parents if here.parent else []):
        if (parent / ".git").exists():
            try:
                out = subprocess.run(
                    ["git", "-C", str(parent), "remote", "get-url", "origin"],
                    capture_output=True, text=True, timeout=10,
                )
                if out.returncode == 0 and REPO.split("/")[1] in out.stdout:
                    return str(parent)
            except (OSError, subprocess.TimeoutExpired):
                return None
            return None
    return None


# ---------------------------------------------------------------------------
# Daemon registration (per platform)
# ---------------------------------------------------------------------------

def _which(name: str) -> bool:
    cmd = ["where", name] if IS_WINDOWS else ["which", name]
    try:
        return subprocess.run(cmd, capture_output=True, timeout=5).returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def _systemd_unit_path() -> str:
    return os.path.join(
        os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config"),
        "systemd", "user", f"{SERVICE_NAME}.service",
    )


def _launchd_plist_path() -> str:
    return os.path.join(os.path.expanduser("~/Library/LaunchAgents"), f"{LAUNCHD_LABEL}.plist")


def setup_daemon() -> None:
    """Install + start the daemon via the platform's autostart mechanism."""
    shim = shim_path()
    if IS_WINDOWS:
        if not _which("schtasks"):
            print(c("  ✗  schtasks not found — cannot enable autostart on this system.", Style.RED))
            return
        subprocess.run(
            ["schtasks", "/Create", "/F", "/SC", "ONLOGON", "/TN", SCHTASKS_NAME,
             "/TR", f'"{shim}" daemon'],
            timeout=30,
        )
        if daemon_active():
            print(c("  ✅  Daemon registered — starts on login (Task Scheduler).", Style.GREEN))
        else:
            print(c("  ⚠️   Registered, but could not verify (check Task Scheduler).", Style.YELLOW))
    elif IS_MACOS:
        plist = _launchd_plist_path()
        os.makedirs(os.path.dirname(plist), exist_ok=True)
        log = os.path.join(app_base_dir(), "daemon.log")
        content = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>{LAUNCHD_LABEL}</string>
  <key>ProgramArguments</key>
  <array>
    <string>/usr/bin/python3</string>
    <string>{os.path.join(current_dir(), "launcher.py")}</string>
    <string>daemon</string>
  </array>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
  <key>StandardOutPath</key><string>{log}</string>
  <key>StandardErrorPath</key><string>{log}</string>
</dict>
</plist>
"""
        with open(plist, "w", encoding="utf-8") as f:
            f.write(content)
        subprocess.run(["launchctl", "unload", plist], capture_output=True, timeout=15)
        subprocess.run(["launchctl", "load", "-w", plist], timeout=15)
        print(c("  ✅  Daemon registered — auto-starts on login (launchd).", Style.GREEN))
    else:
        unit_dir = os.path.dirname(_systemd_unit_path())
        os.makedirs(unit_dir, exist_ok=True)
        unit = f"""[Unit]
Description=Workflow Automator daemon
After=graphical-session.target bluetooth.target

[Service]
Type=simple
ExecStart="{shim}" daemon
Restart=on-failure
RestartSec=5

[Install]
WantedBy=default.target
"""
        with open(_systemd_unit_path(), "w", encoding="utf-8") as f:
            f.write(unit)
        subprocess.run(["systemctl", "--user", "daemon-reload"], timeout=30)
        subprocess.run(["systemctl", "--user", "enable", "--now", SERVICE_NAME], timeout=60)
        if daemon_active():
            print(c("  ✅  Daemon running — auto-starts on login (systemd).", Style.GREEN))
        else:
            print(c("  ⚠️   Service installed but not active — check with:", Style.YELLOW))
            print(c("       systemctl --user status workflow-automator", Style.DIM))


def daemon_active() -> bool:
    """Return True when the daemon service is currently registered/running."""
    try:
        if IS_WINDOWS:
            return subprocess.run(
                ["schtasks", "/Query", "/TN", SCHTASKS_NAME],
                capture_output=True, timeout=15,
            ).returncode == 0
        if IS_MACOS:
            return subprocess.run(
                ["launchctl", "print", f"gui/{os.getuid()}/{LAUNCHD_LABEL}"],
                capture_output=True, timeout=15,
            ).returncode == 0
        return subprocess.run(
            ["systemctl", "--user", "is-active", "--quiet", SERVICE_NAME],
            timeout=15,
        ).returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def uninstall_daemon() -> None:
    """Stop + remove the daemon autostart registration."""
    try:
        if IS_WINDOWS:
            subprocess.run(
                ["schtasks", "/End", "/TN", SCHTASKS_NAME],
                capture_output=True, timeout=15,
            )
            subprocess.run(
                ["schtasks", "/Delete", "/F", "/TN", SCHTASKS_NAME],
                capture_output=True, timeout=15,
            )
            print(c("  ✅  Task Scheduler entry removed.", Style.GREEN))
        elif IS_MACOS:
            plist = _launchd_plist_path()
            subprocess.run(["launchctl", "unload", plist], capture_output=True, timeout=15)
            if os.path.exists(plist):
                os.remove(plist)
            print(c("  ✅  LaunchAgent removed.", Style.GREEN))
        else:
            subprocess.run(
                ["systemctl", "--user", "disable", "--now", SERVICE_NAME],
                capture_output=True, timeout=60,
            )
            if os.path.exists(_systemd_unit_path()):
                os.remove(_systemd_unit_path())
            subprocess.run(["systemctl", "--user", "daemon-reload"], timeout=30)
            print(c("  ✅  systemd service stopped and removed.", Style.GREEN))
    except OSError as exc:
        print(c(f"  ⚠️   Could not remove daemon: {exc}", Style.YELLOW))


def restart_daemon_if_running() -> None:
    """Restart the daemon after an update, but only if it was already running."""
    if not daemon_active():
        return
    try:
        if IS_WINDOWS:
            subprocess.run(["schtasks", "/Run", "/TN", SCHTASKS_NAME], timeout=15)
        elif IS_MACOS:
            subprocess.run(
                ["launchctl", "kickstart", "-k", f"gui/{os.getuid()}/{LAUNCHD_LABEL}"],
                timeout=15,
            )
        else:
            subprocess.run(["systemctl", "--user", "restart", SERVICE_NAME], timeout=60)
        print(c("  🔄  Daemon restarted with the new version.", Style.GREEN))
    except OSError:
        pass


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

def cmd_version() -> None:
    print(f"  workflow-automator v{current_version()}")


def cmd_install(skip_download: bool = False) -> None:
    """Install (or finish installing) the latest version from GitHub."""
    banner()
    print()

    if skip_download:
        # Seeded by the one-liner (install.sh / install.ps1) — just finish up.
        if not os.path.isfile(os.path.join(current_dir(), "launcher.py")):
            print(c(
                "  ✗  App files missing — run the full one-liner instead:\n"
                "     curl -fL https://raw.githubusercontent.com/"
                f"{REPO}/{BRANCH}/install.sh | bash",
                Style.RED,
            ))
            return
        version = read_version(current_dir())
        print(c(f"  ✅  App files found (v{version}).", Style.GREEN))
    else:
        version = _fetch_and_seed()
        if version is None:
            return

    path = _write_shim()
    print(c(f"  ✅  Installed v{version} → {path}", Style.GREEN))

    # Auto-chain: daemon enablement (the one-liner happy path)
    if _ask("🤖   Enable the background daemon + auto-start?", default=True):
        setup_daemon()

    # Summary
    print()
    print(c("  All set! Quick commands:", Style.BOLD))
    print(c("    workflow-automator dashboard     # Open the automation app", Style.CYAN))
    print(c("    workflow-automator daemon        # Run the background daemon", Style.CYAN))
    print(c("    workflow-automator update        # Update to latest version", Style.CYAN))
    print(c("    workflow-automator version       # Show installed version", Style.CYAN))
    print(c("    workflow-automator uninstall     # Remove everything", Style.CYAN))


def cmd_update() -> None:
    """Pull the latest from GitHub (git pull in dev, tarball swap when installed)."""
    banner()
    print()

    checkout = running_from_checkout()
    if checkout is not None:
        print(c(f"  📂  Dev checkout detected ({checkout}) — running git pull…", Style.CYAN))
        result = subprocess.run(
            ["git", "-C", checkout, "pull", "--ff-only", "origin", BRANCH],
            timeout=120,
        )
        if result.returncode == 0:
            print(c("  ✅  Pulled the latest code from GitHub.", Style.GREEN))
            if not IS_WINDOWS:
                print(c("      Tip: restart the daemon if it's running:", Style.DIM))
                print(c(f"      systemctl --user restart {SERVICE_NAME}", Style.DIM))
        else:
            print(c("  ✗  git pull failed (conflicts? not a network error?) — fix manually.", Style.RED))
        return

    before = current_version()
    print(c(f"  Installed version: {before}", Style.DIM))
    version = _fetch_and_seed()
    if version is None:
        return
    if version == before:
        print(c(f"  ✅  Already on the latest version ({before})!", Style.GREEN))
        return
    if version_key(version) < version_key(before):
        print(c(
            f"  ⚠️   Remote ({version}) is OLDER than installed ({before}) — keeping your copy.",
            Style.YELLOW,
        ))
        return

    _write_shim()
    print(c(f"  ✅  Updated {before} → {version}!", Style.GREEN))
    restart_daemon_if_running()


def cmd_uninstall(confirm: bool | None = None) -> None:
    """Remove the CLI, daemon registration, and optionally the database."""
    banner()
    print()
    if confirm is None:
        confirm = _ask("🗑️   Uninstall workflow-automator? This stops the daemon.", default=False)
    if not confirm:
        print(c("  Aborted — nothing was removed.", Style.DIM))
        return

    uninstall_daemon()

    shim = shim_path()
    if os.path.exists(shim):
        os.remove(shim)
        print(c(f"  ✅  Removed {shim}", Style.GREEN))

    base = app_base_dir()
    if os.path.isdir(base):
        shutil.rmtree(base, ignore_errors=True)
        print(c(f"  ✅  Removed app files ({base})", Style.GREEN))

    db = default_db_path()
    if os.path.exists(db):
        if _ask("🗑️   Also remove your workflows database?", default=False):
            os.remove(db)
            print(c(f"  ✅  Removed database ({db})", Style.GREEN))
        else:
            print(c(f"  💾  Kept your workflows database at {db}", Style.DIM))

    print()
    print(c("  Done! workflow-automator has been uninstalled. 👋", Style.BOLD))