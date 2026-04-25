"""/mcp slash command — manage MCP server connections at runtime.

Usage:
    /mcp              List all MCP servers and their status
    /mcp connect      Re-connect all servers from config
    /mcp disconnect   Disconnect all MCP servers
    /mcp status       Detailed status of each server
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ui.console import console
from ui.palette import primary, success, warning
from ui.dimming import muted
from ui.components import section_header

if TYPE_CHECKING:
    from repl.slash import CommandContext


def cmd_mcp(ctx: CommandContext) -> None:
    """Handle /mcp commands."""
    sub = ctx.arg.lower() if ctx.arg else ""

    if sub == "connect":
        _mcp_connect(ctx)
    elif sub in ("disconnect", "off"):
        _mcp_disconnect()
    elif sub in ("status", "info"):
        _mcp_status_detailed()
    else:
        _mcp_status_summary()


def _mcp_connect(ctx: CommandContext) -> None:
    """Re-connect all MCP servers from config."""
    from mcp.manager import get_manager

    mcp_servers = ctx.config.get("mcp_servers")
    if not mcp_servers or not isinstance(mcp_servers, dict):
        console.print(f"  {muted('No mcp_servers defined in config.json')}")
        return

    mgr = get_manager()
    errors = mgr.connect_from_config(mcp_servers)

    for status in mgr.get_status():
        if status["connected"]:
            t_count = status.get('tool_count', 0)
            console.print(
                f"  {success('✔')} {primary(status['name'], bold=False)}"
                f"  {muted(f'{t_count} tools')}"
            )
        else:
            console.print(f"  {warning('✘')} {status['name']}  {muted('not connected')}")

    for err in errors:
        console.print(f"  {warning(err)}")

    # Refresh the tool schemas in the runner's state
    from tools.registry import get_tool_schemas
    ctx.runner.state.tool_schemas = get_tool_schemas()
    console.print(f"  {muted(f'Tool schemas refreshed — {len(ctx.runner.state.tool_schemas)} total')}")


def _mcp_disconnect() -> None:
    """Disconnect all MCP servers."""
    from mcp.manager import get_manager
    mgr = get_manager()
    count = mgr.connected_count
    mgr.disconnect_all()
    console.print(f"  {muted(f'Disconnected {count} MCP server(s)')}")


def _mcp_status_summary() -> None:
    """Show a brief summary of MCP status."""
    from mcp.manager import get_manager
    mgr = get_manager()
    statuses = mgr.get_status()

    if not statuses:
        console.print(f"  {muted('No MCP servers configured.')}")
        console.print(f"  {muted('Add')}"
                      f" {primary('mcp_servers', bold=False)}"
                      f" {muted('to config.json to get started.')}")
        return

    console.print()
    console.print(section_header("MCP Servers"))
    console.print()
    for s in statuses:
        icon = success("●") if s["connected"] else warning("○")
        server_label = f"{s['server_name']} v{s['server_version']}" if s.get("server_name") else s["command"]
        t_count = s.get('tool_count', 0)
        console.print(
            f"    {icon} {primary(s['name'], bold=False):24s}"
            f" {muted(server_label):40s}"
            f" {muted(f'{t_count} tools')}"
        )
    console.print()
    console.print(f"  {muted(mgr.get_summary())}")
    console.print()


def _mcp_status_detailed() -> None:
    """Show detailed status for each MCP server including tool list."""
    from mcp.manager import get_manager
    mgr = get_manager()
    statuses = mgr.get_status()

    if not statuses:
        console.print(f"  {muted('No MCP servers configured.')}")
        return

    console.print()
    for s in statuses:
        icon = success("●") if s["connected"] else warning("○")
        console.print(f"  {icon} {primary(s['name'], bold=True)}")
        console.print(f"    {muted('command:')} {s['command']} {' '.join(s.get('args', []))}")
        if s.get("server_name"):
            console.print(f"    {muted('server:')}  {s['server_name']} v{s.get('server_version', '?')}")
        console.print(f"    {muted('status:')}  {'connected' if s['connected'] else 'disconnected'}")
        console.print(f"    {muted('tools:')}   {s['tool_count']}")
        if s["tools"]:
            for t in s["tools"]:
                console.print(f"      {muted('•')} {t}")
        console.print()
