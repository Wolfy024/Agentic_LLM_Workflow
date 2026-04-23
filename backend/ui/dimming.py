"""
Base styling rendering logic and muted text formatters.

Holds the core color constants and the primary `styled` function 
which applies Rich markup syntax to strings.
"""

from __future__ import annotations

C_PRIMARY = "#6C63FF"       # indigo/violet
C_SECONDARY = "#00D9FF"     # electric cyan
C_ACCENT = "#FF6B6B"        # coral red
C_SUCCESS = "#4ADE80"       # green
C_WARNING = "#FBBF24"       # amber
C_MUTED = "#6B7280"         # gray
C_TEXT = "#E5E7EB"          # light gray
C_DIM = "#4B5563"           # dark gray
C_SURFACE = "#1F2937"       # card background hint


def styled(text: str, color: str, bold: bool = False) -> str:
    """Apply a Rich color and optional bold style to text."""
    b = " bold" if bold else ""
    return f"[{color}{b}]{text}[/]"


def muted(text: str) -> str:
    """Apply the muted text style (gray)."""
    return styled(text, C_MUTED)


def dim(text: str) -> str:
    """Apply the deeply dim text style (dark gray)."""
    return styled(text, C_DIM)
