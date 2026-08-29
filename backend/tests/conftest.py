from __future__ import annotations

import os
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any

# Settings are read at import time by app.worker, so set the environment first.
os.environ.update(
    {
        "DATABASE_URL": "sqlite+aiosqlite:///./test.db",
        "REDIS_URL": "redis://localhost:6379/9",
        "AGENT_TOKENS": "mac-m4:token-a,mac-2015:token-b",
        "CELERY_TASK_ALWAYS_EAGER": "true",
        "MAX_UPLOAD_BYTES": "1024",
    }
)

import pytest  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine  # noqa: E402
from sqlmodel import SQLModel  # noqa: E402
from sqlmodel.ext.asyncio.session import AsyncSession  # noqa: E402

from app import worker  # noqa: E402
from app.db import get_session  # noqa: E402
from app.main import create_app  # noqa: E402
from app.storage import get_storage  # noqa: E402


class FakeStorage:
    def __init__(self) -> None:
        self.objects: dict[str, tuple[bytes, str]] = {}

    async def put(self, key: str, body: Any, content_type: str) -> None:
        self.objects[key] = (body.read(), content_type)

    async def get(self, key: str) -> bytes:
        return self.objects[key][0]

    async def delete(self, key: str) -> None:
        self.objects.pop(key, None)


@pytest.fixture
async def engine():  # noqa: ANN201
    eng = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with eng.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    yield eng
    await eng.dispose()


@pytest.fixture
async def session_maker(engine):  # noqa: ANN001, ANN201
    return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


@pytest.fixture
def storage() -> FakeStorage:
    return FakeStorage()


@pytest.fixture
async def client(session_maker, storage, monkeypatch) -> AsyncIterator[AsyncClient]:  # noqa: ANN001
    app = create_app(mount_realtime=False)

    async def _session() -> AsyncIterator[AsyncSession]:
        async with session_maker() as s:
            yield s

    app.dependency_overrides[get_session] = _session
    app.dependency_overrides[get_storage] = lambda: storage

    # The tagging task runs inline against the same in-memory DB.
    async def _tag(asset_id: str) -> None:
        from sqlmodel import select

        from app.models import Asset

        async with session_maker() as s:
            asset = (await s.exec(select(Asset).where(Asset.asset_id == asset_id))).first()
            if asset is not None:
                asset.tags = worker.basic_tags(asset.payload)
                asset.status = "tagged"
                s.add(asset)
                await s.commit()

    import app.routes.ingest as ingest_mod

    monkeypatch.setattr(ingest_mod, "_queue_tagging", _tag)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


def make_payload(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "asset_id": str(uuid.uuid4()),
        "source_project": "client-rebrand-2026",
        "captured_at": datetime.now(UTC).isoformat(),
        "file": {
            "original_name": "hero-banner.psd",
            "format": "psd",
            "canvas": {"width": 1600, "height": 900, "dpi": 72},
        },
        "layers": [
            {
                "layer_id": "L01",
                "name": "Headline",
                "type": "text",
                "z_index": 0,
                "bbox": {"x": 120, "y": 80, "width": 640, "height": 96},
                "typography": {"font_family": "Neue Haas Grotesk", "font_size": 64},
                "color": {"hex": "#1A1A1A", "opacity": 1.0},
            },
            {
                "layer_id": "L02",
                "name": "Background",
                "type": "shape",
                "z_index": 1,
                "bbox": {"x": 0, "y": 0, "width": 1600, "height": 900},
                "color": {"hex": "#F2A623", "opacity": 1.0},
            },
        ],
        "palette": ["#1a1a1a", "#F2A623"],
        "consent": {"project_opted_in": True, "captured_by_agent_version": "0.3.0"},
    }
    base.update(overrides)
    return base


AUTH_A = {"Authorization": "Bearer token-a"}
AUTH_B = {"Authorization": "Bearer token-b"}
