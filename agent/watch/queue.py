"""
Core file queue manager for watch events.

Accumulates paths safely in a threaded lock queue and supports
debouncing bursts.
"""

from __future__ import annotations
import time
import threading


class FileWatchQueue:
    def __init__(self, debounce_sec: float = 1.5, max_paths: int = 50):
        self.debounce_sec = debounce_sec
        self.max_paths = max_paths
        self.paths: set[str] = set()
        self.lock = threading.Lock()
        self.debounce_until = 0.0

    def add_path(self, norm_path: str) -> None:
        with self.lock:
            self.paths.add(norm_path)
            self.debounce_until = time.time() + self.debounce_sec

    def is_ready(self) -> bool:
        with self.lock:
            if not self.paths:
                return False
            return time.time() >= self.debounce_until

    def count(self) -> int:
        with self.lock:
            if not self.paths or time.time() < self.debounce_until:
                return 0
            return len(self.paths)

    def drain(self) -> list[str]:
        with self.lock:
            if not self.paths or time.time() < self.debounce_until:
                return []
            collected = sorted(self.paths)[: self.max_paths]
            self.paths.clear()
            self.debounce_until = 0.0
            return collected
