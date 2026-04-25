"""Info display commands: /help, /tools, /context, /memory."""

from __future__ import annotations
from typing import TYPE_CHECKING

from ui.help import print_help, print_tools
from ui.context_logs import print_context, print_memory_stats

if TYPE_CHECKING:
    from repl.slash import CommandContext


def cmd_help(ctx: CommandContext) -> None:
    """Show the help menu."""
    print_help()


def cmd_tools(ctx: CommandContext) -> None:
    """List all registered tools."""
    print_tools(ctx.runner.state.tool_schemas)


def cmd_context(ctx: CommandContext) -> None:
    """Display token usage stats."""
    u = ctx.runner.llm.last_usage
    info = {
        "messages": len(ctx.runner.state.messages),
        "tokens_used": ctx.runner.state.context_used(u),
        "tokens_source": "api" if u else "estimate",
    }
    print_context(info)


def cmd_memory(ctx: CommandContext) -> None:
    """Display retrieval memory/index stats."""
    try:
        from tools.fs.search import get_retrieval_memory_stats
        info = get_retrieval_memory_stats()
    except Exception:
        info = {
            "visited_files": 0,
            "important_symbols": 0,
            "summaries": 0,
            "vector_docs": 0,
            "memory_file": "unavailable",
            "vector_index_file": "unavailable",
        }
    print_memory_stats(info)
