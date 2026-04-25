"""
Slash command handler registry.

Each submodule defines one or more handler functions.
COMMAND_DISPATCH maps command strings to their handlers.
"""

from __future__ import annotations

from repl.commands.session import cmd_save, cmd_load, cmd_clear, cmd_compact, cmd_export
from repl.commands.config import (
    cmd_model, cmd_profile, cmd_workspace, cmd_yolo, cmd_safe,
    cmd_verbose, cmd_confirm, cmd_multi,
)
from repl.commands.info import cmd_help, cmd_tools, cmd_context, cmd_memory
from repl.commands.inject import cmd_task, cmd_plan, cmd_recipe, cmd_image
from repl.commands.watch import cmd_watch

COMMAND_DISPATCH: dict[str, callable] = {
    "/help": cmd_help,
    "/tools": cmd_tools,
    "/context": cmd_context,
    "/memory": cmd_memory,
    "/clear": cmd_clear,
    "/compact": cmd_compact,
    "/workspace": cmd_workspace,
    "/yolo": cmd_yolo,
    "/safe": cmd_safe,
    "/multi": cmd_multi,
    "/save": cmd_save,
    "/load": cmd_load,
    "/verbose": cmd_verbose,
    "/confirm": cmd_confirm,
    "/model": cmd_model,
    "/profile": cmd_profile,
    "/recipe": cmd_recipe,
    "/export": cmd_export,
    "/image": cmd_image,
    "/task": cmd_task,
    "/plan": cmd_plan,
    "/watch": cmd_watch,
}
