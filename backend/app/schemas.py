"""Pydantic v2 request and response bodies. Mirrors docs/01 section 3."""

from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

UUID_PATTERN = r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
_HEX_COLOUR = re.compile(r"#[0-9A-Fa-f]{6}")
_UUID = re.compile(UUID_PATTERN)


def is_uuid(value: str) -> bool:
    return bool(_UUID.fullmatch(value))


def to_naive_utc(value: datetime) -> datetime:
    """Database columns are timestamp without time zone; store everything as naive UTC."""
    if value.tzinfo is not None:
        value = value.astimezone(UTC).replace(tzinfo=None)
    return value


class ConsentBlock(BaseModel):
    project_opted_in: bool
    captured_by_agent_version: str = Field(min_length=1, max_length=20)


class CanvasSpec(BaseModel):
    width: int = Field(ge=0)
    height: int = Field(ge=0)
    dpi: int = Field(default=72, ge=1)


class FileSpec(BaseModel):
    original_name: str = Field(min_length=1, max_length=255)
    format: str = Field(min_length=1, max_length=10)
    canvas: CanvasSpec


class BBox(BaseModel):
    x: int
    y: int
    width: int = Field(ge=0)
    height: int = Field(ge=0)


class LayerSpec(BaseModel):
    # Extra keys (typography, color, text, visible, raster_url) are kept as sent so the
    # schema can grow on the collector side without a backend deploy.
    model_config = ConfigDict(extra="allow")

    layer_id: str = Field(min_length=1, max_length=20)
    name: str = Field(max_length=500)
    type: Literal["text", "shape", "image"]
    z_index: int = Field(ge=0)
    bbox: BBox


class AssetPayload(BaseModel):
    asset_id: str = Field(pattern=UUID_PATTERN)
    source_project: str = Field(min_length=1, max_length=200)
    captured_at: datetime
    file: FileSpec
    layers: list[LayerSpec] = Field(default_factory=list)
    palette: list[str] = Field(default_factory=list, max_length=32)
    consent: ConsentBlock | None = None

    @field_validator("asset_id")
    @classmethod
    def _lower_uuid(cls, value: str) -> str:
        return value.lower()

    @field_validator("captured_at")
    @classmethod
    def _naive_utc(cls, value: datetime) -> datetime:
        return to_naive_utc(value)

    @field_validator("palette")
    @classmethod
    def _hex_colours(cls, value: list[str]) -> list[str]:
        for item in value:
            if not _HEX_COLOUR.fullmatch(item):
                raise ValueError(f"palette entry is not #RRGGBB: {item!r}")
        return [v.upper() for v in value]

    @field_validator("source_project")
    @classmethod
    def _plain_project_name(cls, value: str) -> str:
        if "/" in value or "\\" in value or value.strip() != value:
            raise ValueError("source_project must be a plain name")
        return value


class IngestResponse(BaseModel):
    status: Literal["queued", "stored"]
    asset_id: str
    file_key: str | None = None


class AssetRead(BaseModel):
    asset_id: str
    source_project: str
    captured_at: datetime
    agent_id: str
    status: str
    file_key: str | None
    payload: dict[str, Any]
    tags: dict[str, Any] | None
