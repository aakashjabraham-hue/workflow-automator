"""Workflow Automator — GTK Application."""

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gio, Gtk

from src.gui.main_window import MainWindow


class WorkflowAutomatorApp(Gtk.Application):
    """Main application class for the Workflow Automator."""

    def __init__(self) -> None:
        super().__init__(
            application_id="com.workflow.Automator",
            flags=Gio.ApplicationFlags.FLAGS_NONE,
        )
        # The UI is designed around a dark (Linear-style) theme — make sure
        # it stays dark even when the system theme is light.
        settings = Gtk.Settings.get_default()
        if settings is not None:
            settings.set_property("gtk-application-prefer-dark-theme", True)

    def do_activate(self) -> None:
        """Create and show the main window when the application is activated."""
        win = MainWindow(application=self)
        win.present()
