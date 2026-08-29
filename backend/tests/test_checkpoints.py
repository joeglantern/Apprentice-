from __future__ import annotations

from httpx import AsyncClient

from tests.conftest import AUTH_A, AUTH_B, FakeStorage

LEGION = AUTH_B


async def test_checkpoint_register_upload_list(client: AsyncClient, storage: FakeStorage) -> None:
    body = {
        "name": "style-lora-v1",
        "kind": "style-lora",
        "base_model": "stabilityai/stable-diffusion-xl-base-1.0",
        "run": {"steps": 1500, "final_loss": 0.12},
    }
    r = await client.post("/checkpoints", json=body, headers=LEGION)
    assert r.status_code == 201, r.text

    files = {"file": ("style-lora-v1.safetensors", b"\x00" * 64, "application/octet-stream")}
    r = await client.put("/checkpoints/style-lora-v1/files", files=files, headers=LEGION)
    assert r.status_code == 200, r.text
    assert r.json()["files"] == ["style-lora-v1.safetensors"]
    assert "checkpoints/style-lora-v1/style-lora-v1.safetensors" in storage.objects

    r = await client.put(
        "/checkpoints/style-lora-v1/files",
        files={"file": ("run.json", b"{}", "application/json")},
        headers=LEGION,
    )
    assert r.json()["files"] == ["run.json", "style-lora-v1.safetensors"]

    r = await client.get("/checkpoints", params={"kind": "style-lora"}, headers=AUTH_A)
    assert [c["name"] for c in r.json()] == ["style-lora-v1"]

    # Another agent cannot overwrite it; bad file types are refused.
    r = await client.post("/checkpoints", json=body, headers=AUTH_A)
    assert r.status_code == 403
    r = await client.put(
        "/checkpoints/style-lora-v1/files",
        files={"file": ("evil.sh", b"rm", "text/plain")},
        headers=LEGION,
    )
    assert r.status_code == 400


async def test_checkpoint_name_validation(client: AsyncClient) -> None:
    r = await client.post(
        "/checkpoints",
        json={"name": "Bad Name", "kind": "style-lora", "base_model": "x"},
        headers=LEGION,
    )
    assert r.status_code == 422
    r = await client.get("/checkpoints/missing-v9", headers=LEGION)
    assert r.status_code == 404
