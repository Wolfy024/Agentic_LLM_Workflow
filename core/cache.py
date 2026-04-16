"""
Response cache for LLM models API responses.

This module caches GET /v1/models requests with a TTL (Time-To-Live),
preventing unnecessary API calls to lists that rarely change.

Attributes:
    CACHE_PATH (str): Absolute path to the cached JSON file.
    DEFAULT_TTL_SEC (int): Default cache lifetime in seconds (1 hour).
"""

from __future__ import annotations
import json
import os
import time

from core.prefs import PREFS_DIR

CACHE_PATH = os.path.join(PREFS_DIR, "models_cache.json")
DEFAULT_TTL_SEC = 3600


def _read_cache() -> dict | None:
    """
    Read raw cache data from disk.

    Returns:
        dict | None: The parsed dictionary from the cache file, or None if invalid/missing.
    """
    if not os.path.exists(CACHE_PATH):
        return None
    try:
        with open(CACHE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None


def get_cached_models(api_base: str, ttl_sec: float = DEFAULT_TTL_SEC) -> list[dict] | None:
    """
    Retrieve models from the cache if still valid.

    Args:
        api_base (str): The base URL of the LLM API to check against.
        ttl_sec (float): Number of seconds the cache is considered valid.

    Returns:
        list[dict] | None: List of cached models, or None if empty/expired.
    """
    data = _read_cache()
    if not data:
        return None
    if data.get("api_base") != api_base.rstrip("/"):
        return None
    ts = data.get("ts", 0)
    if time.time() - ts > ttl_sec:
        return None
    return data.get("models", [])


def set_cached_models(api_base: str, models: list[dict]) -> None:
    """
    Write models list to the persistent cache on disk.

    Args:
        api_base (str): The base URL string.
        models (list[dict]): Extracted models list from the API response payload.
    """
    os.makedirs(PREFS_DIR, exist_ok=True)
    payload = {"api_base": api_base.rstrip("/"), "ts": time.time(), "models": models}
    try:
        with open(CACHE_PATH, "w", encoding="utf-8") as f:
            json.dump(payload, f)
    except OSError:
        pass
