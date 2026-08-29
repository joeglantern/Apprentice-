"""Build ingestion payloads and send them to the VPS, with an on-disk retry queue.

Consent enforcement here (third line, after state.py and watcher.py):
- `build_payload` writes the `consent` block from *real* state, never a literal True.
- `SyncClient.send` refuses anything whose consent block is not opted in, and refuses
  to send at all while the agent is paused - checked at send time, not just enqueue time,
  so a pause that happens while a file is queued still holds.
- `SyncClient.drop_project` discards queued items for a revoked project.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

from ghost_agent import AGENT_VERSION
from ghost_agent.activity_log import log_event
from ghost_agent.paths import queue_dir


def build_payload(
    *,
    project_name: str,
    file_path: str | Path,
    parsed: dict[str, Any],
    opted_in: bool,
    agent_version: str = AGENT_VERSION,
) -> dict[str, Any]:
    """Assemble the doc 01 §3 record. `opted_in` must come from StateStore.is_opted_in()."""
    return {
        "asset_id": str(uuid.uuid4()),
        "source_project": project_name,
        "captured_at": datetime.now(UTC).isoformat(),
        "file": parsed["file"],
        "layers": parsed.get("layers", []),
        "palette": parsed.get("palette", []),
        "consent": {
            "project_opted_in": bool(opted_in),
            "captured_by_agent_version": agent_version,
        },
        "_local_path": str(file_path),  # stripped before sending; used for file upload
    }


class SyncClient:
    def __init__(
        self,
        base_url: str,
        token: str | None,
        *,
        is_paused: Callable[[], bool],
        is_opted_in: Callable[[str], bool],
        queue_path: Path | None = None,
        timeout: float = 30.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.is_paused = is_paused
        self.is_opted_in = is_opted_in
        self.queue_path = queue_path or queue_dir()
        self.timeout = timeout

    # -- consent gate ----------------------------------------------------------

    def _allowed(self, payload: dict[str, Any]) -> tuple[bool, str]:
        if self.is_paused():
            return False, "capture is paused"
        consent = payload.get("consent") or {}
        if not consent.get("project_opted_in"):
            return False, "project is not opted in"
        if not self.is_opted_in(payload.get("source_project", "")):
            return False, "project was revoked"
        return True, ""

    # -- queue ------------------------------------------------------------------

    def enqueue(self, payload: dict[str, Any]) -> Path:
        self.queue_path.mkdir(parents=True, exist_ok=True)
        target = self.queue_path / f"{payload['asset_id']}.json"
        target.write_text(json.dumps(payload), encoding="utf-8")
        return target

    def queued(self) -> list[Path]:
        if not self.queue_path.exists():
            return []
        return sorted(self.queue_path.glob("*.json"))

    def drop_project(self, project_name: str) -> int:
        """Delete queued (not-yet-sent) items for a revoked project. Returns count dropped."""
        dropped = 0
        for item in self.queued():
            try:
                data = json.loads(item.read_text(encoding="utf-8"))
            except ValueError:
                item.unlink(missing_ok=True)
                continue
            if data.get("source_project") == project_name:
                item.unlink(missing_ok=True)
                dropped += 1
        if dropped:
            log_event(f"dropped {dropped} unsent item(s) for revoked project '{project_name}'")
        return dropped

    # -- sending ----------------------------------------------------------------

    def send(self, payload: dict[str, Any]) -> bool:
        """POST the record (and the file) now. On network failure, queue for retry.
        Returns True if delivered, False if refused or queued."""
        ok, reason = self._allowed(payload)
        if not ok:
            log_event(f"not sent ({reason}): {payload.get('_local_path', '?')}")
            return False
        if not self.base_url or not self.token:
            log_event("not paired with a server yet - kept locally in the queue")
            self.enqueue(payload)
            return False
        try:
            self._post(payload)
        except (httpx.HTTPError, OSError) as exc:
            log_event(f"upload failed ({exc.__class__.__name__}); queued for retry")
            self.enqueue(payload)
            return False
        log_event(
            f"uploaded: {Path(payload.get('_local_path', '')).name} "
            f"(project={payload['source_project']}, asset={payload['asset_id'][:8]})"
        )
        return True

    def flush(self) -> int:
        """Retry queued items. Each is re-checked against the consent gate first."""
        sent = 0
        for item in self.queued():
            try:
                payload = json.loads(item.read_text(encoding="utf-8"))
            except ValueError:
                item.unlink(missing_ok=True)
                continue
            ok, _ = self._allowed(payload)
            if not ok:
                continue  # hold it; state may change later
            if not self.base_url or not self.token:
                break
            try:
                self._post(payload)
            except (httpx.HTTPError, OSError):
                break  # server unreachable; keep the rest for later
            item.unlink(missing_ok=True)
            sent += 1
        if sent:
            log_event(f"flushed {sent} queued item(s)")
        return sent

    def _post(self, payload: dict[str, Any]) -> None:
        headers = {"Authorization": f"Bearer {self.token}"}
        body = {k: v for k, v in payload.items() if not k.startswith("_")}
        with httpx.Client(timeout=self.timeout) as client:
            r = client.post(f"{self.base_url}/ingest/asset", json=body, headers=headers)
            r.raise_for_status()
            local = payload.get("_local_path")
            if local and Path(local).is_file():
                with Path(local).open("rb") as fh:
                    files = {"file": (Path(local).name, fh)}
                    r2 = client.put(
                        f"{self.base_url}/ingest/asset/{payload['asset_id']}/file",
                        files=files,
                        headers=headers,
                    )
                    r2.raise_for_status()
