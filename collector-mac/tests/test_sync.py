from __future__ import annotations

from pathlib import Path
from typing import Any

import httpx
import pytest

from ghost_agent.activity_log import tail
from ghost_agent.sync import SyncClient, build_payload

PARSED: dict[str, Any] = {
    "file": {
        "original_name": "a.png",
        "format": "png",
        "canvas": {"width": 1, "height": 1, "dpi": 72},
    },
    "layers": [],
    "palette": ["#000000"],
}


def make_client(
    agent_home: Path, *, paused: bool = False, opted: bool = True, token: str | None = "t"
) -> SyncClient:
    return SyncClient(
        "https://vps.example",
        token,
        is_paused=lambda: paused,
        is_opted_in=lambda _name: opted,
    )


def test_build_payload_uses_real_consent_state() -> None:
    p = build_payload(project_name="x", file_path="/tmp/a.png", parsed=PARSED, opted_in=False)
    assert p["consent"]["project_opted_in"] is False
    assert p["consent"]["captured_by_agent_version"]
    assert p["source_project"] == "x"


def test_refuses_unconsented_payload(agent_home: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    called = False

    def boom(self: SyncClient, payload: dict[str, Any]) -> None:
        nonlocal called
        called = True

    monkeypatch.setattr(SyncClient, "_post", boom)
    client = make_client(agent_home)
    p = build_payload(project_name="x", file_path="/tmp/a.png", parsed=PARSED, opted_in=False)
    assert client.send(p) is False
    assert called is False
    assert client.queued() == []
    assert any("not opted in" in line for line in tail())


def test_refuses_while_paused(agent_home: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(SyncClient, "_post", lambda self, payload: pytest.fail("must not post"))
    client = make_client(agent_home, paused=True)
    p = build_payload(project_name="x", file_path="/tmp/a.png", parsed=PARSED, opted_in=True)
    assert client.send(p) is False
    assert client.queued() == []


def test_refuses_revoked_project(agent_home: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(SyncClient, "_post", lambda self, payload: pytest.fail("must not post"))
    client = make_client(agent_home, opted=False)
    p = build_payload(project_name="x", file_path="/tmp/a.png", parsed=PARSED, opted_in=True)
    assert client.send(p) is False


def test_network_failure_queues_then_flush_sends(
    agent_home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    attempts: list[str] = []

    def flaky(self: SyncClient, payload: dict[str, Any]) -> None:
        attempts.append(payload["asset_id"])
        if len(attempts) == 1:
            raise httpx.ConnectError("down")

    monkeypatch.setattr(SyncClient, "_post", flaky)
    client = make_client(agent_home)
    p = build_payload(project_name="x", file_path="/tmp/a.png", parsed=PARSED, opted_in=True)
    assert client.send(p) is False
    assert len(client.queued()) == 1
    assert client.flush() == 1
    assert client.queued() == []
    assert attempts == [p["asset_id"], p["asset_id"]]


def test_unpaired_keeps_locally(agent_home: Path) -> None:
    client = make_client(agent_home, token=None)
    p = build_payload(project_name="x", file_path="/tmp/a.png", parsed=PARSED, opted_in=True)
    assert client.send(p) is False
    assert len(client.queued()) == 1


def test_drop_project_removes_queued_items(agent_home: Path) -> None:
    client = make_client(agent_home, token=None)
    for name in ("x", "x", "y"):
        client.send(
            build_payload(project_name=name, file_path="/tmp/a.png", parsed=PARSED, opted_in=True)
        )
    assert len(client.queued()) == 3
    assert client.drop_project("x") == 2
    assert len(client.queued()) == 1


def test_flush_holds_items_while_paused(agent_home: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(SyncClient, "_post", lambda self, payload: pytest.fail("must not post"))
    client = make_client(agent_home, token=None)
    client.send(
        build_payload(project_name="x", file_path="/tmp/a.png", parsed=PARSED, opted_in=True)
    )
    client.token = "t"
    client.is_paused = lambda: True
    assert client.flush() == 0
    assert len(client.queued()) == 1


def test_post_strips_private_fields_and_sends_bearer(agent_home: Path, tmp_path: Path) -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(202, json={"status": "queued"})

    transport = httpx.MockTransport(handler)
    real_client = httpx.Client
    export = tmp_path / "a.png"
    export.write_bytes(b"\x89PNG")

    class PatchedClient(real_client):  # type: ignore[misc,valid-type]
        def __init__(self, **kw: Any) -> None:
            super().__init__(transport=transport, **kw)

    import ghost_agent.sync as sync_mod

    sync_mod.httpx.Client = PatchedClient  # type: ignore[attr-defined]
    try:
        client = make_client(agent_home)
        p = build_payload(project_name="x", file_path=export, parsed=PARSED, opted_in=True)
        assert client.send(p) is True
    finally:
        sync_mod.httpx.Client = real_client  # type: ignore[attr-defined]

    assert len(seen) == 2
    post, put = seen
    assert post.headers["authorization"] == "Bearer t"
    assert b"_local_path" not in post.content
    assert put.method == "PUT"
    assert put.url.path.endswith(f"/ingest/asset/{p['asset_id']}/file")


def test_permanent_4xx_is_not_queued(agent_home: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def rejected(self: SyncClient, payload: dict[str, Any]) -> None:
        resp = httpx.Response(403, json={"detail": "Project is not opted in"})
        raise httpx.HTTPStatusError("403", request=httpx.Request("POST", "http://x"), response=resp)

    monkeypatch.setattr(SyncClient, "_post", rejected)
    client = make_client(agent_home)
    p = build_payload(project_name="x", file_path="/tmp/a.png", parsed=PARSED, opted_in=True)
    assert client.send(p) is False
    assert client.queued() == []
    assert any("rejected by server (403)" in line for line in tail())


def test_429_is_retried(agent_home: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def limited(self: SyncClient, payload: dict[str, Any]) -> None:
        resp = httpx.Response(429)
        raise httpx.HTTPStatusError("429", request=httpx.Request("POST", "http://x"), response=resp)

    monkeypatch.setattr(SyncClient, "_post", limited)
    client = make_client(agent_home)
    p = build_payload(project_name="x", file_path="/tmp/a.png", parsed=PARSED, opted_in=True)
    assert client.send(p) is False
    assert len(client.queued()) == 1


def test_check_reports_plain_reasons(agent_home: Path) -> None:
    import ghost_agent.sync as sync_mod

    real_client = httpx.Client

    def with_status(code: int) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(code, json=[])

        class Patched(real_client):  # type: ignore[misc,valid-type]
            def __init__(self, **kw: Any) -> None:
                super().__init__(transport=httpx.MockTransport(handler), **kw)

        sync_mod.httpx.Client = Patched  # type: ignore[attr-defined]

    try:
        with_status(200)
        ok, msg = make_client(agent_home).check()
        assert ok and "Paired" in msg
        with_status(401)
        ok, msg = make_client(agent_home).check()
        assert not ok and "token" in msg
    finally:
        sync_mod.httpx.Client = real_client  # type: ignore[attr-defined]

    ok, msg = make_client(agent_home, token=None).check()
    assert not ok and "token" in msg.lower()
    ok, msg = SyncClient(
        "http://127.0.0.1:9", "t", is_paused=lambda: False, is_opted_in=lambda n: True
    ).check()
    assert not ok and "Could not connect" in msg
