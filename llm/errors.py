"""
Error classification for LLM api clients.
"""

from __future__ import annotations
import httpx

RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504, 524, 530, 578}

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
    def __init__(self, status_code: int | None, message: str, retryable: bool = False):
        self.status_code = status_code
        self.retryable = retryable
        super().__init__(message)


def classify_error(exc: Exception) -> LLMError:
    if isinstance(exc, httpx.HTTPStatusError):
        code = exc.response.status_code
        friendly = ERROR_MESSAGES.get(code, f"HTTP {code}")
        return LLMError(code, friendly, retryable=(code in RETRYABLE_STATUS_CODES))
    if isinstance(exc, httpx.TimeoutException):
        return LLMError(None, "Request timed out.", retryable=True)
    if isinstance(exc, httpx.ConnectError):
        return LLMError(None, "Connection failed.", retryable=True)
    return LLMError(None, str(exc), retryable=False)
