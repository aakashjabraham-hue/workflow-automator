import threading
from typing import Any


class EventBus:
    """Singleton event bus that routes D-Bus signals and polled events to registered triggers.

    Usage:
        bus = EventBus.get_instance()
        bus.register_trigger(my_trigger)
        bus.on_match(my_callback)    # called when a trigger matches during dispatch
        bus.dispatch("DevicePropertyChanged", {"device": "MyHeadphones", "Connected": True})
    """

    _instance = None
    _lock = threading.Lock()

    def __init__(self):
        self._triggers: list = []
        self._dbus_bus = None
        self._dbus_signal_matches: list = []
        self._match_callbacks: list = []

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

    def on_match(self, callback) -> None:
        """Register a callback invoked whenever a trigger matches during dispatch.

        The callback receives the matched trigger instance and the event_data dict.
        """
        if callback not in self._match_callbacks:
            self._match_callbacks.append(callback)

    def dispatch(self, event_type: str, event_data: dict) -> list:
        """Dispatch an event to all registered triggers whose match() returns True.

        Returns a list of triggers that matched.
        """
        matched = []
        for trigger in self._triggers:
            if event_type in trigger.get_event_types():
                if trigger.match(event_data):
                    matched.append(trigger)
                    # Notify match callbacks so the daemon can execute actions
                    for cb in self._match_callbacks:
                        try:
                            cb(trigger, event_data)
                        except Exception:
                            pass
        return matched

    def setup_dbus_listeners(self) -> None:
        """Register D-Bus signal receivers for all triggers that provide event types.

        Uses dbus.SystemBus() to listen for signals. Each trigger's get_event_types()
        returns a list of D-Bus signal names to listen for.

        Falls back gracefully if dbus-python is not installed.
        """
        try:
            import dbus
            import dbus.mainloop.glib
        except ImportError:
            return

        # Attach D-Bus to GLib main loop so async signal reception works
        dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)

        self._dbus_bus = dbus.SystemBus()

        # Collect all unique signal names from registered triggers
        signal_names: set = set()
        for trigger in self._triggers:
            for sig in trigger.get_event_types():
                signal_names.add(sig)

        for signal_name in signal_names:
            self._dbus_bus.add_signal_receiver(
                self._on_dbus_signal,
                signal_name="PropertiesChanged",
                dbus_interface="org.freedesktop.DBus.Properties",
                bus_name="org.bluez",
                path_keyword="path",
                sender_keyword="sender",
                interface_keyword="interface",
                member_keyword="member",
            )
            self._dbus_signal_matches.append(signal_name)

    def _on_dbus_signal(self, *args, **kwargs) -> None:
        """Callback invoked when a D-Bus PropertiesChanged signal is received.

        ``org.freedesktop.DBus.Properties.PropertiesChanged`` signature::

            sa{sv}as

        …where the three positional args are:
            1. interface name  (s)
            2. changed properties  (a{sv})
            3. invalidated properties  (as)

        Keyword args include the object *path* (the device path), *sender*
        (bus name), and *interface* / *member* — all injected by dbus-python.
        """
        if len(args) < 2:
            return

        iface_name = str(args[0]) if args[0] else ""
        changed_props = dict(args[1]) if len(args) > 1 and args[1] else {}
        # args[2] = invalidated properties (not needed here)

        # Extract the object path so we know which device changed
        object_path = kwargs.get("path", "")

        event_data = {
            "interface": iface_name,
            "changed_properties": changed_props,
            "object_path": object_path,
        }
        self.dispatch("PropertiesChanged", event_data)

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