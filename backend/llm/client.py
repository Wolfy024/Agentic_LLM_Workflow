"""
LLM API client foundational layer.

Handles synchronous REST calls to the chat completions endpoint,
request payload construction, and error classification.
"""

from __future__ import annotations
import time
import httpx

from llm.errors import LLMError, classify_error

REQUEST_TIMEOUT = 300.0
CONNECT_TIMEOUT = 20.0
MAX_RETRIES = 3
RETRY_BACKOFF_BASE = 2.0


def build_payload(model: str, max_tok: int, temp: float, parallel: bool, messages: list[dict], tools: list[dict] | None, stream: bool = False) -> dict:
    pay = {"model": model, "messages": messages, "max_tokens": max_tok, "temperature": temp}
    if stream:
        pay["stream"] = True
    if tools:
        pay["tools"] = tools
        pay["tool_choice"] = "auto"
        if parallel:
            pay["parallel_tool_calls"] = True
    return pay


class LLMClient:
    def __init__(self, api_base: str, api_key: str, model: str,
                 max_tokens: int = 131072, temperature: float = 0.15,
                 context_window: int = 262144, on_retry=None, parallel_tool_calls: bool = False):
        self.api_base = api_base.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.context_window = context_window
        self.on_retry = on_retry
        self.parallel = parallel_tool_calls
        self.last_usage: dict | None = None
        self.client = httpx.Client(timeout=httpx.Timeout(REQUEST_TIMEOUT, connect=CONNECT_TIMEOUT))

    def chat(self, messages: list[dict], tools: list[dict] | None = None) -> dict:
        payload = build_payload(self.model, self.max_tokens, self.temperature, self.parallel, messages, tools)
        last_err = None
        for attempt in range(MAX_RETRIES):
            try:
                resp = self.client.post(
                    f"{self.api_base}/chat/completions",
                    headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
                    json=payload
                )
                resp.raise_for_status()
                data = resp.json()
                self.last_usage = data.get("usage")
                return data
            except Exception as e:
                err = classify_error(e)
                last_err = err
                if err.retryable and attempt < MAX_RETRIES - 1:
                    wait = RETRY_BACKOFF_BASE ** attempt
                    if self.on_retry: self.on_retry(attempt + 1, MAX_RETRIES, str(err), wait)
                    time.sleep(wait)
                    continue
                raise err from e
        raise last_err

    def list_models(self) -> list[dict]:
        try:
            resp = self.client.get(
                f"{self.api_base}/models",
                headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
            )
            resp.raise_for_status()
            return resp.json().get("data", [])
        except Exception as e:
            raise classify_error(e) from e
