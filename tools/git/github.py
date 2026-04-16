"""
GitHub API and credential testing.

Tools that interact directly with github.com via the `gh` CLI.
"""

from __future__ import annotations
import subprocess
from tools.registry import tool, WORKSPACE
from tools.git.core import _git
from tools._subprocess_utf8 import UTF8_TEXT_KWARGS, err_strip, out_strip


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
            ["gh", "auth", "status"], capture_output=True, timeout=10, **UTF8_TEXT_KWARGS
        )
        gh_out = out_strip(result) or err_strip(result)
        lines.append(f"gh auth: {gh_out}")
    except (FileNotFoundError, subprocess.TimeoutExpired):
        lines.append("gh CLI: not installed")
    try:
        result = subprocess.run(
            ["ssh", "-T", "git@github.com"], capture_output=True, timeout=10, **UTF8_TEXT_KWARGS
        )
        ssh_out = err_strip(result) or out_strip(result)
        lines.append(f"SSH github.com: {ssh_out}")
    except (FileNotFoundError, subprocess.TimeoutExpired):
        lines.append("SSH: not available or timed out")
    return "\n".join(lines)


@tool(
    name="github_api",
    description="Call the GitHub API via the gh CLI (must be installed and authed with `gh auth login`).",
    parameters={
        "type": "object",
        "properties": {
            "endpoint": {
                "type": "string",
                "description": "API endpoint path, e.g. 'repos/owner/repo/pulls'",
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
            args,
            capture_output=True,
            timeout=30,
            cwd=WORKSPACE,
            input=body,
            **UTF8_TEXT_KWARGS,
        )
        output = out_strip(result)
        if result.returncode != 0:
            err = err_strip(result)
            return f"[exit {result.returncode}] {err or output}"
        return output[:8000] if output else "(no output)"
    except FileNotFoundError:
        return "Error: gh CLI not installed. Install from https://cli.github.com and run `gh auth login`"
    except subprocess.TimeoutExpired:
        return "Error: request timed out"
