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
_ACTION_TYPES = ["shell", "launch", "notify"]


def _build_trigger_config(trigger_type, widgets):
    """Return a config dict based on the currently-visible config widgets."""
    if trigger_type == "bluetooth":
        return {
            "device_name": widgets.get("bt_device", "").get_text().strip(),
            "mac_pattern": widgets.get("bt_mac", "").get_text().strip(),
        }
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
        if "bt_device" in widgets:
            widgets["bt_device"].set_text(config.get("device_name", ""))
        if "bt_mac" in widgets:
            widgets["bt_mac"].set_text(config.get("mac_pattern", ""))
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

        self._build_ui()
        self._connect_signals()

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
        for child in self.box_trigger_config.get_children():
            child.unparent()
        self._trigger_config_widgets.clear()

    def _on_trigger_type_changed(self, dropdown, _param):
        if self._loading:
            return
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
        w_device = Gtk.Entry()
        w_device.set_placeholder_text("Device name or MAC pattern")
        self._add_config_row("Device", w_device)
        self._trigger_config_widgets["bt_device"] = w_device

        w_mac = Gtk.Entry()
        w_mac.set_placeholder_text("MAC pattern (optional)")
        self._add_config_row("MAC", w_mac)
        self._trigger_config_widgets["bt_mac"] = w_mac

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
        """Build a single action row.  Returns a dict with widget refs."""
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

        # Command container — holds either a text entry or an app dropdown
        cmd_container = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        cmd_container.set_hexpand(True)

        # Text entry for shell/notify commands
        entry_cmd = Gtk.Entry()
        entry_cmd.set_placeholder_text("command")
        entry_cmd.set_text(command)
        entry_cmd.set_hexpand(True)

        # App dropdown for launch type
        _all_apps = get_installed_apps()
        _app_names = [a.name for a in _all_apps]
        app_store = Gtk.StringList.new(_app_names)
        dd_app = Gtk.DropDown()
        dd_app.set_model(app_store)
        dd_app.set_size_request(220, -1)
        dd_app.set_hexpand(True)
        # Auto-completion entry overlay
        dd_app.set_tooltip_text("Select an app to launch")

        # If command matches an app exec, pre-select it
        selected_app_idx = -1
        for i, app in enumerate(_all_apps):
            if app.exec_cmd in command or command in app.exec_cmd:
                selected_app_idx = i
                break
        if selected_app_idx >= 0:
            dd_app.set_selected(selected_app_idx)

        def _on_action_type_changed(*_args):
            """Swap between text entry and app dropdown based on action type."""
            t_idx = dd_type.get_selected()
            t = _ACTION_TYPES[t_idx] if 0 <= t_idx < len(_ACTION_TYPES) else ""

            for child in cmd_container.get_children():
                cmd_container.remove(child)

            if t == "launch":
                cmd_container.append(dd_app)
            else:
                cmd_container.append(entry_cmd)
            cmd_container.show()

        dd_type.connect("notify::selected", _on_action_type_changed)

        # Initialize the right view
        _on_action_type_changed()

        outer.append(cmd_container)

        entry_args = Gtk.Entry()
        entry_args.set_placeholder_text("args (comma-separated)")
        entry_args.set_text(args_str)
        entry_args.set_hexpand(True)
        outer.append(entry_args)

        btn_remove = Gtk.Button()
        btn_remove.set_icon_name("list-remove-symbolic")
        btn_remove.add_css_class("destructive-action")
        btn_remove.set_tooltip_text("Remove action")
        outer.append(btn_remove)

        row_data = {
            "outer": outer,
            "type_dropdown": dd_type,
            "command_entry": entry_cmd,
            "args_entry": entry_args,
            "remove_button": btn_remove,
            "cmd_container": cmd_container,
            "app_dropdown": dd_app,
            "app_list": _all_apps,
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
            # For "launch" type, get command from the app dropdown
            if act_type == "launch":
                app_idx = row["app_dropdown"].get_selected()
                if 0 <= app_idx < len(row["app_list"]):
                    command = row["app_list"][app_idx].exec_cmd
                else:
                    command = row["command_entry"].get_text().strip()
            else:
                command = row["command_entry"].get_text().strip()
            args_raw = row["args_entry"].get_text().strip()
            args = [p.strip() for p in args_raw.split(",")] if args_raw else []
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
            detail=None,
            message_type=Gtk.MessageType.ERROR,
            buttons=Gtk.ButtonsType.OK,
        )
        dlg.connect("response", lambda d, _r: d.destroy())
        dlg.present()

    def _show_info(self, title, message):
        dlg = Gtk.MessageDialog(
            transient_for=self,
            modal=True,
            text=title,
            detail=message,
            message_type=Gtk.MessageType.INFO,
            buttons=Gtk.ButtonsType.OK,
        )
        dlg.connect("response", lambda d, _r: d.destroy())
        dlg.present()
