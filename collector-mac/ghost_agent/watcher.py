"""Filesystem watching for opted-in project folders only.

Second line of consent enforcement: `WatchManager` can only be told to watch a `Project`
that came out of `StateStore`, and `stop`/`stop_all` take effect immediately and locally.
Events are debounced per file so an export being written (many modify events) becomes
one capture once it has been quiet for `settle_seconds`.
"""

from __future__ import annotations

import threading
from collections.abc import Callable
from pathlib import Path

from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer
from watchdog.observers.api import ObservedWatch

from ghost_agent import CAPTURE_EXTENSIONS
from ghost_agent.state import Project

CaptureCallback = Callable[[Path, Project], None]


class _ProjectHandler(FileSystemEventHandler):
    def __init__(
        self, project: Project, on_capture: CaptureCallback, settle_seconds: float
    ) -> None:
        self.project = project
        self.on_capture = on_capture
        self.settle_seconds = settle_seconds
        self._timers: dict[str, threading.Timer] = {}
        self._lock = threading.Lock()

    def _schedule(self, path_str: str) -> None:
        path = Path(path_str)
        if path.suffix.lower() not in CAPTURE_EXTENSIONS:
            return
        if path.name.startswith(".") or path.name.startswith("~"):
            return  # temp / hidden files
        with self._lock:
            existing = self._timers.pop(path_str, None)
            if existing:
                existing.cancel()
            timer = threading.Timer(self.settle_seconds, self._fire, args=(path_str,))
            timer.daemon = True
            self._timers[path_str] = timer
            timer.start()

    def _fire(self, path_str: str) -> None:
        with self._lock:
            self._timers.pop(path_str, None)
        path = Path(path_str)
        if path.is_file():
            self.on_capture(path, self.project)

    def cancel_all(self) -> None:
        with self._lock:
            for t in self._timers.values():
                t.cancel()
            self._timers.clear()

    def on_created(self, event: FileSystemEvent) -> None:
        if not event.is_directory:
            self._schedule(str(event.src_path))

    def on_modified(self, event: FileSystemEvent) -> None:
        if not event.is_directory:
            self._schedule(str(event.src_path))

    def on_moved(self, event: FileSystemEvent) -> None:
        if not event.is_directory:
            self._schedule(str(event.dest_path))


class WatchManager:
    def __init__(self, on_capture: CaptureCallback, settle_seconds: float = 2.0) -> None:
        self.on_capture = on_capture
        self.settle_seconds = settle_seconds
        self._observer = Observer()
        self._watches: dict[str, tuple[ObservedWatch, _ProjectHandler]] = {}
        self._started = False

    def start(self, project: Project) -> None:
        if project.name in self._watches:
            return
        handler = _ProjectHandler(project, self.on_capture, self.settle_seconds)
        watch = self._observer.schedule(handler, project.folder, recursive=True)
        self._watches[project.name] = (watch, handler)
        if not self._started:
            self._observer.start()
            self._started = True

    def stop(self, project_name: str) -> None:
        entry = self._watches.pop(project_name, None)
        if entry is None:
            return
        watch, handler = entry
        handler.cancel_all()
        self._observer.unschedule(watch)

    def stop_all(self) -> None:
        for name in list(self._watches):
            self.stop(name)

    def watching(self) -> list[str]:
        return list(self._watches)

    def shutdown(self) -> None:
        self.stop_all()
        if self._started:
            self._observer.stop()
            self._observer.join(timeout=5)
            self._started = False
