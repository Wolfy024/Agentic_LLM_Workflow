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


def get_root_dir() -> Path:
    from pathlib import Path
    if getattr(sys, 'frozen', False):
        exe_dir = Path(sys.executable).parent
        if (exe_dir / "config.json").exists():
            return exe_dir
        return Path(sys._MEIPASS)
    return Path(__file__).parent.parent.parent


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
        return os.environ.get(var_name, "")
    return value


def load_dotenv() -> None:
    """
    Load .env file from the project root using python-dotenv.
    """
    try:
        import dotenv
        from pathlib import Path
        import sys
        
        env_path = get_root_dir() / ".env"
        
        # In frozen mode, explicitly check next to the executable as well
        if getattr(sys, 'frozen', False):
            exe_env = Path(sys.executable).parent / ".env"
            if exe_env.exists():
                env_path = exe_env
                
        if env_path.exists():
            dotenv.load_dotenv(str(env_path), override=False)
    except ImportError:
        pass  # python-dotenv not installed — skip silently


def load_config() -> dict:
    """
    Load main config.json, resolve env vars, and validate required keys.

    Returns:
        dict: The loaded configuration dictionary.
    """
    load_dotenv()
    
    root_dir = get_root_dir()
    config_path = root_dir / "config.json"
    if not config_path.exists():
        print_error(f"Config not found: {config_path}")
        sys.exit(1)
    try:
        with open(config_path) as f:
            config = json.load(f)
    except json.JSONDecodeError as e:
        print_error(f"Invalid JSON in config.json: {e}")
        sys.exit(1)

    for key in ("api_base", "sd_api_base", "api_key", "serper_api_key"):
        if key in config:
            raw = config[key]
            config[key] = resolve_env(raw)
            if isinstance(raw, str) and raw.startswith("env:") and not config[key]:
                console.print(warning(f"  env var {raw[4:]} not set -- set it or put the key directly in config.json"))

    config.setdefault("profile", "strict")
    if config["profile"] not in ("strict", "dev", "ci"):
        config["profile"] = "strict"

    required = ("api_base", "api_key")
    for key in required:
        if not config.get(key):
            print_error(f"Missing required config key: {key}")
            sys.exit(1)

    return config
