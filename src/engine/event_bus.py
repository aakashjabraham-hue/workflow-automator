import threading
from typing import Any


class EventBus:
    """Singleton event bus that routes D-Bus signals and polled events to registered triggers.

    Usage:
        bus = EventBus.get_instance()
        bus.register_trigger(my_trigger)
        bus.dispatch("DevicePropertyChanged", {"device": "MyHeadphones", "Connected": True})
    """

    _instance = None
    _lock = threading.Lock()

    def __init__(self):
        self._triggers: list = []
        self._dbus_bus = None
        self._dbus_signal_matches: list = []

    @classmethod
    def get_instance(cls) -> "EventBus":
        """Return the singleton EventBus instance, creating it if necessary."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def register_trigger(self, trigger) -> None:
        """Register a trigger so its match() is checked on dispatched events."""
        if trigger not in self._triggers:
            self._triggers.append(trigger)

    def unregister_trigger(self, trigger) -> None:
        """Remove a trigger from the bus."""
        if trigger in self._triggers:
            self._triggers.remove(trigger)

    def dispatch(self, event_type: str, event_data: dict) -> list:
        """Dispatch an event to all registered triggers whose match() returns True.

        Returns a list of triggers that matched.
        """
        matched = []
        for trigger in self._triggers:
            if event_type in trigger.get_event_types():
                if trigger.match(event_data):
                    matched.append(trigger)
        return matched

    def setup_dbus_listeners(self) -> None:
        """Register D-Bus signal receivers for all triggers that provide event types.

        Uses dbus.SystemBus() to listen for signals. Each trigger's get_event_types()
        returns a list of D-Bus signal names to listen for.

        Falls back gracefully if dbus-python is not installed.
        """
        try:
            import dbus
        except ImportError:
            return

        self._dbus_bus = dbus.SystemBus()

        # Collect all unique signal names from registered triggers
        signal_names: set = set()
        for trigger in self._triggers:
            for sig in trigger.get_event_types():
                signal_names.add(sig)

        for signal_name in signal_names:
            match_rule = f"type='signal',interface='org.freedesktop.DBus.Properties',member='PropertiesChanged'"
            self._dbus_bus.add_signal_receiver(
                self._on_dbus_signal,
                signal_name="PropertiesChanged",
                dbus_interface="org.freedesktop.DBus.Properties",
                bus_name="org.bluez",
            )
            self._dbus_signal_matches.append(signal_name)

    def _on_dbus_signal(self, sender: str, iface: str, signal_name: str, params: tuple) -> None:
        """Callback invoked when a D-Bus signal is received."""
        if len(params) >= 2:
            iface_name = params[0]
            changed_props = params[1] if len(params) > 1 else {}
            event_data = {
                "interface": iface_name,
                "changed_properties": changed_props,
            }
            self.dispatch(signal_name, event_data)

    def poll_triggers(self) -> list[dict]:
        """Poll all triggers that support a poll() method (e.g. PowerTrigger).

        Returns a list of event dicts from triggers whose state changed.
        """
        events = []
        for trigger in self._triggers:
            if hasattr(trigger, "poll"):
                event = trigger.poll()
                if event is not None:
                    event["_trigger"] = trigger
                    events.append(event)
                    self.dispatch(event.get("type", "poll"), event)
        return events