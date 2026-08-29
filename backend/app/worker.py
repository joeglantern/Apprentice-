"""Celery app and background tasks. Tasks take IDs only and reload rows themselves."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from celery import Celery
from sqlalchemy import create_engine
from sqlmodel import Session, select

from app.config import get_settings
from app.models import Asset, Checkpoint, Job, utcnow

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
    beat_schedule={
        "retag-received-assets": {
            "task": "app.worker.retag_received",
            "schedule": 300.0,
        }
    },
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


@celery_app.task(name="app.worker.generate_design", bind=True, max_retries=0)
def generate_design(self: Any, job_id: str) -> str:
    from app.generation import SyncStorage, run_generation
    from app.inference import pick_renderer
    from app.profile import build_profile
    from app.realtime import worker_emitter
    from app.storage import get_storage

    emitter = worker_emitter()

    def progress(stage: str, data: dict[str, Any]) -> None:
        with sync_session() as s:
            row = s.get(Job, job_id)
            if row is not None and row.status not in ("done", "error"):
                row.status = stage
                row.updated_at = utcnow()
                s.add(row)
                s.commit()
        try:
            emitter.emit("progress", {"job_id": job_id, "stage": stage, **data}, room=job_id)
        except Exception:  # noqa: BLE001
            pass

    with sync_session() as session:
        job = session.get(Job, job_id)
        if job is None:
            return "missing"
        if job.status in ("done", "error"):
            # Celery redelivery (task_acks_late) after a worker crash mid-job must not
            # re-run a finished job: a second paid director call, a second render, and
            # overwritten results the app may already be showing.
            return job.status
        lora_file = None
        if job.aesthetic_version != "baseline":
            ckpt = session.get(Checkpoint, job.aesthetic_version)
            if ckpt is not None:
                lora_file = next((f for f in ckpt.files if f.endswith(".safetensors")), None)
        assets = session.exec(select(Asset).where(Asset.status == "tagged").limit(500)).all()
        payloads = [
            a.payload for a in assets if (a.payload.get("consent") or {}).get("project_opted_in")
        ]
        profile = build_profile(payloads) if payloads else None
        prompt, width, height, aesthetic = job.prompt, job.width, job.height, job.aesthetic_version

    try:
        plan, result = run_generation(
            job_id=job_id,
            prompt=prompt,
            width=width,
            height=height,
            aesthetic_version=aesthetic,
            lora_file=lora_file,
            profile=profile,
            settings=settings,
            renderer=pick_renderer(settings),
            storage=SyncStorage(get_storage()),
            progress=progress,
        )
    except Exception as exc:  # noqa: BLE001
        with sync_session() as session:
            job = session.get(Job, job_id)
            if job is not None:
                job.status = "error"
                job.error = str(exc)[:500]
                job.updated_at = utcnow()
                session.add(job)
                session.commit()
        try:
            emitter.emit(
                "progress",
                {"job_id": job_id, "stage": "error", "message": str(exc)[:200]},
                room=job_id,
            )
        except Exception:  # noqa: BLE001
            pass
        return "error"

    with sync_session() as session:
        job = session.get(Job, job_id)
        if job is not None:
            job.plan = plan.model_dump()
            job.result = result
            job.status = "done"
            job.updated_at = utcnow()
            session.add(job)
            session.commit()
    try:
        emitter.emit("progress", {"job_id": job_id, "stage": "done"}, room=job_id)
    except Exception:  # noqa: BLE001
        pass
    return "done"


@celery_app.task(name="app.worker.retag_received")
def retag_received() -> int:
    """Sweep for assets whose tagging publish was lost (broker outage) and re-enqueue."""
    cutoff = utcnow() - timedelta(minutes=2)
    with sync_session() as session:
        stmt = select(Asset.asset_id).where(Asset.status == "received", Asset.updated_at < cutoff)
        ids = list(session.exec(stmt).all())
    for asset_id in ids:
        tag_asset.delay(asset_id)
    return len(ids)
