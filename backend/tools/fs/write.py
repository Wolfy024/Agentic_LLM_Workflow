"""
File writing and creation tools.

Provides tools for writing new files, appending to files, creating directories,
moving files, and deleting entities.
"""

from __future__ import annotations
import os
from tools.registry import tool, _resolve


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
    parent = os.path.dirname(resolved)
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(resolved, "w", encoding="utf-8") as f:
        f.write(content)
    return f"Wrote {len(content)} bytes to {path}"


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
    parent = os.path.dirname(resolved)
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(resolved, "a", encoding="utf-8") as f:
        f.write(content)
    return f"Appended {len(content)} bytes to {path}"


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
