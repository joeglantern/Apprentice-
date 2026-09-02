"""Database tables. Request and response bodies live in schemas.py, not here."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import Column
from sqlalchemy.types import JSON
from sqlmodel import Field, SQLModel


def utcnow() -> datetime:
    """Naive UTC, matching the timezone-less DateTime columns."""
    return datetime.now(UTC).replace(tzinfo=None)


class Asset(SQLModel, table=True):
    __tablename__ = "assets"

    asset_id: str = Field(primary_key=True, max_length=36)
    source_project: str = Field(index=True, max_length=200)
    captured_at: datetime = Field(index=True)
    agent_id: str = Field(index=True, max_length=100)
    agent_version: str = Field(max_length=20)

    # The full doc 01 section 3 record as sent by the collector.
    payload: dict[str, Any] = Field(sa_column=Column(JSON, nullable=False))

    # Object storage key of the uploaded export, set by PUT /ingest/asset/{id}/file.
    file_key: str | None = Field(default=None, max_length=500)
    file_size: int | None = None
    file_uploaded_at: datetime | None = None

    # Tagging state only: received -> tagged. File presence is file_key, kept separate so
    # the upload route and the worker never overwrite each other.
    status: str = Field(default="received", index=True, max_length=20)
    tags: dict[str, Any] | None = Field(default=None, sa_column=Column(JSON, nullable=True))

    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


# A job stops moving in exactly these states. Spelled once because "done or error"
# was written out at eight call sites, and adding a third was going to miss one.
JOB_TERMINAL = ("done", "error", "cancelled")


class Job(SQLModel, table=True):
    """One generation request from the app; result holds the layers the canvas renders."""

    __tablename__ = "jobs"

    job_id: str = Field(primary_key=True, max_length=36)
    prompt: str
    aesthetic_version: str = Field(max_length=64)
    # poster: plan + layout + render. image: one photograph, no layout. logo: one
    # mark on a plain ground. See generation.run_generation.
    kind: str = Field(default="poster", max_length=16)
    width: int
    height: int
    requested_by: str = Field(max_length=100)
    # Optional brand kit (docs/06 D19): {name, palette, typeface}, validated by the
    # director's BrandKit model at plan time.
    brand: dict[str, Any] | None = Field(default=None, sa_column=Column(JSON, nullable=True))
    # Revision of an earlier job (docs/06 D20): {source_job_id, rerender_photo}. When
    # set, plan is pre-seeded from the source with overrides and the director is
    # skipped; without rerender_photo the source rendered photo is reused.
    revise: dict[str, Any] | None = Field(default=None, sa_column=Column(JSON, nullable=True))
    status: str = Field(default="queued", index=True, max_length=20)
    # A short name for the finished piece (app/titles.py), written once when the job
    # lands so a gallery reads as work rather than as a list of prompts. Null on jobs
    # made before titles existed, and on anything that never finished.
    title: str | None = Field(default=None, max_length=120)
    plan: dict[str, Any] | None = Field(default=None, sa_column=Column(JSON, nullable=True))
    result: dict[str, Any] | None = Field(default=None, sa_column=Column(JSON, nullable=True))
    error: str | None = None
    created_at: datetime = Field(default_factory=utcnow, index=True)
    updated_at: datetime = Field(default_factory=utcnow)


class Checkpoint(SQLModel, table=True):
    """One trained artefact; its files live under checkpoints/<name>/ in object storage."""

    __tablename__ = "checkpoints"

    name: str = Field(primary_key=True, max_length=64)
    kind: str = Field(index=True, max_length=20)  # style-lora | layout-vlm
    base_model: str = Field(max_length=200)
    files: list[str] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    run: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    pushed_by: str = Field(max_length=100)
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class ChatThread(SQLModel, table=True):
    """One conversation about one evolving piece.

    The thread owns the piece rather than the other way round: `active_job_id` moves
    forward every time a turn produces a render, and the jobs it has produced are the
    version chips in the UI. Kept server-side because the app used to hold the thread
    in component state, which meant a reload lost the conversation while the jobs it
    made survived - the two halves of the same history disagreeing.
    """

    __tablename__ = "chat_threads"

    thread_id: str = Field(primary_key=True, max_length=36)
    owner: str = Field(index=True, max_length=100)
    active_job_id: str | None = Field(default=None, max_length=36)
    created_at: datetime = Field(default_factory=utcnow, index=True)
    updated_at: datetime = Field(default_factory=utcnow)


class ChatMessage(SQLModel, table=True):
    """One turn. `action` and `job_id` are set on assistant turns that did work.

    `landed` is the second sentence, written when the job finished - the reply itself
    is composed before the render runs and is only ever allowed to state an intent, so
    this is the only field that speaks about a result.
    """

    __tablename__ = "chat_messages"

    message_id: str = Field(primary_key=True, max_length=36)
    thread_id: str = Field(index=True, max_length=36, foreign_key="chat_threads.thread_id")
    role: str = Field(max_length=16)  # user | assistant
    text: str
    action: str | None = Field(default=None, max_length=16)
    job_id: str | None = Field(default=None, max_length=36)
    landed: str | None = None
    created_at: datetime = Field(default_factory=utcnow, index=True)
