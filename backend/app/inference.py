"""Render clients for the style stage (docs/01 section 5, docs/06 D2).

The VPS has no GPU. Rendering happens on the Legion through ComfyUI's HTTP API over the
tunnel, with a burst GPU endpoint speaking the same API as the fallback, and a null
renderer when neither is reachable so a job still returns a vector-only result.
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from typing import Any, Protocol

import httpx

from app.config import Settings

log = logging.getLogger(__name__)


class Renderer(Protocol):
    name: str

    def render(self, prompt: str, width: int, height: int, lora: str | None) -> bytes | None: ...


class NullRenderer:
    name = "none"

    def render(self, prompt: str, width: int, height: int, lora: str | None) -> bytes | None:
        return None


def sdxl_workflow(
    prompt: str, width: int, height: int, lora: str | None, seed: int, steps: int
) -> dict[str, Any]:
    """Minimal ComfyUI graph: SDXL base, optional LoRA, one image out."""
    model_ref: list[Any] = ["4", 0]
    clip_ref: list[Any] = ["4", 1]
    graph: dict[str, Any] = {
        "4": {
            "class_type": "CheckpointLoaderSimple",
            "inputs": {"ckpt_name": "sd_xl_base_1.0.safetensors"},
        },
        "5": {
            "class_type": "EmptyLatentImage",
            "inputs": {"width": width, "height": height, "batch_size": 1},
        },
    }
    if lora:
        graph["10"] = {
            "class_type": "LoraLoader",
            "inputs": {
                "lora_name": lora,
                "strength_model": 0.8,
                "strength_clip": 0.8,
                "model": model_ref,
                "clip": clip_ref,
            },
        }
        model_ref, clip_ref = ["10", 0], ["10", 1]
        prompt = f"ghoststyle, {prompt}"
    graph.update(
        {
            "6": {
                "class_type": "CLIPTextEncode",
                "inputs": {"text": prompt, "clip": clip_ref},
            },
            "7": {
                "class_type": "CLIPTextEncode",
                "inputs": {"text": "text, watermark, lowres, blurry", "clip": clip_ref},
            },
            "3": {
                "class_type": "KSampler",
                "inputs": {
                    "seed": seed,
                    "steps": steps,
                    "cfg": 6.0,
                    "sampler_name": "dpmpp_2m",
                    "scheduler": "karras",
                    "denoise": 1.0,
                    "model": model_ref,
                    "positive": ["6", 0],
                    "negative": ["7", 0],
                    "latent_image": ["5", 0],
                },
            },
            "8": {
                "class_type": "VAEDecode",
                "inputs": {"samples": ["3", 0], "vae": ["4", 2]},
            },
            "9": {
                "class_type": "SaveImage",
                "inputs": {"filename_prefix": "ghost", "images": ["8", 0]},
            },
        }
    )
    return graph


class ComfyRenderer:
    """Talks to a ComfyUI instance. Same code serves the Legion and a burst GPU box."""

    def __init__(self, base_url: str, name: str, timeout: float, steps: int = 28) -> None:
        self.base_url = base_url.rstrip("/")
        self.name = name
        self.timeout = timeout
        self.steps = steps

    def reachable(self) -> bool:
        try:
            r = httpx.get(f"{self.base_url}/system_stats", timeout=5.0)
            return r.status_code == 200
        except httpx.HTTPError:
            return False

    def render(self, prompt: str, width: int, height: int, lora: str | None) -> bytes | None:
        client_id = uuid.uuid4().hex
        graph = sdxl_workflow(prompt, width, height, lora, seed=int(time.time()), steps=self.steps)
        with httpx.Client(base_url=self.base_url, timeout=30.0) as client:
            r = client.post("/prompt", json={"prompt": graph, "client_id": client_id})
            r.raise_for_status()
            prompt_id = r.json()["prompt_id"]
            deadline = time.time() + self.timeout
            while time.time() < deadline:
                h = client.get(f"/history/{prompt_id}")
                h.raise_for_status()
                entry = h.json().get(prompt_id)
                if entry and entry.get("outputs"):
                    for node in entry["outputs"].values():
                        for image in node.get("images", []):
                            img = client.get(
                                "/view",
                                params={
                                    "filename": image["filename"],
                                    "subfolder": image.get("subfolder", ""),
                                    "type": image.get("type", "output"),
                                },
                            )
                            img.raise_for_status()
                            return img.content
                    return None
                if entry and entry.get("status", {}).get("status_str") == "error":
                    log.error("comfy job failed: %s", json.dumps(entry.get("status"))[:500])
                    return None
                time.sleep(1.5)
        log.error("comfy job %s timed out after %ss", prompt_id, self.timeout)
        return None


def pick_renderer(settings: Settings) -> Renderer:
    """Legion first, burst GPU second, shapes only last (docs/01 section 5)."""
    candidates = [
        (settings.legion_inference_url, "legion"),
        (settings.burst_inference_url, "burst"),
    ]
    for url, name in candidates:
        if not url:
            continue
        renderer = ComfyRenderer(url, name, settings.inference_timeout_s)
        if renderer.reachable():
            return renderer
        log.warning("renderer %s at %s is not reachable", name, url)
    return NullRenderer()
