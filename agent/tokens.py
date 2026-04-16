"""
Token counting heuristics.

Provides fast fallback estimates for chat messages and schemas
when explicit API token tracking is not returned.
"""

from __future__ import annotations
import json


def estimate_tokens(text: str) -> int:
    """Rough heuristic: 1 token ~= 4 chars or 0.75 words."""
    if not text:
        return 0
    words = len(text.split())
    return int(words / 0.75)


def message_tokens(msg: dict) -> int:
    """Estimate tokens for a single chat turn payload."""
    tokens = 0
    tc = msg.get("tool_calls")
    if tc:
        tokens += estimate_tokens(json.dumps(tc))
    content = msg.get("content")
    if getattr(content, "strip", None):
        tokens += estimate_tokens(content)
    elif isinstance(content, list):
        for item in content:
            if not isinstance(item, dict):
                tokens += estimate_tokens(str(item))
                continue
            itype = item.get("type")
            if itype == "text":
                tokens += estimate_tokens(str(item.get("text", "")))
            elif itype == "image_url":
                url = item.get("image_url") or {}
                s = url.get("url", "") if isinstance(url, dict) else str(url)
                if s.startswith("data:") and "," in s:
                    b64part = s.split(",", 1)[1]
                    tokens += max(400, len(b64part) // 16)
                else:
                    tokens += 500
            else:
                tokens += estimate_tokens(str(item))
    return tokens + 5  # overhead baseline
