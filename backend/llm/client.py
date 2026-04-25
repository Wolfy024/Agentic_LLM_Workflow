"""
LLM API client foundational layer.

Handles synchronous REST calls to the chat completions endpoint,
request payload construction, and error classification.
"""

from __future__ import annotations
import time
import httpx

from llm.errors import LLMError, classify_error, ServerHealthTracker
import core.runtime_config as rc


def _request_timeout():
    return float(rc.get("request_timeout", 300))

def _connect_timeout():
    return float(rc.get("connect_timeout", 20))

def _max_retries():
    return int(rc.get("max_retries", 3))

def _retry_backoff():
    return float(rc.get("retry_backoff_base", 2.0))

# Module-level aliases for import by stream.py
REQUEST_TIMEOUT = 300.0   # default; actual values read dynamically
CONNECT_TIMEOUT = 20.0
MAX_RETRIES = 3
RETRY_BACKOFF_BASE = 2.0


def build_payload(model: str, temp: float, parallel: bool, messages: list[dict], tools: list[dict] | None, stream: bool = False) -> dict:
    # Do not send max_tokens from client-side; let server enforce context/output limits.
    pay = {"model": model, "messages": messages, "temperature": temp}
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
                 temperature: float = 0.15,
                 on_retry=None, parallel_tool_calls: bool = False):
        self.api_base = api_base.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.temperature = temperature
        self.on_retry = on_retry
        self.parallel = parallel_tool_calls
        self.last_usage: dict | None = None
        self.health = ServerHealthTracker()
        # Use HTTP/2 if available (pip install h2) — better streaming performance
        req_t, con_t = _request_timeout(), _connect_timeout()
        try:
            self.client = httpx.Client(
                timeout=httpx.Timeout(req_t, connect=con_t),
                http2=True,
            )
        except Exception:
            self.client = httpx.Client(
                timeout=httpx.Timeout(req_t, connect=con_t),
            )

    def chat(self, messages: list[dict], tools: list[dict] | None = None) -> dict:
        payload = build_payload(self.model, self.temperature, self.parallel, messages, tools)
        last_err = None
        retries = _max_retries()
        backoff = _retry_backoff()

        # Pre-request cooldown if server is persistently failing
        cooldown = self.health.cooldown_seconds
        if cooldown > 0:
            if self.on_retry:
                hint = self.health.get_status_message() or "Server may be recovering..."
                self.on_retry(0, retries, hint, cooldown)
            time.sleep(cooldown)

        for attempt in range(retries):
            try:
                resp = self.client.post(
                    f"{self.api_base}/chat/completions",
                    headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
                    json=payload
                )
                resp.raise_for_status()
                data = resp.json()
                self.last_usage = data.get("usage")
                self.health.record_success()
                return data
            except Exception as e:
                err = classify_error(e)
                last_err = err
                self.health.record_failure(err)
                if err.retryable and attempt < retries - 1:
                    wait = backoff ** attempt
                    if self.on_retry: self.on_retry(attempt + 1, retries, str(err), wait)
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
