from __future__ import annotations

from httpx import AsyncClient

from tests.conftest import AUTH_A, AUTH_B, FakeStorage, make_payload


async def test_health(client: AsyncClient) -> None:
    r = await client.get("/health")
    assert r.status_code == 200


async def test_ingest_happy_path_then_tagged(client: AsyncClient) -> None:
    payload = make_payload()
    r = await client.post("/ingest/asset", json=payload, headers=AUTH_A)
    assert r.status_code == 202, r.text
    assert r.json() == {"status": "queued", "asset_id": payload["asset_id"], "file_key": None}

    r = await client.get(f"/ingest/asset/{payload['asset_id']}", headers=AUTH_A)
    assert r.status_code == 200
    body = r.json()
    assert body["agent_id"] == "mac-m4"
    assert body["status"] == "tagged"
    assert body["tags"]["layer_count"] == 2
    assert body["tags"]["has_text"] is True
    assert body["tags"]["orientation"] == "landscape"
    assert body["payload"]["palette"] == ["#1A1A1A", "#F2A623"]  # normalised to upper case


async def test_consent_false_is_rejected_before_write(client: AsyncClient) -> None:
    payload = make_payload(
        consent={"project_opted_in": False, "captured_by_agent_version": "0.3.0"}
    )
    r = await client.post("/ingest/asset", json=payload, headers=AUTH_A)
    assert r.status_code == 403
    r = await client.get(f"/ingest/asset/{payload['asset_id']}", headers=AUTH_A)
    assert r.status_code == 404


async def test_consent_missing_is_rejected(client: AsyncClient) -> None:
    payload = make_payload()
    del payload["consent"]
    r = await client.post("/ingest/asset", json=payload, headers=AUTH_A)
    assert r.status_code == 403


async def test_auth_required(client: AsyncClient) -> None:
    payload = make_payload()
    assert (await client.post("/ingest/asset", json=payload)).status_code == 401
    bad = {"Authorization": "Bearer nope"}
    assert (await client.post("/ingest/asset", json=payload, headers=bad)).status_code == 401


async def test_query_param_token_is_a_fallback_not_a_bypass(client: AsyncClient) -> None:
    """The ?token= fallback exists only for contexts that can't set a header (an <img>
    tag loading a raster) - it must accept a valid token there, but never let a bad
    query token override a good header, or a bad header block a good query token."""
    r = await client.get("/ingest/assets", params={"token": "token-a"})
    assert r.status_code == 200
    r = await client.get("/ingest/assets", params={"token": "not-a-real-token"})
    assert r.status_code == 401
    r = await client.get("/ingest/assets", headers=AUTH_A, params={"token": "not-a-real-token"})
    assert r.status_code == 200  # good header wins even with a bad query token present


async def test_validation_errors(client: AsyncClient) -> None:
    r = await client.post("/ingest/asset", json=make_payload(palette=["red"]), headers=AUTH_A)
    assert r.status_code == 422
    r = await client.post(
        "/ingest/asset", json=make_payload(source_project="../etc"), headers=AUTH_A
    )
    assert r.status_code == 422
    r = await client.post("/ingest/asset", json=make_payload(asset_id="short"), headers=AUTH_A)
    assert r.status_code == 422


async def test_repost_is_idempotent(client: AsyncClient) -> None:
    payload = make_payload()
    assert (await client.post("/ingest/asset", json=payload, headers=AUTH_A)).status_code == 202
    payload["palette"] = ["#FFFFFF"]
    r = await client.post("/ingest/asset", json=payload, headers=AUTH_A)
    assert r.status_code == 202
    r = await client.get(f"/ingest/asset/{payload['asset_id']}", headers=AUTH_A)
    assert r.json()["payload"]["palette"] == ["#FFFFFF"]
    # Another agent may not overwrite it.
    r = await client.post("/ingest/asset", json=payload, headers=AUTH_B)
    assert r.status_code == 403


async def test_file_upload(client: AsyncClient, storage: FakeStorage) -> None:
    payload = make_payload()
    await client.post("/ingest/asset", json=payload, headers=AUTH_A)
    files = {"file": ("hero-banner.psd", b"8BPS" + b"\x00" * 100, "image/vnd.adobe.photoshop")}
    r = await client.put(f"/ingest/asset/{payload['asset_id']}/file", files=files, headers=AUTH_A)
    assert r.status_code == 200, r.text
    key = r.json()["file_key"]
    assert key == f"assets/client-rebrand-2026/{payload['asset_id']}/hero-banner.psd"
    assert storage.objects[key][0].startswith(b"8BPS")

    r = await client.get(f"/ingest/asset/{payload['asset_id']}", headers=AUTH_A)
    assert r.json()["file_key"] == key


async def test_file_upload_guards(client: AsyncClient) -> None:
    payload = make_payload()
    files = {"file": ("a.psd", b"x", "application/octet-stream")}
    r = await client.put(f"/ingest/asset/{payload['asset_id']}/file", files=files, headers=AUTH_A)
    assert r.status_code == 404  # record first

    await client.post("/ingest/asset", json=payload, headers=AUTH_A)
    r = await client.put(f"/ingest/asset/{payload['asset_id']}/file", files=files, headers=AUTH_B)
    assert r.status_code == 403  # other agent

    big = {"file": ("a.psd", b"x" * 2048, "application/octet-stream")}
    r = await client.put(f"/ingest/asset/{payload['asset_id']}/file", files=big, headers=AUTH_A)
    assert r.status_code == 413

    empty = {"file": ("a.psd", b"", "application/octet-stream")}
    r = await client.put(f"/ingest/asset/{payload['asset_id']}/file", files=empty, headers=AUTH_A)
    assert r.status_code == 400


