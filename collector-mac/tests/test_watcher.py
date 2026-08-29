from __future__ import annotations

import threading
import time
from pathlib import Path

from ghost_agent.state import Project, StateStore
from ghost_agent.watcher import WatchManager


def _wait(cond, timeout: float = 5.0) -> bool:  # noqa: ANN001
    end = time.time() + timeout
    while time.time() < end:
        if cond():
            return True
        time.sleep(0.05)
    return cond()


def test_only_opted_in_folder_is_watched(
    agent_home: Path, project_dir: Path, tmp_path: Path
) -> None:
    store = StateStore()
    project = store.add_project("rebrand", project_dir)
    captured: list[tuple[Path, Project]] = []
    lock = threading.Lock()

    def on_capture(path: Path, proj: Project) -> None:
        with lock:
            captured.append((path, proj))

    wm = WatchManager(on_capture, settle_seconds=0.3)
    try:
        wm.start(project)
        (project_dir / "hero.psd").write_bytes(b"8BPS")
        (tmp_path / "outside.psd").write_bytes(b"8BPS")  # not opted in
        (project_dir / "notes.txt").write_text("ignored extension")
        assert _wait(lambda: len(captured) >= 1)
        time.sleep(0.6)
        assert [c[0].name for c in captured] == ["hero.psd"]
        assert captured[0][1].name == "rebrand"
    finally:
        wm.shutdown()


def test_debounce_collapses_write_bursts(agent_home: Path, project_dir: Path) -> None:
    store = StateStore()
    project = store.add_project("rebrand", project_dir)
    captured: list[Path] = []
    wm = WatchManager(lambda p, _proj: captured.append(p), settle_seconds=0.4)
    try:
        wm.start(project)
        f = project_dir / "export.png"
        for i in range(5):
            f.write_bytes(b"x" * (i + 1))
            time.sleep(0.05)
        assert _wait(lambda: len(captured) >= 1)
        time.sleep(0.8)
        assert len(captured) == 1
    finally:
        wm.shutdown()


def test_stop_takes_effect_immediately(agent_home: Path, project_dir: Path) -> None:
    store = StateStore()
    project = store.add_project("rebrand", project_dir)
    captured: list[Path] = []
    wm = WatchManager(lambda p, _proj: captured.append(p), settle_seconds=0.2)
    try:
        wm.start(project)
        assert wm.watching() == ["rebrand"]
        (project_dir / "pending.png").write_bytes(b"x")
        wm.stop("rebrand")  # cancels pending debounce timers too
        assert wm.watching() == []
        time.sleep(0.6)
        (project_dir / "after.png").write_bytes(b"x")
        time.sleep(0.6)
        assert captured == []
    finally:
        wm.shutdown()
