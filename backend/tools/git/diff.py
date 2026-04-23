"""
Git diffing and branch management tools.

Provides comparisons between refs and branch creation/deletion capabilities.
"""

from __future__ import annotations
from tools.registry import tool, _resolve
from tools.git.core import _git


@tool(
    name="git_diff",
    description="Show diffs — unstaged by default, or staged with --staged.",
    parameters={
        "type": "object",
        "properties": {
            "staged": {"type": "boolean", "description": "Show staged changes? Default false."},
            "path": {"type": "string", "description": "Limit diff to specific path. Optional."},
        },
        "required": [],
    },
)
def git_diff(staged: bool = False, path: str | None = None) -> str:
    args = ["diff"]
    if staged:
        args.append("--staged")
    if path:
        args += ["--", _resolve(path)]
    return _git(*args)


@tool(
    name="git_diff_between",
    description="Show diff between two branches, tags, or commits.",
    parameters={
        "type": "object",
        "properties": {
            "ref_a": {"type": "string", "description": "First ref (branch/tag/commit)"},
            "ref_b": {"type": "string", "description": "Second ref"},
            "stat_only": {"type": "boolean", "description": "Show only file change summary? Default false."},
            "path": {"type": "string", "description": "Limit to specific path. Optional."},
        },
        "required": ["ref_a", "ref_b"],
    },
)
def git_diff_between(ref_a: str, ref_b: str, stat_only: bool = False, path: str | None = None) -> str:
    args = ["diff", f"{ref_a}...{ref_b}"]
    if stat_only:
        args.append("--stat")
    if path:
        args += ["--", _resolve(path)]
    return _git(*args)


@tool(
    name="git_branch",
    description="List branches or show the current branch.",
    parameters={
        "type": "object",
        "properties": {
            "all": {"type": "boolean", "description": "Show all (including remote)? Default false."},
        },
        "required": [],
    },
)
def git_branch(all: bool = False) -> str:
    args = ["branch"]
    if all:
        args.append("-a")
    return _git(*args)


@tool(
    name="git_branch_delete",
    description="Delete a git branch. DESTRUCTIVE — requires permission.",
    parameters={
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "Branch name to delete"},
            "force": {"type": "boolean", "description": "Force delete unmerged branch? Default false."},
        },
        "required": ["name"],
    },
)
def git_branch_delete(name: str, force: bool = False) -> str:
    flag = "-D" if force else "-d"
    return _git("branch", flag, name)
