"""MainWindow — the primary application window for Workflow Automator."""

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk

from src.db import get_db, init_db
from src.gui.widgets import WorkflowRow
from src.models.workflow import Workflow, get_all_workflows


class MainWindow(Gtk.ApplicationWindow):
    """Main application window showing the workflow list."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.set_title("Workflow Automator")
        self.set_default_size(500, 400)
        self.set_min_content_width(500)
        self.set_min_content_height(400)

        # Database path — share with the daemon (use a file-based DB)
        import os
        db_dir = os.path.expanduser("~/.workflow-automator")
        os.makedirs(db_dir, exist_ok=True)
        self.db_path = os.path.join(db_dir, "workflows.db")
        self._conn = None

        self._build_header_bar()
        self._build_body()
        self._refresh_workflows()

    # ------------------------------------------------------------------
    # Database helpers
    # ------------------------------------------------------------------

    @property
    def conn(self):
        """Lazily create a database connection."""
        if self._conn is None:
            self._conn = get_db(self.db_path)
            init_db(self._conn)
        return self._conn

    # ------------------------------------------------------------------
    # Header bar
    # ------------------------------------------------------------------

    def _build_header_bar(self) -> None:
        """Create the header bar with title and add button."""
        header = Gtk.HeaderBar()
        header.set_title("Workflow Automator")
        header.set_show_title_buttons(True)

        # Add workflow button
        add_btn = Gtk.Button()
        add_btn.set_icon_name("list-add-symbolic")
        add_btn.set_tooltip_text("Add new workflow")
        add_btn.add_css_class("suggested-action")
        add_btn.connect("clicked", self._on_add_workflow)
        header.pack_end(add_btn)

        self.set_titlebar(header)

    # ------------------------------------------------------------------
    # Body
    # ------------------------------------------------------------------

    def _build_body(self) -> None:
        """Create the scrolled workflow list."""
        # Scrolled window wrapping the list box
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_vexpand(True)
        scrolled.set_hexpand(True)
        scrolled.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)

        # List box for workflows
        self._listbox = Gtk.ListBox()
        self._listbox.set_activate_on_single_click(True)
        self._listbox.connect("row-activated", self._on_row_activated)
        self._listbox.set_selection_mode(Gtk.SelectionMode.NONE)

        scrolled.set_child(self._listbox)
        self.set_child(scrolled)

    # ------------------------------------------------------------------
    # Refresh
    # ------------------------------------------------------------------

    def _refresh_workflows(self) -> None:
        """Reload workflows from the database and repopulate the list."""
        # Clear existing rows
        old_row = self._listbox.get_first_child()
        while old_row is not None:
            next_row = old_row.get_next_sibling()
            self._listbox.remove(old_row)
            old_row = next_row

        # Query DB and build rows
        workflows = get_all_workflows(self.conn)
        for wf in workflows:
            row = WorkflowRow(
                wf,
                on_toggle=self._on_toggle_workflow,
                on_edit=self._on_edit_workflow,
                on_delete=self._on_delete_workflow,
            )
            self._listbox.append(row)

    # ------------------------------------------------------------------
    # Callbacks
    # ------------------------------------------------------------------

    def _on_add_workflow(self, _button) -> None:
        """Create a new workflow and open the editor."""
        conn = self.conn
        new_wf = Workflow(name="New Workflow")
        new_wf.save(conn)
        self._refresh_workflows()
        # Open the editor for the newly created workflow
        self._open_editor(new_wf)

    def _on_toggle_workflow(self, workflow, enabled) -> None:
        """Toggle a workflow's enabled state in the DB."""
        workflow.enabled = enabled
        workflow.save(self.conn)

    def _on_edit_workflow(self, workflow) -> None:
        """Open the workflow editor dialog."""
        from src.gui.workflow_editor import WorkflowEditorDialog

        self._open_editor(workflow)

    def _on_delete_workflow(self, workflow) -> None:
        """Delete a workflow from the database and refresh the list."""
        workflow.delete(self.conn)
        self._refresh_workflows()

    def _on_row_activated(self, _listbox, row) -> None:
        """Handle double-click on a workflow row — open the editor."""
        if isinstance(row, WorkflowRow):
            self._on_edit_workflow(row.workflow)

    def _open_editor(self, workflow) -> None:
        """Open the WorkflowEditorDialog for the given workflow."""
        from src.gui.workflow_editor import WorkflowEditorDialog

        dialog = WorkflowEditorDialog(
            parent_window=self,
            db_path=self.db_path,
            workflow_id=workflow.id,
        )
        dialog.set_transient_for(self)
        dialog.set_modal(True)

        # Connect response signal to refresh the list on close
        dialog.connect("response", self._on_editor_closed)
        dialog.present()

    def _on_editor_closed(self, dialog, response_id) -> None:
        """Called when the editor dialog is closed — refresh the list."""
        self._refresh_workflows()
        dialog.destroy()
