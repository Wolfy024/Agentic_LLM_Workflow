"""Subprocess helpers: UTF-8 decode on Windows (avoids cp1252 UnicodeDecodeError on git diff, etc.)."""

from __future__ import annotations

import os
import subprocess

# Use instead of text=True (which follows locale / cp1252 on Windows).
UTF8_TEXT_KWARGS = {"encoding": "utf-8", "errors": "replace"}


def run_exe_line(
    exe: str,
    args: list[str] | None = None,
    *,
    timeout: float = 10,
) -> subprocess.CompletedProcess:
    """
    Run *exe* with *args* without WinError 2 on Windows when *exe* is a .cmd/.bat
    (CreateProcess cannot launch batch files without shell).
    """
    args = args or []
    if os.name == "nt" and exe.lower().endswith((".cmd", ".bat")):
        q = exe.replace('"', '\\"')
        rest = " ".join(a.replace('"', '\\"') for a in args)
        cmd = f'"{q}" {rest}'.strip()
        return subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            timeout=timeout,
            **UTF8_TEXT_KWARGS,
        )
    return subprocess.run(
        [exe, *args],
        capture_output=True,
        timeout=timeout,
        **UTF8_TEXT_KWARGS,
    )


def out_strip(proc) -> str:
    return (proc.stdout or "").strip()


def err_strip(proc) -> str:
    return (proc.stderr or "").strip()
