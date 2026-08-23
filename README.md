# Workflow Automator

A GNOME desktop automation app for Linux — create event-driven workflows that respond to system events, schedule tasks, and control apps.

Think Tasker for Linux: connect Bluetooth headphones → launch Spotify → play your playlist, or unplug your laptop → enable power-saving mode.

---

## Features

- **Event-driven triggers**: Bluetooth device connect, AC power plug/unplug, cron schedules
- **Multiple action types**: Launch apps, run shell commands, send notifications, control media players via MPRIS
- **MPRIS media control**: Play, pause, skip tracks, or open playlists in Spotify, VLC, Firefox, and any MPRIS-capable player
- **Background daemon**: Runs as a systemd user service so workflows fire even when the GUI is closed
- **GTK4 GUI**: Create and manage workflows through a visual editor
- **SQLite storage**: All workflows persist locally

---

## Quick Start

### One-liner install (Linux / macOS)

```bash
curl -fL https://raw.githubusercontent.com/aakashjabraham-hue/workflow-automator/master/install.sh | bash
```

### One-liner install (Windows — PowerShell 5.1+)

```powershell
irm https://raw.githubusercontent.com/aakashjabraham-hue/workflow-automator/master/install.ps1 | iex
```

The installer downloads the **latest** version from GitHub, installs the
`workflow-automator` command, and offers to enable the background daemon.
No manual follow-up steps.

### Manual / development setup

```bash
# Clone and enter
cd ~/workflow-automator

# Install dependencies (Ubuntu/Debian)
sudo apt install python3-gi python3-gi-cairo gir1.2-gtk-4.0 playerctl

# Launch the GUI
/usr/bin/python3 -m src.main
```

---

## CLI Commands

| Command | What it does |
|---------|--------------|
| `workflow-automator` | Opens the desktop app (GTK4 GUI) |
| `workflow-automator desktop` | Same as above — explicit |
| `workflow-automator dashboard` | Opens the web dashboard in your browser (localhost) |
| `workflow-automator dashboard --port 9000` | Web dashboard on a specific port |
| `workflow-automator daemon` | Runs the background daemon (`--foreground --verbose` for testing) |
| `workflow-automator update` | Pulls the latest from GitHub and restarts the daemon if running |
| `workflow-automator install` | Installs/repairs the CLI (downloads latest from GitHub) |
| `workflow-automator uninstall` | Stops the daemon, removes the CLI, app files and (optionally) your workflows |
| `workflow-automator version` | Shows the installed version |
| `workflow-automator --version` | Same, as a flag |

In development mode (running from the repo checkout), `update` runs
`git pull` — in installed mode it downloads the latest release from GitHub.
`update` never downgrades and never re-downloads when you're already current.

---

## Web Dashboard

`workflow-automator dashboard` serves the same workflow-management UI as the
desktop app, but in your browser over localhost — no GUI toolkit needed. It
edits the exact same database the desktop app and the daemon use, so changes
show up everywhere instantly.

```bash
workflow-automator dashboard
# → serving at http://127.0.0.1:8899  (opens your browser automatically)
```

- **Zero extra dependencies** — built on Python's standard library
  (`http.server`), no npm, no frameworks, no install step.
- **Port** defaults to `8899`; if it's busy the next free port is used.
  Force one with `--port`:
  ```bash
  workflow-automator dashboard --port 9000
  ```
- **Everything the desktop app does**: create / edit / delete workflows,
  configure triggers (Bluetooth, power, schedule/cron) and
  actions (shell, launch, notify, media), toggle workflows on/off.
- Works headless: `ssh` into a machine and `dashboard` still serves — just
  open the printed URL yourself.

---

## Usage

### Creating a Workflow

1. Launch the app: `/usr/bin/python3 -m src.main`
2. Click the **+** button in the header bar
3. Give your workflow a name
4. Pick a **trigger** (what starts the automation)
5. Add one or more **actions** (what happens)
6. Click **Save**

### Running the Background Daemon

For triggers to fire automatically (Bluetooth, power, schedules), the daemon must be running:

```bash
# Run in foreground (for testing)
cd ~/workflow-automator && /usr/bin/python3 -m src.main daemon --foreground --verbose

# Install as a user service that auto-starts on login
workflow-automator install        # then answer "y" to the daemon prompt
# Or, from the checkout:
systemctl --user enable --now workflow-automator   # Linux only
journalctl --user -u workflow-automator -f
```

The daemon auto-registers on each platform:
- **Linux** → systemd user service
- **macOS** → launchd LaunchAgent
- **Windows** → Task Scheduler (run at logon)

---

## Use Cases

### 🎧 Bluetooth Headphones → Play Music

When you connect your Bluetooth headphones, automatically launch Spotify and start your favorite playlist:

| Step | Setting |
|------|---------|
| **Name** | "Commute Music" |
| **Trigger** | Bluetooth → select your headphones |
| **Action 1** | Launch → Spotify |
| **Action 2** | Media → Spotify → Open URI → `spotify:playlist:37i9dQZF1DXcBWIGoYBM5M` |

