"""
Streaming integration for the UI.

Handles deduplication of parsed LLM chunks and applies formatting
in real-time using rich.live.Live display.
"""

from __future__ import annotations
from rich.padding import Padding
from rich.markdown import Markdown
from ui.console import console
from ui.markdown import dedupe_stream_text, merge_stream_chunk, render_markdown


class StreamingMarkdown:
    """
    Renders streaming markdown using a Live block sequentially.
    """
    _REFRESH_INTERVAL = 0.08

    def __init__(self):
        self._buffer = ""
        self._live = None
        self._last_refresh = 0.0

    def start(self):
        import time
        console.print()
        self._buffer = ""
        self._last_refresh = time.time()
        try:
            from rich.live import Live
            self._live = Live(
                Padding(Markdown("…", code_theme="monokai"), (0, 0, 0, 4)),
                console=console, refresh_per_second=12, transient=True
            )
            self._live.start()
        except Exception:
            self._live = None

    def feed(self, text: str):
        import time
        if not text: return
        new_buf = merge_stream_chunk(self._buffer, text)
        if new_buf == self._buffer: return
        self._buffer = new_buf

        if self._live is not None:
            now = time.time()
            if now - self._last_refresh >= self._REFRESH_INTERVAL:
                self._last_refresh = now
                try:
                    self._live.update(Padding(Markdown(self._buffer, code_theme="monokai"), (0, 0, 0, 4)))
                except Exception: pass

    def abort(self) -> str:
        if self._live is not None:
            try: self._live.stop()
            except Exception: pass
            self._live = None
        console.print()
        return self._buffer

    def finish(self) -> str:
        buf = dedupe_stream_text(self._buffer)
        self._buffer = buf
        if self._live is not None:
            try: self._live.stop()
            except Exception: pass
            self._live = None

        if buf.strip():
            render_markdown(buf)
        else:
            console.print()
        return buf
