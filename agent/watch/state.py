"""
Watch State encapsulating the queue and modes.

Processes the raw queue output into actual text injects.
"""

from __future__ import annotations
from agent.watch.queue import FileWatchQueue
from agent.watch.utils import build_user_message


class FileWatchState:
    def __init__(self, mode: str = "auto"):
        self.mode = mode if mode in ("auto", "batch") else "auto"
        self.queue = FileWatchQueue()
        self._batch_notice_shown = False

    def set_mode(self, mode: str) -> None:
        self.mode = mode if mode in ("auto", "batch") else "auto"
        self._batch_notice_shown = False

    def take_auto_inject_message(self) -> str | None:
        if self.mode != "auto":
            return None
        paths = self.queue.drain()
        return build_user_message(paths) if paths else None

    def peek_batch_notice(self) -> str | None:
        if self.mode != "batch":
            return None
        if not self.queue.is_ready():
            return None
        with self.queue.lock:
            if self._batch_notice_shown or not self.queue.paths:
                return None
            n = len(self.queue.paths)
            self._batch_notice_shown = True
        return f"[watch] {n} file change(s) queued — will attach to your next message"

    def consume_batch_prefix(self) -> str | None:
        if self.mode != "batch":
            return None
        paths = self.queue.drain()
        if not paths:
            return None
        self._batch_notice_shown = False
        return build_user_message(paths)
