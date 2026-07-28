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

    def do_activate(self) -> None:
        """Create and show the main window when the application is activated."""
        win = MainWindow(application=self)
        win.present()
