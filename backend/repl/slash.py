"""
Slash command dispatcher for the LLM Orchestrator REPL.

Routes slash commands to individual handler functions via a dispatch table.
Each handler lives in repl/commands/ and receives a standardized CommandContext.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass, field

from agent.runner import AgentRunner
from agent.state import save_session
from core.prefs import save_prefs
from ui.console import console
from ui.context_logs import print_goodbye
from ui.dimming import muted
from ui.palette import success

from repl.commands import COMMAND_DISPATCH


@dataclass
class CommandContext:
    """Shared state passed to every slash command handler."""
    runner: AgentRunner
    config: dict
    prefs: dict
    watch_ctx: dict
    multiline_mode: bool
    parts: list[str] = field(default_factory=list)

    @property
    def arg(self) -> str:
        """First argument after the command, stripped."""
        return (self.parts[1] if len(self.parts) > 1 else "").strip()

    @property
    def rest(self) -> str:
        """Everything after the command token."""
        return (self.parts[1] if len(self.parts) > 1 else "").strip()


def _auto_save_session(runner: AgentRunner, prefs: dict) -> None:
    """Auto-save the current session with a timestamp name."""
    if len(runner.state.messages) <= 1:
        return  # Nothing to save (only system prompt)
    name = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    path = save_session(runner.state, name, model=runner.llm.model)
    prefs["last_session_name"] = name
    save_prefs(prefs)
    console.print(success(f"  session auto-saved: {name}"))


def execute_slash_command(
    cmd: str,
    parts: list[str],
    runner: AgentRunner,
    watch_ctx: dict,
    multiline_mode: bool,
    config: dict,
    prefs: dict,
) -> tuple[bool, bool]:
    """Returns (should_exit, new_multiline_mode)."""
    if cmd in ("/exit", "/quit", "/q"):
        print_goodbye()
        return True, multiline_mode

    ctx = CommandContext(
        runner=runner,
        config=config,
        prefs=prefs,
        watch_ctx=watch_ctx,
        multiline_mode=multiline_mode,
        parts=parts,
    )

    handler = COMMAND_DISPATCH.get(cmd)
    if handler is None:
        console.print(muted(f"  unknown command: {cmd}"))
        return False, multiline_mode

    result = handler(ctx)

    # Handlers return None (no-op), or (should_exit, new_multiline_mode)
    if result is None:
        return False, ctx.multiline_mode
    return result
