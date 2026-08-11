"""Custom widgets for the Workflow Automator GTK4 GUI.

The card layout mirrors the web dashboard (src/dashboard_ui.py) 1:1:
trigger icon + name on top, pill chips for trigger/action summary,
switch + edit + delete on the foot. Same emoji icons, same structure —
the two UIs share one visual identity.
"""

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, Pango


# Same emoji as the web dashboard.
_TRIGGER_ICONS = {
    "bluetooth": "🎧",
    "power": "🔌",
    "schedule": "🕐",
    "network": "🌐",
    "shell": "⌨️",
}

_ACTION_ICONS = {
    "shell": "🖥️",
    "launch": "🚀",
    "notify": "🔔",
    "media": "🎵",
}

_DEFAULT_ICON = "⚡"


class WorkflowRow(Gtk.ListBoxRow):
    """A single workflow card: icon + name, trigger/action chips, toggle,
    edit and delete buttons."""

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

        # Card container (vertical, like the web .card)
        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        card.add_css_class("card")
        self.card = card
        self._sync_disabled_state()

        # ── Top: trigger icon + name ─────────────────────────────
        top = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        top.set_hexpand(True)

        self.icon_label = Gtk.Label(label=_DEFAULT_ICON)
        self.icon_label.add_css_class("workflow-icon")
        top.append(self.icon_label)

        self.name_label = Gtk.Label(label=workflow.name)
        self.name_label.set_halign(Gtk.Align.START)
        self.name_label.set_hexpand(True)
        self.name_label.set_ellipsize(Pango.EllipsizeMode.END)
        self.name_label.add_css_class("workflow-name")
        top.append(self.name_label)
        card.append(top)

        # ── Chips: trigger + action count ────────────────────────
        chips = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        chips.set_halign(Gtk.Align.START)

        self.trigger_chip = Gtk.Label(label="no trigger")
        self.trigger_chip.add_css_class("chip")
        self.trigger_chip.add_css_class("chip-off")
        chips.append(self.trigger_chip)

        self.actions_chip = Gtk.Label(label="0 actions")
        self.actions_chip.add_css_class("chip")
        self.actions_chip.add_css_class("chip-off")
        chips.append(self.actions_chip)

        card.append(chips)

        # ── Foot: switch + spacer + edit + delete ─────────────────
        foot = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)

        self.switch = Gtk.Switch()
        self.switch.set_active(workflow.enabled)
        self.switch.set_tooltip_text("Enable / disable workflow")
        self.switch.connect("notify::active", self._on_toggle)
        foot.append(self.switch)

        spacer = Gtk.Box()
        spacer.set_hexpand(True)
        foot.append(spacer)

        self.edit_button = Gtk.Button()
        self.edit_button.set_icon_name("document-edit-symbolic")
        self.edit_button.set_tooltip_text("Edit workflow")
        self.edit_button.add_css_class("flat")
        self.edit_button.connect("clicked", self._on_edit)
        foot.append(self.edit_button)

        self.delete_button = Gtk.Button()
        self.delete_button.set_icon_name("user-trash-symbolic")
        self.delete_button.set_tooltip_text("Delete workflow")
        self.delete_button.add_css_class("flat")
        self.delete_button.add_css_class("destructive-action")
        self.delete_button.connect("clicked", self._on_delete)
        foot.append(self.delete_button)

        card.append(foot)

        self.set_child(card)

        # Store callbacks
        self._on_toggle_cb = on_toggle
        self._on_edit_cb = on_edit
        self._on_delete_cb = on_delete

    # ------------------------------------------------------------------
    # Public helpers
    # ------------------------------------------------------------------

    def set_trigger_icon(self, trigger_type: str) -> None:
        """Set the emoji shown next to the workflow name."""
        self.icon_label.set_label(_TRIGGER_ICONS.get(trigger_type, _DEFAULT_ICON))

    def set_trigger_label(self, text: str) -> None:
        """Set the trigger chip text (e.g. 'When Bluetooth connects')."""
        self.trigger_chip.set_label(f"{_TRIGGER_ICONS.get(self.trigger_type, '')} {text}".strip())
        self.trigger_chip.remove_css_class("chip-off")

    @property
    def trigger_type(self) -> str:
        return getattr(self.workflow, "_trigger_type", "")

    def set_trigger_type(self, trigger_type: str) -> None:
        """Remember the trigger type so the chip can show its icon."""
        self.workflow._trigger_type = trigger_type
        self.icon_label.set_label(_TRIGGER_ICONS.get(trigger_type, _DEFAULT_ICON))

    def set_actions_count(self, count: int) -> None:
        """Set the 'N actions' chip."""
        label = "1 action" if count == 1 else f"{count} actions"
        self.actions_chip.set_label(label)

    def set_enabled_state(self, enabled: bool) -> None:
        """Update the UI when the workflow is toggled."""
        self.switch.set_active(enabled)
        self._sync_disabled_state()

    def _sync_disabled_state(self) -> None:
        if self.workflow.enabled:
            self.card.remove_css_class("disabled")
        else:
            self.card.add_css_class("disabled")

    # ------------------------------------------------------------------
    # Signal handlers
    # ------------------------------------------------------------------

    def _on_toggle(self, switch, _param) -> None:
        """Called when the enabled switch is toggled by the user."""
        self.workflow.enabled = switch.get_active()
        self._sync_disabled_state()
        if self._on_toggle_cb is not None:
            self._on_toggle_cb(self.workflow, switch.get_active())

    def _on_edit(self, _button) -> None:
        """Called when the edit button is clicked."""
        if self._on_edit_cb is not None:
            self._on_edit_cb(self.workflow)

    def _on_delete(self, _button) -> None:
        """Called when the delete button is clicked."""
        if self._on_delete_cb is not None:
            self._on_delete_cb(self.workflow)
