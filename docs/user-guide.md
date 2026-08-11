# Workflow Automator — User Guide

## Installation

### One-liner install (Linux / macOS)

```bash
curl -fL https://raw.githubusercontent.com/aakashjabraham-hue/workflow-automator/master/install.sh | bash
```

### One-liner install (Windows — PowerShell 5.1+)

```powershell
irm https://raw.githubusercontent.com/aakashjabraham-hue/workflow-automator/master/install.ps1 | iex
```

Always installs the **latest** version from GitHub. The installer offers to
enable the background daemon so workflows fire automatically.

### Staying up to date

```bash
workflow-automator update
```

`update` pulls the latest from GitHub (a `git pull` when run from a
development checkout). If the daemon is running it is restarted automatically.

### Removing

```bash
workflow-automator uninstall
```

Stops the daemon, removes the CLI and app files, then asks whether to keep
or delete your workflows database.

## First Run

After installation, launch the Workflow Automator from your application menu. The main window opens showing any existing workflows you have configured.

## Creating Your First Workflow

A workflow consists of three parts: a **name**, a **trigger**, and an **action**.

1. Click **New Workflow** in the toolbar.
2. Enter a **Name** for your workflow (e.g., "Bluetooth Music").
3. Choose a **Trigger** from the dropdown:
   - **Bluetooth** — fires when a Bluetooth device connects or disconnects.
   - **Power** — fires when AC power is plugged in or unplugged.
   - **Schedule** — fires at a specific time or on a recurring cron schedule.
4. Choose an **Action**:
   - **Shell** — run any shell command.
   - **Launch** — open an application.
   - **Notify** — display a desktop notification.
   - **DBus** — call a D-Bus method.
5. Click **Save**.

## Example Workflows

### Bluetooth → Spotify

Automatically launch Spotify when your Bluetooth headphones connect.

| Field     | Value                              |
|-----------|------------------------------------|
| Name      | Bluetooth Headphones               |
| Trigger   | Bluetooth device connects          |
| Action    | Launch → Spotify                   |

### Power Unplug → Power Saving

Switch to a power-saving profile when unplugging your laptop.

| Field     | Value                              |
|-----------|------------------------------------|
| Name      | Unplug Power Saving                |
| Trigger   | AC power disconnected              |
| Action    | Shell → `notify-send "Power Saving" "Switched to power saver"` |

### Daily Schedule

Send a morning reminder at 8 AM every weekday.

| Field     | Value                              |
|-----------|------------------------------------|
| Name      | Morning Reminder                   |
| Trigger   | Schedule (cron: `0 8 * * 1-5`)     |
| Action    | Notify → "Good morning! Time to start the day." |

## Service Setup

To run the Workflow Automator as a background systemd user service:

```bash
# Copy the service file to your user systemd directory
cp /usr/share/workflow-automator/resources/com.workflow.Automator.service ~/.config/systemd/user/

# Enable and start the service
systemctl --user enable --now com.workflow.Automator.service
```

To verify the service is running:

```bash
systemctl --user status com.workflow.Automator.service
```

To stop or disable:

```bash
systemctl --user stop com.workflow.Automator.service
systemctl --user disable com.workflow.Automator.service
```

## Uninstall

### From PyPI

```bash
pip uninstall workflow-automator
```

### From Flatpak

```bash
flatpak uninstall com.workflow.Automator
```

To remove the service file:

```bash
rm ~/.config/systemd/user/com.workflow.Automator.service
```
