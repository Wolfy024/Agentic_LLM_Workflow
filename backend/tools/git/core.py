"""
Core git execution and initialization tools.

Provides the primitive `_git` shell binding used by all other git tools, 
and basic initialization.
"""

from __future__ import annotations
import subprocess
from tools.registry import tool, WORKSPACE
from tools._subprocess_utf8 import UTF8_TEXT_KWARGS, err_strip, out_strip


def _git(*args: str, cwd: str | None = None) -> str:
    """Execute a git command and capture output."""
    result = subprocess.run(
        ["git"] + list(args),
        cwd=cwd or WORKSPACE,
        capture_output=True,
        timeout=30,
        **UTF8_TEXT_KWARGS,
    )
    output = out_strip(result)
    if result.returncode != 0:
        err = err_strip(result)
        return f"[exit {result.returncode}] {err or output}"
    return output or "(no output)"


@tool(
    name="git_init",
    description="Initialize a new git repository in the workspace. DESTRUCTIVE — requires permission.",
    parameters={"type": "object", "properties": {}, "required": []},
)
def git_init() -> str:
    return _git("init")
