"""
Help menus and tool inspection UI blocks.

Displays available slash-commands and detailed lists of tool schemas.
"""

from __future__ import annotations
from ui.console import console
from ui.palette import secondary, accent, success, primary
from ui.dimming import muted, dim, styled, C_TEXT
from ui.components import section_header

# Canonical slash commands for /help and REPL tab-completion (command token only).
SLASH_COMMAND_SPECS: list[tuple[str, str]] = [
    ("/help", "Show this help"),
    ("/tools", "List all available tools"),
    ("/context", "Token usage"),
    ("/memory", "Show retrieval memory/index stats"),
    ("/workspace", "Show / change workspace"),
    ("/compact", "Trim conversation context"),
    ("/clear", "Reset conversation"),
    ("/save", "Save conversation to disk"),
    ("/load", "Load conversation (no name = list)"),
    ("/yolo", "Auto-approve all destructive ops"),
    ("/safe", "Restore manual approval"),
    ("/multi", "Toggle multiline input mode"),
    ("/verbose", "Toggle full tool output"),
    ("/confirm", "Toggle diff preview before replace_in_file / patch_file"),
    ("/model", "List or switch models from API"),
    ("/profile", "Permission profile (ci = read-only tools)"),
    ("/task", "Inject a structured task checklist into context"),
    ("/plan", "Add planning checklist message (use with /task)"),
    ("/recipe", "Load prompt from .minillm/recipes/<name>.json"),
    ("/export", "Export conversation to markdown"),
    ("/watch", "File watch status / toggle / auto|batch / run pending now"),
    ("/image", "Workspace image path → base64 to multimodal model (see max_image_mb)"),
    ("/exit", "Quit"),
]

# Optional wider labels for the help table (completion uses SLASH_COMMAND_SPECS keys).
_SLASH_HELP_LABEL: dict[str, str] = {
    "/workspace": "/workspace [path]",
    "/save": "/save [name]",
    "/load": "/load [name]",
    "/model": "/model [name|#]",
    "/profile": "/profile strict|dev|ci",
    "/task": "/task <text>",
    "/recipe": "/recipe <name>",
    "/export": "/export [file]",
    "/watch": "/watch [on|off|mode|flush]",
    "/image": "/image [path] [instruction]",
}


def _slash_help_label(cmd: str) -> str:
    return _SLASH_HELP_LABEL.get(cmd, cmd)


def print_help() -> None:
    """Print the main application help commands list."""
    console.print()
    console.print(section_header("Commands"))
    console.print()
    for cmd, desc in SLASH_COMMAND_SPECS:
        label = _slash_help_label(cmd)
        console.print(f"    {secondary(label, bold=False):36s} {muted(desc)}")
    console.print()
    console.print(f"  {muted('File create/edit in workspace is allowed; delete and other destructive ops need y.')}")
    console.print(f"  {muted('Context compaction is disabled; server handles context sizing.')}")
    console.print()


def print_tools(schemas: list[dict]) -> None:
    """Prints categorized list of available tool functions."""
    from core.permissions_checks import DESTRUCTIVE_TOOLS, CONTEXT_DESTRUCTIVE_TOOLS
    all_destructive = DESTRUCTIVE_TOOLS | set(CONTEXT_DESTRUCTIVE_TOOLS.keys())
    console.print()

    categories: dict[str, list] = {
        "Files": [], "Git Local": [], "Git Remote": [],
        "Search & Web": [], "System": [],
    }

    for s in schemas:
        name = s["function"]["name"]
        desc = s["function"]["description"].split(".")[0]
        locked = name in all_destructive

        if name in ("git_push", "git_pull", "git_fetch", "git_clone",
                    "git_remote", "git_credential_check", "github_api"):
            cat = "Git Remote"
        elif name.startswith("git_"): cat = "Git Local"
        elif name in (
            "web_search",
            "web_search_news",
            "web_search_images",
            "read_url",
            "download_url",
            "search_files",
        ):
            cat = "Search & Web"
        elif name in ("run_command", "run_diagnostics", "env_info", "list_processes"):
            cat = "System"
        else: cat = "Files"
        categories[cat].append((name, desc, locked))

    for cat, tools in categories.items():
        if not tools: continue
        console.print(section_header(cat))
        console.print()
        for name, desc, locked in tools:
            lock_icon = accent("~", bold=False) if locked else " "
            console.print(f"    {lock_icon} {secondary(name, bold=False):30s} {muted(desc)}")
        console.print()
    console.print(f"  {muted(f'{len(schemas)} tools total')}  {dim('//')}  {accent('~', bold=False)} {muted('= needs approval')}")
    console.print()


def print_models(models: list[dict], current_model: str) -> None:
    """Prints enumeration of LLM models retrieved from the endpoint."""
    console.print()
    console.print(section_header("Available Models"))
    console.print()
    for i, m in enumerate(models, 1):
        mid = m.get("id", "unknown")
        is_current = mid == current_model
        marker = success("*") if is_current else " "
        name_style = styled(mid, C_TEXT, bold=True) if is_current else secondary(mid, bold=False)
        index_str = muted(f"{i:>3}.")
        console.print(f"    {marker} {index_str} {name_style}")
    console.print()
    console.print(f"  {muted(f'{len(models)} model(s)')}")
    console.print(f"  {muted('Use')} {primary('/model <number or name>', bold=False)} {muted('to switch.')}")
    console.print()
