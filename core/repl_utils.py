"""Small helpers for REPL slash commands (sessions, recipes, exports)."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from agent.runner import AgentRunner


def safe_name(raw: str) -> str:
    s = os.path.basename(raw.replace("..", "").strip())
    safe = "".join(c for c in s if c.isalnum() or c in "-_")
    return safe[:80] if safe else "default"


def recipe_candidate_paths(workspace: str, name: str) -> list[str]:
    base = safe_name(name)
    roots = (
        os.path.join(workspace, ".minillm", "recipes"),
        os.path.join(os.path.expanduser("~"), ".minillm", "recipes"),
    )
    return [os.path.join(r, f"{base}.json") for r in roots]


def apply_recipe_payload(runner: AgentRunner, data: dict) -> bool:
    if not isinstance(data, dict):
        return False
    if "messages" in data and isinstance(data["messages"], list):
        n = 0
        for m in data["messages"]:
            if isinstance(m, dict) and m.get("role") in ("system", "user", "assistant"):
                runner.state.messages.append({"role": m["role"], "content": m.get("content", "")})
                n += 1
        return n > 0
    for key, role in (("prompt", "system"), ("system", "system"), ("user", "user")):
        if key in data and data[key]:
            runner.state.messages.append({"role": role, "content": str(data[key])})
            return True
    return False
