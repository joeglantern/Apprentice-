"""Checkpoint registry: a folder per checkpoint in object storage plus one DB row.

The Legion pushes finished LoRA weights here; the inference gateway and the app's
aesthetic selector list them. No registry service, on purpose.
"""

from __future__ import annotations

import re
import tempfile
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Path, UploadFile, status
from pydantic import BaseModel, Field
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.auth import verify_agent_token
from app.config import Settings, get_settings
from app.db import get_session
from app.models import Checkpoint, utcnow
from app.storage import Storage, get_storage, safe_filename

router = APIRouter(prefix="/checkpoints", tags=["checkpoints"])

NAME_PATTERN = r"^[a-z0-9][a-z0-9._-]{0,63}$"
CheckpointName = Annotated[str, Path(pattern=NAME_PATTERN)]
CHUNK = 1024 * 1024
_ALLOWED = re.compile(r"\.(safetensors|json|txt|toml|yaml|yml|png|jpg|md)$")


class CheckpointCreate(BaseModel):
    name: str = Field(pattern=NAME_PATTERN, description="e.g. style-lora-v1")
    kind: str = Field(pattern=r"^(style-lora|layout-vlm)$")
    base_model: str = Field(min_length=1, max_length=200)
    run: dict[str, Any] = Field(default_factory=dict, description="run.json contents")


class CheckpointRead(BaseModel):
    name: str
    kind: str
    base_model: str
    files: list[str]
    run: dict[str, Any]
    pushed_by: str
    created_at: Any


@router.post("", status_code=status.HTTP_201_CREATED, response_model=CheckpointRead)
async def register_checkpoint(
    body: CheckpointCreate,
    session: AsyncSession = Depends(get_session),
    agent_id: str = Depends(verify_agent_token),
) -> Checkpoint:
    existing = await session.get(Checkpoint, body.name)
    if existing is not None:
        if existing.pushed_by != agent_id:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Checkpoint belongs to another agent")
        existing.run = body.run
        existing.base_model = body.base_model
        existing.kind = body.kind
        existing.updated_at = utcnow()
        session.add(existing)
        await session.commit()
        return existing
    ckpt = Checkpoint(
        name=body.name,
        kind=body.kind,
        base_model=body.base_model,
        run=body.run,
        files=[],
        pushed_by=agent_id,
    )
    session.add(ckpt)
    await session.commit()
    return ckpt


@router.put("/{name}/files", response_model=CheckpointRead)
async def upload_checkpoint_file(
    name: CheckpointName,
    file: UploadFile,
    session: AsyncSession = Depends(get_session),
    agent_id: str = Depends(verify_agent_token),
    storage: Storage = Depends(get_storage),
    settings: Settings = Depends(get_settings),
) -> Checkpoint:
    ckpt = await session.get(Checkpoint, name)
    if ckpt is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Register the checkpoint first")
    if ckpt.pushed_by != agent_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Checkpoint belongs to another agent")
    filename = safe_filename(file.filename)
    if not _ALLOWED.search(filename):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "File type not allowed")

    size = 0
    with tempfile.SpooledTemporaryFile(max_size=8 * CHUNK) as spool:
        while True:
            chunk = await file.read(CHUNK)
            if not chunk:
                break
            size += len(chunk)
            if size > settings.max_checkpoint_bytes:
                raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, "File is too large")
            spool.write(chunk)
        if size == 0:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Empty file")
        spool.seek(0)
        await storage.put(f"checkpoints/{name}/{filename}", spool, "application/octet-stream")

    files = [f for f in ckpt.files if f != filename] + [filename]
    ckpt.files = sorted(files)
    ckpt.updated_at = utcnow()
    session.add(ckpt)
    await session.commit()
    return ckpt


@router.get("", response_model=list[CheckpointRead])
async def list_checkpoints(
    kind: str | None = None,
    session: AsyncSession = Depends(get_session),
    _agent: str = Depends(verify_agent_token),
) -> list[Checkpoint]:
    stmt = select(Checkpoint)
    if kind:
        stmt = stmt.where(Checkpoint.kind == kind)
    stmt = stmt.order_by(Checkpoint.created_at.desc())  # type: ignore[attr-defined]
    return list((await session.exec(stmt)).all())


@router.get("/{name}", response_model=CheckpointRead)
async def read_checkpoint(
    name: CheckpointName,
    session: AsyncSession = Depends(get_session),
    _agent: str = Depends(verify_agent_token),
) -> Checkpoint:
    ckpt = await session.get(Checkpoint, name)
    if ckpt is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not found")
    return ckpt
