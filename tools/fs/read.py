"""
File reading tools.

Provides tools for reading file contents, extracting JSON paths,
and listing directory structures.
"""

from __future__ import annotations
import os
import json
from tools.registry import tool, _resolve, MAX_READ_SIZE


@tool(
    name="read_file",
    description="Read the contents of a file. Returns the text content with line numbers.",
    parameters={
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "File path (relative to workspace or absolute)"},
            "offset": {"type": "integer", "description": "Start line (1-indexed). Optional."},
            "limit": {"type": "integer", "description": "Max lines to read. Optional."},
        },
        "required": ["path"],
    },
)
def read_file(path: str, offset: int | None = None, limit: int | None = None) -> str:
    resolved = _resolve(path)
    size = os.path.getsize(resolved)
    if size > MAX_READ_SIZE:
        return f"Error: File is {size:,} bytes ({size/1_048_576:.1f} MB), exceeds 1 MB limit. Use offset/limit to read a portion."
    with open(resolved, "r", encoding="utf-8", errors="replace") as f:
        lines = f.readlines()
    start = (offset - 1) if offset and offset > 0 else 0
    end = (start + limit) if limit else len(lines)
    numbered = [f"{i+1:>6}|{line}" for i, line in enumerate(lines[start:end], start=start)]
    return "".join(numbered) if numbered else "(empty file)"


@tool(
    name="read_json",
    description="Read and parse a JSON file. Returns the parsed structure (or a specific key path).",
    parameters={
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Path to the JSON file"},
            "key_path": {"type": "string", "description": "Dot-separated key path to extract (e.g. 'scripts.build'). Optional — returns full JSON if omitted."},
        },
        "required": ["path"],
    },
)
def read_json(path: str, key_path: str | None = None) -> str:
    resolved = _resolve(path)
    with open(resolved, "r", encoding="utf-8") as f:
        data = json.load(f)
    if key_path:
        for key in key_path.split("."):
            if isinstance(data, dict):
                data = data.get(key)
            elif isinstance(data, list) and key.isdigit():
                data = data[int(key)]
            else:
                return f"Key path '{key_path}' not found"
            if data is None:
                return f"Key path '{key_path}' not found"
    return json.dumps(data, indent=2, default=str)[:6000]


@tool(
    name="list_directory",
    description="List files and directories at a given path.",
    parameters={
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Directory path. Defaults to workspace root."},
        },
        "required": [],
    },
)
def list_directory(path: str = ".") -> str:
    resolved = _resolve(path)
    entries = []
    for entry in sorted(os.listdir(resolved)):
        full = os.path.join(resolved, entry)
        kind = "DIR" if os.path.isdir(full) else "FILE"
        size = os.path.getsize(full) if os.path.isfile(full) else ""
        entries.append(f"  [{kind}] {entry}" + (f"  ({size} bytes)" if size else ""))
    return "\n".join(entries) if entries else "(empty directory)"


@tool(
    name="tree",
    description="Show a tree view of the directory structure.",
    parameters={
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Root path. Defaults to workspace."},
            "max_depth": {"type": "integer", "description": "Max depth. Default 3."},
            "show_hidden": {"type": "boolean", "description": "Show hidden files? Default false."},
        },
        "required": [],
    },
)
def tree(path: str = ".", max_depth: int = 3, show_hidden: bool = False) -> str:
    resolved = _resolve(path)
    skip = {".git", "node_modules", "__pycache__", ".venv", "venv", ".tox", "dist", "build", ".next"}
    lines: list[str] = []

    def _walk(dir_path: str, prefix: str, depth: int):
        if depth > max_depth:
            return
        try:
            entries = sorted(os.listdir(dir_path))
        except PermissionError:
            return
        if not show_hidden:
            entries = [e for e in entries if not e.startswith(".")]
        entries = [e for e in entries if e not in skip]
        for i, entry in enumerate(entries):
            is_last = i == len(entries) - 1
            connector = "└── " if is_last else "├── "
            full = os.path.join(dir_path, entry)
            if os.path.isdir(full):
                lines.append(f"{prefix}{connector}{entry}/")
                ext = "    " if is_last else "│   "
                _walk(full, prefix + ext, depth + 1)
            else:
                lines.append(f"{prefix}{connector}{entry}")

    root_name = os.path.basename(resolved) or resolved
    lines.append(f"{root_name}/")
    _walk(resolved, "", 1)
    return "\n".join(lines[:500])
