"""Multi-server MCP manager.

Coordinates multiple MCPClient instances, providing:
  - Bulk connect/disconnect from config
  - Aggregated tool schema list for the LLM
  - Tool-name → server routing for execution
  - Permission classification for MCP tools
  - Status reporting for the UI
"""

from __future__ import annotations

import json
from typing import Any

from mcp.client import MCPClient


class MCPManager:
    """Manages the lifecycle of multiple MCP server connections."""

    def __init__(self):
        self._clients: dict[str, MCPClient] = {}   # server_name → client
        self._tool_map: dict[str, str] = {}         # tool_name → server_name
        self._tool_permissions: dict[str, str] = {} # tool_name → "allow" | "destructive" | "deny"
        self._server_permissions: dict[str, str] = {} # server_name → default permission

    @property
    def connected_count(self) -> int:
        return sum(1 for c in self._clients.values() if c.is_connected)

    @property
    def total_tool_count(self) -> int:
        return len(self._tool_map)

    @property
    def server_names(self) -> list[str]:
        return list(self._clients.keys())

    def connect_from_config(self, mcp_config: dict[str, dict]) -> list[str]:
        """Connect to all MCP servers defined in config.

        Config format (stdio):
            {
                "server-name": {
                    "command": "npx",
                    "args": ["-y", "@modelcontextprotocol/server-filesystem", "/path"],
                    "env": {"KEY": "VALUE"},      # optional
                    "cwd": "/optional/dir",        # optional
                    "permission": "destructive"    # optional: "allow" | "destructive" | "deny"
                }
            }

        Config format (SSE):
            {
                "server-name": {
                    "transport": "sse",
                    "url": "https://mcp-server.example.com",
                    "headers": {"Authorization": "Bearer ..."},  # optional
                    "permission": "allow"
                }
            }

        Returns list of error messages (empty = all success).
        """
        errors: list[str] = []
        for name, server_cfg in mcp_config.items():
            if name in self._clients and self._clients[name].is_connected:
                continue  # Already connected
            try:
                transport_type = server_cfg.get("transport", "stdio")
                permission = server_cfg.get("permission", "destructive")
                self._server_permissions[name] = permission

                self.connect_server(
                    name=name,
                    transport_type=transport_type,
                    command=server_cfg.get("command", ""),
                    args=server_cfg.get("args", []),
                    env=server_cfg.get("env"),
                    cwd=server_cfg.get("cwd"),
                    url=server_cfg.get("url", ""),
                    headers=server_cfg.get("headers"),
                    permission=permission,
                )
            except Exception as e:
                errors.append(f"[{name}] {type(e).__name__}: {e}")
        return errors

    def connect_server(self, name: str, transport_type: str = "stdio",
                       command: str = "", args: list[str] | None = None,
                       env: dict[str, str] | None = None,
                       cwd: str | None = None,
                       url: str = "", headers: dict[str, str] | None = None,
                       permission: str = "destructive") -> MCPClient:
        """Connect to a single MCP server."""
        # Disconnect existing if re-connecting
        if name in self._clients:
            self.disconnect_server(name)

        client = MCPClient(
            name=name,
            transport_type=transport_type,
            command=command,
            args=args,
            env=env,
            cwd=cwd,
            url=url,
            headers=headers,
        )
        client.connect()
        self._clients[name] = client
        self._server_permissions[name] = permission

        # Register tool-name → server mapping + permission classification
        for tool_name in client.tool_names:
            if tool_name in self._tool_map:
                # Name collision — prefix with server name
                prefixed = f"{name}__{tool_name}"
                self._tool_map[prefixed] = name
                self._tool_permissions[prefixed] = permission
            else:
                self._tool_map[tool_name] = name
                self._tool_permissions[tool_name] = permission

        return client

    def disconnect_server(self, name: str) -> None:
        """Disconnect a single MCP server."""
        client = self._clients.pop(name, None)
        if client is None:
            return

        # Remove tool mappings for this server
        to_remove = [t for t, s in self._tool_map.items() if s == name]
        for t in to_remove:
            del self._tool_map[t]
            self._tool_permissions.pop(t, None)

        self._server_permissions.pop(name, None)
        client.disconnect()

    def disconnect_all(self) -> None:
        """Disconnect all MCP servers."""
        for name in list(self._clients):
            self.disconnect_server(name)

    def get_all_schemas(self) -> list[dict]:
        """Return aggregated OpenAI function-calling schemas from all connected servers."""
        schemas: list[dict] = []
        for client in self._clients.values():
            if client.is_connected:
                schemas.extend(client.openai_schemas)
        return schemas

    def is_mcp_tool(self, tool_name: str) -> bool:
        """Check if a tool name belongs to an MCP server."""
        return tool_name in self._tool_map

    def is_mcp_tool_destructive(self, tool_name: str) -> bool:
        """Check if an MCP tool is classified as destructive (needs user approval)."""
        return self._tool_permissions.get(tool_name) == "destructive"

    def is_mcp_tool_denied(self, tool_name: str) -> bool:
        """Check if an MCP tool is denied in the current config."""
        return self._tool_permissions.get(tool_name) == "deny"

    def call_tool(self, tool_name: str, arguments: dict[str, Any]) -> str:
        """Route a tool call to the correct MCP server and return the result."""
        server_name = self._tool_map.get(tool_name)
        if server_name is None:
            return json.dumps({"error": f"No MCP server registered for tool '{tool_name}'"})

        client = self._clients.get(server_name)
        if client is None or not client.is_connected:
            return json.dumps({"error": f"MCP server '{server_name}' is not connected"})

        # Handle prefixed names (server__tool → actual tool name)
        actual_name = tool_name
        if "__" in tool_name:
            prefix = f"{server_name}__"
            if tool_name.startswith(prefix):
                actual_name = tool_name[len(prefix):]

        return client.call_tool(actual_name, arguments)

    def get_status(self) -> list[dict]:
        """Return status info for all servers."""
        statuses = []
        for c in self._clients.values():
            s = c.get_status()
            s["permission"] = self._server_permissions.get(c.name, "destructive")
            statuses.append(s)
        return statuses

    def get_summary(self) -> str:
        """One-line summary for banner/status display."""
        total = len(self._clients)
        connected = self.connected_count
        tools = self.total_tool_count
        if total == 0:
            return "no MCP servers configured"
        return f"{connected}/{total} servers, {tools} tools"


# Module-level singleton — initialized once in main.py
_manager: MCPManager | None = None


def get_manager() -> MCPManager:
    """Get or create the global MCP manager singleton."""
    global _manager
    if _manager is None:
        _manager = MCPManager()
    return _manager


def set_manager(mgr: MCPManager) -> None:
    """Set the global MCP manager singleton."""
    global _manager
    _manager = mgr
