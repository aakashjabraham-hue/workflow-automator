"""Custom widgets for the Workflow Automator GTK4 GUI."""

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk


class WorkflowRow(Gtk.ListBoxRow):
    """A single row in the workflow list showing name, enabled toggle,
    edit button, and delete button."""

    def __init__(
        self,
        workflow,
        on_toggle=None,
        on_edit=None,
        on_delete=None,
    ):
        super().__init__()
        self.workflow = workflow

        # Horizontal layout container
        box = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL, spacing=6
        )
        box.set_margin_start(6)
        box.set_margin_end(6)
        box.set_margin_top(4)
        box.set_margin_bottom(4)

        # Workflow name label
        self.name_label = Gtk.Label(label=workflow.name)
        self.name_label.set_halign(Gtk.Align.START)
        self.name_label.set_hexpand(True)
        self.name_label.add_css_class("title-4")

        # Enabled toggle switch
        self.switch = Gtk.Switch()
        self.switch.set_active(workflow.enabled)
        self.switch.set_tooltip_text("Enable / disable workflow")
        self.switch.connect("notify::active", self._on_toggle)

        # Edit button
        self.edit_button = Gtk.Button()
        self.edit_button.set_icon_name("document-edit-symbolic")
        self.edit_button.set_tooltip_text("Edit workflow")
        self.edit_button.add_css_class("flat")
        self.edit_button.connect("clicked", self._on_edit)

        # Delete button
        self.delete_button = Gtk.Button()
        self.delete_button.set_icon_name("user-trash-symbolic")
        self.delete_button.set_tooltip_text("Delete workflow")
        self.delete_button.add_css_class("flat")
        self.delete_button.add_css_class("destructive-action")
        self.delete_button.connect("clicked", self._on_delete)

        box.append(self.name_label)
        box.append(self.switch)
        box.append(self.edit_button)
        box.append(self.delete_button)

        self.set_child(box)

        # Store callbacks
        self._on_toggle_cb = on_toggle
        self._on_edit_cb = on_edit
        self._on_delete_cb = on_delete

    # ------------------------------------------------------------------
    # Signal handlers
    # ------------------------------------------------------------------

    def _on_toggle(self, switch, _param) -> None:
        """Called when the enabled switch is toggled by the user."""
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
