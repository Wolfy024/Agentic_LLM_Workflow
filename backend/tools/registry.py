"""Tool registry and core infrastructure.

Provides the @tool decorator, workspace management, path resolution with
sandboxing, and the execution engine that dispatches tool calls.
"""

from __future__ import annotations
import os
import json
from typing import Any

TOOL_REGISTRY: dict[str, tuple[Any, dict]] = {}
WORKSPACE: str = os.getcwd()


def _max_read_size() -> int:
    """Get max file read size in bytes from config (default 1 MB)."""
    import core.runtime_config as rc
    return int(rc.get("max_read_size_mb", 1)) * 1_048_576


MAX_READ_SIZE = 1_048_576  # module-level default; use _max_read_size() at runtime


def set_workspace(path: str):
    global WORKSPACE
    WORKSPACE = os.path.abspath(path)


def _resolve(path: str) -> str:
    """Resolve a path. Absolute paths are used as-is; relative paths resolve against WORKSPACE."""
    if os.path.isabs(path):
        resolved = os.path.normpath(path)
    else:
        resolved = os.path.normpath(os.path.join(WORKSPACE, path))
    return resolved


def is_path_inside_workspace(path: str) -> bool:
    """True if *path* resolves to a location under WORKSPACE (including the root itself)."""
    try:
        resolved = os.path.realpath(os.path.abspath(path))
        ws = os.path.realpath(WORKSPACE)
        return os.path.commonpath([resolved, ws]) == ws
    except (OSError, ValueError):
        return False


def tool(name: str, description: str, parameters: dict):
    """Decorator that registers a tool with its OpenAI-function-calling schema."""
    def decorator(fn):
        schema = {
            "type": "function",
            "function": {
                "name": name,
                "description": description,
                "parameters": parameters,
            },
        }
        TOOL_REGISTRY[name] = (fn, schema)
        return fn
    return decorator


def get_tool_schemas() -> list[dict]:
    """Return all tool schemas: native @tool + connected MCP servers."""
    native = [schema for _, schema in TOOL_REGISTRY.values()]
    try:
        from mcp.manager import get_manager
        mgr = get_manager()
        mcp_schemas = mgr.get_all_schemas()
        return native + mcp_schemas
    except Exception:
        return native


def execute_tool(name: str, args: dict) -> str:
    # --- Route to MCP server if tool is external ---
    if name not in TOOL_REGISTRY:
        try:
            from mcp.manager import get_manager
            mgr = get_manager()
            if mgr.is_mcp_tool(name):
                output = mgr.call_tool(name, args)
                _MAX_TOOL_OUTPUT = 40_000
                if len(output) > _MAX_TOOL_OUTPUT:
                    output = output[:_MAX_TOOL_OUTPUT] + f"\n... [output truncated at {_MAX_TOOL_OUTPUT:,} chars]"
                return output
        except Exception as e:
            return json.dumps({"error": f"MCP dispatch error: {type(e).__name__}: {e}"})
        return json.dumps({"error": f"Unknown tool: {name}"})

    fn, _ = TOOL_REGISTRY[name]
    try:
        result = fn(**args)
        if isinstance(result, str):
            output = result
        else:
            output = json.dumps(result, indent=2, default=str)
        # Global safety cap: prevent any single tool result from overwhelming the LLM
        _MAX_TOOL_OUTPUT = 40_000
        if len(output) > _MAX_TOOL_OUTPUT:
            output = output[:_MAX_TOOL_OUTPUT] + f"\n... [output truncated at {_MAX_TOOL_OUTPUT:,} chars]"
        return output
    except Exception as e:
        return json.dumps({"error": f"{type(e).__name__}: {e}"})
