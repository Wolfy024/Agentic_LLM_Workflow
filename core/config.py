"""
Configuration and ENV loading utilities.

Handles parsing of the main `config.json`, loading variables from `.env`,
and resolving `env:VAR` placeholders.
"""

from __future__ import annotations
import json
import os
import sys

from ui.console import console
from ui.palette import warning
from ui.context_logs import print_error


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
