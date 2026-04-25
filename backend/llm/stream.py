"""
LLM streaming integrations.

Extends the core LLMClient to support Server-Sent Events (SSE) streaming 
for live token outputs and yields.
"""

from __future__ import annotations
import json
import time
from typing import Iterator

from llm.client import LLMClient, build_payload, _max_retries, _retry_backoff
from llm.errors import classify_error


def stream_chat(client: LLMClient, messages: list[dict], tools: list[dict] | None = None) -> Iterator[dict]:
    """Execute a stream request using the given client configuration."""
    payload = build_payload(
        model=client.model,
        temp=client.temperature,
        parallel=client.parallel,
        messages=messages,
        tools=tools,
        stream=True
    )
    last_err = None
    retries = _max_retries()
    backoff = _retry_backoff()

    # Pre-request cooldown if server is persistently failing
    cooldown = client.health.cooldown_seconds
    if cooldown > 0:
        if client.on_retry:
            hint = client.health.get_status_message() or "Server may be recovering..."
            client.on_retry(0, retries, hint, cooldown)
        time.sleep(cooldown)

    for attempt in range(retries):
        try:
            with client.client.stream(
                "POST", f"{client.api_base}/chat/completions",
                headers={"Authorization": f"Bearer {client.api_key}", "Content-Type": "application/json"},
                json=payload
            ) as resp:
                resp.raise_for_status()
                client.health.record_success()
                for line in resp.iter_lines():
                    line = line.strip()
                    if not line or line == "data: [DONE]":
                        continue
                    if line.startswith("data: "):
                        line = line[6:]
                    try:
                        chunk = json.loads(line)
                        u = chunk.get("usage")
                        if u:
                            client.last_usage = u
                        yield chunk
                    except json.JSONDecodeError:
                        continue
                return
        except Exception as e:
            err = classify_error(e)
            last_err = err
            client.health.record_failure(err)
            if err.retryable and attempt < retries - 1:
                wait = backoff ** attempt
                if client.on_retry:
                    client.on_retry(attempt + 1, retries, str(err), wait)
                time.sleep(wait)
                continue
            raise err from e
    raise last_err
