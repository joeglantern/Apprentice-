"""Build the curated training sets from data/raw.

Output layout (data/curated):
    style/10_ghoststyle/<asset_id>.png + .txt   kohya sd-scripts folder (10 repeats)
    layout/train.jsonl                          {"image", "canvas_width", "text"} per line
    style_profile.json                          docs/06 D3
    dataset.json                                counts, dataset hash, git sha, timestamp
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import UTC, datetime
from typing import Any

from ghost_training.captions import caption
from ghost_training.config import TrainingConfig, load_config
from ghost_training.render import render_to_png
from ghost_training.serialize import serialize
from ghost_training.style_profile import build_style_profile
from ghost_training.validate import validate_record

STYLE_SUBDIR = "10_ghoststyle"


def _git_sha() -> str | None:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def prepare(cfg: TrainingConfig) -> dict[str, Any]:
    records_dir = cfg.raw_dir / "records"
    files_dir = cfg.raw_dir / "files"
    style_dir = cfg.curated_dir / "style" / STYLE_SUBDIR
    layout_dir = cfg.curated_dir / "layout"
    style_dir.mkdir(parents=True, exist_ok=True)
    layout_dir.mkdir(parents=True, exist_ok=True)

    accepted: list[dict[str, Any]] = []
    rejected: list[tuple[str, list[str]]] = []
    layout_lines: list[str] = []
    hasher = hashlib.sha256()

    for path in sorted(records_dir.glob("*.json")):
        record = json.loads(path.read_text(encoding="utf-8"))
        problems = validate_record(record)
        if problems:
            rejected.append((path.stem, problems))
            continue
        payload = record["payload"]
        asset_id = record["asset_id"]
        source = next(iter(files_dir.glob(f"{asset_id}.*")), None)
        if source is None:
            rejected.append((asset_id, ["export file missing"]))
            continue
        png = render_to_png(source, style_dir / f"{asset_id}.png")
        if png is None:
            rejected.append((asset_id, ["could not render"]))
            continue
        (style_dir / f"{asset_id}.txt").write_text(caption(payload, record.get("tags")), "utf-8")
        if payload.get("layers"):
            layout_lines.append(
                json.dumps(
                    {
                        "image": str(png.relative_to(cfg.curated_dir)).replace("\\", "/"),
                        "canvas_width": payload["file"]["canvas"]["width"],
                        "text": serialize(payload),
                    }
                )
            )
        accepted.append(payload)
        hasher.update(asset_id.encode())
        hasher.update(str(record.get("updated_at")).encode())

    (layout_dir / "train.jsonl").write_text("\n".join(layout_lines) + "\n", "utf-8")
    profile = build_style_profile(accepted)
    (cfg.curated_dir / "style_profile.json").write_text(json.dumps(profile, indent=2), "utf-8")

    summary = {
        "prepared_at": datetime.now(UTC).isoformat(),
        "git_sha": _git_sha(),
        "dataset_hash": hasher.hexdigest()[:16],
        "style_images": len(accepted),
        "layout_examples": len(layout_lines),
        "rejected": [{"asset_id": a, "problems": p} for a, p in rejected],
    }
    (cfg.curated_dir / "dataset.json").write_text(json.dumps(summary, indent=2), "utf-8")
    return summary


def main() -> int:
    cfg = load_config()
    summary = prepare(cfg)
    print(json.dumps({k: v for k, v in summary.items() if k != "rejected"}))
    for item in summary["rejected"]:
        print(f"rejected {item['asset_id']}: {'; '.join(item['problems'])}", file=sys.stderr)
    return 0 if summary["style_images"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
