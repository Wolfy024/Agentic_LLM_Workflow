"""
UI layout components and small visual blocks.

Provides functions to render horizontal dividers, key-value labels,
progress bars, and section headers styled precisely.
"""

from __future__ import annotations
from ui.dimming import styled, muted, dim, C_DIM, C_TEXT, C_SUCCESS, C_WARNING, C_ACCENT
from ui.palette import primary, success


def divider(char: str = "-", width: int = 60, color: str = C_DIM) -> str:
    """Create a horizontal divider line."""
    return f"[{color}]{char * width}[/]"


def label_value(label: str, value: str, label_width: int = 14) -> str:
    """Format a key-value pair aligned nicely."""
    return f"  {muted(label.ljust(label_width))} {styled(value, C_TEXT, bold=True)}"


def status_dot(active: bool = True) -> str:
    """Return a stylized status indicator dot/asterisk."""
    return success("*") if active else styled("*", C_DIM)


def progress_bar(pct: float, width: int = 30) -> str:
    """Render a textual progress bar visualization based on percentage."""
    filled = int(pct * width)
    empty = width - filled
    if pct < 0.5:
        color = C_SUCCESS
    elif pct < 0.8:
        color = C_WARNING
    else:
        color = C_ACCENT
    bar = f"[{color}]{'=' * filled}[/][{C_DIM}]{'-' * empty}[/]"
    return f"{bar} {muted(f'{pct:.0%}')}"


def section_header(title: str, icon: str = "") -> str:
    """Create a stylized section header block."""
    prefix = f"{icon} " if icon else ""
    return f"\n  {primary(prefix + title)}\n  {styled('-' * (len(title) + len(prefix) + 1), C_DIM)}"
