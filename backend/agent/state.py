"""
Agent context window and session state logic.

Tracks message history and token usage estimates.
"""

from __future__ import annotations
import os
import json
from agent.tokens import estimate_tokens, message_tokens

def get_sessions_dir() -> str:
    from tools.registry import WORKSPACE
    return os.path.join(WORKSPACE, "sessions")


class SessionState:
    """Tracks message history and token usage."""
    def __init__(self, config: dict, system_prompt: str, tool_schemas: list[dict]):
        self.system_prompt = system_prompt
        self.messages: list[dict] = [{"role": "system", "content": self.system_prompt}]
        self.tool_call_count = 0
        self.tool_schemas = tool_schemas
        self._schema_tokens = estimate_tokens(json.dumps(tool_schemas))

    def reset(self) -> None:
        """Reset conversation."""
        self.messages = [{"role": "system", "content": self.system_prompt}]
        self.tool_call_count = 0

    def context_used(self, api_usage: dict | None) -> int:
        if api_usage:
            pt = api_usage.get("prompt_tokens")
            if isinstance(pt, int) and pt >= 0:
                return pt
        msg_tokens = sum(message_tokens(m) for m in self.messages)
        return msg_tokens + self._schema_tokens


def save_session(state: SessionState, name: str, model: str = "") -> str:
    """Persist session state to JSON, including model and system prompt."""
    s_dir = get_sessions_dir()
    os.makedirs(s_dir, exist_ok=True)
    path = os.path.join(s_dir, f"{name}.json")
    retrieval_memory = None
    try:
        from tools.fs.search import get_retrieval_memory_snapshot
        retrieval_memory = get_retrieval_memory_snapshot()
    except Exception:
        retrieval_memory = None

    payload = {
        "messages": state.messages,
        "tool_call_count": state.tool_call_count,
        "model": model,
        "system_prompt": state.system_prompt,
    }
    if retrieval_memory is not None:
        payload["retrieval_memory"] = retrieval_memory
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    return path


def load_session(state: SessionState, name: str) -> tuple[str, str]:
    """Hydrate session state from JSON. Returns (path_or_error, saved_model)."""
    s_dir = get_sessions_dir()
    path = os.path.join(s_dir, f"{name}.json")
    if not os.path.exists(path):
        return f"Session not found: {path}", ""
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    state.messages = data.get("messages", [])
    state.tool_call_count = data.get("tool_call_count", 0)
    try:
        from tools.fs.search import load_retrieval_memory_snapshot
        load_retrieval_memory_snapshot(data.get("retrieval_memory"))
    except Exception:
        pass
    saved_model = data.get("model", "")
    return path, saved_model
