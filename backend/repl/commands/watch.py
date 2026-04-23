"""File watch commands: /watch [on|off|mode|flush|status]."""

from __future__ import annotations
from typing import TYPE_CHECKING

from agent.watch.service import FileWatchService
from agent.watch.utils import build_user_message
from core.prefs import save_prefs
from tools.registry import WORKSPACE
from ui.components import label_value
from ui.console import console
from ui.context_logs import print_error
from ui.dimming import muted
from ui.palette import success, warning

if TYPE_CHECKING:
    from repl.slash import CommandContext


def cmd_watch(ctx: CommandContext) -> None:
    """Handle all /watch subcommands."""
    rest = ctx.rest
    bits = rest.split(None, 2)
    head = bits[0].lower() if bits else ""

    if not rest:
        sub, extra = "status", None
    elif head == "mode":
        if len(bits) < 2:
            print_error("Use /watch mode auto  or  /watch mode batch")
            return
        sub, extra = "mode", bits[1].lower()
    elif head in ("on", "off", "flush", "status", "st", "?", "help"):
        sub = {"st": "status", "?": "status", "help": "status"}.get(head, head)
        extra = None
    else:
        console.print(warning(f"  unknown /watch option `{bits[0]}`."))
        console.print(muted("  The watcher covers the whole workspace (not one file path). Use .minillm/watch_ignore to filter."))
        console.print(muted("  Usage: /watch | /watch on | /watch off | /watch mode auto|batch | /watch flush"))
        return

    svc = ctx.watch_ctx.get("service")

    if sub == "status":
        _status(svc)
    elif sub == "on":
        _enable(ctx, svc)
    elif sub == "off":
        _disable(ctx, svc)
    elif sub == "mode":
        _set_mode(ctx, svc, extra)
    elif sub == "flush":
        _flush(ctx, svc)


def _status(svc) -> None:
    if svc is None:
        console.print(muted("  File watch: OFF  (/watch on to enable)"))
    else:
        console.print(label_value("watch", "on"))
        console.print(label_value("mode", svc.state.mode))
        console.print(muted("  (monitors entire workspace recursively)"))


def _enable(ctx, svc) -> None:
    if svc is not None:
        console.print(warning("  file watch already ON"))
        return
    mode = ctx.prefs.get("watch_mode") or "auto"
    if mode not in ("auto", "batch"):
        mode = "auto"
    nsvc = FileWatchService(WORKSPACE, mode=mode)
    if not nsvc.start():
        print_error("Could not start file watch. Install: pip install watchdog")
        return
    ctx.watch_ctx["service"] = nsvc
    ctx.prefs["watch_enabled"] = True
    ctx.prefs["watch_mode"] = mode
    save_prefs(ctx.prefs)
    console.print(success(f"  file watch ON (mode={mode})"))


def _disable(ctx, svc) -> None:
    if svc is None:
        console.print(muted("  file watch already OFF"))
        return
    svc.stop()
    ctx.watch_ctx["service"] = None
    ctx.prefs["watch_enabled"] = False
    save_prefs(ctx.prefs)
    console.print(success("  file watch OFF"))


def _set_mode(ctx, svc, mode: str) -> None:
    if mode not in ("auto", "batch"):
        print_error("Use: /watch mode auto   or   /watch mode batch")
        return
    ctx.prefs["watch_mode"] = mode
    if svc is not None:
        svc.state.set_mode(mode)
    save_prefs(ctx.prefs)
    console.print(success(f"  watch mode set to {mode}" + (" — active" if svc else " (use /watch on to apply)")))


def _flush(ctx, svc) -> None:
    if svc is None:
        print_error("File watch is off. Use /watch on first.")
        return
    paths = svc.state.queue.force_drain()
    svc.state._batch_notice_shown = False
    if not paths:
        console.print(muted("  no queued file changes"))
        return
    msg = build_user_message(paths)
    console.print(muted(f"  flushing {len(paths)} path(s) to model…"))
    ctx.runner.chat_turn(msg)
