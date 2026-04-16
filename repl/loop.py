"""REPL prompt loop: history, completion, watch injection, slash dispatch."""

from __future__ import annotations

import os

from prompt_toolkit import HTML, prompt
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
from prompt_toolkit.history import FileHistory
from prompt_toolkit.shortcuts import CompleteStyle

from agent.runner import AgentRunner
from .slash import execute_slash_command
from ui.console import console
from ui.context_logs import print_goodbye
from ui.dimming import muted
from ui.help import SLASH_COMMAND_SPECS
from ui.palette import warning
from ui.repl_bindings import build_repl_key_bindings
from ui.slash_complete import SlashCommandCompleter

HISTORY_FILE = os.path.join(os.path.expanduser("~"), ".minillm", ".history")

_slash_completer = SlashCommandCompleter(SLASH_COMMAND_SPECS)


def run_repl(runner: AgentRunner, watch_ctx: dict, config: dict, prefs: dict):
    try:
        history = FileHistory(HISTORY_FILE)
    except Exception:
        history = None

    multiline_mode = False

    while True:
        watch_state = watch_ctx.get("service")
        if watch_state and watch_state.state.mode == "auto":
            injected = watch_state.state.take_auto_inject_message()
            if injected:
                console.print(muted("  [watch] workspace changed — running follow-up turn"))
                runner.chat_turn(injected)
        elif watch_state and watch_state.state.mode == "batch":
            notice = watch_state.state.peek_batch_notice()
            if notice:
                console.print(warning(f"  {notice}"))

        try:
            console.print()
            prompt_str = "  >> " if multiline_mode else "  > "
            user_input = prompt(
                HTML(f"<style fg='#6C63FF' bold='true'>{prompt_str}</style>"),
                history=history,
                auto_suggest=AutoSuggestFromHistory() if history else None,
                completer=_slash_completer,
                complete_style=CompleteStyle.MULTI_COLUMN,
                complete_while_typing=True,
                key_bindings=build_repl_key_bindings(),
                multiline=multiline_mode,
            ).strip()
        except (EOFError, KeyboardInterrupt):
            print_goodbye()
            break

        if not user_input:
            continue

        watch_state = watch_ctx.get("service")
        if watch_state and watch_state.state.mode == "batch" and not user_input.startswith("/"):
            batch_pre = watch_state.state.consume_batch_prefix()
            if batch_pre:
                user_input = f"{batch_pre}\n\n{user_input}"

        if user_input.startswith("/"):
            cmd = user_input.lower().split()[0]
            parts = user_input.split(maxsplit=1)
            exit_flag, multiline_mode = execute_slash_command(
                cmd, parts, runner, watch_ctx, multiline_mode, config, prefs
            )
            if exit_flag:
                break
            continue

        runner.chat_turn(user_input)
