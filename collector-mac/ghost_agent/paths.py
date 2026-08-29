"""Where the agent keeps its own files. Overridable via GHOST_AGENT_HOME (used by tests)."""

from __future__ import annotations

import os
from pathlib import Path


def agent_home() -> Path:
    return Path(os.environ.get("GHOST_AGENT_HOME", Path.home() / ".ghost_agent"))


def state_file() -> Path:
    return agent_home() / "state.json"


def token_file() -> Path:
    return agent_home() / "token"


def log_file() -> Path:
    return agent_home() / "activity.log"


def queue_dir() -> Path:
    return agent_home() / "queue"
