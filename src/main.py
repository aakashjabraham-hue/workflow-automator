"""Workflow Automator — entry point.

Usage:
    python -m src.main                       # launch the GTK4 GUI (default)
    python -m src.main dashboard             # same as above (explicit)
    python -m src.main daemon                # run the background daemon
    python -m src.main daemon --verbose      # daemon with debug logging
    python -m src.main update                # pull the latest from GitHub
    python -m src.main install               # install/repair the CLI
    python -m src.main uninstall             # remove the project
    python -m src.main version               # show installed version

Backward-compatible flags are preserved: ``--daemon``, ``--foreground``,
``--verbose`` and ``--db`` still work exactly as before.
"""

import argparse
import logging
import os
import sys


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="workflow-automator",
        description="Workflow Automator — automates desktop workflows on "
                    "Linux, macOS and Windows.",
    )
    parser.add_argument(
        "command",
        nargs="?",
        default=None,
        choices=["dashboard", "daemon", "install", "update", "uninstall", "version"],
        help="What to do: dashboard (open the app), daemon, install, "
             "update, uninstall, version.",
    )
    parser.add_argument(
        "--daemon",
        action="store_true",
        default=False,
        help="Run as a background daemon (no GUI). Shorthand for `daemon`.",
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
        help="Path to the SQLite database file (default: platform data dir).",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"workflow-automator {_read_version()}",
        help="Show the installed version and exit.",
    )
    parser.add_argument(
        "--skip-download",
        action="store_true",
        default=False,
        help="(install only) App files already in place — skip re-downloading "
             "from GitHub. Used by the one-liner installers.",
    )
    return parser


def _read_version() -> str:
    try:
        from src import __version__

        return __version__
    except Exception:  # pragma: no cover - defensive
        return "0.0.0"


def run_gui(argv: list[str] | None = None) -> int:
    """Launch the GTK4 GUI application (the automation dashboard)."""
    try:
        import gi  # noqa: F401

        gi.require_version("Gtk", "4.0")
    except (ImportError, ValueError) as exc:
        print(
            "  ⚠️   The dashboard GUI needs GTK4 (PyGObject).\n"
            f"       ({exc})\n"
            "       On Linux: sudo apt install python3-gi gir1.2-gtk-4.0\n"
            "       On macOS: brew install pygobject3 gtk4\n"
            "       On Windows: install GTK4 for Python (see README).\n"
            "       Headless automation still works: workflow-automator daemon",
            file=sys.stderr,
        )
        return 1

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

    from src.paths import default_db_path

    db_path = args.db if args.db else default_db_path()

    # Ensure the directory exists
    os.makedirs(os.path.dirname(db_path), exist_ok=True)

    daemon = DaemonService(db_path=db_path, verbose=args.verbose)
    daemon.start()
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    # Backward compatibility: the old `--daemon` flag.
    if args.daemon:
        return run_daemon(argv)

    command = args.command

    if command in (None, "dashboard"):
        return run_gui(argv)
    if command == "daemon":
        return run_daemon(argv)
    if command == "version":
        from src.self_update import cmd_version

        cmd_version()
        return 0
    if command == "install":
        from src.self_update import cmd_install

        cmd_install(skip_download=args.skip_download)
        return 0
    if command == "update":
        from src.self_update import cmd_update

        cmd_update()
        return 0
    if command == "uninstall":
        from src.self_update import cmd_uninstall

        cmd_uninstall()
        return 0

    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())