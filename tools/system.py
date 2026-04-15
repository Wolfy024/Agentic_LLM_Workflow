"""System tools — shell command execution, environment info, process listing."""

from __future__ import annotations
import os
import subprocess

from .registry import tool, _resolve, WORKSPACE


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
        command, shell=True, cwd=resolved_cwd,
        capture_output=True, text=True, timeout=timeout,
    )
    output = result.stdout.strip()
    err = result.stderr.strip()
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
    info: dict = {
        "os": platform.platform(),
        "python": platform.python_version(),
        "cwd": os.getcwd(),
        "workspace": WORKSPACE,
        "user": os.environ.get("USER") or os.environ.get("USERNAME", "unknown"),
    }
    git = shutil.which("git")
    if git:
        result = subprocess.run(["git", "--version"], capture_output=True, text=True, timeout=5)
        info["git"] = result.stdout.strip() if result.returncode == 0 else "not found"
    node = shutil.which("node")
    if node:
        result = subprocess.run(["node", "--version"], capture_output=True, text=True, timeout=5)
        info["node"] = result.stdout.strip() if result.returncode == 0 else None
    npm = shutil.which("npm")
    if npm:
        result = subprocess.run(["npm", "--version"], capture_output=True, text=True, timeout=5)
        info["npm"] = result.stdout.strip() if result.returncode == 0 else None
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
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=10)
    lines = result.stdout.strip().splitlines()
    if filter:
        lines = [l for l in lines if filter.lower() in l.lower()]
    return "\n".join(lines[:80]) if lines else "No matching processes"
