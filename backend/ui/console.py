"""
Global Rich console instance.

Provides the configured Rich Console used for all terminal output sizing
and rendering operations throughout the UI modules.
"""

from __future__ import annotations
import sys
import os
from rich.console import Console

if sys.platform == "win32":
    os.system("")  # enable ANSI on Windows
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

console = Console(force_terminal=True)
