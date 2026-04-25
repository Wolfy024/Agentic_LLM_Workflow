"""
LLM Orchestrator Entrypoint.

Ties together the core loops, LLM client, UI console, and tool registry.
"""

import argparse
import os
import sys

from core.bootstrap import pick_model_if_needed
from core.config import load_config
import core.runtime_config as runtime_config
from core.permissions_checks import get_profile, set_profile
from core.permissions_prompts import set_yolo
from core.prefs import load_prefs, save_prefs
from repl import run_repl
from tools.registry import WORKSPACE, set_workspace
from tools.web.serper import set_serper_key
from tools.image_gen import configure_sd
from ui.banner import print_banner
from ui.console import console
from ui.palette import warning
from agent.state import SessionState
from agent.executor import ToolExecutor
from agent.runner import AgentRunner
from agent.watch.service import FileWatchService
from llm.client import LLMClient


def _parse_args():
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(description="LLM Orchestrator — local coding agent")
    parser.add_argument("workspace", nargs="?", default=None)
    parser.add_argument("--model", default=None)
    parser.add_argument("--profile", choices=["strict", "dev", "ci"], default=None)
    parser.add_argument("--no-stream", action="store_true")
    parser.add_argument("--watch", action="store_true")
    parser.add_argument("--watch-mode", choices=["auto", "batch"], default=None)
    parser.add_argument("--skip-model-prompt", action="store_true")
    return parser.parse_args()


def _build_llm_client(config: dict) -> LLMClient:
    """Create and configure the LLM API client."""
    def _on_retry(attempt, mx, err, wait):
        console.print(warning(f"  retry {attempt}/{mx}: {err} (waiting {wait:.0f}s)"))
    return LLMClient(
        api_base=config["api_base"],
        api_key=config["api_key"],
        model=config.get("model", "auto"),
        temperature=config.get("temperature", 0.15),
        on_retry=_on_retry,
        parallel_tool_calls=bool(config.get("parallel_tool_calls", True)),
    )


def _build_runner(config: dict, prefs: dict, llm: LLMClient) -> AgentRunner:
    """Create the agent runner with state, executor, and schemas."""
    from tools.registry import get_tool_schemas

    sys_prompt = config.get("system_prompt", "You are a helpful coding assistant with tools.")
    schemas = get_tool_schemas()
    state = SessionState(config, sys_prompt, schemas)
    executor = ToolExecutor(
        confirm_edits=prefs.get("confirm_edits", True),
        verbose=prefs.get("verbose", False),
    )
    runner = AgentRunner(state, llm, executor, stream=True)
    runner.max_iterations = int(config.get("max_tool_calls", 50))
    return runner


def _setup_watch(args, prefs: dict) -> dict:
    """Initialize file watch service if configured."""
    watch_ctx: dict = {"service": None}
    if args.watch or prefs.get("watch_enabled"):
        mode = args.watch_mode or prefs.get("watch_mode") or "auto"
        if mode not in ("auto", "batch"):
            mode = "auto"
        svc = FileWatchService(WORKSPACE, mode=mode)
        if svc.start():
            watch_ctx["service"] = svc
    return watch_ctx


def _save_exit_prefs(prefs: dict, llm: LLMClient, watch_ctx: dict) -> None:
    """Persist preferences on exit."""
    out_prefs = dict(prefs)
    out_prefs.update({
        "workspace": WORKSPACE,
        "model": llm.model,
        "profile": get_profile(),
        "yolo": prefs.get("yolo", False),
        "watch_enabled": watch_ctx.get("service") is not None,
    })
    if watch_ctx.get("service") is not None:
        out_prefs["watch_mode"] = watch_ctx["service"].state.mode
    save_prefs(out_prefs)


def main():
    args = _parse_args()
    config = load_config()
    runtime_config.set_runtime_config(config)
    prefs = load_prefs()

    # Apply profile
    if args.profile:
        config["profile"] = args.profile
    elif prefs.get("profile") in ("strict", "dev", "ci"):
        config["profile"] = prefs["profile"]
    set_profile(config.get("profile", "strict"))

    if args.model:
        config["model"] = args.model

    # Set workspace
    if args.workspace:
        workspace = os.path.abspath(args.workspace)
    elif prefs.get("workspace"):
        workspace = prefs["workspace"]
    else:
        workspace = os.getcwd()
    set_workspace(workspace)

    if config.get("serper_api_key"):
        set_serper_key(config["serper_api_key"])

    if config.get("sd_api_base"):
        configure_sd(config["sd_api_base"], config.get("api_key", ""))

    # Build components
    llm = _build_llm_client(config)
    pick_model_if_needed(config, llm, skip_interactive=args.skip_model_prompt)

    runner = _build_runner(config, prefs, llm)
    if args.no_stream:
        runner.stream = False

    if prefs.get("yolo"):
        set_yolo(True)

    watch_ctx = _setup_watch(args, prefs)

    # Run
    print_banner(config, WORKSPACE, session_name=prefs.get("last_session_name"))
    try:
        run_repl(runner, watch_ctx, config, prefs)
    finally:
        # Auto-save session if there's actual conversation
        from repl.slash import _auto_save_session
        _auto_save_session(runner, prefs)
        _save_exit_prefs(prefs, llm, watch_ctx)
        if watch_ctx.get("service"):
            watch_ctx["service"].stop()
        llm.client.close()


if __name__ == "__main__":
    main()
