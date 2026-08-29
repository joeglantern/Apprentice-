"""Pydantic v2 request and response bodies. Mirrors docs/01 section 3."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


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
    asset_id: str = Field(min_length=36, max_length=36)
    source_project: str = Field(min_length=1, max_length=200)
    captured_at: datetime
    file: FileSpec
    layers: list[LayerSpec] = Field(default_factory=list)
    palette: list[str] = Field(default_factory=list, max_length=32)
    consent: ConsentBlock | None = None

    @field_validator("palette")
    @classmethod
    def _hex_colours(cls, value: list[str]) -> list[str]:
        for item in value:
            if len(item) != 7 or item[0] != "#":
                raise ValueError(f"palette entry is not #RRGGBB: {item!r}")
            int(item[1:], 16)
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
