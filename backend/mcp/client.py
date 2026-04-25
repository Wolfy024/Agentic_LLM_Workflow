"""Single MCP server client.

Wraps a transport (stdio or SSE) to handle the MCP lifecycle:
  initialize → tools/list → tools/call → shutdown
Converts MCP tool schemas to OpenAI function-calling format for the LLM.
"""

from __future__ import annotations

import json
from typing import Any

from mcp.transport import BaseTransport, create_transport


class MCPClient:
    """Client for a single MCP server process."""

    def __init__(self, name: str, transport_type: str = "stdio",
                 command: str = "", args: list[str] | None = None,
                 env: dict[str, str] | None = None, cwd: str | None = None,
                 url: str = "", headers: dict[str, str] | None = None):
        self.name = name
        self.transport_type = transport_type
        self.command = command
        self.args = args or []
        self.env = env
        self.cwd = cwd
        self.url = url
        self.headers = headers
        self._transport: BaseTransport | None = None
        self._tools: list[dict] = []  # Raw MCP tool definitions
        self._openai_schemas: list[dict] = []  # Converted to OpenAI function-calling format
        self._server_info: dict = {}
        self._connected = False

    @property
    def is_connected(self) -> bool:
        return self._connected and self._transport is not None and self._transport.is_alive

    @property
    def tool_names(self) -> list[str]:
        return [t["name"] for t in self._tools]

    @property
    def openai_schemas(self) -> list[dict]:
        return list(self._openai_schemas)

    def connect(self) -> None:
        """Start the transport and perform the MCP initialize handshake."""
        if self.transport_type == "sse":
            self._transport = create_transport("sse", url=self.url, headers=self.headers)
        else:
            self._transport = create_transport("stdio",
                                               command=self.command,
                                               args=self.args,
                                               env=self.env,
                                               cwd=self.cwd)
        self._transport.start()

        # MCP initialize request
        resp = self._transport.send_request("initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {
                "roots": {"listChanged": False},
            },
            "clientInfo": {
                "name": "llm-orchestrator",
                "version": "1.0.0",
            },
        })

        if "error" in resp:
            raise RuntimeError(f"MCP initialize failed for '{self.name}': {resp['error']}")

        self._server_info = resp.get("result", {}).get("serverInfo", {})

        # Send initialized notification
        self._transport.send_notification("notifications/initialized")

        # Discover tools
        self._discover_tools()
        self._connected = True

    def disconnect(self) -> None:
        """Gracefully shut down the MCP server."""
        if self._transport is None:
            return
        try:
            self._transport.send_notification("notifications/cancelled",
                                              {"requestId": 0, "reason": "shutdown"})
        except Exception:
            pass
        self._transport.stop()
        self._transport = None
        self._connected = False
        self._tools.clear()
        self._openai_schemas.clear()

    def _discover_tools(self) -> None:
        """Call tools/list and convert schemas to OpenAI format."""
        resp = self._transport.send_request("tools/list")
        if "error" in resp:
            raise RuntimeError(f"MCP tools/list failed for '{self.name}': {resp['error']}")

        self._tools = resp.get("result", {}).get("tools", [])
        self._openai_schemas.clear()

        for tool in self._tools:
            schema = self._mcp_to_openai_schema(tool)
            self._openai_schemas.append(schema)

    def call_tool(self, tool_name: str, arguments: dict[str, Any]) -> str:
        """Execute a tool on the MCP server and return the result as a string."""
        if not self.is_connected:
            raise ConnectionError(f"MCP server '{self.name}' is not connected")

        resp = self._transport.send_request("tools/call", {
            "name": tool_name,
            "arguments": arguments,
        })

        if "error" in resp:
            return json.dumps({"error": f"MCP error: {resp['error']}"})

        result = resp.get("result", {})
        content_parts = result.get("content", [])
        is_error = result.get("isError", False)

        # Flatten content parts to a single text string
        text_parts: list[str] = []
        for part in content_parts:
            if isinstance(part, dict):
                if part.get("type") == "text":
                    text_parts.append(part.get("text", ""))
                elif part.get("type") == "resource":
                    res = part.get("resource", {})
                    text_parts.append(
                        f"[Resource: {res.get('uri', '?')}]\n{res.get('text', '')}")
                else:
                    text_parts.append(json.dumps(part, default=str))
            elif isinstance(part, str):
                text_parts.append(part)

        output = "\n".join(text_parts)

        if is_error:
            return json.dumps({"error": output})
        return output

    @staticmethod
    def _mcp_to_openai_schema(mcp_tool: dict) -> dict:
        """Convert an MCP tool definition to OpenAI function-calling format.

        MCP format:
            {"name": "...", "description": "...", "inputSchema": {...}}

        OpenAI format:
            {"type": "function", "function": {"name": "...", "description": "...",
             "parameters": {...}}}
        """
        input_schema = mcp_tool.get("inputSchema",
                                    {"type": "object", "properties": {}})
        return {
            "type": "function",
            "function": {
                "name": mcp_tool.get("name", "unknown"),
                "description": mcp_tool.get("description", ""),
                "parameters": input_schema,
            },
        }

    def get_status(self) -> dict:
        """Return a summary dict for display purposes."""
        return {
            "name": self.name,
            "connected": self.is_connected,
            "transport": self.transport_type,
            "command": self.command,
            "url": self.url,
            "args": self.args,
            "server_name": self._server_info.get("name", ""),
            "server_version": self._server_info.get("version", ""),
            "tools": self.tool_names,
            "tool_count": len(self._tools),
        }
