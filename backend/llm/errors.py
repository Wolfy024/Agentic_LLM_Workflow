"""
Error classification for LLM api clients.
"""

from __future__ import annotations
import time
import httpx

RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504, 524, 530, 578}

ERROR_MESSAGES = {
    401: "Authentication failed -- check your API key.",
    403: "Access forbidden -- your key may lack permissions.",
    404: "Model not found -- check the LLM_MODEL in your .env file.",
    429: "Rate limited by server.",
    500: "Server internal error -- the LLM encountered an unexpected condition and failed to process the request.",
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
        
        # Try to extract exact API error message if available
        try:
            body = exc.response.json()
            api_msg = body.get("error", {}).get("message")
            if not api_msg and "message" in body:
                api_msg = body["message"]
            if api_msg:
                friendly = f"{friendly} (API says: {api_msg})"
        except Exception:
            pass
            
        return LLMError(code, friendly, retryable=(code in RETRYABLE_STATUS_CODES))
    if isinstance(exc, httpx.TimeoutException):
        return LLMError(None, "Request timed out.", retryable=True)
    if isinstance(exc, httpx.ConnectError):
        return LLMError(None, "Connection failed.", retryable=True)
    return LLMError(None, str(exc), retryable=False)


class ServerHealthTracker:
    """Tracks consecutive server failures and applies escalating cooldowns.

    When the LLM server returns repeated 500-class errors, this prevents
    the client from hammering a dead/stuck server with rapid retries.
    After enough consecutive failures, it marks the server as unhealthy
    and returns actionable guidance to the user.
    """
    def __init__(self, max_consecutive: int = 3, max_cooldown: float = 30.0):
        self._consecutive_failures = 0
        self._last_failure_time: float = 0.0
        self._max_consecutive = max_consecutive
        self._max_cooldown = max_cooldown

    def record_success(self) -> None:
        """Reset failure counter on a successful request."""
        self._consecutive_failures = 0

    def record_failure(self, err: LLMError) -> None:
        """Record a failure. Only counts server-side errors (5xx)."""
        if err.status_code and 500 <= err.status_code < 600:
            self._consecutive_failures += 1
            self._last_failure_time = time.monotonic()
        elif err.status_code is None and "timed out" in str(err).lower():
            self._consecutive_failures += 1
            self._last_failure_time = time.monotonic()

    @property
    def is_unhealthy(self) -> bool:
        """True if the server has failed too many times consecutively."""
        return self._consecutive_failures >= self._max_consecutive

    @property
    def cooldown_seconds(self) -> float:
        """Escalating cooldown: 2s, 5s, 10s, 20s, capped at max_cooldown."""
        if self._consecutive_failures <= 1:
            return 0.0
        return min(2.0 * (2 ** (self._consecutive_failures - 2)), self._max_cooldown)

    @property
    def failure_count(self) -> int:
        return self._consecutive_failures

    def get_status_message(self) -> str:
        """User-facing message about server health."""
        if not self.is_unhealthy:
            return ""
        n = self._consecutive_failures
        return (
            f"Server has failed {n} times in a row. "
            f"It may be overloaded or crashed. "
            f"Try: restart the LLM server, or wait a minute and retry."
        )
