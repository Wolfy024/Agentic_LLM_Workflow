"""
Permission prompts logic.

Handles interactions with users via prompt_toolkit to confirm
destructive operations or file edits, supporting 'yolo' mode to bypass.
"""

from __future__ import annotations
from prompt_toolkit import prompt
from prompt_toolkit.formatted_text import HTML

from ui.console import console
from ui.dimming import styled, muted, C_WARNING, C_TEXT
from ui.palette import warning
from core.permissions_checks import is_destructive

_yolo_mode = False


def set_yolo(enabled: bool) -> None:
    """Enable or disable global bypass of interactive prompts."""
    global _yolo_mode
    _yolo_mode = enabled


def is_yolo() -> bool:
    """Check if yolo bypass is active."""
    return _yolo_mode


def _render_args(args: dict) -> str:
    """Formats a dictionary of tool arguments for console display."""
    lines = []
    for k, v in args.items():
        val = str(v)
        if len(val) > 200:
            val = val[:200] + "..."
        lines.append(f"    {muted(k)} {styled(val, C_TEXT)}")
    return "\n".join(lines)


def ask_edit_confirmation(path: str, diff_text: str) -> bool:
    """Confirm a unified diff before applying replace_in_file / patch_file."""
    if _yolo_mode:
        console.print(f"  {warning('yolo')} {muted('edit preview auto-approved')}")
        return True
    console.print()
    console.print(f"  {styled('!', C_WARNING)} {warning('edit preview')} {muted(path)}")
    import core.runtime_config as rc
    limit = int(rc.get("diff_preview_limit", 6000))
    preview = diff_text if len(diff_text) <= limit else diff_text[:limit] + "\n... (truncated)"
    for line in preview.splitlines():
        console.print(f"    {muted(line)}")
    console.print()
    try:
        answer = prompt(
            HTML("  <style fg='#FBBF24'><b>y</b></style><style fg='#6B7280'>/n apply this edit?  </style>")
        ).strip().lower()
    except (EOFError, KeyboardInterrupt):
        return False
    return answer in ("y", "yes")


def ask_permission(tool_name: str, args: dict) -> bool:
    """Ask for explicit execution permission on destructive tasks."""
    if not is_destructive(tool_name, args):
        return True

    if _yolo_mode:
        console.print(f"  {warning('yolo')} {muted('auto-approved')}")
        return True

    console.print()
    console.print(f"  {styled('!', C_WARNING)} {warning('permission required')}")
    console.print(f"    {muted('action')} {styled(tool_name, C_TEXT, bold=True)}")
    console.print(_render_args(args))
    console.print()

    try:
        answer = prompt(
            HTML("  <style fg='#FBBF24'><b>y</b></style><style fg='#6B7280'>/n  </style>")
        ).strip().lower()
    except (EOFError, KeyboardInterrupt):
        return False

    return answer in ("y", "yes")
