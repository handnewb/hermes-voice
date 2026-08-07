"""Cores de terminal, com desligamento automatico quando nao ha TTY.

Existe para que a saida redirecionada para arquivo ou pipe (log de CI, relatorio
de bug) nao venha cheia de escape ANSI.
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
