"""Captions for the style LoRA. Short, factual, always starting with the trigger token."""

from __future__ import annotations

from typing import Any

from ghost_training import TRIGGER_TOKEN


def orientation(width: int, height: int) -> str:
    if not width or not height:
        return "square"
    ratio = width / height
    return "landscape" if ratio > 1.1 else "portrait" if ratio < 0.9 else "square"


def caption(payload: dict[str, Any], tags: dict[str, Any] | None = None) -> str:
    canvas = payload["file"]["canvas"]
    parts = [TRIGGER_TOKEN, f"{orientation(canvas['width'], canvas['height'])} graphic design"]
    layers = payload.get("layers", [])
    kinds = {layer.get("type") for layer in layers}
    if "text" in kinds:
        parts.append("with typography")
    if "image" in kinds:
        parts.append("with photographic elements")
    palette = [c.upper() for c in payload.get("palette", [])[:4]]
    if palette:
        parts.append("palette " + " ".join(palette))
    fmt = payload["file"].get("format")
    if fmt in ("psd", "ai"):
        parts.append("layered composition")
    project = payload.get("source_project")
    if project:
        parts.append(f"project {project}")
    return ", ".join(parts)
