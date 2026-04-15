"""File operation tools — read, write, search, diff, tree, etc."""

from __future__ import annotations
import os
import json
import fnmatch
import pathlib

from .registry import tool, _resolve, WORKSPACE, MAX_READ_SIZE


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
    name="write_file",
    description="Write content to a file. Creates parent directories if needed. DESTRUCTIVE — requires permission.",
    parameters={
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "File path"},
            "content": {"type": "string", "description": "Full file content to write"},
        },
        "required": ["path", "content"],
    },
)
def write_file(path: str, content: str) -> str:
    resolved = _resolve(path)
    os.makedirs(os.path.dirname(resolved) or ".", exist_ok=True)
    with open(resolved, "w", encoding="utf-8") as f:
        f.write(content)
    return f"Wrote {len(content)} bytes to {path}"


@tool(
    name="replace_in_file",
    description="Replace an exact string in a file with new content. DESTRUCTIVE — requires permission.",
    parameters={
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "File path"},
            "old_string": {"type": "string", "description": "Exact text to find"},
            "new_string": {"type": "string", "description": "Replacement text"},
            "replace_all": {"type": "boolean", "description": "Replace all occurrences? Default false."},
        },
        "required": ["path", "old_string", "new_string"],
    },
)
def replace_in_file(path: str, old_string: str, new_string: str, replace_all: bool = False) -> str:
    resolved = _resolve(path)
    with open(resolved, "r", encoding="utf-8") as f:
        text = f.read()
    count = text.count(old_string)
    if count == 0:
        return f"Error: old_string not found in {path}"
    if not replace_all and count > 1:
        return f"Error: old_string found {count} times. Set replace_all=true or provide more context."
    new_text = text.replace(old_string, new_string) if replace_all else text.replace(old_string, new_string, 1)
    with open(resolved, "w", encoding="utf-8") as f:
        f.write(new_text)
    replaced = count if replace_all else 1
    return f"Replaced {replaced} occurrence(s) in {path}"


@tool(
    name="delete_file",
    description="Delete a file. DESTRUCTIVE — requires permission.",
    parameters={
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "File path to delete"},
        },
        "required": ["path"],
    },
)
def delete_file(path: str) -> str:
    resolved = _resolve(path)
    os.remove(resolved)
    return f"Deleted {path}"


@tool(
    name="move_file",
    description="Move/rename a file. DESTRUCTIVE — requires permission.",
    parameters={
        "type": "object",
        "properties": {
            "source": {"type": "string", "description": "Source path"},
            "destination": {"type": "string", "description": "Destination path"},
        },
        "required": ["source", "destination"],
    },
)
def move_file(source: str, destination: str) -> str:
    src = _resolve(source)
    dst = _resolve(destination)
    os.makedirs(os.path.dirname(dst) or ".", exist_ok=True)
    os.rename(src, dst)
    return f"Moved {source} -> {destination}"


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
    name="create_directory",
    description="Create a directory (and parents). DESTRUCTIVE — requires permission.",
    parameters={
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Directory path to create"},
        },
        "required": ["path"],
    },
)
def create_directory(path: str) -> str:
    resolved = _resolve(path)
    os.makedirs(resolved, exist_ok=True)
    return f"Created directory {path}"


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
    name="append_to_file",
    description="Append content to the end of a file (creates it if missing). DESTRUCTIVE — requires permission.",
    parameters={
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "File path"},
            "content": {"type": "string", "description": "Content to append"},
        },
        "required": ["path", "content"],
    },
)
def append_to_file(path: str, content: str) -> str:
    resolved = _resolve(path)
    os.makedirs(os.path.dirname(resolved) or ".", exist_ok=True)
    with open(resolved, "a", encoding="utf-8") as f:
        f.write(content)
    return f"Appended {len(content)} bytes to {path}"


@tool(
    name="patch_file",
    description="Apply a multi-block edit to a file using line-range replacements. DESTRUCTIVE — requires permission. Each edit is {start_line, end_line, new_text} applied top-to-bottom.",
    parameters={
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "File path"},
            "edits": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "start_line": {"type": "integer", "description": "First line to replace (1-indexed)"},
                        "end_line": {"type": "integer", "description": "Last line to replace (inclusive)"},
                        "new_text": {"type": "string", "description": "Replacement text (may be multi-line)"},
                    },
                    "required": ["start_line", "end_line", "new_text"],
                },
                "description": "List of edits sorted by start_line ascending. Non-overlapping.",
            },
        },
        "required": ["path", "edits"],
    },
)
def patch_file(path: str, edits: list[dict]) -> str:
    resolved = _resolve(path)
    with open(resolved, "r", encoding="utf-8") as f:
        lines = f.readlines()
    edits_sorted = sorted(edits, key=lambda e: e["start_line"], reverse=True)
    for edit in edits_sorted:
        s = edit["start_line"] - 1
        e = edit["end_line"]
        new_lines = edit["new_text"].splitlines(keepends=True)
        if new_lines and not new_lines[-1].endswith("\n"):
            new_lines[-1] += "\n"
        lines[s:e] = new_lines
    with open(resolved, "w", encoding="utf-8") as f:
        f.writelines(lines)
    return f"Applied {len(edits)} edit(s) to {path}"


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
    description="Extract the structure of a source file: classes, functions, imports, and top-level definitions. Great for understanding a file without reading every line.",
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
    name="diff_files",
    description="Show a unified diff between two files.",
    parameters={
        "type": "object",
        "properties": {
            "file_a": {"type": "string", "description": "First file path"},
            "file_b": {"type": "string", "description": "Second file path"},
        },
        "required": ["file_a", "file_b"],
    },
)
def diff_files(file_a: str, file_b: str) -> str:
    import difflib
    resolved_a = _resolve(file_a)
    resolved_b = _resolve(file_b)
    with open(resolved_a, "r", encoding="utf-8", errors="replace") as f:
        lines_a = f.readlines()
    with open(resolved_b, "r", encoding="utf-8", errors="replace") as f:
        lines_b = f.readlines()
    diff = difflib.unified_diff(lines_a, lines_b, fromfile=file_a, tofile=file_b, lineterm="")
    result = "\n".join(diff)
    return result[:8000] if result else "Files are identical"


@tool(
    name="count_tokens_estimate",
    description="Rough token count estimate for a file or text (words/0.75). Useful for checking if content fits context window.",
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
