"""WorkflowEditorDialog — create or edit a workflow with trigger, action, and schedule config."""

import json

import gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, GObject, GLib

from src.db import init_db
from src.models.workflow import Workflow, get_workflow
from src.models.trigger import Trigger, get_triggers_for_workflow
from src.models.action import Action, get_actions_for_workflow
from src.engine.executor import ActionExecutor


_TRIGGER_TYPES = ["bluetooth", "power", "schedule", "network", "shell"]
_ACTION_TYPES = ["shell", "launch", "notify", "media"]
_MEDIA_ACTIONS = ["Play", "Pause", "Play-Pause", "Next", "Previous", "Stop", "Open URI"]


def _build_trigger_config(trigger_type, widgets):
    """Return a config dict based on the currently-visible config widgets."""
    if trigger_type == "bluetooth":
        dd = widgets.get("bt_device_dropdown", None)
        devices = widgets.get("_bt_devices", [])
        if dd is not None and devices:
            idx = dd.get_selected()
            if 0 <= idx < len(devices):
                name, mac = devices[idx]
                return {"device_name": name, "mac_pattern": mac}
        return {"device_name": "", "mac_pattern": ""}
    elif trigger_type == "power":
        idx = widgets.get("power_state", None)
        if idx is not None and hasattr(idx, "get_selected"):
            sel = idx.get_selected()
            state = ["plugged", "unplugged"][sel] if 0 <= sel < 2 else "plugged"
        else:
            state = "plugged"
        return {"state": state}
    elif trigger_type == "schedule":
        return {"cron_expr": widgets.get("schedule_cron", "").get_text().strip()}
    elif trigger_type == "network":
        return {
            "ssid": widgets.get("net_ssid", "").get_text().strip(),
            "interface": widgets.get("net_interface", "").get_text().strip(),
        }
    elif trigger_type == "shell":
        return {"command": widgets.get("shell_cmd", "").get_text().strip()}
    return {}


def _populate_trigger_fields(trigger_type, widgets, config):
    """Fill in the dynamic config fields for the given trigger type."""
    if trigger_type == "bluetooth":
        dd = widgets.get("bt_device_dropdown", None)
        devices = widgets.get("_bt_devices", [])
        if dd is not None and devices:
            device_name = config.get("device_name", "")
            mac = config.get("mac_pattern", "")
            for i, (dname, dmac) in enumerate(devices):
                if dname == device_name or dmac == mac:
                    dd.set_selected(i)
                    break
    elif trigger_type == "power":
        state = config.get("state", "plugged")
        idx = ["plugged", "unplugged"].index(state) if state in ("plugged", "unplugged") else 0
        if "power_state" in widgets:
            widgets["power_state"].set_selected(idx)
    elif trigger_type == "schedule":
        if "schedule_cron" in widgets:
            widgets["schedule_cron"].set_text(config.get("cron_expr", ""))
    elif trigger_type == "network":
        if "net_ssid" in widgets:
            widgets["net_ssid"].set_text(config.get("ssid", ""))
        if "net_interface" in widgets:
            widgets["net_interface"].set_text(config.get("interface", ""))
    elif trigger_type == "shell":
        if "shell_cmd" in widgets:
            widgets["shell_cmd"].set_text(config.get("command", ""))


# ---------------------------------------------------------------------------
# WorkflowEditorDialog
# ---------------------------------------------------------------------------

