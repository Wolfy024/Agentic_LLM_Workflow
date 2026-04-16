"""
MINILLM Orchestrator Entrypoint.

Ties together the core loops, LLM client, UI console, and tool registry.
"""

import sys
import os
import argparse
from prompt_toolkit import prompt, HTML
from prompt_toolkit.history import FileHistory
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
from prompt_toolkit.shortcuts import CompleteStyle

from core.config import load_config
from core.prefs import load_prefs, save_prefs
from core.permissions_checks import set_profile, get_profile
from core.permissions_prompts import set_yolo
from ui.console import console
from ui.banner import print_banner
from ui.help import SLASH_COMMAND_SPECS, print_help, print_tools, print_models
from ui.slash_complete import SlashCommandCompleter
from ui.context_logs import print_context, print_goodbye, print_error
from ui.components import label_value
from ui.dimming import muted
from ui.palette import success, warning
from tools.registry import set_workspace, WORKSPACE, _resolve
from tools.web.serper import set_serper_key
from llm.client import LLMClient
from llm.vision import build_user_content_with_image
from agent.state import SessionState
from agent.executor import ToolExecutor
from agent.runner import AgentRunner
from agent.watch.service import FileWatchService

HISTORY_FILE = os.path.join(os.path.expanduser("~"), ".minillm", ".history")

_slash_completer = SlashCommandCompleter(SLASH_COMMAND_SPECS)


def pick_model_if_needed(config: dict, llm: LLMClient, skip_interactive: bool = False) -> None:
    model_val = config.get("model", "")
    if model_val and model_val.lower() != "auto":
        return
    console.print(muted("  fetching available models..."))
    models = []
    try:
        models = llm.list_models()
    except Exception as e:
        console.print(warning(f"  could not fetch models: {e}"))

    if models:
        if skip_interactive:
            config["model"] = models[0]["id"]
            llm.model = models[0]["id"]
            console.print(success(f"  selected (non-interactive): {config['model']}"))
            return
        if len(models) == 1:
            config["model"] = models[0]["id"]
            llm.model = models[0]["id"]
            console.print(success(f"  auto-selected: {config['model']}"))
        else:
            print_models(models, "")
            try:
                choice = prompt(HTML(f"  <style fg='#6C63FF' bold='true'>pick model (1-{len(models)}) or type name: </style>")).strip()
            except (EOFError, KeyboardInterrupt):
                sys.exit(0)
            if choice.isdigit() and 1 <= int(choice) <= len(models):
                config["model"] = models[int(choice) - 1]["id"]
            else:
                match = [m for m in models if choice in m["id"]]
                config["model"] = match[0]["id"] if match else models[0]["id"]
            llm.model = config["model"]
            console.print(success(f"  selected: {config['model']}"))
    else:
        console.print(muted("  /models endpoint unavailable, enter model name manually"))
        try:
            typed = prompt(HTML("  <style fg='#6C63FF' bold='true'>model name: </style>")).strip()
        except (EOFError, KeyboardInterrupt):
            sys.exit(0)
        if not typed:
            print_error("No model specified.")
            sys.exit(1)
        config["model"] = typed
        llm.model = typed
        console.print(success(f"  using: {config['model']}"))


def execute_slash_command(
    cmd: str,
    parts: list[str],
    runner: AgentRunner,
    watch_state: FileWatchService | None,
    multiline_mode: bool,
    config: dict,
) -> tuple[bool, bool]:
    """Returns (should_exit, new_multiline_mode)."""
    if cmd in ("/exit", "/quit", "/q"):
        print_goodbye()
        return True, multiline_mode

    if cmd == "/help": print_help()
    elif cmd == "/clear":
        runner.state.reset()
        console.print(success("  conversation cleared"))
    elif cmd == "/tools": print_tools(runner.state.tool_schemas)
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
                if watch_state and not watch_state.set_workspace(new_ws):
                    console.print(warning("  watch: could not reattach"))
            else: print_error(f"Not a directory: {new_ws}")
        else: console.print(label_value("workspace", WORKSPACE))
    elif cmd == "/compact":
        if len(runner.state.messages) > 5:
            runner.state.auto_compact(runner.llm.chat, runner.llm.last_usage)
            console.print(success("  compacted context"))
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
            runner.state.messages.append({"role": "system", "content": f"[Task checklist]\n1. Restate goal.\n2. List tools.\n3. Execute.\nGoal: {text}"})
            console.print(success("  task checklist injected"))
    elif cmd == "/plan":
        runner.state.messages.append({"role": "system", "content": "[Planning mode]\n- Break work down.\n- Read before write."})
        console.print(success("  planning prompt injected"))
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
    else:
        console.print(muted(f"  unknown command: {cmd}"))

    return False, multiline_mode


