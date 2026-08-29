"""Incremental pull of tagged records and their export files from the VPS.

Writes data/raw/records/<asset_id>.json (the full API record) and
data/raw/files/<asset_id>.<ext>. A manifest keeps the high water mark so each run only
fetches what changed. Records without consent are not even downloaded.
"""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from ghost_training.api import GhostApi
from ghost_training.config import TrainingConfig, load_config
from ghost_training.validate import is_consented


def _manifest_path(cfg: TrainingConfig) -> Path:
    return cfg.raw_dir / "manifest.json"


def load_manifest(cfg: TrainingConfig) -> dict[str, Any]:
    path = _manifest_path(cfg)
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {"since": None, "assets": {}}


def save_manifest(cfg: TrainingConfig, manifest: dict[str, Any]) -> None:
    path = _manifest_path(cfg)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")


def pull(cfg: TrainingConfig, api: GhostApi, full: bool = False) -> dict[str, int]:
    manifest = load_manifest(cfg)
    since = None if full else manifest.get("since")
    records_dir = cfg.raw_dir / "records"
    files_dir = cfg.raw_dir / "files"
    records_dir.mkdir(parents=True, exist_ok=True)
    files_dir.mkdir(parents=True, exist_ok=True)

    counts = {"seen": 0, "updated": 0, "skipped_no_consent": 0, "skipped_no_file": 0}
    newest = since
    for record in api.list_assets(since=since):
        counts["seen"] += 1
        updated_at = record.get("updated_at")
        if updated_at and (newest is None or updated_at > newest):
            newest = updated_at
        if not is_consented(record):
            counts["skipped_no_consent"] += 1
            continue
        if not record.get("file_key"):
            counts["skipped_no_file"] += 1
            continue
        asset_id = record["asset_id"]
        known = manifest["assets"].get(asset_id)
        if known and known.get("updated_at") == updated_at and not full:
            continue
        ext = Path(record["file_key"]).suffix.lower() or ".bin"
        api.download_file(asset_id, files_dir / f"{asset_id}{ext}")
        (records_dir / f"{asset_id}.json").write_text(json.dumps(record, indent=2), "utf-8")
        manifest["assets"][asset_id] = {"updated_at": updated_at, "file": f"{asset_id}{ext}"}
        counts["updated"] += 1

    manifest["since"] = newest
    manifest["pulled_at"] = datetime.now(UTC).isoformat()
    save_manifest(cfg, manifest)
    return counts


def main() -> int:
    cfg = load_config()
    api = GhostApi(cfg.api_url, cfg.api_token)
    try:
        counts = pull(cfg, api, full="--full" in sys.argv)
    finally:
        api.close()
    print(json.dumps(counts))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
