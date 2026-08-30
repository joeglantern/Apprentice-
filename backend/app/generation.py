"""The generation pipeline run by the Celery worker: plan, layout, render.

Kept free of Celery so tests can call `run_generation` directly with fakes.
"""

from __future__ import annotations

import asyncio
import io
import logging
import re
from collections.abc import Callable
from typing import Any

from app.config import Settings
from app.director import DesignPlan, DirectorRefused, PlanElement, plan_design
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
    kind: str = "poster",
) -> tuple[DesignPlan, dict[str, Any]]:
    if kind in ("image", "logo"):
        # No director, no layout: one full-canvas render. A logo names its brand in
        # quotes in the brief ('logo for "Umoja Threads"'); that becomes scene_text so
        # the Flux path (inference.py) sets the actual letters rather than SDXL's
        # gibberish. Without quotes, or without Flux, the mark is rendered wordless.
        plan, layout = direct_plan(prompt, width, height, kind)
        progress("layout", {"message": "Single image, no layout"})
    else:
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
        data = renderer.render(
            layer.get("image_prompt", prompt), w, h, lora_file, layer.get("scene_text")
        )
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


_QUOTED = re.compile(r"[\"“”']([^\"“”']{2,40})[\"“”']")

IMAGE_SUFFIX = (
    "photorealistic photograph, shot on a full frame camera, natural light, sharp focus, "
    "high detail, no text, no watermark"
)
LOGO_SUFFIX = (
    "minimal flat vector logo, clean geometric mark, two colours, centered on a plain "
    "white background, no photo, no gradients, no mockup"
)


def direct_plan(
    prompt: str, width: int, height: int, kind: str
) -> tuple[DesignPlan, dict[str, Any]]:
    """A one-layer plan and layout for kind=image or kind=logo."""
    brand = None
    if kind == "logo":
        m = _QUOTED.search(prompt)
        brand = m.group(1).strip() if m else None
    suffix = LOGO_SUFFIX if kind == "logo" else IMAGE_SUFFIX
    element = PlanElement(
        role="image",
        content="logo" if kind == "logo" else "photograph",
        priority=1,
        image_prompt=f"{prompt.strip().rstrip(',. ')}, {suffix}",
        scene_text=brand,
    )
    plan = DesignPlan(
        rationale=(
            "Direct render, no layout stage: "
            + ("a single logo mark" if kind == "logo" else "a single photograph")
            + " from the brief as written."
        ),
        canvas={"width": width, "height": height},
        mood=["direct"],
        palette_intent=[],
        elements=[element],
        source="heuristic",
    )
    layer: dict[str, Any] = {
        "layer_id": "L01",
        "name": element.content,
        "type": "image",
        "z_index": 0,
        "bbox": {"x": 0, "y": 0, "width": width, "height": height},
        "image_prompt": element.image_prompt,
    }
    if brand:
        layer["scene_text"] = brand
    return plan, {"canvas": {"width": width, "height": height}, "layers": [layer]}


def _sdxl_size(width: int, height: int, max_side: int = 1024) -> tuple[int, int]:
    """Scale to at most max_side and round to multiples of 64, as SDXL expects."""
    scale = min(1.0, max_side / max(width, height))
    w = max(256, int(width * scale) // 64 * 64)
    h = max(256, int(height * scale) // 64 * 64)
    return w, h
