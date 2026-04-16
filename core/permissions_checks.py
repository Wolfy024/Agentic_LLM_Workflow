"""
Permission checks logic.

Manages profiles (strict, dev, ci) and checks whether a given tool invocation
is considered destructive or strictly denied by the profile.
"""

from __future__ import annotations

# File create/modify inside the workspace (write, patch, replace, mkdir, move) do not
# require approval. Only deletion and non-file destructive ops are gated.
DESTRUCTIVE_TOOLS = {
    "delete_file", "git_init", "git_commit", "git_checkout",
    "git_branch_delete", "git_reset", "git_stash", "git_push",
    "git_pull", "git_clone", "run_command"
}

CONTEXT_DESTRUCTIVE_TOOLS = {
    "github_api": lambda args: args.get("method", "GET") != "GET",
    "git_tag": lambda args: args.get("action") in ("create", "delete"),
    "git_remote": lambda args: args.get("action") in ("add", "remove"),
}

CI_DENIED_TOOLS = frozenset({
    "write_file", "append_to_file", "patch_file", "delete_file", "replace_in_file",
    "move_file", "create_directory",
    "git_init", "git_commit", "git_checkout", "git_branch_delete", "git_reset",
    "git_stash", "git_push", "git_pull", "git_clone", "run_command",
})

_profile: str = "strict"


def set_profile(name: str) -> None:
    """Set standard tool-blocking profile."""
    global _profile
    n = (name or "strict").lower().strip()
    if n not in ("strict", "dev", "ci"):
        n = "strict"
    _profile = n


def get_profile() -> str:
    """Retrieve the current tool-blocking profile."""
    return _profile


def is_tool_denied_in_profile(tool_name: str, args: dict) -> bool:
    """In profile 'ci', block mutating tools. dev matches strict for now."""
    if _profile != "ci":
        return False
    if tool_name in CI_DENIED_TOOLS:
        return True
    if tool_name == "git_remote" and args.get("action", "list") in ("add", "remove"):
        return True
    if tool_name == "git_tag" and args.get("action", "list") in ("create", "delete"):
        return True
    if tool_name == "github_api" and args.get("method", "GET") != "GET":
        return True
    return False


def is_destructive(tool_name: str, args: dict) -> bool:
    """Check if the given tool requires explicit approval."""
    if tool_name in DESTRUCTIVE_TOOLS:
        return True
    checker = CONTEXT_DESTRUCTIVE_TOOLS.get(tool_name)
    if checker and checker(args):
        return True
    return False
