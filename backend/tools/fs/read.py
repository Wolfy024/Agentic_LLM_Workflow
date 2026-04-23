"""
File reading tools.

Provides tools for reading file contents, extracting JSON paths,
and listing directory structures.
"""

from __future__ import annotations
import os
import json
from tools.registry import tool, _resolve, MAX_READ_SIZE, is_path_inside_workspace


@tool(
    name="read_file",
    description="Read the contents of a file. Returns the text content with line numbers. Use offset and limit to read in chunks (50-100 lines recommended). For large files (>250 lines), omitting offset/limit returns a structural outline with line ranges so you can read only the relevant sections.",
    parameters={
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "File path (relative to workspace or absolute)"},
            "offset": {"type": "integer", "description": "Start line (1-indexed). Omit for small files or to get an outline of large files."},
            "limit": {"type": "integer", "description": "Max lines to read (50-100 recommended). Omit for small files or to get an outline of large files."},
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
    total_lines = len(lines)

    # Smart mode: for large files without offset/limit, return outline instead of dumping everything
    if offset is None and limit is None and total_lines > 250:
        outline = _build_file_outline(lines, path)
        return (
            f"File: {path} ({total_lines} lines, {size:,} bytes) — TOO LARGE to dump.\n"
            f"Use offset/limit to read specific sections.\n\n"
            f"OUTLINE:\n{outline}\n\n"
            f"FIRST 30 LINES:\n"
            + "".join(f"{i+1:>6}|{line}" for i, line in enumerate(lines[:30]))
            + f"\n\n[Use read_file with offset/limit to read specific sections shown above.]"
        )

    start = (offset - 1) if offset and offset > 0 else 0
    end = (start + limit) if limit else len(lines)
    numbered = [f"{i+1:>6}|{line}" for i, line in enumerate(lines[start:end], start=start)]
    result = "".join(numbered) if numbered else "(empty file)"
    if end < total_lines:
        result += f"\n\n[TRUNCATED: {total_lines - end} more lines. Use offset={end + 1} to continue reading.]"
    return result


def _build_file_outline(lines: list[str], path: str) -> str:
    """Build a structural outline of a file showing key sections with line ranges."""
    import re
    ext = os.path.splitext(path)[1].lower()
    sections: list[str] = []

    # Try AST for Python files
    if ext == ".py":
        try:
            import ast
            source = "".join(lines)
            tree = ast.parse(source)
            for node in ast.iter_child_nodes(tree):
                if isinstance(node, ast.ClassDef):
                    methods = [n for n in node.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
                    method_info = ", ".join(m.name for m in methods[:8])
                    if len(methods) > 8:
                        method_info += f", ... +{len(methods) - 8} more"
                    sections.append(f"  L{node.lineno}-{node.end_lineno}: class {node.name} ({len(methods)} methods: {method_info})")
                elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    sections.append(f"  L{node.lineno}-{node.end_lineno}: def {node.name}()")
                elif isinstance(node, (ast.Import, ast.ImportFrom)):
                    if not sections or not sections[-1].startswith("  L") or "import" not in sections[-1]:
                        # Group consecutive imports
                        sections.append(f"  L{node.lineno}: imports")
            if sections:
                return "\n".join(sections)
        except Exception:
            pass  # Fall through to regex-based outline

    # Regex-based outline for all languages
    patterns = [
        (r'^(class|struct|interface|enum|type)\s+(\w+)', 'class'),
        (r'^(def|async def|function|async function|pub fn|fn)\s+(\w+)', 'function'),
        (r'^(export\s+)?(default\s+)?(class|function|const|let|var)\s+(\w+)', 'export'),
        (r'^#{1,3}\s+(.+)', 'heading'),  # Markdown headings
    ]
    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        for pat, kind in patterns:
            m = re.match(pat, stripped)
            if m:
                sections.append(f"  L{i}: {stripped[:80]}")
                break

    if not sections:
        # Fallback: show every ~50 lines as a section marker
        for i in range(0, len(lines), 50):
            preview = lines[i].strip()[:60]
            sections.append(f"  L{i+1}: {preview}")

    return "\n".join(sections[:60])


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


def _format_directory_listing(resolved: str) -> str:
    entries = []
    for entry in sorted(os.listdir(resolved)):
        full = os.path.join(resolved, entry)
        kind = "DIR" if os.path.isdir(full) else "FILE"
        size = os.path.getsize(full) if os.path.isfile(full) else ""
        entries.append(f"  [{kind}] {entry}" + (f"  ({size} bytes)" if size else ""))
    return "\n".join(entries) if entries else "(empty directory)"


@tool(
    name="list_directory",
    description="List files and directories at any path. Relative paths resolve against the workspace. Absolute paths work anywhere.",
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
    if not os.path.isdir(resolved):
        return f"Error: Not a directory: {path}"
    return _format_directory_listing(resolved)


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
