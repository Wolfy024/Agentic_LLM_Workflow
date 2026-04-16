"""
Operations blocks for tool executions.

Provides formatted logs for tool dispatches, execution results, and 
yolo/manual permission prompts feedback loops.
"""

from __future__ import annotations
from ui.console import console
from ui.dimming import styled, muted, dim, C_TEXT, C_MUTED
from ui.palette import primary, secondary, accent, success


def print_tool_call(name: str, args: dict) -> None:
    """Renders the invocation of a tool with shortened args."""
    args_short = {}
    for k, v in args.items():
        if isinstance(v, str) and len(v) > 100:
            args_short[k] = v[:100] + "..."
        else:
            args_short[k] = v
    args_str = ", ".join(f"{styled(k, C_MUTED)}={styled(repr(v), C_TEXT)}" for k, v in args_short.items())
    console.print(f"\n  {primary('>')} {secondary(name, bold=True)}({args_str})")


def print_tool_result(result: str | None, success: bool = True, verbose: bool = False) -> None:
    """Print the resulting payload string of a tool invocation."""
    if result is None:
        result = ""
    hex_color = "#4B5563" if success else "#FF6B6B"
    
    max_len = 500 if not verbose else 50_000
    max_lines = 20 if not verbose else 500
    if len(result) > max_len:
        display = result[:max_len] + f"\n{muted(f'  ... {len(result):,} chars total')}"
    else:
        display = result
    lines = display.split("\n")
    console.print(f"  {styled(':', hex_color)}")
    for line in lines[:max_lines]:
        console.print(f"  {styled(':', hex_color)} {dim(line)}")
    if len(lines) > max_lines:
        console.print(f"  {styled(':', hex_color)} {muted(f'... {len(lines) - max_lines} more lines')}")
    console.print(f"  {styled('.', hex_color)}")


def print_permission_approved() -> None:
    """Log an approved tool run."""
    console.print(f"  {success('  approved')}")


def print_permission_denied() -> None:
    """Log a denied tool run."""
    console.print(f"  {accent('  denied')}")
