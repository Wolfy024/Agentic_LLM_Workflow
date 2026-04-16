"""System tools — shell command execution, environment info, process listing."""

from __future__ import annotations
import os
import subprocess

from .registry import tool, _resolve, WORKSPACE
from ._subprocess_utf8 import UTF8_TEXT_KWARGS, err_strip, out_strip


@tool(
    name="run_command",
    description="Execute a shell command in the workspace. DESTRUCTIVE — requires permission.",
    parameters={
        "type": "object",
        "properties": {
            "command": {"type": "string", "description": "Shell command to run"},
            "cwd": {"type": "string", "description": "Working directory. Defaults to workspace."},
            "timeout": {"type": "integer", "description": "Timeout in seconds. Default 30."},
        },
        "required": ["command"],
    },
)
def run_command(command: str, cwd: str | None = None, timeout: int = 30) -> str:
    resolved_cwd = _resolve(cwd) if cwd else WORKSPACE
    result = subprocess.run(
        command,
        shell=True,
        cwd=resolved_cwd,
        capture_output=True,
        timeout=timeout,
        **UTF8_TEXT_KWARGS,
    )
    output = out_strip(result)
    err = err_strip(result)
    combined = output
    if err:
        combined += f"\n[stderr] {err}" if output else err
    if result.returncode != 0:
        combined = f"[exit {result.returncode}] {combined}"
    return combined or "(no output)"


@tool(
    name="env_info",
    description="Get environment info: OS, Python version, git version, current user, cwd, and key env vars.",
    parameters={"type": "object", "properties": {}, "required": []},
)
def env_info() -> dict:
    import platform
    import shutil

    from ._subprocess_utf8 import run_exe_line

    info: dict = {
        "os": platform.platform(),
        "python": platform.python_version(),
        "cwd": os.getcwd(),
        "workspace": WORKSPACE,
        "user": os.environ.get("USER") or os.environ.get("USERNAME", "unknown"),
    }
    git = shutil.which("git")
    if git:
        try:
            result = run_exe_line(git, ["--version"], timeout=5)
            info["git"] = out_strip(result) if result.returncode == 0 else "not found"
        except OSError:
            info["git"] = "not found"
    node = shutil.which("node")
    if node:
        try:
            result = run_exe_line(node, ["--version"], timeout=5)
            info["node"] = out_strip(result) if result.returncode == 0 else None
        except OSError:
            info["node"] = None
    npm = shutil.which("npm")
    if npm:
        try:
            result = run_exe_line(npm, ["--version"], timeout=5)
            info["npm"] = out_strip(result) if result.returncode == 0 else None
        except OSError:
            info["npm"] = None
    return info


@tool(
    name="list_processes",
    description="List running processes (optionally filtered by name). Read-only.",
    parameters={
        "type": "object",
        "properties": {
            "filter": {"type": "string", "description": "Filter process names (substring match). Optional."},
        },
        "required": [],
    },
)
def list_processes(filter: str | None = None) -> str:
    import platform as _plat
    if _plat.system() == "Windows":
        cmd = "tasklist /FO CSV /NH"
    else:
        cmd = "ps aux --sort=-%mem"
    result = subprocess.run(cmd, shell=True, capture_output=True, timeout=10, **UTF8_TEXT_KWARGS)
    lines = out_strip(result).splitlines()
    if filter:
        lines = [l for l in lines if filter.lower() in l.lower()]
    return "\n".join(lines[:80]) if lines else "No matching processes"


@tool(
    name="run_diagnostics",
    description="Run a linter/typecheck command in the workspace and return stdout/stderr (e.g. ruff check, eslint). Read-only by default.",
    parameters={
        "type": "object",
        "properties": {
            "command": {
                "type": "string",
                "description": "Shell command. Default 'ruff check .' if ruff exists, else 'python -m compileall -q .'",
            },
            "cwd": {"type": "string", "description": "Working directory relative to workspace. Default '.'"},
            "timeout": {"type": "integer", "description": "Seconds. Default 120."},
        },
        "required": [],
    },
)
def run_diagnostics(command: str | None = None, cwd: str | None = None, timeout: int = 120) -> str:
    import shutil
    resolved = _resolve(cwd) if cwd else WORKSPACE
    cmd = command
    if not cmd:
        if shutil.which("ruff"):
            cmd = "ruff check ."
        else:
            cmd = "python -m compileall -q ."
    result = subprocess.run(
        cmd,
        shell=True,
        cwd=resolved,
        capture_output=True,
        timeout=timeout,
        **UTF8_TEXT_KWARGS,
    )
    out = out_strip(result)
    err = err_strip(result)
    combined = out
    if err:
        combined += f"\n[stderr]\n{err}" if out else err
    if result.returncode != 0:
        combined = f"[exit {result.returncode}]\n{combined}"
    return combined[:24_000] if combined else "(no output)"
