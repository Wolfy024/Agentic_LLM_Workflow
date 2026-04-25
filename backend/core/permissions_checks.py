"""
Permission checks logic.

Manages profiles (strict, dev, ci) and checks whether a given tool invocation
is considered destructive or strictly denied by the profile.
"""

from __future__ import annotations

import os as _os


def _list_directory_targets_outside_workspace(args: dict) -> bool:
    """True when list_directory's path resolves outside WORKSPACE (prompt in strict; deny in ci)."""
    from tools.registry import WORKSPACE as _ws, is_path_inside_workspace

    p = args.get("path", ".") or "."
    if _os.path.isabs(p):
        r = _os.path.abspath(_os.path.normpath(p))
    else:
        r = _os.path.abspath(_os.path.normpath(_os.path.join(_ws, p)))
    return not is_path_inside_workspace(r)


# File create/modify inside the workspace (write, patch, replace, mkdir, move) do not
# require approval. Only deletion and non-file destructive ops are gated.
DESTRUCTIVE_TOOLS = {
    "delete_file", "git_init", "git_commit", "git_checkout",
    "git_branch_delete", "git_reset", "git_stash", "git_push",
    "git_pull", "git_clone", "run_command",
    "read_external_file", "import_external_file",
}

CONTEXT_DESTRUCTIVE_TOOLS = {
    "github_api": lambda args: args.get("method", "GET") != "GET",
    "git_tag": lambda args: args.get("action") in ("create", "delete"),
    "git_remote": lambda args: args.get("action") in ("add", "remove"),
    # list_directory outside workspace is read-only — no y/n prompt (CI still blocks via is_tool_denied_in_profile).
}

CI_DENIED_TOOLS = frozenset({
    "write_file", "append_to_file", "patch_file", "delete_file", "replace_in_file",
    "move_file", "create_directory", "download_url",
    "read_external_file", "import_external_file",
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
    """In profile 'ci', block mutating tools. dev matches strict for now.

    Also handles MCP tools: denied if the server's permission is 'deny',
    or if the profile is 'ci' and the MCP tool isn't explicitly allowed.
    """
    # --- MCP tool checks ---
    try:
        from mcp.manager import get_manager
        mgr = get_manager()
        if mgr.is_mcp_tool(tool_name):
            if mgr.is_mcp_tool_denied(tool_name):
                return True  # Explicitly denied in config
            if _profile == "ci":
                return True  # CI blocks all MCP tools by default
    except Exception:
        pass

    # --- Native tool checks ---
    if _profile != "ci":
        return False
    if tool_name == "list_directory" and _list_directory_targets_outside_workspace(args):
        return True
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
    """Check if the given tool requires explicit approval.

    Covers both native tools and MCP tools (via the manager's per-tool
    permission classification).
    """
    if tool_name in DESTRUCTIVE_TOOLS:
        return True
    checker = CONTEXT_DESTRUCTIVE_TOOLS.get(tool_name)
    if checker and checker(args):
        return True
    # MCP tools classified as "destructive" in config also need approval
    try:
        from mcp.manager import get_manager
        mgr = get_manager()
        if mgr.is_mcp_tool(tool_name) and mgr.is_mcp_tool_destructive(tool_name):
            return True
    except Exception:
        pass
    return False
