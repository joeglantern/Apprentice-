"""Thin helpers so routes never import Celery task objects directly."""

from __future__ import annotations

from app.worker import tag_asset


def enqueue_vision_tagging(asset_id: str) -> None:
    """Blocking kombu publish; routes call it via run_in_threadpool."""
    tag_asset.delay(asset_id)
