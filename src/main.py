"""Workflow Automator — CLI entry point.

Usage:
    python -m src.main                    # start the daemon in the background
    python -m src.main --foreground       # run in the foreground (log to stdout)
    python -m src.main --daemon --verbose # background daemon with debug logging
"""

import argparse
import logging
import sys

from src.daemon import DaemonService


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="workflow-automator",
        description="Workflow Automator background daemon",
    )
    parser.add_argument(
        "--daemon",
        action="store_true",
        default=False,
        help="Run as a background daemon (detached from the terminal).",
    )
    parser.add_argument(
        "--foreground",
        action="store_true",
        default=False,
        help="Run in the foreground and log to stdout.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        default=False,
        help="Enable verbose (DEBUG) logging output.",
    )
    parser.add_argument(
        "--db",
        default=":memory:",
        help="Path to the SQLite database file (default: :memory:).",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
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

    daemon = DaemonService(db_path=args.db, verbose=args.verbose)

    if args.daemon or not args.foreground:
        # Run the daemon (blocks until stopped).
        # In a real deployment this would double-fork or use systemd.
        daemon.start()
    else:
        # Foreground mode — start but do NOT block the event loop
        # indefinitely; useful for testing and interactive use.
        daemon.start()

    return 0


if __name__ == "__main__":
    sys.exit(main())