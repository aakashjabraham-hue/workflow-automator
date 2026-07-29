"""Custom widgets for the Workflow Automator GTK4 GUI."""

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk


_TRIGGER_ICONS = {
    "bluetooth": "󰂯",  # Bluetooth symbol
    "power": "󰚥",      # Plug
    "schedule": "󰥔",   # Clock
    "network": "󰤨",    # WiFi
    "shell": ">_",      # Terminal
}


class WorkflowRow(Gtk.ListBoxRow):
    """A single row in the workflow list showing name, trigger type icon,
    status dot, enabled toggle, edit button, and delete button."""

    def __init__(
        self,
        workflow,
        on_toggle=None,
        on_edit=None,
        on_delete=None,
    ):
        super().__init__()
        self.workflow = workflow
        self.add_css_class("workflow-row")

        # Card container
        card = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL, spacing=8
        )
        card.add_css_class("card")
        card.set_margin_start(8)
        card.set_margin_end(8)
        card.set_margin_top(3)
        card.set_margin_bottom(3)

        # Status dot (enabled/disabled indicator)
        self.status_dot = Gtk.Box()
        self.status_dot.set_size_request(10, 10)
        self.status_dot.add_css_class("status-dot")
        if workflow.enabled:
            self.status_dot.add_css_class("enabled")
        else:
            self.status_dot.add_css_class("disabled")
        card.append(self.status_dot)

        # Trigger type icon
        icon_label = Gtk.Label(label=_TRIGGER_ICONS.get("bluetooth", ""))
        icon_label.add_css_class("workflow-icon")
        card.append(icon_label)

        # Name + trigger label (vertical)
        text_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        text_box.set_hexpand(True)

        self.name_label = Gtk.Label(label=workflow.name)
        self.name_label.set_halign(Gtk.Align.START)
        self.name_label.add_css_class("workflow-name")
        text_box.append(self.name_label)

        self.trigger_label = Gtk.Label(label="")
        self.trigger_label.set_halign(Gtk.Align.START)
        self.trigger_label.add_css_class("workflow-trigger-label")
        text_box.append(self.trigger_label)

        card.append(text_box)

        # Enabled toggle switch
        self.switch = Gtk.Switch()
        self.switch.set_active(workflow.enabled)
        self.switch.set_tooltip_text("Enable / disable workflow")
        self.switch.connect("notify::active", self._on_toggle)
        card.append(self.switch)

        # Edit button
        self.edit_button = Gtk.Button()
        self.edit_button.set_icon_name("document-edit-symbolic")
        self.edit_button.set_tooltip_text("Edit workflow")
        self.edit_button.add_css_class("flat")
        self.edit_button.connect("clicked", self._on_edit)
        card.append(self.edit_button)

        # Delete button
        self.delete_button = Gtk.Button()
        self.delete_button.set_icon_name("user-trash-symbolic")
        self.delete_button.set_tooltip_text("Delete workflow")
        self.delete_button.add_css_class("flat")
        self.delete_button.add_css_class("destructive-action")
        self.delete_button.connect("clicked", self._on_delete)
        card.append(self.delete_button)

        self.set_child(card)

        # Store callbacks
        self._on_toggle_cb = on_toggle
        self._on_edit_cb = on_edit
        self._on_delete_cb = on_delete

    # ------------------------------------------------------------------
    # Public helpers
    # ------------------------------------------------------------------

    def set_trigger_icon(self, trigger_type: str) -> None:
        """Set the trigger type icon shown in the row."""
        icon_text = _TRIGGER_ICONS.get(trigger_type, "")
        icon_label = self.get_child().get_first_child().get_next_sibling()
        if icon_label and hasattr(icon_label, "set_label"):
            icon_label.set_label(icon_text)

    def set_trigger_label(self, text: str) -> None:
        """Set the subtitle text (e.g. 'When power unplugged')."""
        self.trigger_label.set_label(text)

    def set_enabled_state(self, enabled: bool) -> None:
        """Update the UI when the workflow is toggled."""
        self.switch.set_active(enabled)
        self.status_dot.remove_css_class("enabled")
        self.status_dot.remove_css_class("disabled")
        if enabled:
            self.status_dot.add_css_class("enabled")
        else:
            self.status_dot.add_css_class("disabled")

    # ------------------------------------------------------------------
    # Signal handlers
    # ------------------------------------------------------------------

    def _on_toggle(self, switch, _param) -> None:
        """Called when the enabled switch is toggled by the user."""
        active = switch.get_active()
        self.status_dot.remove_css_class("enabled")
        self.status_dot.remove_css_class("disabled")
        self.status_dot.add_css_class("enabled" if active else "disabled")
        if self._on_toggle_cb is not None:
            self._on_toggle_cb(self.workflow, active)

    def _on_edit(self, _button) -> None:
        """Called when the edit button is clicked."""
        if self._on_edit_cb is not None:
            self._on_edit_cb(self.workflow)

    def _on_delete(self, _button) -> None:
        """Called when the delete button is clicked."""
        if self._on_delete_cb is not None:
            self._on_delete_cb(self.workflow)
