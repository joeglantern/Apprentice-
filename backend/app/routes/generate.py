"""Generation API used by the Expo app: start a job, poll it, fetch its rasters."""

from __future__ import annotations

import logging
import uuid
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Path, Response, status
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.auth import verify_agent_token
from app.db import get_session
from app.models import Checkpoint, Job
from app.queue import enqueue_generation
from app.schemas import UUID_PATTERN
from app.storage import Storage, get_storage

log = logging.getLogger(__name__)
router = APIRouter(tags=["generate"])

JobId = Annotated[str, Path(pattern=UUID_PATTERN)]
BASELINE = "baseline"


class GenerateRequest(BaseModel):
    prompt: str = Field(min_length=3, max_length=2000)
    aesthetic_version: str = Field(default=BASELINE, pattern=r"^[a-z0-9][a-z0-9._-]{0,63}$")
    width: int = Field(default=1600, ge=256, le=4096)
    height: int = Field(default=900, ge=256, le=4096)


class GenerateAccepted(BaseModel):
    job_id: str
    status: str


class JobRead(BaseModel):
    job_id: str
    status: Literal["queued", "planning", "layout", "render", "done", "error"]
    prompt: str
    aesthetic_version: str
    plan: dict[str, Any] | None
    result: dict[str, Any] | None
    error: str | None
    created_at: Any
    updated_at: Any


class JobSummary(BaseModel):
    """The list view's row shape - no plan/result, which can be large and are never
    read by the history list (only GET /generate/{id} on the one job someone opens)."""

    job_id: str
    status: Literal["queued", "planning", "layout", "render", "done", "error"]
    prompt: str
    aesthetic_version: str
    created_at: Any
    updated_at: Any


class Aesthetic(BaseModel):
    version: str
    label: str
    kind: str
    trained_on: int | None = None


@router.post("/generate", status_code=status.HTTP_202_ACCEPTED, response_model=GenerateAccepted)
async def start_generation(
    body: GenerateRequest,
    session: AsyncSession = Depends(get_session),
    agent_id: str = Depends(verify_agent_token),
) -> GenerateAccepted:
    if body.aesthetic_version != BASELINE:
        ckpt = await session.get(Checkpoint, body.aesthetic_version)
        if ckpt is None or ckpt.kind != "style-lora":
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Unknown aesthetic version")
    job = Job(
        job_id=str(uuid.uuid4()),
        prompt=body.prompt.strip(),
        aesthetic_version=body.aesthetic_version,
        width=body.width,
        height=body.height,
        requested_by=agent_id,
    )
    session.add(job)
    await session.commit()
    try:
        await run_in_threadpool(enqueue_generation, job.job_id)
    except Exception:  # noqa: BLE001
        log.exception("could not enqueue generation %s", job.job_id)
        job.status = "error"
        job.error = "Could not queue the job; try again"
        session.add(job)
        await session.commit()
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, job.error) from None
    return GenerateAccepted(job_id=job.job_id, status="queued")


@router.get("/generate/{job_id}", response_model=JobRead)
async def read_job(
    job_id: JobId,
    session: AsyncSession = Depends(get_session),
    agent_id: str = Depends(verify_agent_token),
) -> Job:
    job = await session.get(Job, job_id.lower())
    if job is None or job.requested_by != agent_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not found")
    return job


@router.get("/generate", response_model=list[JobSummary])
async def list_jobs(
    limit: int = 50,
    session: AsyncSession = Depends(get_session),
    agent_id: str = Depends(verify_agent_token),
) -> list[JobSummary]:
    """The requesting agent's own generation history, newest first - what a
    collaborator sees when they come back to the app to look at past results.
    Selects only the summary columns, not plan/result, which can be large and are
    never read by this view (opening one job uses GET /generate/{id} instead)."""
    stmt = (
        select(
            Job.job_id,
            Job.status,
            Job.prompt,
            Job.aesthetic_version,
            Job.created_at,
            Job.updated_at,
        )
        .where(Job.requested_by == agent_id)
        .order_by(Job.created_at.desc())
        .limit(min(max(limit, 1), 200))
    )
    rows = (await session.exec(stmt)).all()
    return [JobSummary(**row._mapping) for row in rows]


@router.get("/generate/{job_id}/raster/{layer_id}")
async def read_raster(
    job_id: JobId,
    layer_id: str,
    session: AsyncSession = Depends(get_session),
    agent_id: str = Depends(verify_agent_token),
    storage: Storage = Depends(get_storage),
) -> Response:
    job = await session.get(Job, job_id.lower())
    if job is None or job.requested_by != agent_id or not job.result:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not found")
    key = next(
        (
            layer.get("raster_key")
            for layer in job.result.get("layers", [])
            if layer.get("layer_id") == layer_id and layer.get("raster_key")
        ),
        None,
    )
    if key is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No raster for this layer")
    try:
        data = await storage.get(key)
    except Exception as exc:  # noqa: BLE001 - backend-specific "not found" exceptions vary
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Raster no longer available") from exc
    return Response(content=data, media_type="image/png")


@router.get("/aesthetics", response_model=list[Aesthetic])
async def list_aesthetics(
    session: AsyncSession = Depends(get_session),
    _agent: str = Depends(verify_agent_token),
) -> list[Aesthetic]:
    stmt = select(Checkpoint).where(Checkpoint.kind == "style-lora")
    stmt = stmt.order_by(Checkpoint.created_at.desc())  # type: ignore[attr-defined]
    rows = (await session.exec(stmt)).all()
    out = [
        Aesthetic(
            version=c.name,
            label=c.name.replace("-", " ").title(),
            kind="style-lora",
            trained_on=c.run.get("style_images"),
        )
        for c in rows
    ]
    out.append(Aesthetic(version=BASELINE, label="Baseline (no trained style)", kind="baseline"))
    return out
