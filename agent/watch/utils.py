"""
File watching utilities and path ignoring logic.

Supports loading .minillm/watch_ignore and filtering events
based on predefined core segments and extensions.
"""

from __future__ import annotations
import os
import re

_IGNORE_DIR_SEGMENTS = frozenset({
    ".git", "node_modules", "__pycache__", ".venv", "venv", "dist", "build",
    ".next", "target", ".tox", ".pytest_cache", ".mypy_cache", "coverage",
    "htmlcov", ".nuxt", ".output", "__MACOSX", ".gradle", ".idea", "obj", "bin",
    "site-packages", ".eggs",
})

_IGNORE_EXT_SUFFIXES = (
    ".pyc", ".pyo", ".tmp", ".swp", ".swo", ".ds_store", "thumbs.db",
    ".log", ".lock", ".sock",
)

_EMACS_LOCK = re.compile(r"^\.#")


def workspace_rel(workspace: str, abs_path: str) -> str:
    ws = os.path.normcase(os.path.abspath(workspace))
    ap = os.path.normcase(os.path.abspath(abs_path))
    if not ap.startswith(ws + os.sep) and ap != ws:
        return ""
    rel = os.path.relpath(ap, ws)
    return rel.replace("\\", "/")


def load_pathspec(workspace: str):
    path = os.path.join(workspace, ".minillm", "watch_ignore")
    if not os.path.isfile(path):
        return None
    try:
        import pathspec
        with open(path, encoding="utf-8", errors="replace") as f:
            lines = [ln.strip() for ln in f if ln.strip() and not ln.strip().startswith("#")]
        if not lines:
            return None
        return pathspec.PathSpec.from_lines("gitwildmatch", lines)
    except Exception:
        return None


def should_ignore_path(workspace: str, abs_path: str, spec) -> bool:
    rel = workspace_rel(workspace, abs_path)
    if not rel or rel == ".":
        return True
    parts = rel.split("/")
    for seg in parts:
        if seg in _IGNORE_DIR_SEGMENTS:
            return True
        if seg.endswith(".egg-info"):
            return True
        if seg.startswith(".#") or _EMACS_LOCK.match(seg):
            return True
    bl = parts[-1].lower()
    if bl.endswith(_IGNORE_EXT_SUFFIXES):
        return True
    if bl.startswith(".#"):
        return True
    if spec is not None and spec.match_file(rel):
        return True
    return False


def event_target_path(event) -> str:
    t = getattr(event, "event_type", "")
    if t == "moved":
        d = getattr(event, "dest_path", None) or ""
        if d:
            return d
    return getattr(event, "src_path", "") or ""


def build_user_message(paths: list[str]) -> str:
    lines = "\n".join(f"- {p}" for p in paths)
    return (
        f"[File watcher] {len(paths)} path(s) changed:\n{lines}\n"
        "Acknowledge briefly; re-read files if you need fresh content."
    )
