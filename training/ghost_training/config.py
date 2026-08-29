"""Environment driven settings for the training machine."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class TrainingConfig:
    api_url: str
    api_token: str
    data_dir: Path
    agent_id: str = "legion"

    @property
    def raw_dir(self) -> Path:
        return self.data_dir / "raw"

    @property
    def curated_dir(self) -> Path:
        return self.data_dir / "curated"

    @property
    def checkpoints_dir(self) -> Path:
        return self.data_dir / "checkpoints"


def load_config() -> TrainingConfig:
    url = os.environ.get("GHOST_API_URL", "").rstrip("/")
    token = os.environ.get("GHOST_API_TOKEN", "")
    if not url or not token:
        raise SystemExit(
            "Set GHOST_API_URL (e.g. http://localhost:8000 through the ssh tunnel) and "
            "GHOST_API_TOKEN (the legion agent token from the VPS .env)."
        )
    return TrainingConfig(
        api_url=url,
        api_token=token,
        data_dir=Path(os.environ.get("GHOST_DATA_DIR", "data")).resolve(),
    )
