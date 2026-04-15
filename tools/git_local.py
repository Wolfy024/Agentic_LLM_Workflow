"""Local git operation tools — status, diff, log, commit, branch, etc."""

from __future__ import annotations
import subprocess

from .registry import tool, _resolve, WORKSPACE


def _git(*args: str, cwd: str | None = None) -> str:
    result = subprocess.run(
        ["git"] + list(args),
        cwd=cwd or WORKSPACE,
        capture_output=True, text=True, timeout=30,
    )
    output = result.stdout.strip()
    if result.returncode != 0:
        err = result.stderr.strip()
        return f"[exit {result.returncode}] {err or output}"
    return output or "(no output)"


@tool(
    name="git_status",
    description="Show working tree status (git status).",
    parameters={"type": "object", "properties": {}, "required": []},
)
def git_status() -> str:
    return _git("status", "--short", "--branch")


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
    name="git_init",
    description="Initialize a new git repository in the workspace. DESTRUCTIVE — requires permission.",
    parameters={"type": "object", "properties": {}, "required": []},
)
def git_init() -> str:
    return _git("init")


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
