"""
File editing and patching tools.

Provides the ability to replace text in files or apply multi-block patches,
along with functions to preview those edits.
"""

from __future__ import annotations
from tools.registry import tool, _resolve


def preview_replace_in_file(
    path: str, old_string: str, new_string: str, replace_all: bool = False
) -> tuple[bool, str, str]:
    """Compute before/after full file text for replace_in_file (no writes)."""
    try:
        resolved = _resolve(path)
    except PermissionError as e:
        return False, str(e), ""
    try:
        with open(resolved, "r", encoding="utf-8") as f:
            text = f.read()
    except OSError as e:
        return False, str(e), ""
    count = text.count(old_string)
    if count == 0:
        return False, f"old_string not found in {path}", ""
    if not replace_all and count > 1:
        return (
            False,
            f"old_string found {count} times in {path}; set replace_all=true or narrow the match.",
            "",
        )
    new_text = text.replace(old_string, new_string) if replace_all else text.replace(old_string, new_string, 1)
    return True, text, new_text


def preview_patch_file(path: str, edits: list[dict]) -> tuple[bool, str, str]:
    """Compute before/after full file text for patch_file (no writes)."""
    try:
        resolved = _resolve(path)
    except PermissionError as e:
        return False, str(e), ""
    try:
        with open(resolved, "r", encoding="utf-8") as f:
            lines = f.readlines()
    except OSError as e:
        return False, str(e), ""
    before = "".join(lines)
    edits_sorted = sorted(edits, key=lambda e: e["start_line"], reverse=True)
    try:
        for edit in edits_sorted:
            s = edit["start_line"] - 1
            e = edit["end_line"]
            new_lines = edit["new_text"].splitlines(keepends=True)
            if new_lines and not new_lines[-1].endswith("\n"):
                new_lines[-1] += "\n"
            lines[s:e] = new_lines
    except (TypeError, KeyError, IndexError) as ex:
        return False, str(ex), ""
    return True, before, "".join(lines)


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
        return f"Error: old_string found {count} times. Set replace_all=true."
    new_text = text.replace(old_string, new_string) if replace_all else text.replace(old_string, new_string, 1)
    with open(resolved, "w", encoding="utf-8") as f:
        f.write(new_text)
    replaced = count if replace_all else 1
    # Track updated file in retrieval memory
    try:
        from tools.fs.search import track_file
        track_file(path, resolved, new_text, new_text.count("\n") + 1)
    except Exception:
        pass
    return f"Replaced {replaced} occurrence(s) in {path}"


@tool(
    name="patch_file",
    description="Apply a multi-block edit to a file using line-range replacements. DESTRUCTIVE — requires permission.",
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
    # Track updated file in retrieval memory
    try:
        from tools.fs.search import track_file
        full_text = "".join(lines)
        track_file(path, resolved, full_text, full_text.count("\n") + 1)
    except Exception:
        pass
    return f"Applied {len(edits)} edit(s) to {path}"


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
