"""Session management commands: /save, /load, /clear, /compact, /export."""

from __future__ import annotations

import datetime
import os
from typing import TYPE_CHECKING

from agent.state import load_session, save_session, get_sessions_dir
from core.prefs import save_prefs
from tools.registry import _resolve
from ui.console import console
from ui.context_logs import print_error
from ui.dimming import muted
from ui.palette import secondary, success
from core.repl_utils import safe_name

if TYPE_CHECKING:
    from repl.slash import CommandContext


def cmd_clear(ctx: CommandContext) -> None:
    """Reset conversation history."""
    ctx.runner.state.reset()
    console.print(success("  conversation cleared"))


def cmd_compact(ctx: CommandContext) -> None:
    """Trim conversation context."""
    if len(ctx.runner.state.messages) > 5:
        ctx.runner.state.auto_compact(ctx.runner.llm.chat, ctx.runner.llm.last_usage)
        console.print(success("  compacted context"))
    else:
        console.print(muted("  nothing to compact yet (need more than a few messages)"))


def cmd_save(ctx: CommandContext) -> None:
    """Save session to disk."""
    raw = ctx.arg or "default"
    name = safe_name(raw)
    path = save_session(ctx.runner.state, name, model=ctx.runner.llm.model)
    ctx.prefs["last_session_name"] = name
    save_prefs(ctx.prefs)
    console.print(success(f"  session saved: {path}"))


def cmd_load(ctx: CommandContext) -> None:
    """Load session from disk. Lists available sessions if no argument given."""
    arg = ctx.arg

    if not arg:
        _list_sessions()
        return

    # Allow selection by number
    if arg.isdigit():
        sessions = _get_sorted_sessions()
        idx = int(arg)
        if not sessions or idx < 1 or idx > len(sessions):
            print_error(f"Invalid session number. Use /load to see available sessions.")
            return
        name = sessions[idx - 1]["name"]
    else:
        name = safe_name(arg.replace(".json", ""))

    res, saved_model = load_session(ctx.runner.state, name)
    if res.startswith("Session not found"):
        print_error(res)
    else:
        if saved_model:
            ctx.runner.llm.model = saved_model
            ctx.config["model"] = saved_model
        ctx.prefs["last_session_name"] = name
        save_prefs(ctx.prefs)
        model_note = f", model: {saved_model}" if saved_model else ""
        console.print(success(f"  session loaded ({name}{model_note})"))


def _get_sorted_sessions() -> list[dict]:
    """Get all sessions sorted newest-first with metadata."""
    s_dir = get_sessions_dir()
    if not os.path.isdir(s_dir):
        return []
    sessions = []
    for f in os.listdir(s_dir):
        if not f.endswith(".json"):
            continue
        path = os.path.join(s_dir, f)
        name = f[:-5]
        mtime = os.path.getmtime(path)
        # Try to get message count and model
        msg_count = 0
        model = ""
        try:
            import json as _json
            with open(path, "r", encoding="utf-8") as fh:
                data = _json.load(fh)
                msg_count = len(data.get("messages", []))
                model = data.get("model", "")
        except Exception:
            pass
        sessions.append({
            "name": name,
            "mtime": mtime,
            "msg_count": msg_count,
            "model": model,
        })
    sessions.sort(key=lambda s: s["mtime"], reverse=True)
    return sessions


def _list_sessions() -> None:
    """Print a numbered list of available sessions."""
    sessions = _get_sorted_sessions()
    if not sessions:
        console.print(muted("  no saved sessions"))
        return

    console.print(muted("  saved sessions (newest first):"))
    console.print()
    for i, s in enumerate(sessions, 1):
        dt = datetime.datetime.fromtimestamp(s["mtime"])
        date_str = dt.strftime("%b %d, %Y  %H:%M")
        model_short = s["model"].split("/")[-1][:25] if s["model"] else ""
        model_tag = f"  [dim]({model_short})[/dim]" if model_short else ""
        msg_tag = f"[dim]{s['msg_count']} msgs[/dim]"

        console.print(f"    [bold cyan]{i:>3}[/bold cyan]  {secondary(s['name'], bold=False)}  {msg_tag}{model_tag}")
        console.print(f"         [dim]{date_str}[/dim]")

    console.print()
    console.print(muted("  use: /load <number> or /load <name>"))


def cmd_export(ctx: CommandContext) -> None:
    """Export conversation to markdown file."""
    arg = ctx.arg
    rel = arg or f"chat_export_{datetime.datetime.now():%Y%m%d_%H%M}.md"
    out_path = _resolve(rel)
    lines = ["# LLM Orchestrator export\n\n", f"model: `{ctx.runner.llm.model}`\n\n---\n\n"]
    for m in ctx.runner.state.messages:
        role = m.get("role", "")
        c = m.get("content")
        if isinstance(c, list):
            body = "[multimodal content omitted]\n"
        else:
            body = (c or "") + "\n"
        lines.append(f"## {role}\n\n{body}\n---\n\n")
    try:
        parent = os.path.dirname(out_path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            f.write("".join(lines))
    except OSError as e:
        print_error(str(e))
        return
    console.print(success(f"  exported -> {out_path}"))
