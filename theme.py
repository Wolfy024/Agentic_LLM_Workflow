"""MINILLM Boss -- centralized theme and UI components.

Modern, minimal aesthetic. No box-drawing characters. Uses color, spacing,
and typography to create visual hierarchy.
"""

import sys
import os

if sys.platform == "win32":
    os.system("")  # enable ANSI on Windows
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from rich.console import Console, Group
from rich.text import Text
from rich.table import Table
from rich.columns import Columns
from rich.padding import Padding
from rich.markdown import Markdown
from rich.live import Live
from rich.panel import Panel
from rich import box

console = Console(force_terminal=True)

# -- Color palette -------------------------------------------------------------

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
    b = " bold" if bold else ""
    return f"[{color}{b}]{text}[/]"


def primary(text: str, bold: bool = True) -> str:
    return styled(text, C_PRIMARY, bold)


def secondary(text: str, bold: bool = True) -> str:
    return styled(text, C_SECONDARY, bold)


def accent(text: str, bold: bool = True) -> str:
    return styled(text, C_ACCENT, bold)


def success(text: str) -> str:
    return styled(text, C_SUCCESS)


def warning(text: str) -> str:
    return styled(text, C_WARNING)


def muted(text: str) -> str:
    return styled(text, C_MUTED)


def dim(text: str) -> str:
    return styled(text, C_DIM)


# -- Visual components ---------------------------------------------------------

def divider(char: str = "-", width: int = 60, color: str = C_DIM) -> str:
    return f"[{color}]{char * width}[/]"


def label_value(label: str, value: str, label_width: int = 14) -> str:
    return f"  {muted(label.ljust(label_width))} {styled(value, C_TEXT, bold=True)}"


def status_dot(active: bool = True) -> str:
    return success("*") if active else styled("*", C_DIM)


def progress_bar(pct: float, width: int = 30) -> str:
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
    prefix = f"{icon} " if icon else ""
    return f"\n  {primary(prefix + title)}\n  {styled('-' * (len(title) + len(prefix) + 1), C_DIM)}"


BANNER = f"""
  {styled("M I N I L L M", C_PRIMARY, bold=True)}   {styled("B O S S", C_SECONDARY, bold=True)}

  {muted("local model agent")}  {dim("//")}  {muted("46 tools")}  {dim("//")}  {muted("256K context")}  {dim("//")}  {muted("streaming")}
"""

WELCOME_TIP = f"  {muted('Type a message to start. Use')} {primary('/help', bold=False)} {muted('for commands.')}"


def print_banner(config: dict, workspace: str):
    console.print()
    console.print(BANNER)
    console.print(f"  {divider(width=72)}")
    console.print()
    model_short = config.get("model", "unknown").split("/")[-1].split(":")[0]
    console.print(label_value("workspace", workspace))
    console.print(label_value("model", model_short))
    console.print(label_value("context", f"{config.get('context_window', 262144):,} tokens"))
    console.print(label_value("output cap", f"{config.get('max_tokens', 131072):,} tokens"))
    console.print(label_value("streaming", f"{status_dot(True)} enabled"))
    console.print(label_value("search", f"{status_dot(bool(config.get('serper_api_key')))} serper"))
    console.print()
    console.print(f"  {divider(width=72)}")
    console.print(WELCOME_TIP)
    console.print()


def print_help():
    console.print()
    console.print(section_header("Commands"))
    console.print()
    cmds = [
        ("/help", "Show this help"),
        ("/tools", "List all available tools"),
        ("/context", "Context window usage"),
        ("/workspace [path]", "Show / change workspace"),
        ("/compact", "Trim conversation context"),
        ("/clear", "Reset conversation"),
        ("/save [name]", "Save conversation to disk"),
        ("/load [name]", "Load conversation (no name = list)"),
        ("/yolo", "Auto-approve all destructive ops"),
        ("/safe", "Restore manual approval"),
        ("/multi", "Toggle multiline input mode"),
        ("/verbose", "Toggle full tool output"),
        ("/exit", "Quit"),
    ]
    for cmd, desc in cmds:
        console.print(f"    {secondary(cmd, bold=False):36s} {muted(desc)}")
    console.print()
    console.print(f"  {muted('Destructive operations require explicit y to approve.')}")
    console.print(f"  {muted('Context auto-compacts with summary at 80%.')}")
    console.print()


