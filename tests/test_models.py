import sqlite3
from src.db import init_db
from src.models.workflow import Workflow, get_all_workflows, get_workflow
from src.models.trigger import Trigger, get_triggers_for_workflow, get_trigger
from src.models.action import Action, get_actions_for_workflow, get_action


def test_init_db_creates_all_tables():
    conn = sqlite3.connect(":memory:")
    init_db(conn)
    tables = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name IN ('workflows','triggers','actions','schedules')"
    ).fetchall()
    table_names = {t[0] for t in tables}
    assert table_names == {"workflows", "triggers", "actions", "schedules"}
    conn.close()


def test_schema_columns_workflows():
    conn = sqlite3.connect(":memory:")
    init_db(conn)
    columns = {row[1] for row in conn.execute("PRAGMA table_info(workflows)").fetchall()}
    assert "id" in columns
    assert "name" in columns
    assert "enabled" in columns
    assert "created_at" in columns
    assert "updated_at" in columns
    conn.close()


def test_schema_columns_triggers():
    conn = sqlite3.connect(":memory:")
    init_db(conn)
    columns = {row[1] for row in conn.execute("PRAGMA table_info(triggers)").fetchall()}
    assert "id" in columns
    assert "workflow_id" in columns
    assert "type" in columns
    assert "config" in columns
    assert "enabled" in columns
    conn.close()


def test_schema_columns_actions():
    conn = sqlite3.connect(":memory:")
    init_db(conn)
    columns = {row[1] for row in conn.execute("PRAGMA table_info(actions)").fetchall()}
    assert "id" in columns
    assert "workflow_id" in columns
    assert "type" in columns
    assert "command" in columns
    assert "args" in columns
    assert "enabled" in columns
    conn.close()


def test_schema_columns_schedules():
    conn = sqlite3.connect(":memory:")
    init_db(conn)
    columns = {row[1] for row in conn.execute("PRAGMA table_info(schedules)").fetchall()}
    assert "id" in columns
    assert "workflow_id" in columns
    assert "cron_expr" in columns
    assert "next_run" in columns
    conn.close()


def test_workflow_crud():
    conn = sqlite3.connect(":memory:")
    init_db(conn)
    wf = Workflow(name="Test Workflow")
    wf.save(conn)
    assert wf.id is not None

    fetched = get_workflow(conn, wf.id)
    assert fetched is not None
    assert fetched.name == "Test Workflow"
    assert fetched.enabled is True

    wf.enabled = False
    wf.save(conn)
    fetched2 = get_workflow(conn, wf.id)
    assert fetched2.enabled is False

    wf.delete(conn)
    assert get_workflow(conn, wf.id) is None
    conn.close()


def test_trigger_crud():
    conn = sqlite3.connect(":memory:")
    init_db(conn)
    wf = Workflow(name="Trigger Test")
    wf.save(conn)

    trig = Trigger(workflow_id=wf.id, type="bluetooth", config={"device": "MyHeadphones"}, enabled=True)
    trig.save(conn)
    assert trig.id is not None

    fetched = get_trigger(conn, trig.id)
    assert fetched is not None
    assert fetched.type == "bluetooth"
    assert fetched.config == {"device": "MyHeadphones"}

    trig.delete(conn)
    assert get_trigger(conn, trig.id) is None
    conn.close()


def test_action_crud():
    conn = sqlite3.connect(":memory:")
    init_db(conn)
    wf = Workflow(name="Action Test")
    wf.save(conn)

    act = Action(workflow_id=wf.id, type="shell", command="echo hello", args=[], enabled=True)
    act.save(conn)
    assert act.id is not None

    fetched = get_action(conn, act.id)
    assert fetched is not None
    assert fetched.command == "echo hello"

    act.delete(conn)
    assert get_action(conn, act.id) is None
    conn.close()


def test_get_triggers_for_workflow():
    conn = sqlite3.connect(":memory:")
    init_db(conn)
    wf = Workflow(name="Multi-Trigger")
    wf.save(conn)

    Trigger(workflow_id=wf.id, type="bluetooth", config={"device": "Headphones"}).save(conn)
    Trigger(workflow_id=wf.id, type="power", config={"state": "unplugged"}).save(conn)

    triggers = get_triggers_for_workflow(conn, wf.id)
    assert len(triggers) == 2
    types = {t.type for t in triggers}
    assert types == {"bluetooth", "power"}
    conn.close()


def test_get_actions_for_workflow():
    conn = sqlite3.connect(":memory:")
    init_db(conn)
    wf = Workflow(name="Multi-Action")
    wf.save(conn)

    Action(workflow_id=wf.id, type="shell", command="notify-send hi").save(conn)
    Action(workflow_id=wf.id, type="launch", command="spotify").save(conn)

    actions = get_actions_for_workflow(conn, wf.id)
    assert len(actions) == 2
    types = {a.type for a in actions}
    assert types == {"shell", "launch"}
    conn.close()