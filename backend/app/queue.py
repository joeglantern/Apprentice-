"""Thin helpers so routes never import Celery task objects directly."""

from __future__ import annotations

from app.worker import tag_asset


async def enqueue_vision_tagging(asset_id: str) -> None:
    tag_asset.delay(asset_id)
