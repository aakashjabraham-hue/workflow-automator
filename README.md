# Workflow Automator

A GNOME desktop automation app for Linux — create event-driven workflows that respond to system events, schedule tasks, and control apps.

Think Tasker for Linux: connect Bluetooth headphones → launch Spotify → play your playlist, or unplug your laptop → enable power-saving mode.

---

## Features

- **Event-driven triggers**: Bluetooth device connect, AC power plug/unplug, cron schedules, network changes
- **Multiple action types**: Launch apps, run shell commands, send notifications, control media players via MPRIS
- **MPRIS media control**: Play, pause, skip tracks, or open playlists in Spotify, VLC, Firefox, and any MPRIS-capable player
- **Background daemon**: Runs as a systemd user service so workflows fire even when the GUI is closed
- **GTK4 GUI**: Create and manage workflows through a visual editor
- **SQLite storage**: All workflows persist locally

---

## Quick Start

```bash
# Clone and enter
cd ~/workflow-automator

# Install dependencies (Ubuntu/Debian)
sudo apt install python3-gi python3-gi-cairo gir1.2-gtk-4.0 playerctl

# Launch the GUI
/usr/bin/python3 -m src.main
```

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
cd ~/workflow-automator && /usr/bin/python3 -m src.main --daemon --foreground

# Run as a systemd user service (auto-starts on login)
python3 -m src.main --install-service
systemctl --user enable --now workflow-automator
journalctl --user -u workflow-automator -f
```

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
| **Network** | Fires when connecting to a specific network/SSID |
| **Shell** | Fires when a watched command exits with a specific output |

---

## Project Structure

```
workflow-automator/
├── src/
│   ├── main.py                 # Entry point (GUI or daemon)
│   ├── app.py                  # GTK Application
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

## Dependencies

- **Python 3.11+** with `python3-gi` (PyGObject)
- **GTK 4** with `gir1.2-gtk-4.0`
- **systemd** (for daemon auto-start)
- **playerctl** (for media controls) — `sudo apt install playerctl`

---

## License

MIT