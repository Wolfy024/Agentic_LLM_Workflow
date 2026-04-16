"""
Semantic color palette styling functions.

Wraps the core `styled` formatter into highly semantic domain-colored variants
like `primary`, `secondary`, and `success`.
"""

from __future__ import annotations
from ui.dimming import styled, C_PRIMARY, C_SECONDARY, C_ACCENT, C_SUCCESS, C_WARNING


def primary(text: str, bold: bool = True) -> str:
    """Apply the primary brand color (indigo/violet)."""
    return styled(text, C_PRIMARY, bold)


def secondary(text: str, bold: bool = True) -> str:
    """Apply the secondary brand color (electric cyan)."""
    return styled(text, C_SECONDARY, bold)


def accent(text: str, bold: bool = True) -> str:
    """Apply the accent brand color (coral red)."""
    return styled(text, C_ACCENT, bold)


def success(text: str) -> str:
    """Apply the success color (green)."""
    return styled(text, C_SUCCESS)


def warning(text: str) -> str:
    """Apply the warning color (amber)."""
    return styled(text, C_WARNING)
