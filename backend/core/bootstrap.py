"""Startup: interactive model selection when config has model=auto."""

from __future__ import annotations

import sys

from prompt_toolkit import prompt, HTML

from llm.client import LLMClient
from core.cache import get_cached_models, set_cached_models
from ui.console import console
from ui.help import print_models
from ui.context_logs import print_error
from ui.dimming import muted
from ui.palette import success, warning


def pick_model_if_needed(
    config: dict,
    llm: LLMClient,
    skip_interactive: bool = False,
) -> None:
    model_val = config.get("model", "")
    if model_val and model_val.lower() != "auto":
        return
    console.print(muted("  fetching available models..."))
    models = get_cached_models(llm.api_base) or []
    if not models:
        try:
            models = llm.list_models()
            if models:
                set_cached_models(llm.api_base, models)
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
                choice = prompt(
                    HTML(f"  <style fg='#6C63FF' bold='true'>pick model (1-{len(models)}) or type name: </style>")
                ).strip()
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
