"""Info display commands: /help, /tools, /context."""

from __future__ import annotations
from typing import TYPE_CHECKING

from ui.help import print_help, print_tools
from ui.context_logs import print_context

if TYPE_CHECKING:
    from repl.slash import CommandContext


def cmd_help(ctx: CommandContext) -> None:
    """Show the help menu."""
    print_help()


def cmd_tools(ctx: CommandContext) -> None:
    """List all registered tools."""
    print_tools(ctx.runner.state.tool_schemas)


def cmd_context(ctx: CommandContext) -> None:
    """Display context window usage stats."""
    u = ctx.runner.llm.last_usage
    info = {
        "messages": len(ctx.runner.state.messages),
        "tokens_used": ctx.runner.state.context_used(u),
        "tokens_source": "api" if u else "estimate",
        "context_window": ctx.runner.state.context_window,
        "max_output": ctx.runner.state.max_output,
        "remaining": ctx.runner.state.context_remaining(u),
        "pct_used": f"{ctx.runner.state.context_used(u) / ctx.runner.state.context_window:.1%}",
    }
    print_context(info)
