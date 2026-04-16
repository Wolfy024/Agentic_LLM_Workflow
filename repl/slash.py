"""Slash command handlers for the LLM Orchestrator REPL."""

from __future__ import annotations

import datetime
import json
import os

from agent.runner import AgentRunner
from agent.state import SESSIONS_DIR, load_session, save_session
from agent.watch.service import FileWatchService
from agent.watch.utils import build_user_message
from core.permissions_checks import get_profile, set_profile
from core.permissions_prompts import set_yolo
from core.prefs import save_prefs
from core.repl_utils import apply_recipe_payload, recipe_candidate_paths, safe_name
from llm.vision import build_user_content_with_image
from tools.registry import WORKSPACE, _resolve, set_workspace
from ui.components import label_value
from ui.console import console
from ui.context_logs import print_context, print_error, print_goodbye
from ui.dimming import muted
from ui.help import print_help, print_models, print_tools
from ui.palette import secondary, success, warning


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

    if cmd == "/help":
        print_help()
    elif cmd == "/clear":
        runner.state.reset()
        console.print(success("  conversation cleared"))
    elif cmd == "/tools":
        print_tools(runner.state.tool_schemas)
    elif cmd == "/context":
        u = runner.llm.last_usage
        info = {
            "messages": len(runner.state.messages),
            "tokens_used": runner.state.context_used(u),
            "tokens_source": "api" if u else "estimate",
            "context_window": runner.state.context_window,
            "max_output": runner.state.max_output,
            "remaining": runner.state.context_remaining(u),
            "pct_used": f"{runner.state.context_used(u) / runner.state.context_window:.1%}",
        }
        print_context(info)
    elif cmd == "/workspace":
        if len(parts) > 1:
            new_ws = os.path.abspath(parts[1])
            if os.path.isdir(new_ws):
                set_workspace(new_ws)
                console.print(success(f"  workspace -> {new_ws}"))
                ws = watch_ctx.get("service")
                if ws and not ws.set_workspace(new_ws):
                    console.print(warning("  watch: could not reattach"))
            else:
                print_error(f"Not a directory: {new_ws}")
        else:
            console.print(label_value("workspace", WORKSPACE))
    elif cmd == "/compact":
        if len(runner.state.messages) > 5:
            runner.state.auto_compact(runner.llm.chat, runner.llm.last_usage)
            console.print(success("  compacted context"))
        else:
            console.print(muted("  nothing to compact yet (need more than a few messages)"))
    elif cmd == "/yolo":
        set_yolo(True)
        console.print(warning("  YOLO mode ON -- all destructive ops auto-approved"))
    elif cmd == "/safe":
        set_yolo(False)
        console.print(success("  safe mode ON -- destructive ops require approval"))
    elif cmd == "/multi":
        multiline_mode = not multiline_mode
        console.print(muted(f"  multiline input {'ON' if multiline_mode else 'OFF'}"))
    elif cmd == "/task":
        text = parts[1] if len(parts) > 1 else ""
        if text.strip():
            runner.state.messages.append(
                {
                    "role": "system",
                    "content": f"[Task checklist]\n1. Restate goal.\n2. List tools.\n3. Execute.\nGoal: {text}",
                }
            )
            console.print(success("  task checklist injected"))
    elif cmd == "/plan":
        runner.state.messages.append(
            {"role": "system", "content": "[Planning mode]\n- Break work down.\n- Read before write."}
        )
        console.print(success("  planning prompt injected"))

    elif cmd == "/save":
        raw = (parts[1] if len(parts) > 1 else "").strip() or "default"
        name = safe_name(raw)
        path = save_session(runner.state, name)
        prefs["last_session_name"] = name
        save_prefs(prefs)
        console.print(success(f"  session saved: {path}"))

    elif cmd == "/load":
        arg = (parts[1] if len(parts) > 1 else "").strip()
        if not arg:
            if not os.path.isdir(SESSIONS_DIR):
                console.print(muted("  no sessions directory yet"))
                return False, multiline_mode
            names = sorted(f[:-5] for f in os.listdir(SESSIONS_DIR) if f.endswith(".json"))
            if not names:
                console.print(muted("  no saved sessions"))
                return False, multiline_mode
            console.print(muted("  saved sessions:"))
            for n in names:
                console.print(f"    {secondary(n, bold=False)}")
            console.print(muted("  use: /load <name>"))
            return False, multiline_mode
        name = safe_name(arg.replace(".json", ""))
        res = load_session(runner.state, name)
        if res.startswith("Session not found"):
            print_error(res)
        else:
            prefs["last_session_name"] = name
            save_prefs(prefs)
            console.print(success(f"  session loaded ({name})"))

    elif cmd == "/verbose":
        cur = prefs.get("verbose", False)
        prefs["verbose"] = not cur
        runner.executor.verbose = prefs["verbose"]
        save_prefs(prefs)
        console.print(success(f"  verbose tool output {'ON' if prefs['verbose'] else 'OFF'}"))

    elif cmd == "/confirm":
        cur = prefs.get("confirm_edits", True)
        prefs["confirm_edits"] = not cur
        runner.executor.confirm_edits = prefs["confirm_edits"]
        save_prefs(prefs)
        console.print(
            success(f"  edit diff preview before apply {'ON' if prefs['confirm_edits'] else 'OFF'}")
        )

    elif cmd == "/model":
        arg = (parts[1] if len(parts) > 1 else "").strip()
        if not arg:
            try:
                models = runner.llm.list_models()
            except Exception as e:
                print_error(str(e))
                return False, multiline_mode
            if not models:
                console.print(muted('  no models from API; set "model" in config.json'))
                console.print(label_value("current", runner.llm.model))
                return False, multiline_mode
            print_models(models, runner.llm.model)
            console.print(muted("  /model <1-N> or /model <id substring>"))
            return False, multiline_mode
        models: list = []
        try:
            models = runner.llm.list_models()
        except Exception:
            pass
        if models:
            if arg.isdigit():
                i = int(arg)
                if 1 <= i <= len(models):
                    mid = models[i - 1]["id"]
                else:
                    print_error(f"use index 1–{len(models)}")
                    return False, multiline_mode
            else:
                match = [m for m in models if arg in m.get("id", "")]
                mid = match[0]["id"] if match else arg
        else:
            mid = arg
        config["model"] = mid
        runner.llm.model = mid
        prefs["model"] = mid
        save_prefs(prefs)
        console.print(success(f"  model -> {mid}"))

    elif cmd == "/profile":
        arg = (parts[1] if len(parts) > 1 else "").strip().lower()
        if arg not in ("strict", "dev", "ci"):
            console.print(label_value("profile", get_profile()))
            console.print(muted("  /profile strict | /profile dev | /profile ci"))
            return False, multiline_mode
        set_profile(arg)
        config["profile"] = arg
        prefs["profile"] = arg
        save_prefs(prefs)
        console.print(success(f"  profile -> {arg}"))

    elif cmd == "/recipe":
        arg = (parts[1] if len(parts) > 1 else "").strip()
        if not arg:
            console.print(
                muted("  /recipe <name>  — loads .minillm/recipes/<name>.json (workspace or ~/.minillm)")
            )
            return False, multiline_mode
        found = None
        for path in recipe_candidate_paths(WORKSPACE, arg):
            if os.path.isfile(path):
                found = path
                break
        if not found:
            bn = safe_name(arg)
            print_error(f"Recipe not found: .minillm/recipes/{bn}.json")
            return False, multiline_mode
        try:
            with open(found, encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError) as e:
            print_error(str(e))
            return False, multiline_mode
        if not isinstance(data, dict) or not apply_recipe_payload(runner, data):
            print_error("Recipe JSON needs prompt, system, user, or messages[]")
            return False, multiline_mode
        console.print(success(f"  recipe injected ({os.path.basename(found)})"))

    elif cmd == "/export":
        arg = (parts[1] if len(parts) > 1 else "").strip()
        rel = arg or f"chat_export_{datetime.datetime.now():%Y%m%d_%H%M}.md"
        try:
            out_path = _resolve(rel)
        except PermissionError:
            print_error("Export path must be under the workspace")
            return False, multiline_mode
        lines = ["# LLM Orchestrator export\n\n", f"model: `{runner.llm.model}`\n\n---\n\n"]
        for m in runner.state.messages:
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
            return False, multiline_mode
        console.print(success(f"  exported -> {out_path}"))

    elif cmd == "/image":
        rest = (parts[1] if len(parts) > 1 else "").strip()
        if not rest:
            console.print(muted("  Usage: /image <file.png> [instruction]  — file under workspace."))
            console.print(muted("  Embeds the image as base64 for multimodal models (OpenAI-style image_url)."))
            console.print(muted("  Example: /image 1.png describe what you see"))
            return False, multiline_mode
        path_raw, _, tail = rest.partition(" ")
        path_raw = path_raw.strip()
        instruction = tail.strip() if tail.strip() else "Describe this image in detail."
        try:
            resolved = _resolve(path_raw)
        except PermissionError:
            print_error(f"Path must stay inside the workspace: {path_raw}")
            return False, multiline_mode
        if not os.path.isfile(resolved):
            print_error(f"Not a file: {path_raw}")
            return False, multiline_mode
        rel = os.path.relpath(resolved, WORKSPACE).replace("\\", "/")
        max_mb = float(config.get("max_image_mb", 20))
        max_bytes = int(max_mb * 1024 * 1024)
        d_raw = config.get("vision_image_detail", "auto")
        detail_kw: str | None
        if d_raw in (False, None, "", "omit", "none"):
            detail_kw = None
        else:
            detail_kw = str(d_raw)
        try:
            content = build_user_content_with_image(
                instruction, resolved, max_bytes=max_bytes, detail=detail_kw
            )
        except ValueError as e:
            print_error(str(e))
            return False, multiline_mode
        console.print(muted(f"  sending image to model ({rel})…"))
        runner.chat_turn(content)
    elif cmd == "/watch":
        rest = (parts[1] if len(parts) > 1 else "").strip()
        bits = rest.split(None, 2)
        head = bits[0].lower() if bits else ""

        if not rest:
            sub = "status"
            extra = None
        elif bits[0].lower() == "mode":
            if len(bits) < 2:
                print_error("Use /watch mode auto  or  /watch mode batch")
                return False, multiline_mode
            sub = "mode"
            extra = bits[1].lower()
        elif head in ("on", "off", "flush", "status", "st", "?", "help"):
            sub = {"st": "status", "?": "status", "help": "status"}.get(head, head)
            extra = None
        else:
            console.print(warning(f"  unknown /watch option `{bits[0]}`."))
            console.print(
                muted(
                    "  The watcher covers the whole workspace (not one file path). Use .minillm/watch_ignore to filter."
                )
            )
            console.print(muted("  Usage: /watch | /watch on | /watch off | /watch mode auto|batch | /watch flush"))
            return False, multiline_mode

        svc = watch_ctx.get("service")

        if sub == "status":
            if svc is None:
                console.print(muted("  File watch: OFF  (/watch on to enable)"))
            else:
                console.print(label_value("watch", "on"))
                console.print(label_value("mode", svc.state.mode))
                console.print(muted("  (monitors entire workspace recursively)"))
            return False, multiline_mode

        if sub == "on":
            if svc is not None:
                console.print(warning("  file watch already ON"))
                return False, multiline_mode
            mode = prefs.get("watch_mode") or "auto"
            if mode not in ("auto", "batch"):
                mode = "auto"
            nsvc = FileWatchService(WORKSPACE, mode=mode)
            if not nsvc.start():
                print_error("Could not start file watch. Install: pip install watchdog")
                return False, multiline_mode
            watch_ctx["service"] = nsvc
            prefs["watch_enabled"] = True
            prefs["watch_mode"] = mode
            save_prefs(prefs)
            console.print(success(f"  file watch ON (mode={mode})"))
            return False, multiline_mode

        if sub == "off":
            if svc is None:
                console.print(muted("  file watch already OFF"))
                return False, multiline_mode
            svc.stop()
            watch_ctx["service"] = None
            prefs["watch_enabled"] = False
            save_prefs(prefs)
            console.print(success("  file watch OFF"))
            return False, multiline_mode

        if sub == "mode":
            if extra not in ("auto", "batch"):
                print_error("Use: /watch mode auto   or   /watch mode batch")
                return False, multiline_mode
            prefs["watch_mode"] = extra
            if svc is not None:
                svc.state.set_mode(extra)
            save_prefs(prefs)
            console.print(
                success(f"  watch mode set to {extra}" + (" — active" if svc else " (use /watch on to apply)"))
            )
            return False, multiline_mode

        if sub == "flush":
            if svc is None:
                print_error("File watch is off. Use /watch on first.")
                return False, multiline_mode
            paths = svc.state.queue.force_drain()
            svc.state._batch_notice_shown = False
            if not paths:
                console.print(muted("  no queued file changes"))
                return False, multiline_mode
            msg = build_user_message(paths)
            console.print(muted(f"  flushing {len(paths)} path(s) to model…"))
            runner.chat_turn(msg)
            return False, multiline_mode

    else:
        console.print(muted(f"  unknown command: {cmd}"))

    return False, multiline_mode
