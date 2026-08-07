"""Terminal colors, with automatic disable when there's no TTY.

Exists so that output redirected to a file or pipe (CI log, bug report) doesn't
come full of ANSI escapes.
"""

from __future__ import annotations

import os
import sys


def _color_enabled() -> bool:
    if os.environ.get("NO_COLOR"):
        return False
    if os.environ.get("FORCE_COLOR"):
        return True
    return sys.stdout.isatty()


if _color_enabled():
    DIM, BOLD, RESET = "\033[2m", "\033[1m", "\033[0m"
    RED, GREEN, YELLOW, CYAN = "\033[31m", "\033[32m", "\033[33m", "\033[36m"
else:
    DIM = BOLD = RESET = RED = GREEN = YELLOW = CYAN = ""

OK, WARN, FAIL = "ok", "!!", "XX"
