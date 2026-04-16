"""
File searching and metadata inspection tools.

Provides functions to find files by glob or regex, extract structural summaries 
for large files, get file info, and estimate token counts.
"""

from __future__ import annotations
import os
import fnmatch
import pathlib
from tools.registry import tool, _resolve, MAX_READ_SIZE


@tool(
    name="find_files",
    description="Find files matching a glob pattern recursively in the workspace.",
    parameters={
        "type": "object",
        "properties": {
            "pattern": {"type": "string", "description": "Glob pattern (e.g. '*.py', 'src/**/*.ts')"},
            "path": {"type": "string", "description": "Directory to search. Defaults to workspace root."},
        },
        "required": ["pattern"],
    },
)
def find_files(pattern: str, path: str = ".") -> str:
    resolved = _resolve(path)
    matches = []
    for p in pathlib.Path(resolved).rglob(pattern):
        matches.append(str(p.relative_to(resolved)))
    matches.sort()
    if not matches:
        return f"No files matching '{pattern}'"
    return "\n".join(matches[:200]) + (f"\n... and {len(matches)-200} more" if len(matches) > 200 else "")


@tool(
    name="search_files",
    description="Search for a text pattern (regex supported) across files in the workspace. Like ripgrep.",
    parameters={
        "type": "object",
        "properties": {
            "pattern": {"type": "string", "description": "Search pattern (regex)"},
            "path": {"type": "string", "description": "Directory to search. Defaults to workspace."},
            "file_pattern": {"type": "string", "description": "Glob to filter files (e.g. '*.py'). Optional."},
            "max_results": {"type": "integer", "description": "Max results. Default 50."},
        },
        "required": ["pattern"],
    },
)
def search_files(pattern: str, path: str = ".", file_pattern: str | None = None, max_results: int = 50) -> str:
    import re
    resolved = _resolve(path)
    regex = re.compile(pattern, re.IGNORECASE)
    results = []
    root = pathlib.Path(resolved)

    skip_dirs = {".git", "node_modules", "__pycache__", ".venv", "venv", ".tox", "dist", "build"}

    for fpath in root.rglob("*"):
        if any(part in skip_dirs for part in fpath.parts):
            continue
        if not fpath.is_file():
            continue
        if file_pattern and not fnmatch.fnmatch(fpath.name, file_pattern):
            continue
        try:
            if fpath.stat().st_size > MAX_READ_SIZE:
                continue
            text = fpath.read_text(encoding="utf-8", errors="replace")
        except (PermissionError, OSError):
            continue
        for i, line in enumerate(text.splitlines(), 1):
            if regex.search(line):
                rel = str(fpath.relative_to(resolved))
                results.append(f"{rel}:{i}: {line.strip()}")
                if len(results) >= max_results:
                    return "\n".join(results) + f"\n(capped at {max_results} results)"
    return "\n".join(results) if results else f"No matches for '{pattern}'"


@tool(
    name="file_info",
    description="Get metadata about a file (size, modified time, type, line count).",
    parameters={
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "File path"},
        },
        "required": ["path"],
    },
)
def file_info(path: str) -> dict:
    resolved = _resolve(path)
    stat = os.stat(resolved)
    import time
    line_count = None
    if os.path.isfile(resolved):
        try:
            with open(resolved, "r", encoding="utf-8", errors="replace") as f:
                line_count = sum(1 for _ in f)
        except Exception:
            pass
    return {
        "path": path,
        "resolved": resolved,
        "size_bytes": stat.st_size,
        "line_count": line_count,
        "modified": time.ctime(stat.st_mtime),
        "is_file": os.path.isfile(resolved),
        "is_dir": os.path.isdir(resolved),
    }


@tool(
    name="summarize_code",
    description="Extract the structure of a source file: classes, functions, imports. Great for large files.",
    parameters={
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "File path"},
        },
        "required": ["path"],
    },
)
def summarize_code(path: str) -> str:
    import re as _re
    resolved = _resolve(path)
    with open(resolved, "r", encoding="utf-8", errors="replace") as f:
        lines = f.readlines()

    sections: dict[str, list[str]] = {"imports": [], "classes": [], "functions": [], "exports": [], "other": []}
    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or stripped.startswith("//"):
            continue
        if _re.match(r"^(import |from .+ import |const .+ = require|#include|using )", stripped):
            sections["imports"].append(f"  L{i}: {stripped}")
        elif _re.match(r"^(class |struct |interface |enum |type )\w+", stripped):
            sections["classes"].append(f"  L{i}: {stripped}")
        elif _re.match(r"^(def |async def |function |async function |export (default )?(function|const|class)|pub fn |fn )", stripped):
            sections["functions"].append(f"  L{i}: {stripped}")
        elif _re.match(r"^(export |module\.exports|__all__)", stripped):
            sections["exports"].append(f"  L{i}: {stripped}")

    out = [f"File: {path} ({len(lines)} lines)"]
    for key, items in sections.items():
        if items:
            out.append(f"\n{key.upper()} ({len(items)}):")
            out.extend(items[:50])
            if len(items) > 50:
                out.append(f"  ... and {len(items)-50} more")
    return "\n".join(out) if len(out) > 1 else f"File: {path} ({len(lines)} lines) — no recognizable structure found"


@tool(
    name="count_tokens_estimate",
    description="Rough token count estimate for a file or text (words/0.75).",
    parameters={
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "File path to count. Provide this OR text."},
            "text": {"type": "string", "description": "Raw text to count. Provide this OR path."},
        },
        "required": [],
    },
)
def count_tokens_estimate(path: str | None = None, text: str | None = None) -> dict:
    if path:
        resolved = _resolve(path)
        with open(resolved, "r", encoding="utf-8", errors="replace") as f:
            text = f.read()
    if not text:
        return {"error": "Provide path or text"}
    words = len(text.split())
    chars = len(text)
    estimated_tokens = int(words / 0.75)
    return {"chars": chars, "words": words, "estimated_tokens": estimated_tokens}
