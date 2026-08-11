"""Tests for the localhost web dashboard (src.dashboard).

The server is exercised over real HTTP against a temporary database, the
same way the browser would talk to it.
"""

import json
import threading
import urllib.error
import urllib.request
from typing import Any

import pytest

from src.dashboard import (
    DashboardHandler,
    ThreadingDashboardServer,
    find_free_port,
)


@pytest.fixture()
def server(tmp_path):
    db = tmp_path / "test.db"
    DashboardHandler.db_path = str(db)
    srv = ThreadingDashboardServer(("127.0.0.1", 0), DashboardHandler)
    thread = threading.Thread(target=srv.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{srv.server_address[1]}"
    yield base
    srv.shutdown()
    srv.server_close()


def _request(base, path, method="GET", body=None) -> tuple[int, Any]:
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(base + path, data=data, method=method)
    if data is not None:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            raw = resp.read()
            try:
                return resp.status, json.loads(raw) if raw else None
            except ValueError:
                return resp.status, raw.decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        raw = exc.read()
        try:
            payload = json.loads(raw) if raw else None
        except ValueError:
            payload = None
        return exc.code, payload


# --------------------------------------------------------------------------
# Page + meta
# --------------------------------------------------------------------------


def test_index_serves_dashboard_html(server):
    status, body = _request(server, "/")
    assert status == 200
    assert "<html" in body
    assert "Workflow" in body
    assert "Web Dashboard" in body


def test_meta_reports_version_db_and_port(server):
    status, meta = _request(server, "/api/meta")
    assert status == 200
    assert meta["version"]
    assert meta["db_path"].endswith("test.db")
    assert isinstance(meta["port"], int)
    assert meta["platform"]


# --------------------------------------------------------------------------
# Workflow CRUD
# --------------------------------------------------------------------------


def test_workflow_create_list_toggle_delete(server):
    status, wf = _request(server, "/api/workflows", method="POST",
                          body={"name": "Morning coffee", "enabled": True})
    assert status == 201
    wf_id = wf["id"]
    assert wf["name"] == "Morning coffee"
    assert wf["triggers"] == []
    assert wf["actions"] == []

    status, items = _request(server, "/api/workflows")
    assert status == 200
    assert len(items) == 1
    assert items[0]["id"] == wf_id

    status, updated = _request(server, f"/api/workflows/{wf_id}", method="PUT",
                               body={"enabled": False})
    assert status == 200
    assert updated["enabled"] is False
    assert updated["name"] == "Morning coffee"  # untouched

    status, renamed = _request(server, f"/api/workflows/{wf_id}", method="PUT",
                               body={"name": "Coffee time"})
    assert status == 200
    assert renamed["name"] == "Coffee time"
    assert renamed["enabled"] is False

    status, _ = _request(server, f"/api/workflows/{wf_id}", method="DELETE")
    assert status == 204
    status, items = _request(server, "/api/workflows")
    assert items == []


def test_workflow_get_detail_404(server):
    status, payload = _request(server, "/api/workflows/999")
    assert status == 404
    assert "not found" in payload["error"].lower()


def test_workflow_create_requires_name(server):
    status, payload = _request(server, "/api/workflows", method="POST", body={})
    assert status == 400
    assert "name" in payload["error"]


def test_workflow_update_validates_enabled(server):
    status, wf = _request(server, "/api/workflows", method="POST",
                          body={"name": "X"})
    assert status == 201
    status, payload = _request(server, f"/api/workflows/{wf['id']}", method="PUT",
                               body={"enabled": "yes"})
    assert status == 400


# --------------------------------------------------------------------------
# Triggers + actions
# --------------------------------------------------------------------------


def _make_workflow(server, name="Demo"):
    _, wf = _request(server, "/api/workflows", method="POST", body={"name": name})
    return wf["id"]


def test_add_and_update_trigger(server):
    wf_id = _make_workflow(server)
    status, trig = _request(server, f"/api/workflows/{wf_id}/triggers",
                            method="POST",
                            body={"type": "schedule", "config": {"cron_expr": "0 8 * * *"}})
    assert status == 201
    assert trig["type"] == "schedule"
    assert trig["config"]["cron_expr"] == "0 8 * * *"
    assert trig["workflow_id"] == wf_id

    status, updated = _request(server, f"/api/triggers/{trig['id']}", method="PUT",
                               body={"config": {"cron_expr": "0 9 * * *"}})
    assert status == 200
    assert updated["config"] == {"cron_expr": "0 9 * * *"}

    status, detail = _request(server, f"/api/workflows/{wf_id}")
    assert len(detail["triggers"]) == 1
    assert detail["triggers"][0]["config"]["cron_expr"] == "0 9 * * *"


def test_add_update_delete_action(server):
    wf_id = _make_workflow(server)
    status, act = _request(server, f"/api/workflows/{wf_id}/actions",
                           method="POST",
                           body={"type": "notify", "command": "Coffee's ready",
                                 "args": ["Enjoy!"]})
    assert status == 201
    assert act["command"] == "Coffee's ready"
    assert act["args"] == ["Enjoy!"]

    status, updated = _request(server, f"/api/actions/{act['id']}", method="PUT",
                               body={"args": ["Enjoy! ☕"]})
    assert status == 200
    assert updated["args"] == ["Enjoy! ☕"]

    status, _ = _request(server, f"/api/actions/{act['id']}", method="DELETE")
    assert status == 204
    status, detail = _request(server, f"/api/workflows/{wf_id}")
    assert detail["actions"] == []


def test_trigger_type_validated(server):
    wf_id = _make_workflow(server)
    status, payload = _request(server, f"/api/workflows/{wf_id}/triggers",
                               method="POST",
                               body={"type": "alien", "config": {}})
    assert status == 400
    assert "type" in payload["error"]


def test_action_type_validated(server):
    wf_id = _make_workflow(server)
    status, payload = _request(server, f"/api/workflows/{wf_id}/actions",
                               method="POST",
                               body={"type": "teleport", "command": "beam"})
    assert status == 400
    assert "type" in payload["error"]


def test_trigger_config_must_be_object(server):
    wf_id = _make_workflow(server)
    status, payload = _request(server, f"/api/workflows/{wf_id}/triggers",
                               method="POST",
                               body={"type": "power", "config": ["plugged"]})
    assert status == 400


def test_media_action_roundtrip(server):
    wf_id = _make_workflow(server)
    status, act = _request(server, f"/api/workflows/{wf_id}/actions",
                           method="POST",
                           body={"type": "media",
                                 "command": "spotify|Open URI",
                                 "args": ["spotify:playlist:37i9dQZF1DXcBWIGoYBM5M"]})
    assert status == 201
    assert act["command"] == "spotify|Open URI"
    assert act["args"][0].startswith("spotify:")


def test_cascade_delete_removes_children(server):
    wf_id = _make_workflow(server)
    _request(server, f"/api/workflows/{wf_id}/triggers", method="POST",
             body={"type": "schedule", "config": {"cron_expr": "* * * * *"}})
    _request(server, f"/api/workflows/{wf_id}/actions", method="POST",
             body={"type": "shell", "command": "echo hi"})
    status, _ = _request(server, f"/api/workflows/{wf_id}", method="DELETE")
    assert status == 204
    status, items = _request(server, "/api/workflows")
    assert items == []


def test_unknown_route_404(server):
    status, _ = _request(server, "/api/nope")
    assert status == 404


# --------------------------------------------------------------------------
# Port selection
# --------------------------------------------------------------------------


def test_find_free_port_skips_occupied():
    import socket

    occupied = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    occupied.bind(("127.0.0.1", 0))
    occupied.listen(1)
    taken = occupied.getsockname()[1]
    try:
        free = find_free_port(taken, attempts=5)
        assert free is not None
        assert free != taken
        probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        probe.bind(("127.0.0.1", free))  # must be actually free
        probe.close()
    finally:
        occupied.close()
