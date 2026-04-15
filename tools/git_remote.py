"""Remote git and GitHub tools — push, pull, fetch, clone, remotes, GitHub API."""

from __future__ import annotations
import subprocess

from .registry import tool, _resolve, WORKSPACE
from .git_local import _git


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
    description="Push commits to a remote. DESTRUCTIVE — requires permission. Needs git credentials configured on the machine (SSH key, credential helper, or gh auth).",
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
            "depth": {"type": "integer", "description": "Shallow clone depth. Optional (full clone if omitted)."},
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


@tool(
    name="git_credential_check",
    description="Check if git credentials are configured. Shows the credential helper and tests SSH access to github.com.",
    parameters={"type": "object", "properties": {}, "required": []},
)
def git_credential_check() -> str:
    lines = []
    helper = _git("config", "--global", "credential.helper")
    lines.append(f"credential.helper: {helper}")
    user = _git("config", "--global", "user.name")
    lines.append(f"user.name: {user}")
    email = _git("config", "--global", "user.email")
    lines.append(f"user.email: {email}")
    try:
        result = subprocess.run(
            ["gh", "auth", "status"], capture_output=True, text=True, timeout=10
        )
        gh_out = result.stdout.strip() or result.stderr.strip()
        lines.append(f"gh auth: {gh_out}")
    except (FileNotFoundError, subprocess.TimeoutExpired):
        lines.append("gh CLI: not installed")
    try:
        result = subprocess.run(
            ["ssh", "-T", "git@github.com"], capture_output=True, text=True, timeout=10
        )
        ssh_out = result.stderr.strip() or result.stdout.strip()
        lines.append(f"SSH github.com: {ssh_out}")
    except (FileNotFoundError, subprocess.TimeoutExpired):
        lines.append("SSH: not available or timed out")
    return "\n".join(lines)


@tool(
    name="github_api",
    description="Call the GitHub API via the gh CLI (must be installed and authed with `gh auth login`). Use for PRs, issues, releases, repo info, etc.",
    parameters={
        "type": "object",
        "properties": {
            "endpoint": {
                "type": "string",
                "description": "API endpoint path, e.g. 'repos/owner/repo/pulls' or 'repos/owner/repo/issues'",
            },
            "method": {
                "type": "string",
                "enum": ["GET", "POST", "PATCH", "PUT", "DELETE"],
                "description": "HTTP method. Default GET.",
            },
            "body": {
                "type": "string",
                "description": "JSON body for POST/PATCH/PUT. Optional.",
            },
        },
        "required": ["endpoint"],
    },
)
def github_api(endpoint: str, method: str = "GET", body: str | None = None) -> str:
    args = ["gh", "api", endpoint, "--method", method]
    if body:
        args += ["--input", "-"]
    try:
        result = subprocess.run(
            args, capture_output=True, text=True, timeout=30,
            cwd=WORKSPACE, input=body,
        )
        output = result.stdout.strip()
        if result.returncode != 0:
            err = result.stderr.strip()
            return f"[exit {result.returncode}] {err or output}"
        return output[:8000] if output else "(no output)"
    except FileNotFoundError:
        return "Error: gh CLI not installed. Install from https://cli.github.com and run `gh auth login`"
    except subprocess.TimeoutExpired:
        return "Error: request timed out"
