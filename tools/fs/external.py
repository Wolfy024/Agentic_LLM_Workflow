"""
Access files outside the workspace.

Reading arbitrary paths and importing copies into the workspace require explicit
approval (strict/dev). All normal edits should target paths under the workspace
after import.
"""

from __future__ import annotations

import os
import shutil

from tools.registry import (
    MAX_READ_SIZE,
    WORKSPACE,
    _resolve,
    is_path_inside_workspace,
    tool,
)


# Larger than text reads — binaries and archives.
MAX_EXTERNAL_IMPORT_BYTES = 100 * 1024 * 1024  # 100 MiB


@tool(
    name="read_external_file",
    description=(
        "Read a text file from an absolute path OUTSIDE the current workspace (preview only). "
        "For files already in the workspace, use read_file instead. "
        "Subject to size limit; use offset/limit for large files."
    ),
    parameters={
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Absolute path to a file on disk (must be outside the workspace)",
            },
            "offset": {"type": "integer", "description": "Start line (1-indexed). Optional."},
            "limit": {"type": "integer", "description": "Max lines to read. Optional."},
        },
        "required": ["path"],
    },
)
def read_external_file(path: str, offset: int | None = None, limit: int | None = None) -> str:
    resolved = os.path.abspath(os.path.normpath(path))
    if not os.path.isfile(resolved):
        return f"Error: Not a file or does not exist: {path}"
    if is_path_inside_workspace(resolved):
        return (
            "Error: Path is inside the workspace — use read_file with a workspace-relative path "
            f"(current workspace: {WORKSPACE})"
        )
    size = os.path.getsize(resolved)
    if size > MAX_READ_SIZE:
        return (
            f"Error: File is {size:,} bytes ({size / 1_048_576:.1f} MB), exceeds read limit "
            f"({MAX_READ_SIZE // 1_048_576} MiB). Use offset/limit after splitting, or import_external_file."
        )
    with open(resolved, "r", encoding="utf-8", errors="replace") as f:
        lines = f.readlines()
    start = (offset - 1) if offset and offset > 0 else 0
    end = (start + limit) if limit else len(lines)
    numbered = [f"{i + 1:>6}|{line}" for i, line in enumerate(lines[start:end], start=start)]
    return "".join(numbered) if numbered else "(empty file)"


@tool(
    name="import_external_file",
    description=(
        "Copy a file from any absolute path OUTSIDE the workspace into the workspace. "
        "Then edit the destination path with write_file, replace_in_file, etc. "
        "Does not modify the original file. Use a destination like .minillm/imports/<name>."
    ),
    parameters={
        "type": "object",
        "properties": {
            "source": {
                "type": "string",
                "description": "Absolute path to the existing file to copy (outside workspace)",
            },
            "destination": {
                "type": "string",
                "description": "Path inside the workspace for the copy (relative to workspace root)",
            },
        },
        "required": ["source", "destination"],
    },
)
def import_external_file(source: str, destination: str) -> str:
    src = os.path.abspath(os.path.normpath(source))
    if not os.path.isfile(src):
        return f"Error: Source is not a file or does not exist: {source}"
    if is_path_inside_workspace(src):
        return (
            "Error: Source is already under the workspace — use read_file / normal edit tools on that path. "
            f"Workspace: {WORKSPACE}"
        )
    size = os.path.getsize(src)
    if size > MAX_EXTERNAL_IMPORT_BYTES:
        return (
            f"Error: Source is {size:,} bytes; max import size is {MAX_EXTERNAL_IMPORT_BYTES // (1024 * 1024)} MiB."
        )

    dest_resolved = _resolve(destination)
    parent = os.path.dirname(dest_resolved)
    if parent:
        os.makedirs(parent, exist_ok=True)
    shutil.copy2(src, dest_resolved)
    nbytes = os.path.getsize(dest_resolved)
    return (
        f"Copied external file into workspace at {destination} ({nbytes:,} bytes). "
        f"Edit only this workspace path; the original at {src} is unchanged."
    )
