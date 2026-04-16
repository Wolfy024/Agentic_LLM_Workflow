"""
Configuration and ENV loading utilities.

Handles parsing of the main `config.json`, loading variables from `.env`,
resolving `env:VAR` placeholders, and interactively picking models.
"""

from __future__ import annotations
import json
import os
import sys

from prompt_toolkit import prompt
from prompt_toolkit.formatted_text import HTML

from ui.console import console
from ui.dimming import muted
from ui.palette import success, warning
from ui.help import print_models
from ui.context_logs import print_error
from core.cache import get_cached_models, set_cached_models


def resolve_env(value: str) -> str:
    """
    Resolve 'env:VAR_NAME' strings to environment variable values.
    
    Args:
        value (str): The raw string from config.

    Returns:
        str: The resolved environment value, or empty if not found.
    """
    if isinstance(value, str) and value.startswith("env:"):
        var_name = value[4:]
        env_val = os.environ.get(var_name)
        if not env_val:
            console.print(warning(
                f"  env var {var_name} not set -- "
                f"set it or put the key directly in config.json"
            ))
            return ""
        return env_val
    return value


def load_dotenv() -> None:
    """
    Load .env file from the script directory if it exists, injecting 
    values into os.environ.
    """
    env_path = os.path.join(os.getcwd(), ".env")
    if not os.path.exists(env_path):
        return
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            key, val = key.strip(), val.strip()
            if val and val[0] in ('"', "'") and val[-1] == val[0]:
                val = val[1:-1]
            if key not in os.environ:
                os.environ[key] = val


def fetch_models_list(config: dict) -> list:
    """
    GET /models with file cache to list available LLM models.

    Args:
        config (dict): The configuration containing api_base and api_key.

    Returns:
        list: The models list.
    """
    cached = get_cached_models(config["api_base"])
    if cached is not None:
        return cached
    import httpx
    resp = httpx.get(
        f"{config['api_base']}/models",
        headers={"Authorization": f"Bearer {config['api_key']}"},
        timeout=15,
    )
    resp.raise_for_status()
    data = resp.json()
    models = data.get("data", [])
    set_cached_models(config["api_base"], models)
    return models


def pick_model_if_needed(config: dict, skip_interactive: bool = False) -> None:
    """
    Resolve model when missing or 'auto'. Mutates config.

    Args:
        config (dict): Configuration dict.
        skip_interactive (bool): If True, picks first model automatically.
    """
    model_val = config.get("model", "")
    if model_val and model_val.lower() != "auto":
        return
    console.print(muted("  fetching available models..."))
    models = []
    try:
        models = fetch_models_list(config)
    except Exception as e:
        console.print(warning(f"  could not fetch models: {e}"))

    if models:
        if skip_interactive:
            config["model"] = models[0]["id"]
            console.print(success(f"  selected (non-interactive): {config['model']}"))
            return
        if len(models) == 1:
            config["model"] = models[0]["id"]
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
            console.print(success(f"  selected: {config['model']}"))
    else:
        console.print(muted("  /models endpoint unavailable, enter model name manually"))
        try:
            typed = prompt(
                HTML("  <style fg='#6C63FF' bold='true'>model name: </style>")
            ).strip()
        except (EOFError, KeyboardInterrupt):
            sys.exit(0)
        if not typed:
            print_error("No model specified.")
            sys.exit(1)
        config["model"] = typed
        console.print(success(f"  using: {config['model']}"))


def load_config() -> dict:
    """
    Load main config.json, resolve env vars, and validate required keys.

    Returns:
        dict: The loaded configuration dictionary.
    """
    config_path = os.path.join(os.getcwd(), "config.json")
    if not os.path.exists(config_path):
        print_error(f"Config not found: {config_path}")
        sys.exit(1)
    try:
        with open(config_path) as f:
            config = json.load(f)
    except json.JSONDecodeError as e:
        print_error(f"Invalid JSON in config.json: {e}")
        sys.exit(1)

    for key in ("api_key", "serper_api_key"):
        if key in config:
            config[key] = resolve_env(config[key])

    config.setdefault("profile", "strict")
    if config["profile"] not in ("strict", "dev", "ci"):
        config["profile"] = "strict"

    required = ("api_base", "api_key")
    for key in required:
        if not config.get(key):
            print_error(f"Missing required config key: {key}")
            sys.exit(1)

    return config
