"""Small client for the backend routes the training machine needs."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import httpx


class GhostApi:
    def __init__(self, base_url: str, token: str, timeout: float = 120.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.client = httpx.Client(
            base_url=self.base_url,
            headers={"Authorization": f"Bearer {token}"},
            timeout=timeout,
        )

    def close(self) -> None:
        self.client.close()

    def list_assets(self, since: str | None = None, page: int = 500) -> Iterator[dict[str, Any]]:
        """Every tagged asset from every agent, newest first, paginated by the API limit."""
        params: dict[str, Any] = {"all_agents": "true", "status_filter": "tagged", "limit": page}
        if since:
            params["since"] = since
        r = self.client.get("/ingest/assets", params=params)
        r.raise_for_status()
        yield from r.json()

    def download_file(self, asset_id: str, target: Path) -> Path:
        target.parent.mkdir(parents=True, exist_ok=True)
        with self.client.stream("GET", f"/ingest/asset/{asset_id}/file") as r:
            r.raise_for_status()
            tmp = target.with_suffix(target.suffix + ".part")
            with tmp.open("wb") as fh:
                for chunk in r.iter_bytes(1024 * 1024):
                    fh.write(chunk)
            tmp.replace(target)
        return target

    def register_checkpoint(
        self, name: str, kind: str, base_model: str, run: dict[str, Any]
    ) -> dict[str, Any]:
        r = self.client.post(
            "/checkpoints",
            json={"name": name, "kind": kind, "base_model": base_model, "run": run},
        )
        r.raise_for_status()
        return r.json()

    def upload_checkpoint_file(self, name: str, path: Path) -> dict[str, Any]:
        with path.open("rb") as fh:
            r = self.client.put(
                f"/checkpoints/{name}/files",
                files={"file": (path.name, fh, "application/octet-stream")},
                timeout=None,
            )
        r.raise_for_status()
        return r.json()

    def list_checkpoints(self, kind: str | None = None) -> list[dict[str, Any]]:
        r = self.client.get("/checkpoints", params={"kind": kind} if kind else None)
        r.raise_for_status()
        return r.json()
