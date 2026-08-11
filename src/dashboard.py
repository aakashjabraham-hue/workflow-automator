"""Workflow Automator — localhost web dashboard.

``workflow-automator dashboard`` starts a small HTTP server on
``http://127.0.0.1:<port>`` that serves the same workflow-management UI as
the GTK desktop app (see :mod:`src.gui`), over the same SQLite database the
desktop app and the daemon use.

Zero external dependencies: only ``http.server``, ``socketserver``,
``threading`` and ``webbrowser`` from the standard library.

Routes
------
``GET  /``                          → the dashboard page (embedded HTML)
``GET  /api/meta``                  → {version, db_path, port, platform}
``GET  /api/workflows``             → all workflows with triggers + actions
``POST /api/workflows``             → create a workflow            {name, enabled?}
``GET  /api/workflows/<id>``        → one workflow (detailed)
``PUT  /api/workflows/<id>``        → update name / enabled
``DELETE /api/workflows/<id>``      → delete workflow (cascade)
``POST /api/workflows/<id>/triggers`` → add trigger  {type, config, enabled?}
``PUT  /api/triggers/<id>``         → update trigger {type?, config?, enabled?}
``DELETE /api/triggers/<id>``       → delete trigger
``POST /api/workflows/<id>/actions``  → add action   {type, command, args?, enabled?}
``PUT  /api/actions/<id>``          → update action  {type?, command?, args?, enabled?}
``DELETE /api/actions/<id>``        → delete action
"""

import json
import os
import socket
import socketserver
import sys
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler

from src.dashboard_ui import ACTION_TYPES, DASHBOARD_HTML, TRIGGER_TYPES
from src.db import get_db, init_db
from src.models.action import Action, get_action, get_actions_for_workflow
from src.models.trigger import Trigger, get_trigger, get_triggers_for_workflow
from src.models.workflow import Workflow, get_all_workflows, get_workflow
from src.paths import default_db_path

DEFAULT_PORT = 8899
PORT_SCAN_RANGE = 10  # try DEFAULT_PORT .. DEFAULT_PORT + PORT_SCAN_RANGE - 1


