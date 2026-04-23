"""
Git structural operations.

Tools for commits, checkouts, tags, resets, and stashes.
"""

from __future__ import annotations
from tools.registry import tool
from tools.git.core import _git


@tool(
    name="git_commit",
    description="Stage files and commit. DESTRUCTIVE — requires permission.",
    parameters={
        "type": "object",
        "properties": {
            "message": {"type": "string", "description": "Commit message"},
            "files": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Files to stage. Use ['.'] for all.",
            },
        },
        "required": ["message"],
    },
)
def git_commit(message: str, files: list[str] | None = None) -> str:
    targets = files or ["."]
    for f in targets:
        _git("add", f)
    return _git("commit", "-m", message)


@tool(
    name="git_checkout",
    description="Checkout a branch or file. DESTRUCTIVE — requires permission.",
    parameters={
        "type": "object",
        "properties": {
            "target": {"type": "string", "description": "Branch name, commit, or file path."},
            "create": {"type": "boolean", "description": "Create new branch? Default false."},
        },
        "required": ["target"],
    },
)
def git_checkout(target: str, create: bool = False) -> str:
    args = ["checkout"]
    if create:
        args.append("-b")
    args.append(target)
    return _git(*args)


@tool(
    name="git_stash",
    description="Stash or pop working directory changes. DESTRUCTIVE — requires permission.",
    parameters={
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["push", "pop", "list", "drop", "show"],
                "description": "Stash action. Default 'push'.",
            },
            "message": {"type": "string", "description": "Stash message (only for push). Optional."},
        },
        "required": [],
    },
)
def git_stash(action: str = "push", message: str | None = None) -> str:
    args = ["stash", action]
    if action == "push" and message:
        args += ["-m", message]
    return _git(*args)


@tool(
    name="git_reset",
    description="Reset current HEAD to a state. DESTRUCTIVE — requires permission.",
    parameters={
        "type": "object",
        "properties": {
            "target": {"type": "string", "description": "Commit/ref to reset to. Default 'HEAD'."},
            "mode": {
                "type": "string",
                "enum": ["soft", "mixed", "hard"],
                "description": "Reset mode. Default 'mixed'. 'hard' discards all changes!",
            },
        },
        "required": [],
    },
)
def git_reset(target: str = "HEAD", mode: str = "mixed") -> str:
    return _git("reset", f"--{mode}", target)


@tool(
    name="git_tag",
    description="List or create git tags.",
    parameters={
        "type": "object",
        "properties": {
            "action": {"type": "string", "enum": ["list", "create", "delete"], "description": "Default 'list'."},
            "name": {"type": "string", "description": "Tag name (for create/delete)."},
            "message": {"type": "string", "description": "Annotated tag message (for create). Optional."},
        },
        "required": [],
    },
)
def git_tag(action: str = "list", name: str | None = None, message: str | None = None) -> str:
    if action == "list":
        return _git("tag", "-l", "--sort=-creatordate")
    elif action == "create" and name:
        if message:
            return _git("tag", "-a", name, "-m", message)
        return _git("tag", name)
    elif action == "delete" and name:
        return _git("tag", "-d", name)
    return "Error: provide tag name"
