"""Configuration commands: /model, /profile, /workspace, /yolo, /safe, /verbose, /confirm, /multi."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

from core.cache import get_cached_models, set_cached_models
from core.permissions_checks import get_profile, set_profile
from core.permissions_prompts import set_yolo
from core.prefs import save_prefs
from tools.registry import WORKSPACE, set_workspace
from ui.components import label_value
from ui.console import console
from ui.context_logs import print_error
from ui.dimming import muted
from ui.help import print_models
from ui.palette import success, warning

if TYPE_CHECKING:
    from repl.slash import CommandContext


def cmd_workspace(ctx: CommandContext) -> None:
    """Show or change workspace directory."""
    if len(ctx.parts) > 1:
        new_ws = os.path.abspath(ctx.parts[1])
        if os.path.isdir(new_ws):
            set_workspace(new_ws)
            console.print(success(f"  workspace -> {new_ws}"))
            ws = ctx.watch_ctx.get("service")
            if ws and not ws.set_workspace(new_ws):
                console.print(warning("  watch: could not reattach"))
        else:
            print_error(f"Not a directory: {new_ws}")
    else:
        console.print(label_value("workspace", WORKSPACE))


def cmd_yolo(ctx: CommandContext) -> None:
    """Enable auto-approve for destructive ops."""
    set_yolo(True)
    console.print(warning("  YOLO mode ON -- all destructive ops auto-approved"))


def cmd_safe(ctx: CommandContext) -> None:
    """Restore manual approval for destructive ops."""
    set_yolo(False)
    console.print(success("  safe mode ON -- destructive ops require approval"))


def cmd_multi(ctx: CommandContext) -> None:
    """Toggle multiline input mode."""
    ctx.multiline_mode = not ctx.multiline_mode
    console.print(muted(f"  multiline input {'ON' if ctx.multiline_mode else 'OFF'}"))


def cmd_verbose(ctx: CommandContext) -> None:
    """Toggle verbose tool output."""
    cur = ctx.prefs.get("verbose", False)
    ctx.prefs["verbose"] = not cur
    ctx.runner.executor.verbose = ctx.prefs["verbose"]
    save_prefs(ctx.prefs)
    console.print(success(f"  verbose tool output {'ON' if ctx.prefs['verbose'] else 'OFF'}"))


def cmd_confirm(ctx: CommandContext) -> None:
    """Toggle edit diff preview."""
    cur = ctx.prefs.get("confirm_edits", True)
    ctx.prefs["confirm_edits"] = not cur
    ctx.runner.executor.confirm_edits = ctx.prefs["confirm_edits"]
    save_prefs(ctx.prefs)
    console.print(success(f"  edit diff preview before apply {'ON' if ctx.prefs['confirm_edits'] else 'OFF'}"))


def _fetch_models(ctx: CommandContext) -> list[dict]:
    """Fetch models from cache or API."""
    models = get_cached_models(ctx.runner.llm.api_base) or []
    if not models:
        try:
            models = ctx.runner.llm.list_models()
            if models:
                set_cached_models(ctx.runner.llm.api_base, models)
        except Exception:
            pass
    return models


def cmd_model(ctx: CommandContext) -> None:
    """List or switch LLM models."""
    arg = ctx.arg
    if not arg:
        models = _fetch_models(ctx)
        if not models:
            console.print(muted('  no models from API; set "LLM_MODEL" in your .env file'))
            console.print(label_value("current", ctx.runner.llm.model))
            return
        print_models(models, ctx.runner.llm.model)
        console.print(muted("  /model <1-N> or /model <id substring>"))
        return

    models = _fetch_models(ctx)
    if models:
        if arg.isdigit():
            i = int(arg)
            if 1 <= i <= len(models):
                mid = models[i - 1]["id"]
            else:
                print_error(f"use index 1–{len(models)}")
                return
        else:
            match = [m for m in models if arg in m.get("id", "")]
            mid = match[0]["id"] if match else arg
    else:
        mid = arg
    ctx.config["model"] = mid
    ctx.runner.llm.model = mid
    ctx.prefs["model"] = mid
    save_prefs(ctx.prefs)
    console.print(success(f"  model -> {mid}"))


def cmd_profile(ctx: CommandContext) -> None:
    """Show or switch permission profile."""
    arg = ctx.arg.lower()
    if arg not in ("strict", "dev", "ci"):
        console.print(label_value("profile", get_profile()))
        console.print(muted("  /profile strict | /profile dev | /profile ci"))
        return
    set_profile(arg)
    ctx.config["profile"] = arg
    ctx.prefs["profile"] = arg
    save_prefs(ctx.prefs)
    console.print(success(f"  profile -> {arg}"))
