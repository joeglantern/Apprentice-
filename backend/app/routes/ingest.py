"""Ingestion: the collector posts a record, then uploads the export file for it.

Consent is enforced structurally here: a record whose consent block is missing or not
opted in is rejected with 403 before anything is written to the database or storage.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.auth import verify_agent_token
from app.config import Settings, get_settings
from app.db import get_session
from app.models import Asset, utcnow
from app.queue import enqueue_vision_tagging
from app.schemas import AssetPayload, AssetRead, IngestResponse
from app.storage import Storage, asset_file_key, get_storage

router = APIRouter(prefix="/ingest", tags=["ingest"])


def _require_consent(payload: AssetPayload) -> None:
    if payload.consent is None or not payload.consent.project_opted_in:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Project is not opted in for capture; the record was not stored",
        )


@router.post("/asset", status_code=status.HTTP_202_ACCEPTED, response_model=IngestResponse)
async def ingest_asset(
    payload: AssetPayload,
    session: AsyncSession = Depends(get_session),
    agent_id: str = Depends(verify_agent_token),
) -> IngestResponse:
    _require_consent(payload)  # before any write, on purpose

    existing = await session.get(Asset, payload.asset_id)
    if existing is not None:
        if existing.agent_id != agent_id:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Asset belongs to another agent")
        # Idempotent re-post from a retrying collector: refresh the record, keep the file.
        existing.payload = payload.model_dump(mode="json")
        existing.source_project = payload.source_project
        existing.captured_at = payload.captured_at
        existing.updated_at = utcnow()
        session.add(existing)
        await session.commit()
        return IngestResponse(
            status="queued", asset_id=existing.asset_id, file_key=existing.file_key
        )

    asset = Asset(
        asset_id=payload.asset_id,
        source_project=payload.source_project,
        captured_at=payload.captured_at,
        agent_id=agent_id,
        agent_version=payload.consent.captured_by_agent_version,  # type: ignore[union-attr]
        payload=payload.model_dump(mode="json"),
    )
    session.add(asset)
    await session.commit()
    await enqueue_vision_tagging(asset.asset_id)
    return IngestResponse(status="queued", asset_id=asset.asset_id)


@router.put("/asset/{asset_id}/file", response_model=IngestResponse)
async def upload_asset_file(
    asset_id: str,
    file: UploadFile,
    session: AsyncSession = Depends(get_session),
    agent_id: str = Depends(verify_agent_token),
    storage: Storage = Depends(get_storage),
    settings: Settings = Depends(get_settings),
) -> IngestResponse:
    asset = await session.get(Asset, asset_id)
    if asset is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Post the asset record first")
    if asset.agent_id != agent_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Asset belongs to another agent")
    # Defence in depth: the stored record must still carry consent.
    if not asset.payload.get("consent", {}).get("project_opted_in"):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Stored record is not opted in")

    data = await file.read(settings.max_upload_bytes + 1)
    if len(data) > settings.max_upload_bytes:
        raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, "File is too large")
    if not data:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Empty file")

    key = asset_file_key(asset.source_project, asset.asset_id, file.filename or "file")
    await storage.put(key, data, file.content_type or "application/octet-stream")

    asset.file_key = key
    asset.file_size = len(data)
    asset.file_uploaded_at = utcnow()
    if asset.status == "received":
        asset.status = "stored"
    asset.updated_at = utcnow()
    session.add(asset)
    await session.commit()
    return IngestResponse(status="stored", asset_id=asset.asset_id, file_key=key)


@router.get("/asset/{asset_id}", response_model=AssetRead)
async def read_asset(
    asset_id: str,
    session: AsyncSession = Depends(get_session),
    agent_id: str = Depends(verify_agent_token),
) -> Asset:
    asset = await session.get(Asset, asset_id)
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