async def test_list_assets_scoped_to_agent(client: AsyncClient) -> None:
    a = make_payload(source_project="alpha")
    b = make_payload(source_project="beta")
    await client.post("/ingest/asset", json=a, headers=AUTH_A)
    await client.post("/ingest/asset", json=b, headers=AUTH_B)
    r = await client.get("/ingest/assets", headers=AUTH_A)
    assert [x["source_project"] for x in r.json()] == ["alpha"]
    r = await client.get("/ingest/assets", params={"project": "beta"}, headers=AUTH_B)
    assert len(r.json()) == 1


async def test_aware_captured_at_is_stored_as_naive_utc(client: AsyncClient) -> None:
    payload = make_payload(captured_at="2026-08-30T12:00:00+02:00")
    r = await client.post("/ingest/asset", json=payload, headers=AUTH_A)
    assert r.status_code == 202, r.text
    r = await client.get(f"/ingest/asset/{payload['asset_id']}", headers=AUTH_A)
    assert r.json()["captured_at"] == "2026-08-30T10:00:00"


async def test_palette_rejects_lookalikes(client: AsyncClient) -> None:
    for bad in ["#+1A1A1", "# 1A1A1", "#0x1A1A", "#1_A1A1", "1A1A1A"]:
        r = await client.post("/ingest/asset", json=make_payload(palette=[bad]), headers=AUTH_A)
        assert r.status_code == 422, bad


async def test_asset_id_must_be_uuid(client: AsyncClient) -> None:
    bad = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaa/../aaa"
    r = await client.post("/ingest/asset", json=make_payload(asset_id=bad), headers=AUTH_A)
    assert r.status_code == 422
    r = await client.get(f"/ingest/asset/{bad}", headers=AUTH_A)
    assert r.status_code in (404, 422)


async def test_non_ascii_token_is_401_not_500(client: AsyncClient) -> None:
    raw = {b"Authorization": "Bearer töken".encode("latin-1")}
    r = await client.get("/ingest/assets", headers=raw)
    assert r.status_code == 401


async def test_repost_retags_and_updates_version(client: AsyncClient) -> None:
    payload = make_payload()
    await client.post("/ingest/asset", json=payload, headers=AUTH_A)
    payload["palette"] = ["#FFFFFF"]
    payload["consent"]["captured_by_agent_version"] = "0.4.0"
    await client.post("/ingest/asset", json=payload, headers=AUTH_A)
    r = await client.get(f"/ingest/asset/{payload['asset_id']}", headers=AUTH_A)
    body = r.json()
    assert body["status"] == "tagged"
    assert body["tags"]["palette_size"] == 1


async def test_upload_does_not_regress_tagging_state(
    client: AsyncClient, storage: FakeStorage
) -> None:
    payload = make_payload()
    await client.post("/ingest/asset", json=payload, headers=AUTH_A)
    files = {"file": ("../../evil.psd", b"8BPS", "application/octet-stream")}
    r = await client.put(f"/ingest/asset/{payload['asset_id']}/file", files=files, headers=AUTH_A)
    assert r.status_code == 200, r.text
    key = r.json()["file_key"]
    assert key.endswith("/evil.psd") and ".." not in key
    r = await client.get(f"/ingest/asset/{payload['asset_id']}", headers=AUTH_A)
    assert r.json()["status"] == "tagged"
    assert r.json()["file_key"] == key
    # Re-upload under a new name replaces the object and removes the old one.
    files = {"file": ("renamed.psd", b"8BPS", "application/octet-stream")}
    r = await client.put(f"/ingest/asset/{payload['asset_id']}/file", files=files, headers=AUTH_A)
    assert list(storage.objects) == [r.json()["file_key"]]


async def test_declared_content_length_rejected_early(client: AsyncClient) -> None:
    payload = make_payload()
    await client.post("/ingest/asset", json=payload, headers=AUTH_A)
    req = client.build_request(
        "PUT",
        f"/ingest/asset/{payload['asset_id']}/file",
        files={"file": ("a.psd", b"x", "application/octet-stream")},
        headers=AUTH_A,
    )
    req.headers["content-length"] = "999999999"
    r = await client.send(req)
    assert r.status_code == 413


async def test_download_file_and_training_listing(client: AsyncClient) -> None:
    payload = make_payload()
    await client.post("/ingest/asset", json=payload, headers=AUTH_A)
    files = {"file": ("hero.psd", b"8BPS-data", "application/octet-stream")}
    await client.put(f"/ingest/asset/{payload['asset_id']}/file", files=files, headers=AUTH_A)

    r = await client.get(f"/ingest/asset/{payload['asset_id']}/file", headers=AUTH_B)
    assert r.status_code == 200
    assert r.content == b"8BPS-data"

    params = {"all_agents": "true", "status_filter": "tagged"}
    r = await client.get("/ingest/assets", params=params, headers=AUTH_B)
    assert [a["asset_id"] for a in r.json()] == [payload["asset_id"]]
    params = {"all_agents": "true", "since": "2999-01-01T00:00:00Z"}
    r = await client.get("/ingest/assets", params=params, headers=AUTH_B)
    assert r.json() == []
