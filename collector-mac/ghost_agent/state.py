"""Persistent agent state: which project folders are opted in, and whether capture is paused.

This module is the first line of consent enforcement. Every change goes through a method
that (a) validates the request against the consent rules and (b) persists synchronously,
so pause/revoke are effective on disk before anything else - including any network call -
can happen.
"""

from __future__ import annotations

import json
import os
import stat
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from ghost_agent.paths import state_file, token_file

Status = Literal["off", "watching", "paused"]


class ConsentError(ValueError):
    """Raised when a request would violate the opt-in-per-folder rule."""


@dataclass
class Project:
    name: str
    folder: str
    opted_in_at: str


@dataclass
class State:
    watched_projects: dict[str, Project] = field(default_factory=dict)
    paused: bool = False
    api_base_url: str = ""

    def to_json(self) -> str:
        data = asdict(self)
        return json.dumps(data, indent=2)

    @classmethod
    def from_json(cls, text: str) -> State:
        raw = json.loads(text)
        projects = {name: Project(**p) for name, p in raw.get("watched_projects", {}).items()}
        return cls(
            watched_projects=projects,
            paused=bool(raw.get("paused", False)),
            api_base_url=str(raw.get("api_base_url", "")),
        )


def _is_blanket_path(folder: Path) -> bool:
    """True for paths that would amount to 'everything', which is never allowed."""
    resolved = folder.resolve()
    home = Path.home().resolve()
    if resolved == home or resolved in home.parents:
        return True
    if resolved == Path(resolved.anchor):  # filesystem root / volume root
        return True
    if resolved.parent == Path("/Volumes") or resolved == Path("/Volumes"):
        return True
    # Top-level user library folders are too broad to count as "a project".
    broad = {home / "Library", home / "Desktop", home / "Documents", home / "Downloads"}
    return resolved in {b.resolve() for b in broad}


class StateStore:
    """Loads, validates, and persists `State`. One instance per running agent."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or state_file()
        self.state = self._load()

    # -- persistence ---------------------------------------------------------

    def _load(self) -> State:
        if self.path.exists():
            try:
                return State.from_json(self.path.read_text(encoding="utf-8"))
            except (ValueError, TypeError):
                # Corrupt state -> start from "off". Never silently start watching.
                return State()
        return State()

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".json.tmp")
        tmp.write_text(self.state.to_json(), encoding="utf-8")
        os.replace(tmp, self.path)

    # -- queries -------------------------------------------------------------

    def status(self) -> Status:
        if self.state.paused:
            return "paused"
        if self.state.watched_projects:
            return "watching"
        return "off"

    def projects(self) -> list[Project]:
        return list(self.state.watched_projects.values())

    def is_opted_in(self, project_name: str) -> bool:
        return project_name in self.state.watched_projects

    def project_for_path(self, path: str | Path) -> Project | None:
        """Return the opted-in project that contains `path`, if any."""
        p = Path(path).resolve()
        for project in self.state.watched_projects.values():
            folder = Path(project.folder).resolve()
            if p == folder or folder in p.parents:
                return project
        return None

    # -- mutations (each persists synchronously) -----------------------------

    def add_project(self, name: str, folder: str | Path) -> Project:
        name = name.strip()
        if not name:
            raise ConsentError("A project needs a name so the log can say what was captured.")
        if name in self.state.watched_projects:
            raise ConsentError(f"A project named '{name}' is already opted in.")
        path = Path(folder).expanduser()
        if not path.is_absolute():
            raise ConsentError("Project folder must be an absolute path.")
        if not path.is_dir():
            raise ConsentError(f"Not a folder: {path}")
        if _is_blanket_path(path):
            raise ConsentError(
                "That folder is too broad. Capture is opt-in per project folder, "
                "never your whole home directory, a volume, or a top-level folder."
            )
        for existing in self.state.watched_projects.values():
            ef = Path(existing.folder).resolve()
            if ef == path.resolve() or ef in path.resolve().parents or path.resolve() in ef.parents:
                raise ConsentError(
                    f"'{existing.name}' already covers that folder or is nested with it."
                )
        project = Project(
            name=name,
            folder=str(path.resolve()),
            opted_in_at=datetime.now(UTC).isoformat(),
        )
        self.state.watched_projects[name] = project
        self.save()
        return project

    def remove_project(self, name: str) -> Project:
        """Revoke a project. Persists immediately; the caller must also stop its watcher."""
        project = self.state.watched_projects.pop(name, None)
        if project is None:
            raise KeyError(name)
        self.save()
        return project

    def set_paused(self, paused: bool) -> None:
        self.state.paused = paused
        self.save()

    def set_api_base_url(self, url: str) -> None:
        self.state.api_base_url = url.strip().rstrip("/")
        self.save()

    # -- pairing token (kept out of state.json, 0600) ------------------------

    def get_token(self) -> str | None:
        tf = token_file()
        if tf.exists():
            return tf.read_text(encoding="utf-8").strip() or None
        return None

    def set_token(self, token: str) -> None:
        tf = token_file()
        tf.parent.mkdir(parents=True, exist_ok=True)
        tf.write_text(token.strip(), encoding="utf-8")
        try:
            os.chmod(tf, stat.S_IRUSR | stat.S_IWUSR)
        except OSError:
            pass
