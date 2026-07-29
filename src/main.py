"""Workflow Automator — entry point.

Usage:
    python -m src.main                  # launch the GTK4 GUI (default)
    python -m src.main --daemon         # run the background daemon
    python -m src.main --daemon --verbose  # daemon with debug logging
"""

import argparse
import logging
import sys


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="workflow-automator",
        description="Workflow Automator — automates GNOME desktop workflows.",
    )
    parser.add_argument(
        "--daemon",
        action="store_true",
        default=False,
        help="Run as a background daemon (no GUI).",
    )
    parser.add_argument(
        "--foreground",
        action="store_true",
        default=False,
        help="Run the daemon in the foreground and log to stdout.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        default=False,
        help="Enable verbose (DEBUG) logging output.",
    )
    parser.add_argument(
        "--db",
        default=None,
        help="Path to the SQLite database file (default: ~/.workflow-automator/workflows.db).",
    )
    return parser


def run_gui(argv: list[str] | None = None) -> int:
    """Launch the GTK4 GUI application."""
    import gi

    gi.require_version("Gtk", "4.0")
    from gi.repository import Gio, Gtk

    from src.app import WorkflowAutomatorApp

    app = WorkflowAutomatorApp()
    return app.run(argv)


def run_daemon(argv: list[str] | None = None) -> int:
    """Launch the background daemon."""
    from src.daemon import DaemonService

    parser = build_parser()
    args = parser.parse_args(argv)

    if args.verbose:
        logging.basicConfig(
            level=logging.DEBUG,
            format="%(asctime)s %(name)s %(levelname)s %(message)s",
            stream=sys.stdout,
        )
    else:
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s %(name)s %(levelname)s %(message)s",
            stream=sys.stdout if args.foreground else None,
        )

    import os

    default_db = os.path.expanduser("~/.workflow-automator/workflows.db")
    db_path = args.db if args.db else default_db

    # Ensure the directory exists
    os.makedirs(os.path.dirname(db_path), exist_ok=True)

    daemon = DaemonService(db_path=db_path, verbose=args.verbose)
    daemon.start()
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.daemon:
        return run_daemon(argv)
    else:
        return run_gui(argv)


if __name__ == "__main__":
    sys.exit(main())
