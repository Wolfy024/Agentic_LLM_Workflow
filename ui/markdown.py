"""
Markdown rendering tools.

Handles static text preprocessing, merging of fragments, and terminal rendering.
"""

from __future__ import annotations
import re
from rich.padding import Padding
from rich.markdown import Markdown
from ui.console import console
from ui.palette import primary


def merge_stream_chunk(buffer: str, piece: str) -> str:
    """Combine a streaming chunk with the buffer securely."""
    if not piece: return buffer
    if piece == buffer: return buffer
    if buffer and piece.startswith(buffer): return piece
    return buffer + piece


def dedupe_stream_text(text: str) -> str:
    """Remove duplicate text structures from stream anomalies."""
    if not text: return text
    t = text.replace("\r\n", "\n")
    lines = t.split("\n")
    out_lines: list[str] = []
    for ln in lines:
        if not out_lines:
            out_lines.append(ln)
            continue
        a, b = ln.strip(), out_lines[-1].strip()
        if a and a == b: continue
        if ln == out_lines[-1] and ln.strip(): continue
        out_lines.append(ln)
    
    t = "\n".join(out_lines)
    paras = re.split(r"\n{2,}", t)
    merged: list[str] = []
    for p in paras:
        if not p.strip(): continue
        if not merged or p.strip() != merged[-1].strip(): merged.append(p)
    t = "\n\n".join(merged)

    for min_len in (48, 32):
        for _ in range(32):
            pat = rf"(.{{{min_len},}}?)(\s*\1)+"
            nt = re.sub(pat, r"\1", t, flags=re.DOTALL)
            if nt == t:
                break
            t = nt
    return t


def render_markdown(text: str) -> None:
    """Render a complete markdown string structurally."""
    console.print()
    console.print(Padding(Markdown(text, code_theme="monokai"), (0, 0, 0, 4)))
    console.print()


def print_stream_start() -> None:
    """Mark the beginning of a stream output with a star bullet."""
    console.print()
    console.print(f"  {primary('*')} ", end="")
