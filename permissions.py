"""Permission system -- gates destructive operations behind user approval.

Supports context-aware gating (e.g. github_api only destructive for non-GET)
and a session-level yolo mode to skip prompts.
"""

from prompt_toolkit import prompt
from prompt_toolkit.formatted_text import HTML
from theme import console, accent, muted, styled, warning, success, C_WARNING, C_TEXT, C_MUTED, C_ACCENT, C_DIM

DESTRUCTIVE_TOOLS = {
    "write_file",
    "append_to_file",
    "patch_file",
    "delete_file",
    "replace_in_file",
    "move_file",
    "create_directory",
    "git_init",
    "git_commit",
    "git_checkout",
    "git_branch_delete",
    "git_reset",
    "git_stash",
    "git_push",
    "git_pull",
    "git_clone",
    "run_command",
}

CONTEXT_DESTRUCTIVE_TOOLS = {
    "github_api": lambda args: args.get("method", "GET") != "GET",
    "git_tag": lambda args: args.get("action") in ("create", "delete"),
    "git_remote": lambda args: args.get("action") in ("add", "remove"),
}

_yolo_mode = False


def set_yolo(enabled: bool):
    global _yolo_mode
    _yolo_mode = enabled


def is_yolo() -> bool:
    return _yolo_mode


def _is_destructive(tool_name: str, args: dict) -> bool:
    if tool_name in DESTRUCTIVE_TOOLS:
        return True
    checker = CONTEXT_DESTRUCTIVE_TOOLS.get(tool_name)
    if checker and checker(args):
        return True
    return False


def _render_args(args: dict) -> str:
    lines = []
    for k, v in args.items():
        val = str(v)
        if len(val) > 200:
            val = val[:200] + "..."
        lines.append(f"    {muted(k)} {styled(val, C_TEXT)}")
    return "\n".join(lines)


def ask_permission(tool_name: str, args: dict) -> bool:
    if not _is_destructive(tool_name, args):
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