class Style:
    """ANSI escape helpers (same as src/self_update.py — no external deps)."""

    BOLD = "\033[1m"
    GREEN = "\033[92m"
    CYAN = "\033[96m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    MAGENTA = "\033[95m"
    DIM = "\033[2m"
    RESET = "\033[0m"


def _c(text: str, *styles: str) -> str:
    """Colorize *text* (no-op when output is not a tty)."""
    if not sys.stdout.isatty():
        return text
    return "".join(styles) + text + Style.RESET


# --------------------------------------------------------------------------
# DB helpers
# --------------------------------------------------------------------------


def _connect(db_path: str):
    conn = get_db(db_path)
    init_db(conn)
    return conn


def _workflow_detail(conn, wf: Workflow) -> dict:
    """Workflow dict with nested triggers and actions."""
    data = wf.to_dict()
    data["triggers"] = [t.to_dict() for t in get_triggers_for_workflow(conn, wf.id)]
    data["actions"] = [a.to_dict() for a in get_actions_for_workflow(conn, wf.id)]
    return data


# --------------------------------------------------------------------------
# HTTP handler
# --------------------------------------------------------------------------


class DashboardHandler(BaseHTTPRequestHandler):
    """Serves the embedded dashboard page and its JSON API.

    ``db_path`` is a class attribute so tests can point the server at a
    temporary database before binding.
    """

    db_path: str = ":memory:"
    port: int = DEFAULT_PORT

    # -- plumbing ---------------------------------------------------------

    def _conn(self):
        return _connect(self.db_path)

    def _send_json(self, data, status: int = 200) -> None:
        body = json.dumps(data, default=str).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def _send_html(self, html: str, status: int = 200) -> None:
        body = html.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(body)

    def _send_error(self, message: str, status: int = 400) -> None:
        self._send_json({"error": message}, status=status)

    def _read_body(self) -> dict:
        length = int(self.headers.get("Content-Length") or 0)
        if length <= 0:
            return {}
        raw = self.rfile.read(length)
        try:
            data = json.loads(raw.decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            return {}
        return data if isinstance(data, dict) else {}

    def log_message(self, format, *args) -> None:
        pass  # keep the terminal quiet — the banner already told the user the URL

    # -- routing ----------------------------------------------------------

    def do_GET(self):
        import urllib.parse

        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        parts = [p for p in path.split("/") if p]

        if path == "/":
            return self._send_html(DASHBOARD_HTML)
        if path == "/api/meta":
            return self._api_meta()
        if path == "/api/workflows":
            return self._api_list_workflows()
        if len(parts) == 3 and parts[0] == "api" and parts[1] == "workflows":
            return self._api_get_workflow(parts[2])
        self._send_error("Not found", 404)

    def do_POST(self):
        import urllib.parse

        parsed = urllib.parse.urlparse(self.path)
        parts = [p for p in parsed.path.split("/") if p]
        body = self._read_body()

        if len(parts) == 2 and parts == ["api", "workflows"]:
            return self._api_create_workflow(body)
        if len(parts) == 4 and parts[0:2] == ["api", "workflows"] and parts[3] == "triggers":
            return self._api_add_trigger(parts[2], body)
        if len(parts) == 4 and parts[0:2] == ["api", "workflows"] and parts[3] == "actions":
            return self._api_add_action(parts[2], body)
        self._send_error("Not found", 404)

    def do_PUT(self):
        import urllib.parse

        parsed = urllib.parse.urlparse(self.path)
        parts = [p for p in parsed.path.split("/") if p]
        body = self._read_body()

        if len(parts) == 3 and parts[:2] == ["api", "workflows"]:
            return self._api_update_workflow(parts[2], body)
        if len(parts) == 3 and parts[:2] == ["api", "triggers"]:
            return self._api_update_trigger(parts[2], body)
        if len(parts) == 3 and parts[:2] == ["api", "actions"]:
            return self._api_update_action(parts[2], body)
        self._send_error("Not found", 404)

    def do_DELETE(self):
        import urllib.parse

        parsed = urllib.parse.urlparse(self.path)
        parts = [p for p in parsed.path.split("/") if p]

        if len(parts) == 3 and parts[:2] == ["api", "workflows"]:
            return self._api_delete_workflow(parts[2])
        if len(parts) == 3 and parts[:2] == ["api", "triggers"]:
            return self._api_delete_trigger(parts[2])
        if len(parts) == 3 and parts[:2] == ["api", "actions"]:
            return self._api_delete_action(parts[2])
        self._send_error("Not found", 404)

    def _int_id(self, raw: str):
        try:
            return int(raw)
        except ValueError:
            return None

    # -- API: meta --------------------------------------------------------

    def _api_meta(self):
        try:
            from src import __version__
        except Exception:  # pragma: no cover
            __version__ = "0.0.0"
        self._send_json({
            "version": __version__,
            "db_path": self.db_path,
            "port": self.port,
            "platform": sys.platform,
        })

    # -- API: workflows ---------------------------------------------------

    def _api_list_workflows(self):
        conn = self._conn()
        try:
            data = [_workflow_detail(conn, wf) for wf in get_all_workflows(conn)]
        finally:
            conn.close()
        self._send_json(data)

    def _api_get_workflow(self, raw_id):
        wf_id = self._int_id(raw_id)
        conn = self._conn()
        try:
            wf = get_workflow(conn, wf_id) if wf_id is not None else None
            if wf is None:
                return self._send_error("Workflow not found", 404)
            self._send_json(_workflow_detail(conn, wf))
        finally:
            conn.close()

    def _api_create_workflow(self, body):
        name = body.get("name")
        if not isinstance(name, str) or not name.strip():
            return self._send_error("Field 'name' (string) is required")
        enabled = body.get("enabled", True)
        if not isinstance(enabled, bool):
            enabled = True
        conn = self._conn()
        try:
            wf = Workflow(name=name.strip(), enabled=enabled)
            wf.save(conn)
            self._send_json(_workflow_detail(conn, wf), status=201)
        finally:
            conn.close()

    def _api_update_workflow(self, raw_id, body):
        wf_id = self._int_id(raw_id)
        conn = self._conn()
        try:
            wf = get_workflow(conn, wf_id) if wf_id is not None else None
            if wf is None:
                return self._send_error("Workflow not found", 404)
            if "name" in body:
                if not isinstance(body["name"], str) or not body["name"].strip():
                    return self._send_error("Field 'name' must be a non-empty string")
                wf.name = body["name"].strip()
            if "enabled" in body:
                if not isinstance(body["enabled"], bool):
                    return self._send_error("Field 'enabled' must be a boolean")
                wf.enabled = body["enabled"]
            wf.save(conn)
            self._send_json(_workflow_detail(conn, wf))
        finally:
            conn.close()

    def _api_delete_workflow(self, raw_id):
        wf_id = self._int_id(raw_id)
        conn = self._conn()
        try:
            wf = get_workflow(conn, wf_id) if wf_id is not None else None
            if wf is None:
                return self._send_error("Workflow not found", 404)
            wf.delete(conn)
            self.send_response(204)
            self.send_header("Content-Length", "0")
            self.end_headers()
        finally:
            conn.close()

    # -- API: triggers ----------------------------------------------------

    def _api_add_trigger(self, raw_wf_id, body):
        wf_id = self._int_id(raw_wf_id)
        ttype = body.get("type")
        config = body.get("config", {})
        if ttype not in TRIGGER_TYPES:
            return self._send_error(
                f"Field 'type' must be one of {TRIGGER_TYPES}")
        if not isinstance(config, dict):
            return self._send_error("Field 'config' must be an object")
        conn = self._conn()
        try:
            wf = get_workflow(conn, wf_id) if wf_id is not None else None
            if wf_id is None or wf is None:
                return self._send_error("Workflow not found", 404)
            enabled = body.get("enabled", True)
            trigger = Trigger(workflow_id=wf_id, type=ttype, config=config,
                              enabled=enabled if isinstance(enabled, bool) else True)
            trigger.save(conn)
            self._send_json(trigger.to_dict(), status=201)
        finally:
            conn.close()

    def _api_update_trigger(self, raw_id, body):
        trig_id = self._int_id(raw_id)
        conn = self._conn()
        try:
            trigger = get_trigger(conn, trig_id) if trig_id is not None else None
            if trigger is None:
                return self._send_error("Trigger not found", 404)
            if "type" in body:
                if body["type"] not in TRIGGER_TYPES:
                    return self._send_error(
                        f"Field 'type' must be one of {TRIGGER_TYPES}")
                trigger.type = body["type"]
            if "config" in body:
                if not isinstance(body["config"], dict):
                    return self._send_error("Field 'config' must be an object")
                trigger.config = body["config"]
            if "enabled" in body:
                if not isinstance(body["enabled"], bool):
                    return self._send_error("Field 'enabled' must be a boolean")
                trigger.enabled = body["enabled"]
            trigger.save(conn)
            self._send_json(trigger.to_dict())
        finally:
            conn.close()

    def _api_delete_trigger(self, raw_id):
        trig_id = self._int_id(raw_id)
        conn = self._conn()
        try:
            trigger = get_trigger(conn, trig_id) if trig_id is not None else None
            if trigger is None:
                return self._send_error("Trigger not found", 404)
            trigger.delete(conn)
            self.send_response(204)
            self.send_header("Content-Length", "0")
            self.end_headers()
        finally:
            conn.close()

    # -- API: actions -----------------------------------------------------

    def _api_add_action(self, raw_wf_id, body):
        wf_id = self._int_id(raw_wf_id)
        atype = body.get("type")
        command = body.get("command", "")
        args = body.get("args", [])
        if atype not in ACTION_TYPES:
            return self._send_error(f"Field 'type' must be one of {ACTION_TYPES}")
        if not isinstance(command, str):
            return self._send_error("Field 'command' must be a string")
        if not isinstance(args, list):
            return self._send_error("Field 'args' must be an array")
        conn = self._conn()
        try:
            wf = get_workflow(conn, wf_id) if wf_id is not None else None
            if wf_id is None or wf is None:
                return self._send_error("Workflow not found", 404)
            enabled = body.get("enabled", True)
            action = Action(workflow_id=wf_id, type=atype, command=command,
                            args=args, enabled=enabled if isinstance(enabled, bool) else True)
            action.save(conn)
            self._send_json(action.to_dict(), status=201)
        finally:
            conn.close()

    def _api_update_action(self, raw_id, body):
        act_id = self._int_id(raw_id)
        conn = self._conn()
        try:
            action = get_action(conn, act_id) if act_id is not None else None
            if action is None:
                return self._send_error("Action not found", 404)
            if "type" in body:
                if body["type"] not in ACTION_TYPES:
                    return self._send_error(
                        f"Field 'type' must be one of {ACTION_TYPES}")
                action.type = body["type"]
            if "command" in body:
                if not isinstance(body["command"], str):
                    return self._send_error("Field 'command' must be a string")
                action.command = body["command"]
            if "args" in body:
                if not isinstance(body["args"], list):
                    return self._send_error("Field 'args' must be an array")
                action.args = body["args"]
            if "enabled" in body:
                if not isinstance(body["enabled"], bool):
                    return self._send_error("Field 'enabled' must be a boolean")
                action.enabled = body["enabled"]
            action.save(conn)
            self._send_json(action.to_dict())
        finally:
            conn.close()

    def _api_delete_action(self, raw_id):
        act_id = self._int_id(raw_id)
        conn = self._conn()
        try:
            action = get_action(conn, act_id) if act_id is not None else None
            if action is None:
                return self._send_error("Action not found", 404)
            action.delete(conn)
            self.send_response(204)
            self.send_header("Content-Length", "0")
            self.end_headers()
        finally:
            conn.close()


class ThreadingDashboardServer(socketserver.ThreadingTCPServer):
    """Thread-per-request dashboard server (browser fetches run in parallel)."""

    allow_reuse_address = True
    daemon_threads = True


# --------------------------------------------------------------------------
# Server bootstrap
# --------------------------------------------------------------------------


def find_free_port(start: int = DEFAULT_PORT, attempts: int = PORT_SCAN_RANGE) -> int | None:
    """Return the first free port at or above *start*, or None if none found."""
    for port in range(start, start + attempts):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            sock.bind(("127.0.0.1", port))
            return port
        except OSError:
            continue
        finally:
            sock.close()
    return None


def run_dashboard(db_path: str | None = None,
                  port: int | None = None,
                  open_browser: bool = True,
                  block: bool = True) -> int:
    """Start the localhost web dashboard.

    Args:
        db_path: SQLite database to manage (default: platform default,
            the same file the daemon and desktop app use).
        port: Preferred port (default 8899; next free port is used if busy).
        open_browser: Open the default browser at the dashboard URL.
        block: Keep serving until Ctrl+C. Pass False in tests to return
            immediately after the server starts.

    Returns:
        Exit code (0 on success / clean shutdown).
    """
    resolved_db = db_path or default_db_path()
    os.makedirs(os.path.dirname(resolved_db) or ".", exist_ok=True)
    # Touch the DB so the page never renders empty before the first write.
    _connect(resolved_db).close()

    start_port = port or DEFAULT_PORT
    free_port = find_free_port(start_port)
    if free_port is None:
        print(
            _c(f"  ✗  No free port found near {start_port}.", Style.RED),
            file=sys.stderr,
        )
        return 1

    DashboardHandler.db_path = resolved_db
    DashboardHandler.port = free_port
    server = ThreadingDashboardServer(("127.0.0.1", free_port), DashboardHandler)
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()

    url = f"http://127.0.0.1:{free_port}"
    print()
    print(_c("  ⚡ Workflow Automator — Web Dashboard", Style.BOLD))
    print(_c(f"  📊  {url}", Style.CYAN))
    print(_c(f"  🗄️   Database: {resolved_db}", Style.CYAN))
    print(_c("  Press Ctrl+C to stop the server.", Style.CYAN))
    print()

    if open_browser:
        webbrowser.open(url)

    if not block:
        return 0

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print(_c("\n  ✅  Dashboard stopped.", Style.GREEN))
    finally:
        server.shutdown()
        server.server_close()
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(run_dashboard())
