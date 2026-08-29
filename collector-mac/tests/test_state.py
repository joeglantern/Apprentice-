from __future__ import annotations

import json
from pathlib import Path

import pytest

from ghost_agent.state import ConsentError, StateStore


def test_fresh_store_is_off(agent_home: Path) -> None:
    store = StateStore()
    assert store.status() == "off"
    assert store.projects() == []


def test_add_project_persists_and_watches(agent_home: Path, project_dir: Path) -> None:
    store = StateStore()
    p = store.add_project("rebrand", project_dir)
    assert p.folder == str(project_dir.resolve())
    assert store.status() == "watching"
    # persisted synchronously
    on_disk = json.loads((agent_home / "state.json").read_text())
    assert "rebrand" in on_disk["watched_projects"]
    # reload from disk
    assert StateStore().is_opted_in("rebrand")


def test_pause_persists_before_anything_else(agent_home: Path, project_dir: Path) -> None:
    store = StateStore()
    store.add_project("rebrand", project_dir)
    store.set_paused(True)
    assert store.status() == "paused"
    assert json.loads((agent_home / "state.json").read_text())["paused"] is True
    store.set_paused(False)
    assert store.status() == "watching"


def test_remove_project_revokes(agent_home: Path, project_dir: Path) -> None:
    store = StateStore()
    store.add_project("rebrand", project_dir)
    store.remove_project("rebrand")
    assert store.status() == "off"
    assert not StateStore().is_opted_in("rebrand")
    with pytest.raises(KeyError):
        store.remove_project("rebrand")


@pytest.mark.parametrize("bad", [Path.home(), Path(Path.home().anchor)])
def test_blanket_paths_are_refused(agent_home: Path, bad: Path) -> None:
    store = StateStore()
    with pytest.raises(ConsentError):
        store.add_project("everything", bad)
    assert store.status() == "off"


def test_relative_and_missing_paths_refused(agent_home: Path, tmp_path: Path) -> None:
    store = StateStore()
    with pytest.raises(ConsentError):
        store.add_project("x", "relative/path")
    with pytest.raises(ConsentError):
        store.add_project("x", tmp_path / "does-not-exist")


def test_nested_or_duplicate_folders_refused(agent_home: Path, project_dir: Path) -> None:
    store = StateStore()
    store.add_project("rebrand", project_dir)
    sub = project_dir / "exports"
    sub.mkdir()
    with pytest.raises(ConsentError):
        store.add_project("sub", sub)
    with pytest.raises(ConsentError):
        store.add_project("again", project_dir)
    with pytest.raises(ConsentError):
        store.add_project("rebrand", project_dir.parent)


def test_project_for_path(agent_home: Path, project_dir: Path, tmp_path: Path) -> None:
    store = StateStore()
    store.add_project("rebrand", project_dir)
    assert store.project_for_path(project_dir / "a" / "b.psd").name == "rebrand"
    assert store.project_for_path(tmp_path / "elsewhere.psd") is None


def test_corrupt_state_starts_off(agent_home: Path) -> None:
    agent_home.mkdir(parents=True)
    (agent_home / "state.json").write_text("{not json")
    assert StateStore().status() == "off"


def test_token_kept_out_of_state(agent_home: Path) -> None:
    store = StateStore()
    store.set_token("secret-token")
    assert store.get_token() == "secret-token"
    assert (
        "secret" not in (agent_home / "state.json").read_text()
        if (agent_home / "state.json").exists()
        else True
    )
