"""
Persistent user preferences management for LLM Orchestrator.

This module handles loading and saving user configuration files located
under the `~/.minillm/` directory.

Attributes:
    PREFS_DIR (str): Absolute path to the config directory.
    PREFS_PATH (str): Absolute path to the preferences JSON file.
"""

from __future__ import annotations
import json
import os
import tempfile

PREFS_DIR = os.path.join(os.path.expanduser("~"), ".minillm")
PREFS_PATH = os.path.join(PREFS_DIR, "preferences.json")


def load_prefs() -> dict:
    """
    Load user preferences from the JSON configuration file.

    Returns:
        dict: The loaded preferences dictionary, or an empty dict if the 
              file is missing or corrupted.
    """
    if not os.path.exists(PREFS_PATH):
        return {}
    try:
        with open(PREFS_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def save_prefs(prefs: dict) -> None:
    """
    Atomically save the given dictionary as user preferences.

    Uses write-to-temp + rename to prevent corruption on crash.
    """
    os.makedirs(PREFS_DIR, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(dir=PREFS_DIR, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(prefs, f, indent=2)
        os.replace(tmp_path, PREFS_PATH)
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise

