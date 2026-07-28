import sqlite3
from pathlib import Path


def get_db(db_path):
    """Return a sqlite3 connection for the given database path."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(conn):
    """Read schema.sql from the same directory as this module and execute it."""
    schema_path = Path(__file__).parent / "schema.sql"
    schema_sql = schema_path.read_text()
    conn.executescript(schema_sql)