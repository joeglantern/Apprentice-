from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any

import pytest
from PIL import Image

from ghost_training.config import TrainingConfig


def payload(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "asset_id": str(uuid.uuid4()),
        "source_project": "client-rebrand-2026",
        "captured_at": "2026-08-30T10:00:00",
        "file": {
            "original_name": "hero.png",
            "format": "psd",
            "canvas": {"width": 1600, "height": 900, "dpi": 72},
        },
        "layers": [
            {
                "layer_id": "L01",
                "name": "Background",
                "type": "shape",
                "z_index": 0,
                "bbox": {"x": 0, "y": 0, "width": 1600, "height": 900},
                "color": {"hex": "#F2A623", "opacity": 1.0},
            },
            {
                "layer_id": "L02",
                "name": "Headline",
                "type": "text",
                "z_index": 1,
                "bbox": {"x": 120, "y": 80, "width": 640, "height": 96},
                "typography": {
                    "font_family": "Neue Haas Grotesk",
                    "font_size": 64,
                    "font_weight": 700,
                },
                "color": {"hex": "#1A1A1A", "opacity": 1.0},
            },
            {
                "layer_id": "L03",
                "name": "Photo",
                "type": "image",
                "z_index": 2,
                "bbox": {"x": 832, "y": 128, "width": 640, "height": 640},
            },
        ],
        "palette": ["#1A1A1A", "#F2A623", "#3B8BD4", "#FFFFFF"],
        "consent": {"project_opted_in": True, "captured_by_agent_version": "0.3.0"},
    }
    base.update(overrides)
    return base


def record(p: dict[str, Any], **overrides: Any) -> dict[str, Any]:
    rec = {
        "asset_id": p["asset_id"],
        "source_project": p["source_project"],
        "captured_at": p["captured_at"],
        "agent_id": "mac-2015",
        "status": "tagged",
        "file_key": f"assets/{p['source_project']}/{p['asset_id']}/hero.png",
        "file_size": 100,
        "updated_at": "2026-08-30T10:05:00",
        "payload": p,
        "tags": {"layer_count": len(p["layers"])},
    }
    rec.update(overrides)
    return rec


@pytest.fixture
def cfg(tmp_path: Path) -> TrainingConfig:
    return TrainingConfig(api_url="http://test", api_token="t", data_dir=tmp_path / "data")


def write_raw(cfg: TrainingConfig, recs: list[dict[str, Any]], with_files: bool = True) -> None:
    records = cfg.raw_dir / "records"
    files = cfg.raw_dir / "files"
    records.mkdir(parents=True, exist_ok=True)
    files.mkdir(parents=True, exist_ok=True)
    for rec in recs:
        (records / f"{rec['asset_id']}.json").write_text(json.dumps(rec), encoding="utf-8")
        if with_files:
            img = Image.new("RGB", (1600, 900), "#F2A623")
            img.paste("#1A1A1A", (120, 80, 760, 176))
            img.save(files / f"{rec['asset_id']}.png")
