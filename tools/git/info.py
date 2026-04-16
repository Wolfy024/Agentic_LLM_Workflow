"""
Git information and search utilities.

Tools to query git history, check working tree status, blame files,
and search through commits.
"""

from __future__ import annotations
from tools.registry import tool, _resolve
from tools.git.core import _git


@tool(
    name="git_status",
    description="Show working tree status (git status).",
    parameters={"type": "object", "properties": {}, "required": []},
)
def git_status() -> str:
    return _git("status", "--short", "--branch")


@tool(
    name="git_log",
    description="Show recent commit history.",
    parameters={
        "type": "object",
        "properties": {
            "count": {"type": "integer", "description": "Number of commits. Default 10."},
            "oneline": {"type": "boolean", "description": "One-line format? Default true."},
            "path": {"type": "string", "description": "Limit to path. Optional."},
        },
        "required": [],
    },
)
def git_log(count: int = 10, oneline: bool = True, path: str | None = None) -> str:
    args = ["log", f"-{count}"]
    if oneline:
        args.append("--oneline")
    else:
        args.append("--format=%h %an %ar %s")
    if path:
        args += ["--", _resolve(path)]
    return _git(*args)


@tool(
    name="git_show",
    description="Show the content of a specific commit.",
    parameters={
        "type": "object",
        "properties": {
            "ref": {"type": "string", "description": "Commit hash, branch, or tag."},
        },
        "required": ["ref"],
    },
)
def git_show(ref: str) -> str:
    return _git("show", ref, "--stat")


@tool(
    name="git_search",
    description="Search git history for a pattern (git log --grep or -S for code changes).",
    parameters={
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Search query"},
            "mode": {
                "type": "string",
                "enum": ["message", "code"],
                "description": "'message' searches commit messages, 'code' searches diffs for added/removed text.",
            },
            "count": {"type": "integer", "description": "Max results. Default 15."},
        },
        "required": ["query"],
    },
)
def git_search(query: str, mode: str = "message", count: int = 15) -> str:
    if mode == "code":
        return _git("log", f"-{count}", "--oneline", f"-S{query}")
    return _git("log", f"-{count}", "--oneline", f"--grep={query}")


@tool(
    name="git_blame",
    description="Show git blame for a file (who last modified each line).",
    parameters={
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "File path"},
            "start_line": {"type": "integer", "description": "Start line. Optional."},
            "end_line": {"type": "integer", "description": "End line. Optional."},
        },
        "required": ["path"],
    },
)
def git_blame(path: str, start_line: int | None = None, end_line: int | None = None) -> str:
    args = ["blame"]
    if start_line and end_line:
        args += [f"-L{start_line},{end_line}"]
    args.append(_resolve(path))
    return _git(*args)
