"""
LLM Orchestrator Entrypoint.

Ties together the core loops, LLM client, UI console, and tool registry.
"""

import argparse
import os
import sys

from core.bootstrap import pick_model_if_needed
from core.config import load_config
from core.permissions_checks import get_profile, set_profile
from core.permissions_prompts import set_yolo
from core.prefs import load_prefs, save_prefs
from repl import run_repl
from tools.registry import WORKSPACE, set_workspace
from tools.web.serper import set_serper_key
from ui.banner import print_banner
from ui.console import console
from ui.palette import warning
from agent.state import SessionState
from agent.executor import ToolExecutor
from agent.runner import AgentRunner
from agent.watch.service import FileWatchService
from llm.client import LLMClient


def main():
    parser = argparse.ArgumentParser(description="LLM Orchestrator — local coding agent")
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

    if args.profile:
        config["profile"] = args.profile
    elif prefs.get("profile") in ("strict", "dev", "ci"):
        config["profile"] = prefs["profile"]
    set_profile(config.get("profile", "strict"))

    if args.model:
        config["model"] = args.model

    workspace = os.path.abspath(args.workspace) if args.workspace else prefs.get("workspace") or os.getcwd()
    set_workspace(workspace)

    if config.get("serper_api_key"):
        set_serper_key(config["serper_api_key"])

    def _on_retry(attempt, mx, err, wait):
        console.print(warning(f"  retry {attempt}/{mx}: {err} (waiting {wait:.0f}s)"))

    llm = LLMClient(
        api_base=config["api_base"],
        api_key=config["api_key"],
        model=config.get("model", "auto"),
        max_tokens=config.get("max_tokens", 131072),
        temperature=config.get("temperature", 0.15),
        context_window=config.get("context_window", 262144),
        on_retry=_on_retry,
        parallel_tool_calls=bool(config.get("parallel_tool_calls", False)),
    )

    pick_model_if_needed(config, llm, skip_interactive=args.skip_model_prompt)

    sys_prompt = config.get("system_prompt", "You are a helpful coding assistant with tools.")
    from tools.registry import get_tool_schemas

    schemas = get_tool_schemas()
    state = SessionState(config, sys_prompt, schemas)
    executor = ToolExecutor(confirm_edits=prefs.get("confirm_edits", True), verbose=prefs.get("verbose", False))
    stream = not args.no_stream
    runner = AgentRunner(state, llm, executor, stream=stream)

    if prefs.get("yolo"):
        set_yolo(True)
    watch_mode_eff = args.watch_mode or prefs.get("watch_mode") or "auto"
    watch_ctx: dict = {"service": None}
    if args.watch or prefs.get("watch_enabled"):
        watch_ctx["service"] = FileWatchService(WORKSPACE, mode=watch_mode_eff)
        watch_ctx["service"].start()

    last_saved_name = prefs.get("last_session_name")
    print_banner(config, WORKSPACE, session_name=last_saved_name)

    try:
        run_repl(runner, watch_ctx, config, prefs)
    finally:
        out_prefs = dict(prefs)
        out_prefs.update(
            {
                "workspace": WORKSPACE,
                "model": llm.model,
                "profile": get_profile(),
                "yolo": prefs.get("yolo", False),
                "watch_enabled": watch_ctx.get("service") is not None,
            }
        )
        if watch_ctx.get("service") is not None:
            out_prefs["watch_mode"] = watch_ctx["service"].state.mode
        save_prefs(out_prefs)
        if watch_ctx.get("service"):
            watch_ctx["service"].stop()
        llm.client.close()


if __name__ == "__main__":
    import dotenv

    dotenv.load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))
    main()
