from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture
def agent_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Isolate every test's state/log/queue under a temp dir."""
    home = tmp_path / "ghost_home"
    monkeypatch.setenv("GHOST_AGENT_HOME", str(home))
    return home


@pytest.fixture
def project_dir(tmp_path: Path) -> Path:
    d = tmp_path / "client-rebrand-2026"
    d.mkdir()
    return d
