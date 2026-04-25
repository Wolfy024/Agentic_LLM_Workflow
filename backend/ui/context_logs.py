"""
Logging output displays for contextual operations.

Handles context compaction notifications, streaming progress,
fatal error lines, and generic structural outputs.
"""

from __future__ import annotations
from ui.console import console
from ui.dimming import styled, muted, dim, C_TEXT
from ui.components import section_header
from ui.palette import accent


def print_context(info: dict) -> None:
    """Renders token usage details."""
    console.print()
    console.print(section_header("Token Usage"))
    console.print()
    used = info["tokens_used"]
    msg_count = info["messages"]
    console.print(f"    {muted('used'):14s} {styled(f'~{used:,}', C_TEXT)} {muted('tokens')}")
    console.print(f"    {muted('messages'):14s} {styled(str(msg_count), C_TEXT)}")
    basis = "API prompt_tokens" if info.get("tokens_source") == "api" else "local estimate"
    console.print(f"    {muted('basis'):14s} {styled(basis, C_TEXT)}")
    console.print()


def print_memory_stats(info: dict) -> None:
    """Render retrieval-memory stats."""
    console.print()
    console.print(section_header("Retrieval Memory"))
    console.print()
    console.print(f"    {muted('visited files'):14s} {styled(str(info.get('visited_files', 0)), C_TEXT)}")
    console.print(f"    {muted('symbols'):14s} {styled(str(info.get('important_symbols', 0)), C_TEXT)}")
    console.print(f"    {muted('summaries'):14s} {styled(str(info.get('summaries', 0)), C_TEXT)}")
    console.print(f"    {muted('vector docs'):14s} {styled(str(info.get('vector_docs', 0)), C_TEXT)}")
    console.print(f"    {muted('memory file'):14s} {styled(str(info.get('memory_file', '-')), C_TEXT)}")
    console.print(f"    {muted('vector index'):14s} {styled(str(info.get('vector_index_file', '-')), C_TEXT)}")
    console.print()


def print_token_status(info: dict, api_usage: dict | None = None) -> None:
    """Dim status line after each turn showing token usage."""
    used = info["tokens_used"]
    msgs = info["messages"]
    est = "" if info.get("tokens_source") == "api" else "est. "
    line = f"~{used:,} {est}in  //  {msgs} msgs"
    if api_usage:
        pin = api_usage.get("prompt_tokens")
        cout = api_usage.get("completion_tokens")
        if pin is not None or cout is not None:
            line += f"  //  api in={pin} out={cout}"
    console.print(f"\n  {dim(line)}")


def print_error(msg: str) -> None:
    """Prints standard CLI error line."""
    console.print(f"\n  {accent('error')} {muted(msg)}")


def print_goodbye() -> None:
    """Exit notification."""
    from ui.banner import build_goodbye_banner
    from rich.align import Align
    console.print()
    console.print(Align.center(build_goodbye_banner()))
    console.print(f"\n  {muted('goodbye.')}\n")