def print_tools(schemas: list[dict]):
    from permissions import DESTRUCTIVE_TOOLS, CONTEXT_DESTRUCTIVE_TOOLS

    all_destructive = DESTRUCTIVE_TOOLS | set(CONTEXT_DESTRUCTIVE_TOOLS.keys())

    console.print()

    categories: dict[str, list] = {
        "Files": [],
        "Git Local": [],
        "Git Remote": [],
        "Search & Web": [],
        "System": [],
    }

    for s in schemas:
        name = s["function"]["name"]
        desc = s["function"]["description"].split(".")[0]
        locked = name in all_destructive

        if name in ("git_push", "git_pull", "git_fetch", "git_clone",
                    "git_remote", "git_credential_check", "github_api"):
            cat = "Git Remote"
        elif name.startswith("git_"):
            cat = "Git Local"
        elif name in ("web_search", "web_search_news", "web_search_images", "read_url", "search_files"):
            cat = "Search & Web"
        elif name in ("run_command", "env_info", "list_processes"):
            cat = "System"
        else:
            cat = "Files"

        categories[cat].append((name, desc, locked))

    for cat, tools in categories.items():
        if not tools:
            continue
        console.print(section_header(cat))
        console.print()
        for name, desc, locked in tools:
            lock_icon = accent("~", bold=False) if locked else " "
            console.print(f"    {lock_icon} {secondary(name, bold=False):30s} {muted(desc)}")
        console.print()

    console.print(f"  {muted(f'{len(schemas)} tools total')}  {dim('//')}  {accent('~', bold=False)} {muted('= needs approval')}")
    console.print()


def print_context(info: dict):
    console.print()
    console.print(section_header("Context Window"))
    console.print()

    used = info["tokens_used"]
    total = info["context_window"]
    pct = used / total if total else 0

    console.print(f"    {progress_bar(pct, width=40)}")
    console.print()
    remaining = info["remaining"]
    max_out = info["max_output"]
    msg_count = info["messages"]
    console.print(f"    {muted('used'):14s} {styled(f'~{used:,}', C_TEXT)} {muted('tokens')}")
    console.print(f"    {muted('remaining'):14s} {styled(f'~{remaining:,}', C_TEXT)} {muted('tokens')}")
    console.print(f"    {muted('output reserve'):14s} {styled(f'{max_out:,}', C_TEXT)} {muted('tokens')}")
    console.print(f"    {muted('messages'):14s} {styled(str(msg_count), C_TEXT)}")
    console.print()


# -- Tool call display ---------------------------------------------------------

def print_tool_call(name: str, args: dict):
    args_short = {}
    for k, v in args.items():
        if isinstance(v, str) and len(v) > 100:
            args_short[k] = v[:100] + "..."
        else:
            args_short[k] = v
    args_str = ", ".join(f"{styled(k, C_MUTED)}={styled(repr(v), C_TEXT)}" for k, v in args_short.items())
    console.print(f"\n  {styled('>', C_PRIMARY)} {secondary(name, bold=True)}({args_str})")


def print_tool_result(result: str, success: bool = True, verbose: bool = False):
    color = C_DIM if success else C_ACCENT
    max_len = 500 if not verbose else 50_000
    max_lines = 20 if not verbose else 500
    if len(result) > max_len:
        display = result[:max_len] + f"\n{muted(f'  ... {len(result):,} chars total')}"
    else:
        display = result
    lines = display.split("\n")
    console.print(f"  {styled(':', color)}")
    for line in lines[:max_lines]:
        console.print(f"  {styled(':', color)} {dim(line)}")
    if len(lines) > max_lines:
        console.print(f"  {styled(':', color)} {muted(f'... {len(lines) - max_lines} more lines')}")
    console.print(f"  {styled('.', color)}")


def print_permission_approved():
    console.print(f"  {success('  approved')}")


def print_permission_denied():
    console.print(f"  {accent('  denied')}")


def print_token_status(info: dict):
    """Dim status line after each turn showing token usage."""
    used = info["tokens_used"]
    total = info["context_window"]
    pct = used / total if total else 0
    remaining = info["remaining"]
    msgs = info["messages"]
    console.print(
        f"\n  {dim(f'~{used:,} in  //  {remaining:,} free  //  {pct:.1%} used  //  {msgs} msgs')}"
    )


class StreamingMarkdown:
    """Renders markdown progressively using Rich Live display."""

    def __init__(self):
        self._buffer = ""
        self._live = Live(
            "",
            console=console,
            refresh_per_second=8,
            vertical_overflow="visible",
        )

    def start(self):
        console.print()
        self._buffer = ""
        self._live.start()

    def feed(self, text: str):
        self._buffer += text
        try:
            padded = Padding(Markdown(self._buffer, code_theme="monokai"), (0, 0, 0, 4))
            self._live.update(padded)
        except Exception:
            self._live.update(Text(self._buffer))

    def finish(self) -> str:
        self._live.stop()
        console.print()
        return self._buffer


def render_markdown(text: str):
    """Render a complete markdown string."""
    console.print()
    console.print(Padding(Markdown(text, code_theme="monokai"), (0, 0, 0, 4)))
    console.print()


def print_stream_start():
    console.print()
    console.print(f"  {styled('*', C_PRIMARY)} ", end="")


def print_auto_compact(freed: int, old_pct: float, new_pct: float):
    console.print(
        f"\n  {warning('compacted')} {muted(f'dropped {freed} messages')} "
        f"{muted(f'{old_pct:.0%} -> {new_pct:.0%}')}"
    )


def print_error(msg: str):
    console.print(f"\n  {accent('error')} {muted(msg)}")


def print_goodbye():
    console.print(f"\n  {muted('goodbye.')}\n")
