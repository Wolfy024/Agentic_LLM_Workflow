"""
Integrates the file watchdog observer.

Attaches event handlers to directories and pumps them into the FileWatchState.
"""

from __future__ import annotations
import os
from agent.watch.state import FileWatchState
from agent.watch.utils import load_pathspec, should_ignore_path, event_target_path


class FileWatchService:
    def __init__(self, workspace: str, mode: str = "auto"):
        self.workspace = os.path.abspath(workspace)
        self.state = FileWatchState(mode)
        self._observer = None
        self._spec = load_pathspec(self.workspace)

    def set_workspace(self, workspace: str) -> bool:
        self.stop()
        self.workspace = os.path.abspath(workspace)
        self._spec = load_pathspec(self.workspace)
        self.state.queue.drain()
        self.state._batch_notice_shown = False
        return self.start()

    def _record_event(self, abs_path: str) -> None:
        if should_ignore_path(self.workspace, abs_path, self._spec):
            return
        self.state.queue.add_path(os.path.normpath(abs_path))

    def start(self) -> bool:
        try:
            from watchdog.events import FileSystemEventHandler
            from watchdog.observers import Observer
        except ImportError:
            return False

        outer = self

        class Handler(FileSystemEventHandler):
            def on_any_event(self, event):
                if getattr(event, "is_directory", False):
                    return
                p = event_target_path(event)
                if not p:
                    return
                outer._record_event(p)

        self._observer = Observer()
        self._observer.schedule(Handler(), self.workspace, recursive=True)
        self._observer.start()
        return True

    def stop(self) -> None:
        if self._observer:
            self._observer.stop()
            self._observer.join(timeout=3)
            self._observer = None
