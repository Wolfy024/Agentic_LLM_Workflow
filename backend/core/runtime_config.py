"""
Runtime config singleton.

Stores the loaded config dict so modules can read tunable parameters
without needing config passed through every call stack.
"""

from __future__ import annotations

_CONFIG: dict = {}


def set_runtime_config(config: dict) -> None:
    """Set the global runtime config (called once at startup)."""
    global _CONFIG
    _CONFIG = config


def get(key: str, default=None):
    """Read a config value. Falls back to default if missing."""
    return _CONFIG.get(key, default)
