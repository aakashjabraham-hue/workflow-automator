"""MainWindow — the primary application window for Workflow Automator."""

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk

from src.db import get_db, init_db
from src.gui.widgets import WorkflowRow
from src.models.workflow import Workflow, get_all_workflows
from src.models.trigger import get_triggers_for_workflow


def _load_css():
    """Load the custom stylesheet from style.css."""
    import os
    provider = Gtk.CssProvider()
    css_path = os.path.join(os.path.dirname(__file__), "style.css")
    if not os.path.exists(css_path):
        return
    provider.load_from_path(css_path)
    # Apply to default display only when available
    display = Gtk.Widget.get_default()
    if display is not None:
        Gtk.StyleContext.add_provider_for_display(
            display,
            provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
        )


class MainWindow(Gtk.ApplicationWindow):
    """Main application window showing the workflow list."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        _load_css()

        self.set_title("Workflow Automator")
        self.set_default_size(500, 400)
        self.add_css_class("workflow-automator")

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
        # Main vertical layout
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.set_child(main_box)

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
        main_box.append(scrolled)

        # Empty state placeholder
        self._empty_state = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL, spacing=8
        )
        self._empty_state.set_vexpand(True)
        self._empty_state.set_valign(Gtk.Align.CENTER)
        self._empty_state.set_halign(Gtk.Align.CENTER)
        self._empty_state.add_css_class("empty-state")

        empty_icon = Gtk.Label(label="⚡")
        empty_icon.add_css_class("empty-icon")
        self._empty_state.append(empty_icon)

        empty_title = Gtk.Label(label="No Workflows Yet")
        empty_title.set_markup("<b>No Workflows Yet</b>")
        self._empty_state.append(empty_title)

        empty_hint = Gtk.Label(
            label='Click <b>+</b> above to create your first automation.'
        )
        empty_hint.set_use_markup(True)
        self._empty_state.append(empty_hint)

        main_box.append(self._empty_state)

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
        _TRIGGER_SUBTITLES = {
            "bluetooth": "When Bluetooth connects",
            "power": "When power changes",
            "schedule": "Scheduled",
            "network": "When network changes",
            "shell": "When command matches",
        }
        workflows = get_all_workflows(self.conn)
        for wf in workflows:
            row = WorkflowRow(
                wf,
                on_toggle=self._on_toggle_workflow,
                on_edit=self._on_edit_workflow,
                on_delete=self._on_delete_workflow,
            )
            # Set trigger type icon and label
            triggers = get_triggers_for_workflow(self.conn, wf.id)
            if triggers:
                ttype = triggers[0].type
                row.set_trigger_icon(ttype)
                row.set_trigger_label(
                    _TRIGGER_SUBTITLES.get(ttype, f"When {ttype}")
                )
            self._listbox.append(row)

        # Toggle empty state
        has_workflows = len(workflows) > 0
        self._empty_state.set_visible(not has_workflows)

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
