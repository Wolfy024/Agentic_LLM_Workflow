"""JSON-RPC transports for MCP server communication.

Two transport types are supported:
  - StdioTransport: spawns a local subprocess, speaks JSON-RPC over stdin/stdout
  - SSETransport:   connects to a remote MCP server over Server-Sent Events (HTTP)

Both implement the same send_request / send_notification interface so the
MCPClient above them is transport-agnostic.
"""

from __future__ import annotations

import json
import subprocess
import threading
import os
import queue
from typing import Any


# ---------------------------------------------------------------------------
# Base interface
# ---------------------------------------------------------------------------

class BaseTransport:
    """Abstract interface for MCP transports."""

    @property
    def is_alive(self) -> bool:
        raise NotImplementedError

    def start(self) -> None:
        raise NotImplementedError

    def stop(self) -> None:
        raise NotImplementedError

    def send_request(self, method: str, params: dict | None = None) -> dict:
        raise NotImplementedError

    def send_notification(self, method: str, params: dict | None = None) -> None:
        raise NotImplementedError


# ---------------------------------------------------------------------------
# Stdio transport  (local subprocess — npx, python, etc.)
# ---------------------------------------------------------------------------

class StdioTransport(BaseTransport):
    """Manages a child process and provides send/receive for JSON-RPC 2.0 messages."""

    def __init__(self, command: str, args: list[str] | None = None,
                 env: dict[str, str] | None = None, cwd: str | None = None):
        self.command = command
        self.args = args or []
        self.env = env
        self.cwd = cwd
        self._proc: subprocess.Popen | None = None
        self._read_lock = threading.Lock()
        self._write_lock = threading.Lock()
        self._request_id = 0

    @property
    def is_alive(self) -> bool:
        return self._proc is not None and self._proc.poll() is None

    def start(self) -> None:
        """Launch the child process."""
        merged_env = dict(os.environ)
        if self.env:
            merged_env.update(self.env)
        self._proc = subprocess.Popen(
            [self.command, *self.args],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=merged_env,
            cwd=self.cwd,
            bufsize=0,
        )

    def stop(self) -> None:
        """Terminate the child process gracefully."""
        if self._proc is None:
            return
        try:
            self._proc.stdin.close()
        except Exception:
            pass
        try:
            self._proc.terminate()
            self._proc.wait(timeout=5)
        except Exception:
            try:
                self._proc.kill()
            except Exception:
                pass
        self._proc = None

    def _next_id(self) -> int:
        self._request_id += 1
        return self._request_id

    def send_request(self, method: str, params: dict | None = None) -> dict:
        """Send a JSON-RPC request and wait for the response."""
        req_id = self._next_id()
        message: dict[str, Any] = {
            "jsonrpc": "2.0",
            "id": req_id,
            "method": method,
        }
        if params is not None:
            message["params"] = params
        self._write_message(message)
        return self._read_response(req_id)

    def send_notification(self, method: str, params: dict | None = None) -> None:
        """Send a JSON-RPC notification (no id, no response expected)."""
        message: dict[str, Any] = {
            "jsonrpc": "2.0",
            "method": method,
        }
        if params is not None:
            message["params"] = params
        self._write_message(message)

    def _write_message(self, message: dict) -> None:
        """Write a length-prefixed JSON-RPC message to stdin."""
        if not self.is_alive:
            raise ConnectionError("MCP server process is not running")
        body = json.dumps(message).encode("utf-8")
        header = f"Content-Length: {len(body)}\r\n\r\n".encode("ascii")
        with self._write_lock:
            self._proc.stdin.write(header + body)
            self._proc.stdin.flush()

    def _read_response(self, expected_id: int, timeout: float = 30.0) -> dict:
        """Read messages until we get the response matching expected_id."""
        import time
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            msg = self._read_message(timeout=max(0.1, deadline - time.monotonic()))
            if msg is None:
                continue
            # Skip notifications (no "id" field)
            if "id" not in msg:
                continue
            if msg.get("id") == expected_id:
                return msg
        raise TimeoutError(f"Timed out waiting for response id={expected_id}")

    def _read_message(self, timeout: float = 30.0) -> dict | None:
        """Read one length-prefixed JSON-RPC message from stdout."""
        if not self.is_alive:
            raise ConnectionError("MCP server process is not running")

        with self._read_lock:
            stdout = self._proc.stdout
            # Read headers
            headers = {}
            while True:
                line = self._readline_with_timeout(stdout, timeout)
                if line is None:
                    return None
                line_str = line.decode("ascii", errors="replace").strip()
                if line_str == "":
                    break  # End of headers
                if ":" in line_str:
                    key, val = line_str.split(":", 1)
                    headers[key.strip()] = val.strip()

            content_length = int(headers.get("Content-Length", 0))
            if content_length == 0:
                return None

            body = b""
            while len(body) < content_length:
                chunk = stdout.read(content_length - len(body))
                if not chunk:
                    raise ConnectionError("MCP server closed stdout")
                body += chunk

            return json.loads(body.decode("utf-8"))

    @staticmethod
    def _readline_with_timeout(stream, timeout: float) -> bytes | None:
        """Read a line from a stream with timeout. Works on Windows via threading."""
        result_q: queue.Queue[bytes | None] = queue.Queue()

        def _reader():
            try:
                result_q.put(stream.readline())
            except Exception:
                result_q.put(None)

        t = threading.Thread(target=_reader, daemon=True)
        t.start()
        try:
            return result_q.get(timeout=timeout)
        except queue.Empty:
            return None