def run_repl(runner: AgentRunner, watch_state: FileWatchService | None, config: dict):
    try:
        history = FileHistory(HISTORY_FILE)
    except Exception:
        history = None

    multiline_mode = False

    while True:
        if watch_state and watch_state.state.mode == "auto":
            injected = watch_state.state.take_auto_inject_message()
            if injected:
                console.print(muted("  [watch] workspace changed — running follow-up turn"))
                runner.chat_turn(injected)
        elif watch_state and watch_state.state.mode == "batch":
            notice = watch_state.state.peek_batch_notice()
            if notice: console.print(warning(f"  {notice}"))

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
                multiline=multiline_mode,
            ).strip()
        except (EOFError, KeyboardInterrupt):
            print_goodbye()
            break

        if not user_input:
            continue

        if watch_state and watch_state.state.mode == "batch" and not user_input.startswith("/"):
            batch_pre = watch_state.state.consume_batch_prefix()
            if batch_pre: user_input = f"{batch_pre}\n\n{user_input}"

        if user_input.startswith("/"):
            cmd = user_input.lower().split()[0]
            parts = user_input.split(maxsplit=1)
            exit_flag, multiline_mode = execute_slash_command(cmd, parts, runner, watch_state, multiline_mode, config)
            if exit_flag: break
            continue
            
        runner.chat_turn(user_input)


def main():
    parser = argparse.ArgumentParser(description="MINILLM Boss — local coding agent")
    parser.add_argument("workspace", nargs="?", default=None)
    parser.add_argument("--model", default=None)
    parser.add_argument("--profile", choices=["strict", "dev", "ci"], default=None)
    parser.add_argument("--no-stream", action="store_true")
    parser.add_argument("--watch", action="store_true")
    parser.add_argument("--watch-mode", choices=["auto", "batch"], default=None)
    parser.add_argument("--skip-model-prompt", action="store_true")
    args = parser.parse_args()

    config = load_config()
    prefs = load_prefs()

    if args.profile: config["profile"] = args.profile
    elif prefs.get("profile") in ("strict", "dev", "ci"): config["profile"] = prefs["profile"]
    set_profile(config.get("profile", "strict"))

    if args.model: config["model"] = args.model

    workspace = os.path.abspath(args.workspace) if args.workspace else prefs.get("workspace") or os.getcwd()
    set_workspace(workspace)

    if config.get("serper_api_key"): set_serper_key(config["serper_api_key"])

    def _on_retry(attempt, mx, err, wait):
        console.print(warning(f"  retry {attempt}/{mx}: {err} (waiting {wait:.0f}s)"))

    llm = LLMClient(
        api_base=config["api_base"], api_key=config["api_key"], model=config.get("model", "auto"),
        max_tokens=config.get("max_tokens", 131072), temperature=config.get("temperature", 0.15),
        context_window=config.get("context_window", 262144), on_retry=_on_retry, parallel_tool_calls=bool(config.get("parallel_tool_calls", False))
    )

    pick_model_if_needed(config, llm, skip_interactive=args.skip_model_prompt)

    sys_prompt = config.get("system_prompt", "You are a helpful coding assistant with tools.")
    from tools.registry import get_tool_schemas
    schemas = get_tool_schemas()
    state = SessionState(config, sys_prompt, schemas)
    executor = ToolExecutor(confirm_edits=prefs.get("confirm_edits", True), verbose=prefs.get("verbose", False))
    stream = not args.no_stream
    runner = AgentRunner(state, llm, executor, stream=stream)

    if prefs.get("yolo"): set_yolo(True)
    watch_mode_eff = args.watch_mode or prefs.get("watch_mode") or "auto"
    watch_state = None
    if args.watch or prefs.get("watch_enabled"):
        watch_state = FileWatchService(WORKSPACE, mode=watch_mode_eff)
        watch_state.start()
        
    last_saved_name = prefs.get("last_session_name")
    print_banner(config, WORKSPACE, session_name=last_saved_name)

    try:
        run_repl(runner, watch_state, config)
    finally:
        save_prefs({"workspace": WORKSPACE, "model": llm.model, "profile": get_profile(), "yolo": prefs.get("yolo", False)})
        if watch_state: watch_state.stop()
        llm.client.close()

if __name__ == "__main__":
    import dotenv
    dotenv.load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))
    main()
