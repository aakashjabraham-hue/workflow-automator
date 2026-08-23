import logging
import sys
import threading
import time
from typing import Any, Optional

from src.db import get_db, init_db
from src.engine.event_bus import EventBus
from src.engine.executor import ActionExecutor
from src.models.workflow import get_all_workflows, Workflow
from src.models.trigger import get_triggers_for_workflow, Trigger

logger = logging.getLogger(__name__)

# Registry mapping trigger type names to their classes.
_TRIGGER_REGISTRY: dict[str, Any] = {}


def register_trigger_type(name: str, cls: type) -> None:
    """Register a trigger class under *name* so the daemon can instantiate it."""
    _TRIGGER_REGISTRY[name] = cls


def _import_builtin_triggers() -> None:
    """Lazy-import known trigger types and register them."""
    try:
        from src.engine.triggers.bluetooth import BluetoothTrigger
        register_trigger_type("bluetooth", BluetoothTrigger)
    except ImportError:
        pass
    try:
        from src.engine.triggers.power import PowerTrigger
        register_trigger_type("power", PowerTrigger)
    except ImportError:
        pass
    try:
        from src.engine.triggers.schedule import ScheduleTrigger
        register_trigger_type("schedule", ScheduleTrigger)
    except ImportError:
        pass


class DaemonService:
    """Background daemon that loads workflows, registers triggers, and
    executes actions when triggers fire.

    Args:
        db_path: Path to the SQLite database file.
        verbose: If True, set logging level to DEBUG.

    The daemon owns a singleton EventBus and an ActionExecutor.  It loads
    all enabled workflows and their triggers from the database, instantiates
    the corresponding trigger classes, and registers them so that dispatched
    events are routed to the right workflow's actions.
    """

    def __init__(self, db_path: str = ":memory:", verbose: bool = False):
        # Configure logging
        log_level = logging.DEBUG if verbose else logging.INFO
        logging.basicConfig(
            level=log_level,
            format="%(asctime)s %(name)s %(levelname)s %(message)s",
            stream=sys.stdout,
        )
        self.logger = logging.getLogger("workflow-automator.daemon")
        self.logger.info("DaemonService initialising (db_path=%s)", db_path)

        # Open the SQLite database and ensure the schema is in place.
        self.db_path = db_path
        self.conn = get_db(db_path)
        init_db(self.conn)
        self.logger.debug("Database opened at %s", db_path)

        # Core engine components.
        self.event_bus = EventBus.get_instance()
        self.executor = ActionExecutor()
        self._triggers: list[Any] = []
        self._workflows: list[Workflow] = []
        self._main_loop: Optional[Any] = None
        self._poll_thread: Optional[threading.Thread] = None
        self._running = False

        # Load workflows and register triggers.
        self._load_workflows()

        # Try to set up D-Bus signal listeners.
        self.event_bus.setup_dbus_listeners()

        # Subscribe to trigger-match callbacks so D-Bus-driven matches
        # (e.g. Bluetooth) actually execute the workflow actions.
        self._setup_match_callback()

    # ------------------------------------------------------------------ #
    #  Lifecycle
    # ------------------------------------------------------------------ #

    def _load_workflows(self) -> None:
        """Load all enabled workflows from the database and register their triggers."""
        _import_builtin_triggers()

        workflows = get_all_workflows(self.conn)
        self._workflows = [wf for wf in workflows if wf.enabled]
        self.logger.info("Loaded %d enabled workflow(s)", len(self._workflows))

        for workflow in self._workflows:
            self._register_workflow_triggers(workflow)

    def _register_workflow_triggers(self, workflow: Workflow) -> None:
        """Instantiate and register all triggers belonging to *workflow*."""
        trigger_rows = get_triggers_for_workflow(self.conn, workflow.id)
        for row in trigger_rows:
            if not row.enabled:
                continue
            cls = _TRIGGER_REGISTRY.get(row.type)
            if cls is None:
                self.logger.warning(
                    "Unknown trigger type '%s' for workflow '%s' (id=%d); skipping",
                    row.type,
                    workflow.name,
                    workflow.id,
                )
                continue
            # ScheduleTrigger takes (cron_expr, workflow_id, config); every
            # other builtin takes (config,).  Build args accordingly so a
            # saved schedule workflow doesn't raise TypeError at startup.
            if cls.__name__ == "ScheduleTrigger":
                cron_expr = (row.config or {}).get("cron_expr") or "* * * * *"
                trigger = cls(cron_expr, workflow.id, row.config)
            else:
                trigger = cls(row.config)
            trigger.workflow_id = workflow.id
            self._triggers.append(trigger)
            self.event_bus.register_trigger(trigger)
            self.logger.info(
                "Registered trigger '%s' (type=%s) for workflow '%s'",
                trigger.name(),
                row.type,
                workflow.name,
            )

    def _setup_match_callback(self) -> None:
        """Register a callback so D-Bus-driven matches execute their workflow actions.

        Without this, ``EventBus.dispatch()`` returns matched triggers but
        nobody triggers action execution.
        """
        def _on_match(trigger, event_data) -> None:
            wf_id = getattr(trigger, "workflow_id", None)
            if wf_id is not None:
                self.logger.info(
                    "Match callback: executing actions for workflow id=%s "
                    "(trigger=%s)", wf_id, trigger.name(),
                )
                self._execute_workflow_actions(wf_id)

        self.event_bus.on_match(_on_match)

    def start(self) -> None:
        """Start the daemon main loop (D-Bus handling + schedule polling)."""
        self._running = True
        self.logger.info("Daemon starting")

        if not self._try_start_glm_main_loop():
            self._start_fallback_polling()

        self.logger.info("Daemon started successfully")

    def _try_start_glm_main_loop(self) -> bool:
        """Attempt to start a GLib.MainLoop for D-Bus + schedule polling.

        Returns True if GLib is available and the main loop was started.
        """
        try:
            from gi.repository import GLib
        except ImportError:
            self.logger.info("GLib not available; falling back to polling thread")
            return False

        loop = GLib.MainLoop()
        self._main_loop = loop

        # Add a periodic source for schedule-trigger polling (~every 10 s).
        def _poll_schedules() -> bool:
            if not self._running:
                return False  # stop the source
            self._poll_schedule_triggers()
            return True  # keep the source alive

        GLib.timeout_add_seconds(10, _poll_schedules)

        self.logger.info("GLib.MainLoop started")
        loop.run()
        return True

    def _start_fallback_polling(self) -> None:
        """Start a background thread that polls schedule triggers periodically."""
        self._poll_thread = threading.Thread(target=self._poll_loop, daemon=True)
        self._poll_thread.start()
        self.logger.info("Fallback polling thread started (interval=10s)")

    def _poll_loop(self) -> None:
        """Simple polling loop used when GLib is unavailable."""
        while self._running:
            self._poll_schedule_triggers()
            time.sleep(10)

    def stop(self) -> None:
        """Stop the daemon and clean up resources."""
        self.logger.info("Daemon stopping")
        self._running = False

        if self._main_loop is not None:
            self._main_loop.quit()
            self._main_loop = None
            self.logger.debug("GLib.MainLoop stopped")

        if self._poll_thread is not None and self._poll_thread.is_alive():
            self._poll_thread.join(timeout=5)
            self.logger.debug("Polling thread joined")

        self.conn.close()
        self.logger.info("Daemon stopped")

    # ------------------------------------------------------------------ #
    #  Schedule polling
    # ------------------------------------------------------------------ #

    def _poll_schedule_triggers(self) -> None:
        """Check all registered triggers — schedule + power polling."""
        self.logger.debug("Polling triggers (%d registered)", len(self._triggers))

        # Run poll-based triggers (power, etc.) — dispatch returns matched triggers
        poll_events = self.event_bus.poll_triggers()
        for event in poll_events:
            trigger = event.get("_trigger")
            if trigger and hasattr(trigger, "workflow_id"):
                self.logger.info(
                    "Poll trigger '%s' fired for workflow id=%s",
                    trigger.name(), trigger.workflow_id,
                )
                self._execute_workflow_actions(trigger.workflow_id)

        # Check schedule triggers
        for trigger in self._triggers:
            if not hasattr(trigger, "check"):
                continue
            try:
                if trigger.check():
                    self.logger.info(
                        "Schedule trigger fired for workflow id=%s", trigger.workflow_id
                    )
                    self._execute_workflow_actions(trigger.workflow_id)
            except Exception as exc:
                self.logger.error(
                    "Error polling schedule trigger: %s", exc, exc_info=True
                )

    # ------------------------------------------------------------------ #
    #  D-Bus dispatch bridge
    # ------------------------------------------------------------------ #

    def handle_dbus_signal(self, event_type: str, event_data: dict) -> None:
        """Bridge D-Bus signal dispatch to workflow execution.

        This method is meant to be connected as a D-Bus signal handler.
        The EventBus dispatches the event to matching triggers; when a
        trigger matches, the associated workflow's actions are executed.
        """
        self.logger.debug("D-Bus signal: %s %s", event_type, event_data)
        self.event_bus.dispatch(event_type, event_data)
        self._execute_matching_workflows(event_type, event_data)

    def _execute_matching_workflows(self, event_type: str, event_data: dict) -> None:
        """Find triggers that match the event and execute their workflows."""
        for trigger in self._triggers:
            if event_type not in trigger.get_event_types():
                continue
            try:
                if trigger.match(event_data):
                    self.logger.info(
                        "Trigger '%s' matched event '%s' for workflow id=%s",
                        trigger.name(),
                        event_type,
                        trigger.workflow_id,
                    )
                    self._execute_workflow_actions(trigger.workflow_id)
            except Exception as exc:
                self.logger.error(
                    "Error matching trigger '%s': %s", trigger.name(), exc, exc_info=True
                )

    # ------------------------------------------------------------------ #
    #  Action execution
    # ------------------------------------------------------------------ #

    def _execute_workflow_actions(self, workflow_id: int) -> None:
        """Execute all enabled actions belonging to *workflow_id*."""
        from src.models.action import Action, get_actions_for_workflow

        actions = get_actions_for_workflow(self.conn, workflow_id)
        for action in actions:
            if not action.enabled:
                continue
            self.logger.info(
                "Executing action type=%s command=%s for workflow id=%s",
                action.type,
                action.command,
                workflow_id,
            )
            try:
                result = self.executor.execute(action)
                if result["success"]:
                    self.logger.debug(
                        "Action succeeded: %s", result.get("output", "").strip()
                    )
                else:
                    self.logger.warning(
                        "Action failed: %s", result.get("error", "unknown error")
                    )
            except Exception as exc:
                self.logger.error(
                    "Exception executing action: %s", exc, exc_info=True
                )

    # ------------------------------------------------------------------ #
    #  Property accessors (useful for tests)
    # ------------------------------------------------------------------ #

    @property
    def triggers(self) -> list[Any]:
        """Return the list of registered trigger instances."""
        return list(self._triggers)

    @property
    def workflows(self) -> list[Workflow]:
        """Return the list of loaded enabled workflows."""
        return list(self._workflows)