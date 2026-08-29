from __future__ import annotations

import json

import httpx

from ghost_training.api import GhostApi
from ghost_training.config import TrainingConfig
from ghost_training.pull import load_manifest, pull
from tests.conftest import payload, record


def make_api(records: list[dict], files: dict[str, bytes], calls: list[str]) -> GhostApi:
    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(f"{request.method} {request.url.path}?{request.url.query.decode()}")
        if request.url.path == "/ingest/assets":
            return httpx.Response(200, json=records)
        if request.url.path.startswith("/ingest/asset/") and request.url.path.endswith("/file"):
            asset_id = request.url.path.split("/")[3]
            return httpx.Response(200, content=files[asset_id])
        return httpx.Response(404)

    api = GhostApi("http://test", "t")
    api.client = httpx.Client(
        base_url="http://test", transport=httpx.MockTransport(handler), headers=api.client.headers
    )
    return api


def test_pull_downloads_only_consented_and_is_incremental(cfg: TrainingConfig) -> None:
    good = record(payload())
    unconsented_payload = payload()
    unconsented_payload["consent"]["project_opted_in"] = False
    unconsented = record(unconsented_payload, updated_at="2026-08-30T11:00:00")
    nofile = record(payload(), file_key=None)
    calls: list[str] = []
    api = make_api([good, unconsented, nofile], {good["asset_id"]: b"\x89PNG"}, calls)

    counts = pull(cfg, api)
    assert counts == {"seen": 3, "updated": 1, "skipped_no_consent": 1, "skipped_no_file": 1}
    assert (cfg.raw_dir / "files" / f"{good['asset_id']}.png").read_bytes() == b"\x89PNG"
    assert not any(unconsented["asset_id"] in c for c in calls)  # never even requested
    saved = json.loads((cfg.raw_dir / "records" / f"{good['asset_id']}.json").read_text())
    assert saved["payload"]["consent"]["project_opted_in"] is True

    manifest = load_manifest(cfg)
    assert manifest["since"] == "2026-08-30T11:00:00"
    assert manifest["assets"][good["asset_id"]]["updated_at"] == good["updated_at"]

    # Second run passes the high water mark and re-downloads nothing.
    calls.clear()
    counts = pull(cfg, api)
    assert counts["updated"] == 0
    assert calls[0].endswith("since=2026-08-30T11%3A00%3A00") or "since=2026-08-30T11" in calls[0]
    assert len(calls) == 1
