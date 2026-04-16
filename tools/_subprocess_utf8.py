"""Subprocess helpers: UTF-8 decode on Windows (avoids cp1252 UnicodeDecodeError on git diff, etc.)."""

from __future__ import annotations

# Use instead of text=True (which follows locale / cp1252 on Windows).
UTF8_TEXT_KWARGS = {"encoding": "utf-8", "errors": "replace"}


def out_strip(proc) -> str:
    return (proc.stdout or "").strip()


def err_strip(proc) -> str:
    return (proc.stderr or "").strip()
