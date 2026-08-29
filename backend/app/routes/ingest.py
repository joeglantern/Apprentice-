"""Ingestion: the collector posts a record, then uploads the export file for it.

Consent is enforced structurally here: a record whose consent block is missing or not
opted in is rejected with 403 before anything is written to the database or storage.

Lifecycle columns are independent so concurrent writers cannot clobber each other:
  status    tagging state only, received -> tagged (written by the worker)
  file_key  set once the export file is in object storage (written by the upload route)
An asset is ready for curation when status == "tagged" and file_key is not null.
"""

from __future__ import annotations

import logging
import tempfile
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Request, UploadFile, status
from fastapi.concurrency import run_in_threadpool
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.auth import verify_agent_token
from app.config import Settings, get_settings
from app.db import get_session
from app.models import Asset, utcnow
from app.queue import enqueue_vision_tagging
from app.schemas import UUID_PATTERN, AssetPayload, AssetRead, IngestResponse
from app.storage import Storage, asset_file_key, get_storage

log = logging.getLogger(__name__)
router = APIRouter(prefix="/ingest", tags=["ingest"])

AssetId = Annotated[str, Path(pattern=UUID_PATTERN)]
CHUNK = 1024 * 1024


def _require_consent(payload: AssetPayload) -> None:
    if payload.consent is None or not payload.consent.project_opted_in:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Project is not opted in for capture; the record was not stored",
        )


async def _queue_tagging(asset_id: str) -> None:
    """Publish off the event loop; never fail the request because the broker blinked.
    The worker's periodic retag sweep picks up anything left in status=received."""
    try:
        await run_in_threadpool(enqueue_vision_tagging, asset_id)
    except Exception:  # noqa: BLE001
        log.exception("could not enqueue tagging for %s; the sweep will retry", asset_id)


@router.post("/asset", status_code=status.HTTP_202_ACCEPTED, response_model=IngestResponse)
async def ingest_asset(
    payload: AssetPayload,
    session: AsyncSession = Depends(get_session),
    agent_id: str = Depends(verify_agent_token),
) -> IngestResponse:
    _require_consent(payload)  # before any write, on purpose
    assert payload.consent is not None

    existing = await session.get(Asset, payload.asset_id)
    if existing is not None:
        if existing.agent_id != agent_id:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Asset belongs to another agent")
        # Idempotent re-post from a retrying collector: refresh the record and retag it.
        existing.payload = payload.model_dump(mode="json")
        existing.source_project = payload.source_project
        existing.captured_at = payload.captured_at
        existing.agent_version = payload.consent.captured_by_agent_version
        existing.status = "received"
        existing.updated_at = utcnow()
        session.add(existing)
        await session.commit()
        await _queue_tagging(existing.asset_id)
        return IngestResponse(
            status="queued", asset_id=existing.asset_id, file_key=existing.file_key
        )

    asset = Asset(
        asset_id=payload.asset_id,
        source_project=payload.source_project,
        captured_at=payload.captured_at,
        agent_id=agent_id,
        agent_version=payload.consent.captured_by_agent_version,
        payload=payload.model_dump(mode="json"),
    )
    session.add(asset)
    await session.commit()
    await _queue_tagging(asset.asset_id)
    return IngestResponse(status="queued", asset_id=asset.asset_id)


@router.put("/asset/{asset_id}/file", response_model=IngestResponse)
async def upload_asset_file(
    asset_id: AssetId,
    file: UploadFile,
    request: Request,
    session: AsyncSession = Depends(get_session),
    agent_id: str = Depends(verify_agent_token),
    storage: Storage = Depends(get_storage),
    settings: Settings = Depends(get_settings),
) -> IngestResponse:
    asset_id = asset_id.lower()
    declared = request.headers.get("content-length")
    if declared and declared.isdigit() and int(declared) > settings.max_upload_bytes + 4096:
        raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, "File is too large")

    asset = await session.get(Asset, asset_id)
    if asset is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Post the asset record first")
    if asset.agent_id != agent_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Asset belongs to another agent")
    # Defence in depth: the stored record must still carry consent.
    if not asset.payload.get("consent", {}).get("project_opted_in"):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Stored record is not opted in")

    # Stream to a spooled temp file so a large PSD never sits in memory as one bytes object.
    size = 0
    with tempfile.SpooledTemporaryFile(max_size=8 * CHUNK) as spool:
        while True:
            chunk = await file.read(CHUNK)
            if not chunk:
                break
            size += len(chunk)
            if size > settings.max_upload_bytes:
                raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, "File is too large")
            spool.write(chunk)
        if size == 0:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Empty file")
        spool.seek(0)

        key = asset_file_key(asset.source_project, asset.asset_id, file.filename)
        previous_key = asset.file_key
        await storage.put(key, spool, file.content_type or "application/octet-stream")

    asset.file_key = key
    asset.file_size = size
    asset.file_uploaded_at = utcnow()
    asset.updated_at = utcnow()
    session.add(asset)
    try:
        await session.commit()
    except Exception:
        await _best_effort_delete(storage, key)
        raise
    if previous_key and previous_key != key:
        await _best_effort_delete(storage, previous_key)
    return IngestResponse(status="stored", asset_id=asset.asset_id, file_key=key)


async def _best_effort_delete(storage: Storage, key: str) -> None:
    try:
        await storage.delete(key)
    except Exception:  # noqa: BLE001
        log.warning("could not delete object %s", key)


@router.get("/asset/{asset_id}", response_model=AssetRead)
async def read_asset(
    asset_id: AssetId,
    session: AsyncSession = Depends(get_session),
    agent_id: str = Depends(verify_agent_token),
) -> Asset:
    asset = await session.get(Asset, asset_id.lower())
    if asset is None or asset.agent_id != agent_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not found")
    return asset


@router.get("/assets", response_model=list[AssetRead])
async def list_assets(
    project: str | None = None,
    limit: int = 50,
    session: AsyncSession = Depends(get_session),
    agent_id: str = Depends(verify_agent_token),
) -> list[Asset]:
    stmt = select(Asset).where(Asset.agent_id == agent_id)
    if project:
        stmt = stmt.where(Asset.source_project == project)
    stmt = stmt.order_by(Asset.captured_at.desc()).limit(min(max(limit, 1), 500))  # type: ignore[attr-defined]
    result = await session.exec(stmt)
    return list(result.all())
