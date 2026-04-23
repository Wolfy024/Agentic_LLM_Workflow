"""
Logging output displays for contextual operations.

Handles context compaction notifications, streaming progress,
fatal error lines, and generic structural outputs.
"""

from __future__ import annotations
from ui.console import console
from ui.dimming import styled, muted, dim, C_TEXT
from ui.components import progress_bar, section_header
from ui.palette import warning, accent


def print_context(info: dict) -> None:
    """Renders the context window tracking block."""
    console.print()
    console.print(section_header("Context Window"))
    console.print()
    used = info["tokens_used"]
    total = info["context_window"]
    pct = used / total if total else 0

    console.print(f"    {progress_bar(pct, width=40)}")
    console.print()
    remaining = info["remaining"]
    max_out = info["max_output"]
    msg_count = info["messages"]
    console.print(f"    {muted('used'):14s} {styled(f'~{used:,}', C_TEXT)} {muted('tokens')}")
    console.print(f"    {muted('remaining'):14s} {styled(f'~{remaining:,}', C_TEXT)} {muted('tokens')}")
    console.print(f"    {muted('output reserve'):14s} {styled(f'{max_out:,}', C_TEXT)} {muted('tokens')}")
    console.print(f"    {muted('messages'):14s} {styled(str(msg_count), C_TEXT)}")
    basis = "API prompt_tokens" if info.get("tokens_source") == "api" else "local estimate"
    console.print(f"    {muted('basis'):14s} {styled(basis, C_TEXT)}")
    console.print()


def print_token_status(info: dict, api_usage: dict | None = None) -> None:
    """Dim status line after each turn showing token usage."""
    used = info["tokens_used"]
    total = info["context_window"]
    pct = used / total if total else 0
    remaining = info["remaining"]
    msgs = info["messages"]
    est = "" if info.get("tokens_source") == "api" else "est. "
    line = f"~{used:,} {est}in  //  {remaining:,} free  //  {pct:.1%} used  //  {msgs} msgs"
    if api_usage:
        pin = api_usage.get("prompt_tokens")
        cout = api_usage.get("completion_tokens")
        if pin is not None or cout is not None:
            line += f"  //  api in={pin} out={cout}"
    console.print(f"\n  {dim(line)}")


def print_auto_compact(freed: int, old_pct: float, new_pct: float) -> None:
    """Alerts the user when the token context limit trims automatically."""
    console.print(
        f"\n  {warning('compacted')} {muted(f'dropped {freed} messages')} "
        f"{muted(f'{old_pct:.0%} -> {new_pct:.0%}')}"
    )


def print_error(msg: str) -> None:
    """Prints standard CLI error line."""
    console.print(f"\n  {accent('error')} {muted(msg)}")


def print_goodbye() -> None:
    """Exit notification."""
    console.print(f"\n  {muted('goodbye.')}\n")
