"""Celery app and background tasks. Tasks take IDs only and reload rows themselves."""

from __future__ import annotations

from typing import Any

from celery import Celery
from sqlalchemy import create_engine
from sqlmodel import Session, select

from app.config import get_settings
from app.models import Asset, utcnow

settings = get_settings()

celery_app = Celery("ghostagent", broker=settings.redis_url, backend=settings.redis_url)
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    task_always_eager=settings.celery_task_always_eager,
    task_eager_propagates=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
)

_sync_engine = None


def sync_session() -> Session:
    global _sync_engine
    if _sync_engine is None:
        _sync_engine = create_engine(settings.sync_database_url, pool_pre_ping=True)
    return Session(_sync_engine)


def basic_tags(payload: dict[str, Any]) -> dict[str, Any]:
    """Cheap structural tags from the record itself. A vision model can enrich these later."""
    layers = payload.get("layers", [])
    canvas = payload.get("file", {}).get("canvas", {})
    width, height = canvas.get("width", 0), canvas.get("height", 0)
    kinds = {"text": 0, "shape": 0, "image": 0}
    for layer in layers:
        kinds[layer.get("type", "image")] = kinds.get(layer.get("type", "image"), 0) + 1
    orientation = "square"
    if width and height:
        ratio = width / height
        orientation = "landscape" if ratio > 1.1 else "portrait" if ratio < 0.9 else "square"
    return {
        "layer_count": len(layers),
        "layer_kinds": kinds,
        "orientation": orientation,
        "aspect_ratio": round(width / height, 3) if width and height else None,
        "palette_size": len(payload.get("palette", [])),
        "has_text": kinds.get("text", 0) > 0,
        "tagger": "basic-v1",
    }


@celery_app.task(name="app.worker.tag_asset", bind=True, max_retries=3)
def tag_asset(self: Any, asset_id: str) -> str:
    """Idempotent: re-running on the same asset just recomputes the same tags."""
    with sync_session() as session:
        asset = session.exec(select(Asset).where(Asset.asset_id == asset_id)).first()
        if asset is None:
            return "missing"
        asset.tags = basic_tags(asset.payload)
        asset.status = "tagged"
        asset.updated_at = utcnow()
        session.add(asset)
        session.commit()
    return "tagged"
