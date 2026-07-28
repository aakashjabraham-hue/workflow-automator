"""Tests for the workflow editor dialog (WorkflowEditorDialog)."""

import sqlite3

import pytest

# Skip all tests in this module if GTK/PyGObject is unavailable (headless CI).
gi = pytest.importorskip("gi")
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk

from src.db import init_db
from src.gui.workflow_editor import WorkflowEditorDialog
from src.models.workflow import Workflow, get_workflow
from src.models.trigger import Trigger, get_triggers_for_workflow
from src.models.action import Action, get_actions_for_workflow


DB_COLUMNS = [
    "id",
    "name",
    "enabled",
    "created_at",
    "updated_at",
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_db():
    """Return an in-memory sqlite3 DB with the full schema."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    init_db(conn)
    return conn


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_editor_dialog_imports():
    """WorkflowEditorDialog must be importable from src.gui.workflow_editor."""
    assert WorkflowEditorDialog is not None
    assert issubclass(WorkflowEditorDialog, Gtk.Dialog)


def test_editor_can_be_created(tmp_path):
    """Create a WorkflowEditorDialog with no DB workflow — all widgets exist."""
    db_path = str(tmp_path / "test.db")

    # Ensure the DB file exists and schema is initialised.
    conn = sqlite3.connect(db_path)
    init_db(conn)
    conn.close()

    # We need a parent window; a bareGtk.Window works for dialogs.
    parent = Gtk.Window()

    dlg = WorkflowEditorDialog(parent_window=parent, db_path=db_path)

    # --- Name field ---
    assert dlg.entry_name is not None
    assert isinstance(dlg.entry_name, Gtk.Entry)

    # --- Enabled toggle ---
    assert dlg.switch_enabled is not None
    assert isinstance(dlg.switch_enabled, Gtk.Switch)
    assert dlg.switch_enabled.get_active() is True  # default: enabled

    # --- Trigger section (Frame + DropDown + config box) ---
    assert dlg.dropdown_trigger is not None
    assert isinstance(dlg.dropdown_trigger, Gtk.DropDown)
    assert dlg.box_trigger_config is not None
    assert isinstance(dlg.box_trigger_config, Gtk.Box)

    # Default trigger type is "bluetooth" — verify config fields exist
    trigger_children = dlg.box_trigger_config.get_children()
    assert len(trigger_children) > 0  # at least Device + MAC entries

    # --- Actions section ---
    assert dlg.listbox_actions is not None
    assert isinstance(dlg.listbox_actions, Gtk.ListBox)

    # --- Schedule section ---
    assert dlg.entry_cron is not None
    assert isinstance(dlg.entry_cron, Gtk.Entry)
    assert dlg.switch_schedule_enabled is not None
    assert isinstance(dlg.switch_schedule_enabled, Gtk.Switch)
    assert dlg.switch_schedule_enabled.get_active() is False  # default: off

    # --- Buttons ---
    assert dlg.btn_test is not None
    assert dlg.btn_save is not None
    assert dlg.btn_cancel is not None

    dlg.destroy()
    parent.destroy()


def test_editor_loads_existing_workflow(tmp_path):
    """When workflow_id is passed, the dialog pre-fills fields from the DB."""
    db_path = str(tmp_path / "test_load.db")
    conn = _make_db()
    try:
        wf = Workflow(name="Existing Workflow", enabled=False)
        wf.save(conn)

        trig = Trigger(
            workflow_id=wf.id,
            type="power",
            config={"state": "unplugged"},
            enabled=True,
        )
        trig.save(conn)

        act = Action(
            workflow_id=wf.id,
            type="shell",
            command="notify-send hello",
            args=[],
            enabled=True,
        )
        act.save(conn)
    finally:
        conn.close()

    parent = Gtk.Window()
    dlg = WorkflowEditorDialog(
        parent_window=parent,
        db_path=db_path,
        workflow_id=wf.id,
    )

    assert dlg.entry_name.get_text() == "Existing Workflow"
    assert dlg.switch_enabled.get_active() is False

    # Trigger type should be "power" (index 1)
    assert dlg.dropdown_trigger.get_selected() == 1

    dlg.destroy()
    parent.destroy()


def test_editor_saves_new_workflow(tmp_path):
    """Saving a new workflow writes it to the DB and emits workflow-saved."""
    db_path = str(tmp_path / "test_save.db")
    conn = _make_db()
    conn.close()

    parent = Gtk.Window()
    dlg = WorkflowEditorDialog(
        parent_window=parent,
        db_path=db_path,
    )

    dlg.entry_name.set_text("Saved Workflow")
    dlg.switch_enabled.set_active(True)

    # Add an action row
    dlg._on_add_action(None)
    row = dlg._action_rows[0]
    row["type_dropdown"].set_selected(0)  # shell
    row["command_entry"].set_text("echo hello")
    row["args_entry"].set_text("")

    # Collect signal data
    saved_ids = []

    def _on_saved(_dialog, workflow_id):
        saved_ids.append(workflow_id)

    dlg.connect("workflow-saved", _on_saved)

    dlg._on_save(None)

    assert len(saved_ids) == 1
    saved_id = saved_ids[0]

    # Verify in DB
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        saved_wf = get_workflow(conn, saved_id)
        assert saved_wf is not None
        assert saved_wf.name == "Saved Workflow"
        assert saved_wf.enabled is True

        triggers = get_triggers_for_workflow(conn, saved_id)
        assert len(triggers) == 1
        assert triggers[0].type == "bluetooth"

        actions = get_actions_for_workflow(conn, saved_id)
        assert len(actions) == 1
        assert actions[0].type == "shell"
        assert actions[0].command == "echo hello"
    finally:
        conn.close()

    dlg.destroy()
    parent.destroy()


def test_editor_cancel_destroys_dialog(tmp_path):
    """Clicking Cancel destroys the dialog without saving."""
    db_path = str(tmp_path / "test_cancel.db")
    conn = _make_db()
    conn.close()

    parent = Gtk.Window()
    dlg = WorkflowEditorDialog(
        parent_window=parent,
        db_path=db_path,
    )

    dlg._on_cancel(None)
    # After destroy, the dialog should not be visible
    assert not dlg.get_visible()

    parent.destroy()
