"""
Agent context window and session state logic.

Tracks message history, handles context utilization estimates, and 
auto-compacts history when limits are reached.
"""

from __future__ import annotations
import os
import json
from ui.context_logs import print_auto_compact
from agent.tokens import estimate_tokens, message_tokens
from core.prefs import PREFS_DIR
import core.runtime_config as rc

def get_sessions_dir() -> str:
    from tools.registry import WORKSPACE
    return os.path.join(WORKSPACE, "sessions")


def _content_preview(content, n: int) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return content[:n]
    if isinstance(content, list):
        return "[multimodal message]"
    return str(content)[:n]


class SessionState:
    """Tracks message history and context window."""
    def __init__(self, config: dict, system_prompt: str, tool_schemas: list[dict]):
        self.context_window = config.get("context_window", 262144)
        self.max_output = config.get("max_tokens", 131072)
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
                return min(pt, self.context_window)
        msg_tokens = sum(message_tokens(m) for m in self.messages)
        return msg_tokens + self._schema_tokens

    def context_remaining(self, api_usage: dict | None) -> int:
        return self.context_window - self.context_used(api_usage) - self.max_output

    def auto_compact(self, llm_chat_fn, api_usage: dict | None) -> None:
        """Compress old context via a lightweight inner LLM completion."""
        used = self.context_used(api_usage)
        limit = self.context_window - self.max_output
        pct = used / limit if limit > 0 else 1.0
        compact_pct = float(rc.get("auto_compact_pct", 0.80))
        if pct < compact_pct or len(self.messages) <= 4:
            return

        summary_prompt = (
            "Summarize the conversation so far in 2-3 sentences. "
            "Focus on: what the user asked for, what tools were used, "
            "and what decisions were made. Be concise."
        )
        try:
            summary_resp = llm_chat_fn([
                {"role": "system", "content": "You are a summarizer. Be extremely concise."},
                {"role": "user", "content": summary_prompt + "\n\nConversation:\n" +
                 "\n".join(f"{m['role']}: {_content_preview(m.get('content'), 200)}" for m in self.messages[1:10])},
            ])
            summary = summary_resp["choices"][0]["message"].get("content", "")
        except Exception:
            summary = ""

        before = len(self.messages)
        keep_end = max(6, len(self.messages) // 3)
        self.messages = self.messages[:1] + self.messages[-keep_end:]

        if summary:
            self.messages.insert(1, {"role": "system", "content": f"[Earlier conversation summary: {summary}]"})

        freed = before - len(self.messages)
        # Use estimate-based counting after compact — api_usage is stale
        new_pct = self.context_used(None) / limit if limit > 0 else 0
        print_auto_compact(freed, pct, new_pct)


def save_session(state: SessionState, name: str, model: str = "") -> str:
    """Persist session state to JSON, including model and system prompt."""
    s_dir = get_sessions_dir()
    os.makedirs(s_dir, exist_ok=True)
    path = os.path.join(s_dir, f"{name}.json")
    payload = {
        "messages": state.messages,
        "tool_call_count": state.tool_call_count,
        "model": model,
        "system_prompt": state.system_prompt,
    }
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
    saved_model = data.get("model", "")
    return path, saved_model