# ---------------------------------------------------------------------------
# SSE transport  (remote HTTP — Brave Search, API gateways, etc.)
# ---------------------------------------------------------------------------

class SSETransport(BaseTransport):
    """Connects to a remote MCP server over HTTP + Server-Sent Events.

    Flow:
      1. GET /sse  → opens a persistent SSE stream for server→client messages
      2. POST /message?sessionId=...  → sends client→server JSON-RPC messages
    The SSE endpoint delivers both responses and server-initiated notifications.
    """

    def __init__(self, url: str, headers: dict[str, str] | None = None,
                 timeout: float = 30.0):
        self._base_url = url.rstrip("/")
        self._headers = headers or {}
        self._timeout = timeout
        self._request_id = 0
        self._session_id: str | None = None
        self._response_queues: dict[int, queue.Queue] = {}
        self._sse_thread: threading.Thread | None = None
        self._alive = False
        self._client = None  # httpx client, lazily created

    @property
    def is_alive(self) -> bool:
        return self._alive

    def start(self) -> None:
        """Open the SSE stream and discover the message endpoint."""
        import httpx
        self._client = httpx.Client(timeout=self._timeout, http2=True)
        self._alive = True
        self._sse_thread = threading.Thread(target=self._sse_listener, daemon=True)
        self._sse_thread.start()

        # Wait for the SSE stream to deliver the session endpoint
        import time
        deadline = time.monotonic() + self._timeout
        while self._session_id is None and time.monotonic() < deadline:
            time.sleep(0.1)
        if self._session_id is None:
            self._alive = False
            raise ConnectionError("SSE stream did not provide a session/endpoint event")

    def stop(self) -> None:
        """Close the SSE stream and HTTP client."""
        self._alive = False
        if self._client:
            try:
                self._client.close()
            except Exception:
                pass
            self._client = None

    def _next_id(self) -> int:
        self._request_id += 1
        return self._request_id

    def send_request(self, method: str, params: dict | None = None) -> dict:
        """POST a JSON-RPC request and wait for the SSE-delivered response."""
        req_id = self._next_id()
        message: dict[str, Any] = {
            "jsonrpc": "2.0",
            "id": req_id,
            "method": method,
        }
        if params is not None:
            message["params"] = params

        response_q: queue.Queue[dict] = queue.Queue()
        self._response_queues[req_id] = response_q

        try:
            self._post_message(message)
            return response_q.get(timeout=self._timeout)
        finally:
            self._response_queues.pop(req_id, None)

    def send_notification(self, method: str, params: dict | None = None) -> None:
        """POST a JSON-RPC notification (no id, no response expected)."""
        message: dict[str, Any] = {
            "jsonrpc": "2.0",
            "method": method,
        }
        if params is not None:
            message["params"] = params
        try:
            self._post_message(message)
        except Exception:
            pass  # Best-effort for notifications

    def _post_message(self, message: dict) -> None:
        """POST a message to the server's message endpoint."""
        if not self._alive or not self._client:
            raise ConnectionError("SSE transport is not connected")
        url = self._session_id  # The SSE endpoint event gives us the full POST URL
        if not url:
            raise ConnectionError("No message endpoint available")
        resp = self._client.post(
            url,
            json=message,
            headers={**self._headers, "Content-Type": "application/json"},
        )
        resp.raise_for_status()

    def _sse_listener(self) -> None:
        """Background thread: read the SSE stream and route messages."""
        import httpx
        sse_url = f"{self._base_url}/sse"
        try:
            with httpx.stream("GET", sse_url, headers=self._headers,
                              timeout=None) as resp:
                event_type = ""
                data_buf = ""
                for line in resp.iter_lines():
                    if not self._alive:
                        break
                    if line.startswith("event:"):
                        event_type = line[6:].strip()
                    elif line.startswith("data:"):
                        data_buf = line[5:].strip()
                        self._handle_sse_event(event_type, data_buf)
                        event_type = ""
                        data_buf = ""
        except Exception:
            pass
        finally:
            self._alive = False

    def _handle_sse_event(self, event_type: str, data: str) -> None:
        """Process a single SSE event."""
        if event_type == "endpoint":
            # data is the relative or absolute URL for POSTing messages
            if data.startswith("/") or data.startswith("http"):
                if data.startswith("/"):
                    self._session_id = f"{self._base_url}{data}"
                else:
                    self._session_id = data
            return

        if event_type == "message":
            try:
                msg = json.loads(data)
                msg_id = msg.get("id")
                if msg_id is not None and msg_id in self._response_queues:
                    self._response_queues[msg_id].put(msg)
            except (json.JSONDecodeError, TypeError):
                pass


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

def create_transport(transport_type: str, **kwargs) -> BaseTransport:
    """Create the appropriate transport based on config.

    Args:
        transport_type: "stdio" or "sse"
        **kwargs: passed through to the transport constructor.
    """
    if transport_type == "sse":
        return SSETransport(
            url=kwargs["url"],
            headers=kwargs.get("headers"),
            timeout=kwargs.get("timeout", 30.0),
        )
    # Default: stdio
    return StdioTransport(
        command=kwargs["command"],
        args=kwargs.get("args"),
        env=kwargs.get("env"),
        cwd=kwargs.get("cwd"),
    )
