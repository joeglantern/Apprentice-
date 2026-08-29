"""The generation pipeline run by the Celery worker: plan, layout, render.

Kept free of Celery so tests can call `run_generation` directly with fakes.
"""

from __future__ import annotations

import asyncio
import io
import logging
from collections.abc import Callable
from typing import Any

from app.config import Settings
from app.director import DesignPlan, DirectorRefused, plan_design
from app.inference import Renderer
from app.layout import heuristic_layout

log = logging.getLogger(__name__)

Progress = Callable[[str, dict[str, Any]], None]


class SyncStorage:
    """Small sync wrapper so the worker can use the async storage client."""

    def __init__(self, storage: Any) -> None:
        self.storage = storage

    def put(self, key: str, data: bytes, content_type: str) -> None:
        asyncio.run(self.storage.put(key, io.BytesIO(data), content_type))


def run_generation(
    *,
    job_id: str,
    prompt: str,
    width: int,
    height: int,
    aesthetic_version: str,
    lora_file: str | None,
    profile: dict[str, Any] | None,
    settings: Settings,
    renderer: Renderer,
    storage: SyncStorage,
    progress: Progress,
) -> tuple[DesignPlan, dict[str, Any]]:
    progress("planning", {"message": "Thinking about the brief"})
    try:
        plan = asyncio.run(plan_design(prompt, width, height, profile, settings))
    except DirectorRefused as exc:
        raise RuntimeError(f"Declined: {exc}") from exc

    progress("layout", {"message": "Composing in the designer's habits"})
    layout = heuristic_layout(plan, profile)

    image_layers = [layer for layer in layout["layers"] if layer["type"] == "image"]
    progress(
        "render",
        {"message": f"Rendering {len(image_layers)} image area(s) with {renderer.name}"},
    )
    for i, layer in enumerate(image_layers, 1):
        bbox = layer["bbox"]
        w, h = _sdxl_size(bbox["width"], bbox["height"])
        data = renderer.render(layer.get("image_prompt", prompt), w, h, lora_file)
        if data:
            key = f"renders/{job_id}/{layer['layer_id']}.png"
            storage.put(key, data, "image/png")
            layer["raster_key"] = key
            layer["raster_url"] = f"/generate/{job_id}/raster/{layer['layer_id']}"
        else:
            layer["color"] = {"hex": (plan.palette_intent or ["#CCCCCC"])[-1], "opacity": 0.35}
        progress("render", {"message": f"Rendered {i}/{len(image_layers)}", "step": i})

    result = {
        "canvas_width": width,
        "canvas_height": height,
        "aesthetic_version": aesthetic_version,
        "renderer": renderer.name,
        "layers": layout["layers"],
    }
    return plan, result


def _sdxl_size(width: int, height: int, max_side: int = 1024) -> tuple[int, int]:
    """Scale to at most max_side and round to multiples of 64, as SDXL expects."""
    scale = min(1.0, max_side / max(width, height))
    w = max(256, int(width * scale) // 64 * 64)
    h = max(256, int(height * scale) // 64 * 64)
    return w, h
