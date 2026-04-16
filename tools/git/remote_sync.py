"""
Remote git syncing operations.

Tools to manage remotes, push, pull, fetch, and clone repositories.
"""

from __future__ import annotations
from tools.registry import tool, _resolve
from tools.git.core import _git


@tool(
    name="git_remote",
    description="Show or manage git remotes.",
    parameters={
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["list", "add", "remove"],
                "description": "Action. Default 'list'.",
            },
            "name": {"type": "string", "description": "Remote name (for add/remove)."},
            "url": {"type": "string", "description": "Remote URL (for add)."},
        },
        "required": [],
    },
)
def git_remote(action: str = "list", name: str | None = None, url: str | None = None) -> str:
    if action == "list":
        return _git("remote", "-v")
    elif action == "add" and name and url:
        return _git("remote", "add", name, url)
    elif action == "remove" and name:
        return _git("remote", "remove", name)
    return "Error: provide name (and url for add)"


@tool(
    name="git_push",
    description="Push commits to a remote. DESTRUCTIVE — requires permission.",
    parameters={
        "type": "object",
        "properties": {
            "remote": {"type": "string", "description": "Remote name. Default 'origin'."},
            "branch": {"type": "string", "description": "Branch to push. Default: current branch."},
            "set_upstream": {"type": "boolean", "description": "Set upstream tracking (-u). Default false."},
            "force": {"type": "boolean", "description": "Force push? Default false. DANGEROUS."},
        },
        "required": [],
    },
)
def git_push(remote: str = "origin", branch: str | None = None, set_upstream: bool = False, force: bool = False) -> str:
    args = ["push"]
    if set_upstream:
        args.append("-u")
    if force:
        args.append("--force-with-lease")
    args.append(remote)
    if branch:
        args.append(branch)
    return _git(*args)


@tool(
    name="git_pull",
    description="Pull changes from a remote. DESTRUCTIVE — requires permission.",
    parameters={
        "type": "object",
        "properties": {
            "remote": {"type": "string", "description": "Remote name. Default 'origin'."},
            "branch": {"type": "string", "description": "Branch to pull. Optional."},
            "rebase": {"type": "boolean", "description": "Rebase instead of merge? Default false."},
        },
        "required": [],
    },
)
def git_pull(remote: str = "origin", branch: str | None = None, rebase: bool = False) -> str:
    args = ["pull"]
    if rebase:
        args.append("--rebase")
    args.append(remote)
    if branch:
        args.append(branch)
    return _git(*args)


@tool(
    name="git_fetch",
    description="Fetch refs from a remote (does not modify working tree).",
    parameters={
        "type": "object",
        "properties": {
            "remote": {"type": "string", "description": "Remote name. Default 'origin'."},
            "prune": {"type": "boolean", "description": "Prune deleted remote branches? Default false."},
        },
        "required": [],
    },
)
def git_fetch(remote: str = "origin", prune: bool = False) -> str:
    args = ["fetch", remote]
    if prune:
        args.append("--prune")
    return _git(*args)


@tool(
    name="git_clone",
    description="Clone a repository. DESTRUCTIVE — requires permission (creates files).",
    parameters={
        "type": "object",
        "properties": {
            "url": {"type": "string", "description": "Repository URL (HTTPS or SSH)"},
            "dest": {"type": "string", "description": "Destination folder. Optional (uses repo name)."},
            "depth": {"type": "integer", "description": "Shallow clone depth. Optional."},
        },
        "required": ["url"],
    },
)
def git_clone(url: str, dest: str | None = None, depth: int | None = None) -> str:
    args = ["clone"]
    if depth:
        args += ["--depth", str(depth)]
    args.append(url)
    if dest:
        args.append(_resolve(dest))
    return _git(*args)
