import sqlite3

import pytest

from src.db import get_db, init_db


@pytest.fixture
def conn():
    """Return an in-memory database connection with schema applied."""
    c = sqlite3.connect(":memory:")
    init_db(c)
    yield c
    c.close()


def test_init_db_creates_all_tables(conn):
    """init_db() must create all four tables."""
    cursor = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    )
    tables = {row[0] for row in cursor.fetchall()}
    assert tables == {"actions", "workflows", "triggers", "schedules"}


def test_schema_columns_workflows(conn):
    """workflows table must have the expected columns."""
    cursor = conn.execute("PRAGMA table_info(workflows)")
    columns = {row[1] for row in cursor.fetchall()}
    assert "id" in columns
    assert "name" in columns
    assert "enabled" in columns
    assert "created_at" in columns
    assert "updated_at" in columns


def test_schema_columns_triggers(conn):
    """triggers table must have the expected columns."""
    cursor = conn.execute("PRAGMA table_info(triggers)")
    columns = {row[1] for row in cursor.fetchall()}
    assert "id" in columns
    assert "workflow_id" in columns
    assert "type" in columns
    assert "config" in columns
    assert "enabled" in columns
    assert "created_at" in columns


def test_schema_columns_actions(conn):
    """actions table must have the expected columns."""
    cursor = conn.execute("PRAGMA table_info(actions)")
    columns = {row[1] for row in cursor.fetchall()}
    assert "id" in columns
    assert "workflow_id" in columns
    assert "type" in columns
    assert "command" in columns
    assert "args" in columns
    assert "enabled" in columns
    assert "created_at" in columns


def test_schema_columns_schedules(conn):
    """schedules table must have the expected columns."""
    cursor = conn.execute("PRAGMA table_info(schedules)")
    columns = {row[1] for row in cursor.fetchall()}
    assert "id" in columns
    assert "workflow_id" in columns
    assert "cron_expr" in columns
    assert "next_run" in columns
    assert "created_at" in columns