### 🔋 Unplug Laptop → Power-Saving Mode

When you disconnect from AC power, automatically enable power-saving settings:

| Step | Setting |
|------|---------|
| **Name** | "Power Saver" |
| **Trigger** | Power → unplugged |
| **Action** | Shell → `powerprofilesctl set power-saver` |

### ⏰ Daily Reminder at 8 AM

Get a notification every morning:

| Step | Setting |
|------|---------|
| **Name** | "Morning Standup" |
| **Trigger** | Schedule → `0 8 * * *` |
| **Action** | Notify → Subject: "Standup time" / Body: "Time for the morning meeting!" |

### 📺 Movie Time

When you connect your Bluetooth speaker, dim the screen and launch VLC:

| Step | Setting |
|------|---------|
| **Name** | "Movie Night" |
| **Trigger** | Bluetooth → your speaker |
| **Action 1** | Shell → `brightnessctl set 30%` |
| **Action 2** | Launch → VLC |
| **Action 3** | Media → VLC → Play |

### 🔊 Pause Music When Laptop Unplugs

| Step | Setting |
|------|---------|
| **Name** | "Quiet Unplug" |
| **Trigger** | Power → unplugged |
| **Action** | Media → Spotify → Pause |

---

## Action Types

| Type | Description |
|------|-------------|
| **Shell** | Run any shell command or script |
| **Launch** | Launch a desktop app (picks from all installed `.desktop` files) |
| **Notify** | Send a desktop notification with subject and body |
| **Media** | Control MPRIS-compatible media players (Play, Pause, Next, Previous, Stop, Open URI) |

## Trigger Types

| Type | Description |
|------|-------------|
| **Bluetooth** | Fires when a specific paired Bluetooth device connects |
| **Power** | Fires when AC power is plugged in or unplugged (polls every 10s) |
| **Schedule** | Cron-like scheduling (`0 8 * * *` for daily at 8am) |

---

## Project Structure

```
workflow-automator/
├── launcher.py                # Cwd-independent entry point (used by the installed CLI)
├── install.sh                 # One-liner installer (Linux/macOS)
├── install.ps1                # One-liner installer (Windows)
├── src/
│   ├── main.py                # Entry point: GUI, daemon, install/update/uninstall/version
│   ├── paths.py               # Platform-aware paths (Linux/macOS/Windows)
│   ├── self_update.py         # install/update/uninstall + daemon registration
│   ├── app.py                 # GTK Application
│   ├── gui/
│   │   ├── main_window.py      # Workflow list view
│   │   ├── workflow_editor.py  # Workflow creation/editing dialog
│   │   ├── widgets.py          # Custom widget classes
│   │   ├── app_picker.py       # Desktop app scanner
│   │   └── style.css           # Dark theme stylesheet
│   ├── engine/
│   │   ├── executor.py         # Action execution
│   │   ├── event_bus.py        # Event dispatch system
│   │   └── triggers/
│   │       ├── bluetooth.py    # Bluetooth device trigger
│   │       ├── bluetooth_devices.py  # BT device scanner
│   │       ├── power.py        # AC power trigger
│   │       └── schedule.py     # Cron schedule trigger
│   ├── models/
│   │   ├── workflow.py         # Workflow model
│   │   ├── trigger.py          # Trigger model
│   │   └── action.py           # Action model
│   ├── db/
│   │   └── __init__.py         # SQLite setup
│   └── daemon/
│       └── service.py          # Background daemon
├── resources/
│   └── com.workflow.Automator.service  # systemd unit
└── tests/
    └── ...
```

---

## Cross-Platform Support

| | Linux | macOS | Windows |
|--|-------|-------|---------|
| **CLI** (`desktop`, `dashboard`, `daemon`, `update`, `install`, `uninstall`, `version`) | ✅ | ✅ | ✅ |
| **Desktop app** (GTK4) | ✅ | via `brew install pygobject3 gtk4` | via GTK for Python |
| **Web dashboard** (localhost, no extra deps) | ✅ | ✅ | ✅ |
| **Daemon autostart** | systemd user service | launchd LaunchAgent | Task Scheduler |
| **Bluetooth / Power / Network triggers** | ✅ | — (no BlueZ/sysfs) | — |
| **Schedule trigger (cron)** | ✅ | ✅ | ✅ |
| **Shell / Launch / Notify actions** | ✅ | ✅ | ✅ (notify via PowerShell balloon) |
| **Media actions (MPRIS/playerctl)** | ✅ | — | — |
| **Database** | `~/.workflow-automator/workflows.db` | `~/Library/Application Support/workflow-automator/` | `%APPDATA%\workflow-automator\` |

Platform-specific triggers simply never fire on unsupported OSes — the
daemon degrades gracefully instead of crashing. `update` and `install`
always fetch the latest from GitHub, cache-busted, on every platform.

---

## Dependencies

- **Python 3.11+** with `python3-gi` (PyGObject)
- **GTK 4** with `gir1.2-gtk-4.0`
- **systemd** (for daemon auto-start)
- **playerctl** (for media controls) — `sudo apt install playerctl`

---

## License

MIT