class WorkflowEditorDialog(Gtk.Dialog):
    """Dialog for creating or editing a workflow.

    Signals:
        workflow-saved: emitted after a successful save, passing the workflow id (int).
    """

    __gsignals__ = {
        "workflow-saved": (GObject.SignalFlags.RUN_LAST, None, (int,)),
    }

    def __init__(self, parent_window, db_path, workflow_id=None):
        super().__init__(
            title="New Workflow",
            transient_for=parent_window,
            modal=True,
            use_header_bar=True,
        )

        self.db_path = db_path
        self.workflow_id = workflow_id
        self._action_rows = []
        self._trigger_config_widgets = {}
        self._loading = False

        self.add_css_class("workflow-editor")
        self.add_css_class("workflow-automator")

        self._build_ui()
        self._connect_signals()

        # Build the initial trigger type's config fields (signal won't fire)
        self._on_trigger_type_changed(self.dropdown_trigger, None)

        if workflow_id is not None:
            self._load_workflow(workflow_id)

        self.set_default_size(520, 640)

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        box.set_margin_start(18)
        box.set_margin_end(18)
        box.set_margin_top(12)
        box.set_margin_bottom(12)
        self.get_content_area().append(box)

        self._add_name_field(box)
        self._add_enabled_toggle(box)
        self._add_trigger_section(box)
        self._add_actions_section(box)
        self._add_schedule_section(box)
        self._add_buttons(box)

    def _add_name_field(self, parent):
        label = Gtk.Label(label="Workflow Name", halign=Gtk.Align.START)
        label.add_css_class("dim-label")
        parent.append(label)

        self.entry_name = Gtk.Entry()
        self.entry_name.set_placeholder_text("My workflow\u2026")
        parent.append(self.entry_name)

    def _add_enabled_toggle(self, parent):
        row = Gtk.Box(spacing=12, orientation=Gtk.Orientation.HORIZONTAL)
        row.set_halign(Gtk.Align.START)
        label = Gtk.Label(label="Enabled", halign=Gtk.Align.START)
        row.append(label)

        self.switch_enabled = Gtk.Switch()
        self.switch_enabled.set_active(True)
        row.append(self.switch_enabled)
        parent.append(row)

    def _add_trigger_section(self, parent):
        frame = Gtk.Frame(label="Trigger")
        frame.set_margin_bottom(6)
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        vbox.set_margin_start(12)
        vbox.set_margin_end(12)
        vbox.set_margin_top(8)
        vbox.set_margin_bottom(8)

        type_label = Gtk.Label(label="Trigger type", halign=Gtk.Align.START)
        type_label.add_css_class("dim-label")
        vbox.append(type_label)

        self.dropdown_trigger = Gtk.DropDown()
        self.dropdown_trigger.set_model(Gtk.StringList.new(_TRIGGER_TYPES))
        self.dropdown_trigger.set_selected(0)
        vbox.append(self.dropdown_trigger)

        self.box_trigger_config = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL, spacing=6
        )
        vbox.append(self.box_trigger_config)

        frame.set_child(vbox)
        parent.append(frame)

    def _add_actions_section(self, parent):
        frame = Gtk.Frame(label="Actions")
        frame.set_margin_bottom(6)
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        vbox.set_margin_start(12)
        vbox.set_margin_end(12)
        vbox.set_margin_top(8)
        vbox.set_margin_bottom(8)

        self.scrolled_actions = Gtk.ScrolledWindow()
        self.scrolled_actions.set_policy(
            Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC
        )
        self.scrolled_actions.set_vexpand(True)
        self.scrolled_actions.set_min_content_height(120)

        self.listbox_actions = Gtk.ListBox()
        self.listbox_actions.set_selection_mode(Gtk.SelectionMode.NONE)
        self.scrolled_actions.set_child(self.listbox_actions)
        vbox.append(self.scrolled_actions)

        btn_add = Gtk.Button(label="Add Action")
        btn_add.add_css_class("suggested-action")
        vbox.append(btn_add)
        self.btn_add_action = btn_add

        frame.set_child(vbox)
        parent.append(frame)

    def _add_schedule_section(self, parent):
        frame = Gtk.Frame(label="Schedule")
        frame.set_margin_bottom(6)
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        vbox.set_margin_start(12)
        vbox.set_margin_end(12)
        vbox.set_margin_top(8)
        vbox.set_margin_bottom(8)

        cron_label = Gtk.Label(label="Cron expression (e.g. 0 8 * * *)", halign=Gtk.Align.START)
        cron_label.add_css_class("dim-label")
        vbox.append(cron_label)

        self.entry_cron = Gtk.Entry()
        self.entry_cron.set_placeholder_text("0 8 * * *")
        vbox.append(self.entry_cron)

        sched_row = Gtk.Box(spacing=12, orientation=Gtk.Orientation.HORIZONTAL)
        sched_row.set_halign(Gtk.Align.START)
        sched_label = Gtk.Label(label="Schedule enabled", halign=Gtk.Align.START)
        sched_row.append(sched_label)

        self.switch_schedule_enabled = Gtk.Switch()
        self.switch_schedule_enabled.set_active(False)
        sched_row.append(self.switch_schedule_enabled)
        vbox.append(sched_row)

        frame.set_child(vbox)
        parent.append(frame)

    def _add_buttons(self, parent):
        btn_test = Gtk.Button(label="Test")
        btn_test.add_css_class("destructive-action")
        parent.append(btn_test)
        self.btn_test = btn_test

        btn_save = Gtk.Button(label="Save")
        btn_save.add_css_class("suggested-action")
        parent.append(btn_save)
        self.btn_save = btn_save

        btn_cancel = Gtk.Button(label="Cancel")
        parent.append(btn_cancel)
        self.btn_cancel = btn_cancel

    def _connect_signals(self):
        self.dropdown_trigger.connect("notify::selected", self._on_trigger_type_changed)
        self.btn_add_action.connect("clicked", self._on_add_action)
        self.btn_test.connect("clicked", self._on_test)
        self.btn_save.connect("clicked", self._on_save)
        self.btn_cancel.connect("clicked", self._on_cancel)
        self.connect("close-request", self._on_cancel)

    # ------------------------------------------------------------------
    # Trigger type dynamic fields
    # ------------------------------------------------------------------

    def _clear_trigger_config(self):
        child = self.box_trigger_config.get_first_child()
        while child is not None:
            next_child = child.get_next_sibling()
            child.unparent()
            child = next_child
        self._trigger_config_widgets.clear()

    def _on_trigger_type_changed(self, dropdown, _param):
        idx = dropdown.get_selected()
        if idx < 0 or idx >= len(_TRIGGER_TYPES):
            return
        trigger_type = _TRIGGER_TYPES[idx]
        self._clear_trigger_config()

        builders = {
            "bluetooth": self._build_bt_fields,
            "power": self._build_power_fields,
            "schedule": self._build_schedule_fields,
            "network": self._build_network_fields,
            "shell": self._build_shell_fields,
        }
        builder = builders.get(trigger_type)
        if builder:
            builder()

    def _add_config_row(self, label_text, widget):
        row = Gtk.Box(spacing=12, orientation=Gtk.Orientation.HORIZONTAL)
        row.set_halign(Gtk.Align.FILL)
        lbl = Gtk.Label(label=label_text)
        lbl.set_halign(Gtk.Align.START)
        lbl.set_hexpand(False)
        row.append(lbl)
        widget.set_hexpand(True)
        row.append(widget)
        self.box_trigger_config.append(row)
        return row

    def _build_bt_fields(self):
        from src.engine.triggers.bluetooth_devices import get_device_store

        device_names, devices = get_device_store()
        store = Gtk.StringList.new(device_names)
        dd_device = Gtk.DropDown()
        dd_device.set_model(store)
        dd_device.set_hexpand(True)
        dd_device.set_tooltip_text("Select a paired Bluetooth device")
        if not devices:
            dd_device.set_sensitive(False)
        self._add_config_row("Device", dd_device)
        self._trigger_config_widgets["bt_device_dropdown"] = dd_device
        self._trigger_config_widgets["_bt_devices"] = devices

    def _build_power_fields(self):
        store = Gtk.StringList.new(["plugged", "unplugged"])
        dd = Gtk.DropDown()
        dd.set_model(store)
        dd.set_selected(0)
        self._add_config_row("State", dd)
        self._trigger_config_widgets["power_state"] = dd

    def _build_schedule_fields(self):
        w = Gtk.Entry()
        w.set_placeholder_text("0 8 * * *")
        self._add_config_row("Cron", w)
        self._trigger_config_widgets["schedule_cron"] = w

    def _build_network_fields(self):
        w_ssid = Gtk.Entry()
        w_ssid.set_placeholder_text("SSID name")
        self._add_config_row("SSID", w_ssid)
        self._trigger_config_widgets["net_ssid"] = w_ssid

        w_iface = Gtk.Entry()
        w_iface.set_placeholder_text("Interface (optional)")
        self._add_config_row("Interface", w_iface)
        self._trigger_config_widgets["net_interface"] = w_iface

    def _build_shell_fields(self):
        w = Gtk.Entry()
        w.set_placeholder_text("Command to watch")
        self._add_config_row("Command", w)
        self._trigger_config_widgets["shell_cmd"] = w

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def _on_add_action(self, _button):
        row = self._build_action_row("", "", "")
        self.listbox_actions.append(row["outer"])
        row["outer"].show()
        self._action_rows.append(row)

    def _build_action_row(self, action_type, command, args_str):
        """Build a single action row.  Returns a dict with widget refs.
        
        For notify: command=subject, args_str=body
        For launch: command=exec_path
        For shell: command=command_text
        """
        from src.gui.app_picker import get_installed_apps

        outer = Gtk.Box(spacing=8, orientation=Gtk.Orientation.HORIZONTAL)
        outer.set_margin_top(4)
        outer.set_margin_bottom(4)
        outer.add_css_class("action-row")

        type_store = Gtk.StringList.new(_ACTION_TYPES)
        dd_type = Gtk.DropDown()
        dd_type.set_model(type_store)
        dd_type.set_size_request(100, -1)
        if action_type in _ACTION_TYPES:
            dd_type.set_selected(_ACTION_TYPES.index(action_type))
        outer.append(dd_type)

        # Command container — swaps content based on selected action type
        cmd_container = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        cmd_container.set_hexpand(True)

        # --- Shell: single text entry ---
        entry_shell_cmd = Gtk.Entry()
        entry_shell_cmd.set_placeholder_text("command")
        entry_shell_cmd.set_text(command)
        entry_shell_cmd.set_hexpand(True)

        # --- Launch: app dropdown ---
        _all_apps = get_installed_apps()
        _app_names = [a.name for a in _all_apps]
        app_store = Gtk.StringList.new(_app_names)
        dd_app = Gtk.DropDown()
        dd_app.set_model(app_store)
        dd_app.set_size_request(220, -1)
        dd_app.set_hexpand(True)
        dd_app.set_tooltip_text("Select an app to launch")

        # If command matches an app exec, pre-select it
        selected_app_idx = -1
        for i, app in enumerate(_all_apps):
            if app.exec_cmd in command or command in app.exec_cmd:
                selected_app_idx = i
                break
        if selected_app_idx >= 0:
            dd_app.set_selected(selected_app_idx)

        # --- Notify: Subject + Body entries ---
        notify_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        notify_box.set_hexpand(True)

        entry_notify_subject = Gtk.Entry()
        entry_notify_subject.set_placeholder_text("Notification subject")

        entry_notify_body = Gtk.Entry()
        entry_notify_body.set_placeholder_text("Notification body")
        entry_notify_body.set_hexpand(True)

        # Pre-populate fields if loading an existing notify action
        if action_type == "notify":
            entry_notify_subject.set_text(command)
            entry_notify_body.set_text(args_str)

        notify_box.append(entry_notify_subject)
        notify_box.append(entry_notify_body)

        # --- Media: MPRIS player + action picker ---
        media_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=3)
        media_box.set_hexpand(True)

        # Player + action row
        media_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        media_row.set_hexpand(True)

        import subprocess as _sp
        # Known MPRIS player names (always included even if not currently running)
        _known_mpris = [
            "spotify", "vlc", "firefox", "chromium", "mpv",
            "audacious", "clementine", "rhythmbox", "amarok",
            "plasma-browser-integration", "strawberry", "tauon",
        ]
        # Get currently active MPRIS players
        _mp_players = []
        try:
            _players_raw = _sp.run(
                ["playerctl", "-l"], capture_output=True, text=True, timeout=5
            ).stdout.strip().split("\n")
            _active = [p.strip() for p in _players_raw if p.strip()]
            _mp_players = list(_active)  # active first
            # Add known players that aren't already in the list
            for known in _known_mpris:
                if known not in _mp_players:
                    _mp_players.append(known)
        except (FileNotFoundError, OSError, _sp.TimeoutExpired):
            _mp_players = list(_known_mpris)

        # Add 'Custom...' option and a custom name entry
        _mp_players.append("Custom...")

        media_player_store = Gtk.StringList.new(_mp_players)
        dd_media_player = Gtk.DropDown()
        dd_media_player.set_model(media_player_store)
        dd_media_player.set_hexpand(True)
        dd_media_player.set_tooltip_text("Select a media player")
        media_row.append(dd_media_player)

        # Custom player name entry (hidden by default)
        entry_custom_player = Gtk.Entry()
        entry_custom_player.set_placeholder_text("Custom player name (e.g. spotify)")
        entry_custom_player.set_hexpand(True)
        entry_custom_player.set_visible(False)
        media_box.append(entry_custom_player)

        # Toggle custom entry visibility
        def _on_media_player_changed(*_args):
            p_idx = dd_media_player.get_selected()
            is_custom = _mp_players[p_idx] == "Custom..." if 0 <= p_idx < len(_mp_players) else False
            entry_custom_player.set_visible(is_custom)
        dd_media_player.connect("notify::selected", _on_media_player_changed)

        _MEDIA_ACTIONS = ["Play", "Pause", "Play-Pause", "Next", "Previous", "Stop", "Open URI"]
        media_action_store = Gtk.StringList.new(_MEDIA_ACTIONS)
        dd_media_action = Gtk.DropDown()
        dd_media_action.set_model(media_action_store)
        dd_media_action.set_selected(0)
        dd_media_action.set_size_request(120, -1)
        media_row.append(dd_media_action)
        media_box.append(media_row)

        # URI entry (only visible when action is "Open URI")
        entry_media_uri = Gtk.Entry()
        entry_media_uri.set_placeholder_text("spotify:playlist:37i9dQZF1DXcBWIGoYBM5M")
        entry_media_uri.set_hexpand(True)
        entry_media_uri.set_visible(False)
        media_box.append(entry_media_uri)

        def _on_media_action_changed(*_args):
            act_idx = dd_media_action.get_selected()
            act = _MEDIA_ACTIONS[act_idx] if 0 <= act_idx < len(_MEDIA_ACTIONS) else ""
            entry_media_uri.set_visible(act == "Open URI")

        dd_media_action.connect("notify::selected", _on_media_action_changed)

        # Pre-populate media fields if loading
        if action_type == "media":
            parts = command.split("|", 1)
            if len(parts) == 2:
                player, media_act = parts
                if player in _mp_players:
                    dd_media_player.set_selected(_mp_players.index(player))
                else:
                    # Unknown player — use "Custom..." and fill the entry
                    custom_idx = _mp_players.index("Custom...")
                    dd_media_player.set_selected(custom_idx)
                    entry_custom_player.set_text(player)
                    entry_custom_player.set_visible(True)
                if media_act in _MEDIA_ACTIONS:
                    dd_media_action.set_selected(_MEDIA_ACTIONS.index(media_act))
                    if media_act == "Open URI" and args_str:
                        entry_media_uri.set_text(args_str)
                        entry_media_uri.set_visible(True)

        def _on_action_type_changed(*_args):
            """Swap the command container content based on action type."""
            t_idx = dd_type.get_selected()
            t = _ACTION_TYPES[t_idx] if 0 <= t_idx < len(_ACTION_TYPES) else ""

            # Remove any existing child
            existing = cmd_container.get_first_child()
            while existing is not None:
                nxt = existing.get_next_sibling()
                cmd_container.remove(existing)
                existing = nxt

            if t == "launch":
                cmd_container.append(dd_app)
            elif t == "notify":
                cmd_container.append(notify_box)
            elif t == "media":
                cmd_container.append(media_box)
            else:
                cmd_container.append(entry_shell_cmd)
            cmd_container.show()

        dd_type.connect("notify::selected", _on_action_type_changed)

        # Initialize the right view
        _on_action_type_changed()

        outer.append(cmd_container)

        btn_remove = Gtk.Button()
        btn_remove.set_icon_name("list-remove-symbolic")
        btn_remove.add_css_class("destructive-action")
        btn_remove.set_tooltip_text("Remove action")
        outer.append(btn_remove)

        row_data = {
            "outer": outer,
            "type_dropdown": dd_type,
            "cmd_container": cmd_container,
            "remove_button": btn_remove,
            # Shell
            "shell_entry": entry_shell_cmd,
            # Launch
            "app_dropdown": dd_app,
            "app_list": _all_apps,
            # Notify
            "notify_subject_entry": entry_notify_subject,
            "notify_body_entry": entry_notify_body,
            # Media
            "media_player_dropdown": dd_media_player,
            "media_action_dropdown": dd_media_action,
            "media_uri_entry": entry_media_uri,
            "media_players": _mp_players,
            "media_custom_entry": entry_custom_player,
        }

        def _on_remove(btn):
            for i, r in enumerate(self._action_rows):
                if r["outer"] is outer:
                    del self._action_rows[i]
                    break
            outer.unparent()

        btn_remove.connect("clicked", _on_remove)

        return row_data

    # ------------------------------------------------------------------
    # Load / save
    # ------------------------------------------------------------------

    def _load_workflow(self, workflow_id):
        """Populate all fields from an existing workflow in the DB."""
        self._loading = True
        try:
            conn = self._open_conn()
            try:
                wf = get_workflow(conn, workflow_id)
                if wf is None:
                    return

                self.set_title("Edit Workflow")
                self.entry_name.set_text(wf.name or "")
                self.switch_enabled.set_active(wf.enabled)

                # Trigger
                triggers = get_triggers_for_workflow(conn, workflow_id)
                trig = triggers[0] if triggers else None
                if trig and trig.type in _TRIGGER_TYPES:
                    idx = _TRIGGER_TYPES.index(trig.type)
                    # Block signal while setting the dropdown
                    self.dropdown_trigger.handler_block_by_func(
                        self._on_trigger_type_changed
                    )
                    self.dropdown_trigger.set_selected(idx)
                    self.dropdown_trigger.handler_unblock_by_func(
                        self._on_trigger_type_changed
                    )
                    # Manually build the config fields
                    self._on_trigger_type_changed(self.dropdown_trigger, None)
                    # Populate the fields with existing values
                    _populate_trigger_fields(trig.type, self._trigger_config_widgets, trig.config)

                # Actions
                actions = get_actions_for_workflow(conn, workflow_id)
                for act in actions:
                    args_str = ", ".join(act.args) if isinstance(act.args, list) else str(act.args)
                    row = self._build_action_row(act.type, act.command, args_str)
                    self.listbox_actions.append(row["outer"])
                    row["outer"].show()
                    self._action_rows.append(row)

                # Schedule
                schedule_trigger = None
                for t in triggers:
                    if t.type == "schedule":
                        schedule_trigger = t
                        break

                if schedule_trigger:
                    config = schedule_trigger.config or {}
                    self.entry_cron.set_text(config.get("cron_expr", ""))
                    self.switch_schedule_enabled.set_active(schedule_trigger.enabled)
                else:
                    self.switch_schedule_enabled.set_active(False)

            finally:
                conn.close()
        finally:
            self._loading = False

    def _open_conn(self):
        """Return a sqlite3 connection for the DB."""
        import sqlite3
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        init_db(conn)
        return conn

    def _collect_form_data(self):
        """Read all widget values and return a dict."""
        name = self.entry_name.get_text().strip()
        enabled = self.switch_enabled.get_active()

        trig_idx = self.dropdown_trigger.get_selected()
        trigger_type = (
            _TRIGGER_TYPES[trig_idx]
            if 0 <= trig_idx < len(_TRIGGER_TYPES)
            else ""
        )
        trigger_config = _build_trigger_config(
            trigger_type, self._trigger_config_widgets
        )

        actions = []
        for row in self._action_rows:
            act_type_idx = row["type_dropdown"].get_selected()
            act_type = (
                _ACTION_TYPES[act_type_idx]
                if 0 <= act_type_idx < len(_ACTION_TYPES)
                else ""
            )
            if act_type == "launch":
                app_idx = row["app_dropdown"].get_selected()
                if 0 <= app_idx < len(row["app_list"]):
                    command = row["app_list"][app_idx].exec_cmd
                else:
                    command = ""
                args = []
            elif act_type == "notify":
                command = row["notify_subject_entry"].get_text().strip()
                body = row["notify_body_entry"].get_text().strip()
                args = [body] if body else []
            elif act_type == "media":
                p_idx = row["media_player_dropdown"].get_selected()
                a_idx = row["media_action_dropdown"].get_selected()
                players = row["media_players"]
                if 0 <= p_idx < len(players):
                    player = players[p_idx]
                    if player == "Custom...":
                        player = row["media_custom_entry"].get_text().strip()
                        if not player:
                            player = "spotify"
                else:
                    player = "spotify"
                action = _MEDIA_ACTIONS[a_idx] if 0 <= a_idx < len(_MEDIA_ACTIONS) else "Play"
                command = f"{player}|{action}"
                uri = row["media_uri_entry"].get_text().strip()
                args = [uri] if uri else []
            else:
                command = row["shell_entry"].get_text().strip()
                args = []
            actions.append(
                {"type": act_type, "command": command, "args": args}
            )

        schedule_cron = self.entry_cron.get_text().strip()
        schedule_enabled = self.switch_schedule_enabled.get_active()

        return {
            "name": name,
            "enabled": enabled,
            "trigger_type": trigger_type,
            "trigger_config": trigger_config,
            "actions": actions,
            "schedule_cron": schedule_cron,
            "schedule_enabled": schedule_enabled,
        }

    def _on_save(self, _button):
        data = self._collect_form_data()
        if not data["name"]:
            self._show_error("Workflow name is required.")
            return

        conn = self._open_conn()
        try:
            wf = Workflow(
                name=data["name"],
                enabled=data["enabled"],
                id=self.workflow_id,
            )
            wf.save(conn)
            new_id = wf.id

            # Clean slate for editing
            if self.workflow_id is not None:
                conn.execute(
                    "DELETE FROM triggers WHERE workflow_id=?",
                    (self.workflow_id,),
                )
                conn.execute(
                    "DELETE FROM actions WHERE workflow_id=?",
                    (self.workflow_id,),
                )
                conn.execute(
                    "DELETE FROM schedules WHERE workflow_id=?",
                    (self.workflow_id,),
                )

            # Insert trigger
            trig = Trigger(
                workflow_id=new_id,
                type=data["trigger_type"],
                config=data["trigger_config"],
                enabled=True,
            )
            trig.save(conn)

            # Insert actions
            for act_data in data["actions"]:
                act = Action(
                    workflow_id=new_id,
                    type=act_data["type"],
                    command=act_data["command"],
                    args=act_data["args"],
                    enabled=True,
                )
                act.save(conn)

            # Insert schedule if configured
            if data["schedule_cron"] and data["schedule_enabled"]:
                conn.execute(
                    "INSERT INTO schedules (workflow_id, cron_expr, next_run) VALUES (?, ?, NULL)",
                    (new_id, data["schedule_cron"]),
                )
                conn.commit()

            self.workflow_id = new_id
            self.emit("workflow-saved", new_id)
            self.destroy()

        except Exception as e:
            self._show_error(f"Failed to save workflow: {e}")
        finally:
            conn.close()

    def _on_cancel(self, _button):
        self.destroy()

    def _on_test(self, _button):
        """Run all actions once and show the results in a popup."""
        data = self._collect_form_data()
        if not data["actions"]:
            self._show_info("Test Results", "No actions to test.")
            return

        executor = ActionExecutor()
        results = []

        for act_data in data["actions"]:
            class _FakeAction:
                pass

            fake = _FakeAction()
            fake.type = act_data["type"]
            fake.command = act_data["command"]
            fake.args = act_data["args"]
            fake.enabled = True
            result = executor.execute(fake)
            status = "OK" if result["success"] else "FAIL"
            results.append(f"{act_data['type']}: {act_data['command']} \u2192 {status}")

        summary = "\n".join(results)
        self._show_info("Test Results", summary)

    def _show_error(self, message):
        dlg = Gtk.MessageDialog(
            transient_for=self,
            modal=True,
            text=message,
            message_type=Gtk.MessageType.ERROR,
            buttons=Gtk.ButtonsType.OK,
        )
        dlg.connect("response", lambda d, _r: d.destroy())
        dlg.present()

    def _show_info(self, title, message):
        dlg = Gtk.MessageDialog(
            transient_for=self,
            modal=True,
            text=f"{title}\n\n{message}",
            message_type=Gtk.MessageType.INFO,
            buttons=Gtk.ButtonsType.OK,
        )
        dlg.connect("response", lambda d, _r: d.destroy())
        dlg.present()
