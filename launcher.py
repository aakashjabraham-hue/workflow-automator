#!/usr/bin/env python3
"""Cwd-independent entry point for workflow-automator.

Used by the installed ``workflow-automator`` shim so the app works no
matter which directory the user invokes it from.  Equivalent to
``python -m src.main`` from the project root.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.main import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())