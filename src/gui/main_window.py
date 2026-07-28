"""MainWindow — the primary application window for the Workflow Automator.

Provides a list workflow overview and opens WorkflowEditorDialog for
creating/editing workflows.  After a save the workflow list is refreshed
automatically via the editor's workflow-saved signal.
"""

import gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, GObject

from src.gui.workflow_editor import WorkflowEditorDialog


class MainWindow(Gtk.ApplicationWindow):
    """Main window showing all workflows and providing CRUD via the editor."""

    def __init__(self, app, db_path):
        super().__init__(application=app)
        self.set_title("Workflow Automator")
        self.set_default_size(600, 480)
        self.db_path = db_path

        self._build_ui()
        self._refresh_workflow_list()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _build_ui(self):
        header = Gtk.HeaderBar()
        header.set_title("Workflow Automator")
        header.set_show_title_buttons(True)

        btn_new = Gtk.Button(label="New Workflow")
        btn_new.add_css_class("suggested-action")
        header.pack_start(btn_new)
        self.btn_new = btn_new
        btn_new.connect("clicked", self._on_new_workflow)

        self.set_titlebar(header)

        # Main content — scrolled list of workflows
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_vexpand(True)

        self.listbox_workflows = Gtk.ListBox()
        self.listbox_workflows.set_selection_mode(Gtk.SelectionMode.SINGLE)
        scrolled.set_child(self.listbox_workflows)

        # Buttons bar at the bottom
        bar = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=8,
            margin_start=12,
            margin_end=12,
            margin_top=8,
            margin_bottom=12,
        )

        btn_edit = Gtk.Button(label="Edit")
        bar.append(btn_edit)
        self.btn_edit = btn_edit
        btn_edit.connect("clicked", self._on_edit_workflow)

        btn_delete = Gtk.Button(label="Delete")
        btn_delete.add_css_class("destructive-action")
        bar.append(btn_delete)
        self.btn_delete = btn_delete
        btn_delete.connect("clicked", self._on_delete_workflow)

        # Status label
        self.label_status = Gtk.Label(label="")
        self.label_status.set_halign(Gtk.Align.START)
        bar.append(self.label_status)

        # Main vertical box
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        vbox.append(scrolled)
        vbox.append(bar)
        self.set_child(vbox)

        # Wire up editor signal
        self.connect("workflow-saved", self._on_workflow_saved)

    # ------------------------------------------------------------------
    # Workflow list
    # ------------------------------------------------------------------

    def _refresh_workflow_list(self):
        """Reload workflows from the DB and repopulate the ListBox."""
        # Clear existing rows
        for row in self.listbox_workflows.get_children():
            row.unparent()

        from src.db import get_db, init_db
        from src.models.workflow import get_all_workflows

        conn = get_db(self.db_path)
        try:
            workflows = get_all_workflows(conn)
        finally:
            conn.close()

        for wf in workflows:
            label = Gtk.Label(label=wf.name)
            label.set_halign(Gtk.Align.START)
            row = Gtk.ListBoxRow()
            row.set_child(label)
            row._workflow_id = wf.id  # type: ignore[attr-defined]
            self.listbox_workflows.append(row)

        count = len(workflows)
        self.label_status.set_text(f"{count} workflow{'s' if count != 1 else ''}")

    # ------------------------------------------------------------------
    # Editor integration
    # ------------------------------------------------------------------

    def _open_editor(self, workflow_id=None):
        """Open WorkflowEditorDialog and attach a save callback."""
        dlg = WorkflowEditorDialog(
            parent_window=self,
            db_path=self.db_path,
            workflow_id=workflow_id,
        )
        dlg.connect("workflow-saved", self._on_editor_saved)
        dlg.present()

    def _on_editor_saved(self, _dialog, workflow_id):
        """Refresh the list when the editor saves a workflow."""
        self._refresh_workflow_list()

    def _on_workflow_saved(self, _widget, workflow_id):
        """Signal handler for workflow-saved from anywhere in the app."""
        self._refresh_workflow_list()

    # ------------------------------------------------------------------
    # Button callbacks
    # ------------------------------------------------------------------

    def _on_new_workflow(self, _button):
        self._open_editor(workflow_id=None)

    def _on_edit_workflow(self, _button):
        selected = self.listbox_workflows.get_selected_row()
        if selected is None:
            self._show_status("Select a workflow to edit.")
            return
        wf_id = getattr(selected, "_workflow_id", None)
        if wf_id is None:
            return
        self._open_editor(workflow_id=wf_id)

    def _on_delete_workflow(self, _button):
        selected = self.listbox_workflows.get_selected_row()
        if selected is None:
            self._show_status("Select a workflow to delete.")
            return
        wf_id = getattr(selected, "_workflow_id", None)
        if wf_id is None:
            return

        from src.db import get_db
        from src.models.workflow import get_workflow

        conn = get_db(self.db_path)
        try:
            wf = get_workflow(conn, wf_id)
            if wf is None:
                return
            wf.delete(conn)
        finally:
            conn.close()

        self._refresh_workflow_list()

    def _show_status(self, message):
        self.label_status.set_text(message)
