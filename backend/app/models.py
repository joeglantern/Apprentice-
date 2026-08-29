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
