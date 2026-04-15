"""LLM API client — handles communication with the chat completions endpoint.

Includes retry with exponential backoff for transient failures and
user-friendly error classification.
"""

import json
import time
import httpx

REQUEST_TIMEOUT = 300.0
CONNECT_TIMEOUT = 20.0
MAX_RETRIES = 3
RETRY_BACKOFF_BASE = 2.0

RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}

ERROR_MESSAGES = {
    401: "Authentication failed -- check your API key.",
    403: "Access forbidden -- your key may lack permissions.",
    404: "Model not found -- check the model name in config.json.",
    429: "Rate limited by server.",
    500: "Server internal error.",
    502: "Bad gateway -- server may be restarting.",
    503: "Service unavailable -- server is overloaded.",
    504: "Gateway timeout -- server took too long.",
}


class LLMError(Exception):
    """Structured error with status code and user-friendly message."""

    def __init__(self, status_code: int | None, message: str, retryable: bool = False):
        self.status_code = status_code
        self.retryable = retryable
        super().__init__(message)


def classify_error(exc: Exception) -> LLMError:
    if isinstance(exc, httpx.HTTPStatusError):
        code = exc.response.status_code
        friendly = ERROR_MESSAGES.get(code, f"HTTP {code}")
        retryable = code in RETRYABLE_STATUS_CODES
        return LLMError(code, friendly, retryable=retryable)
    if isinstance(exc, httpx.TimeoutException):
        return LLMError(None, "Request timed out -- server may be slow.", retryable=True)
    if isinstance(exc, httpx.ConnectError):
        return LLMError(None, "Connection failed -- check your network and api_base.", retryable=True)
    return LLMError(None, str(exc), retryable=False)


class LLMClient:
    def __init__(self, api_base: str, api_key: str, model: str,
                 max_tokens: int = 131072, temperature: float = 0.15,
                 context_window: int = 262144,
                 on_retry=None):
        self.api_base = api_base.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.context_window = context_window
        self.on_retry = on_retry
        self._client = httpx.Client(
            timeout=httpx.Timeout(REQUEST_TIMEOUT, connect=CONNECT_TIMEOUT)
        )

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def _payload(self, messages: list[dict], tools: list[dict] | None, stream: bool = False) -> dict:
        payload: dict = {
            "model": self.model,
            "messages": messages,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
        }
        if stream:
            payload["stream"] = True
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"
        return payload

    def chat(self, messages: list[dict], tools: list[dict] | None = None) -> dict:
        payload = self._payload(messages, tools)
        last_err = None
        for attempt in range(MAX_RETRIES):
            try:
                resp = self._client.post(
                    f"{self.api_base}/chat/completions",
                    headers=self._headers(), json=payload
                )
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                err = classify_error(e)
                last_err = err
                if err.retryable and attempt < MAX_RETRIES - 1:
                    wait = RETRY_BACKOFF_BASE ** attempt
                    if self.on_retry:
                        self.on_retry(attempt + 1, MAX_RETRIES, str(err), wait)
                    time.sleep(wait)
                    continue
                raise err from e
        raise last_err

    def chat_stream(self, messages: list[dict], tools: list[dict] | None = None):
        payload = self._payload(messages, tools, stream=True)
        last_err = None
        for attempt in range(MAX_RETRIES):
            try:
                with self._client.stream(
                    "POST", f"{self.api_base}/chat/completions",
                    headers=self._headers(), json=payload
                ) as resp:
                    resp.raise_for_status()
                    for line in resp.iter_lines():
                        line = line.strip()
                        if not line or line == "data: [DONE]":
                            continue
                        if line.startswith("data: "):
                            line = line[6:]
                        try:
                            yield json.loads(line)
                        except json.JSONDecodeError:
                            continue
                    return
            except Exception as e:
                err = classify_error(e)
                last_err = err
                if err.retryable and attempt < MAX_RETRIES - 1:
                    wait = RETRY_BACKOFF_BASE ** attempt
                    if self.on_retry:
                        self.on_retry(attempt + 1, MAX_RETRIES, str(err), wait)
                    time.sleep(wait)
                    continue
                raise err from e
        raise last_err

    def close(self):
        self._client.close()
