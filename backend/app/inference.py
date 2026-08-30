"""Render clients for the style stage (docs/01 section 5, docs/06 D2).

The VPS has no GPU. Rendering happens on the Legion through ComfyUI's HTTP API over the
tunnel, with a burst GPU endpoint speaking the same API as the fallback, and a null
renderer when neither is reachable so a job still returns a vector-only result.

The graph is the standard two-stage SDXL pipeline (docs/06 D8): base model composes,
refiner model spends the last fraction of steps on fine detail, exactly how Stability AI
designed SDXL 1.0 to be used. The refiner is optional - `sdxl_workflow` degrades to a
single-stage graph when no refiner checkpoint is configured, so this keeps working on a
Legion that hasn't downloaded it yet. An optional hires-fix pass (docs/06 D11) - upscale
the finished latent, then a short low-denoise re-sample - adds further detail on top of
either path; off by default (hires_scale=1.0) until verified not to strain the 8GB card.
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

# Broader than "text, watermark" alone: the standard SDXL community negative prompt,
# free quality win, no extra model or data needed.
DEFAULT_NEGATIVE = (
    "text, letters, words, typography, signage, logo, watermark, signature, lowres, "
    "low quality, jpeg artifacts, blurry, out of "
    "focus, worst quality, extra limbs, deformed, disfigured, bad anatomy, cropped, "
    "duplicate, ugly, oversaturated, illustration, cartoon, anime, painting, drawing, "
    "3d render, cgi, vector art"
)


class Renderer(Protocol):
    name: str

    def render(
        self,
        prompt: str,
        width: int,
        height: int,
        lora: str | None,
        scene_text: str | None = None,
    ) -> bytes | None: ...


class NullRenderer:
    name = "none"

    def render(
        self,
        prompt: str,
        width: int,
        height: int,
        lora: str | None,
        scene_text: str | None = None,
    ) -> bytes | None:
        return None


def flux_workflow(
    prompt: str,
    width: int,
    height: int,
    seed: int,
    steps: int,
    unet: str,
    t5: str,
    clip_l: str,
    vae: str,
) -> dict[str, Any]:
    """FLUX.1-schnell through the ComfyUI-GGUF loaders: 4 steps, cfg 1, no negative
    prompt (schnell is distilled and ignores guidance). Used for the one case SDXL
    cannot do - legible words inside the photograph."""
    return {
        "1": {"class_type": "UnetLoaderGGUF", "inputs": {"unet_name": unet}},
        "2": {
            "class_type": "DualCLIPLoaderGGUF",
            "inputs": {"clip_name1": t5, "clip_name2": clip_l, "type": "flux"},
        },
        "3": {"class_type": "VAELoader", "inputs": {"vae_name": vae}},
        "4": {"class_type": "CLIPTextEncode", "inputs": {"text": prompt, "clip": ["2", 0]}},
        "5": {"class_type": "CLIPTextEncode", "inputs": {"text": "", "clip": ["2", 0]}},
        "6": {
            "class_type": "EmptySD3LatentImage",
            "inputs": {"width": width, "height": height, "batch_size": 1},
        },
        "7": {
            "class_type": "KSampler",
            "inputs": {
                "seed": seed,
                "steps": steps,
                "cfg": 1.0,
                "sampler_name": "euler",
                "scheduler": "simple",
                "denoise": 1.0,
                "model": ["1", 0],
                "positive": ["4", 0],
                "negative": ["5", 0],
                "latent_image": ["6", 0],
            },
        },
        "8": {"class_type": "VAEDecode", "inputs": {"samples": ["7", 0], "vae": ["3", 0]}},
        "9": {
            "class_type": "SaveImage",
            "inputs": {"filename_prefix": "ghost-flux", "images": ["8", 0]},
        },
    }


def face_detail_nodes(
    graph: dict[str, Any],
    *,
    seed: int,
    denoise: float,
    model: list[Any],
    clip: list[Any],
    positive: list[Any],
    negative: list[Any],
) -> None:
    """Appends a face-detail pass to a finished SDXL graph (docs/06 D18): detect faces
    with face_yolov8m, re-render each region at guide_size resolution, paste back.
    Rewires SaveImage to the detailed image. Field set mirrors the live FaceDetailer
    schema fetched from /object_info, not documentation."""
    graph["40"] = {
        "class_type": "UltralyticsDetectorProvider",
        "inputs": {"model_name": "bbox/face_yolov8m.pt"},
    }
    graph["41"] = {
        "class_type": "FaceDetailer",
        "inputs": {
            "image": graph["9"]["inputs"]["images"],
            "model": model,
            "clip": clip,
            "vae": graph["8"]["inputs"]["vae"],
            "guide_size": 512,
            "guide_size_for": True,
            "max_size": 1024,
            "seed": seed,
            "steps": 14,
            "cfg": 6.5,
            "sampler_name": "dpmpp_2m",
            "scheduler": "karras",
            "positive": positive,
            "negative": negative,
            "denoise": denoise,
            "feather": 5,
            "noise_mask": True,
            "force_inpaint": True,
            "bbox_threshold": 0.5,
            "bbox_dilation": 10,
            "bbox_crop_factor": 3.0,
            "sam_detection_hint": "center-1",
            "sam_dilation": 0,
            "sam_threshold": 0.93,
            "sam_bbox_expansion": 0,
            "sam_mask_hint_threshold": 0.7,
            "sam_mask_hint_use_negative": "False",
            "drop_size": 10,
            "bbox_detector": ["40", 0],
            "wildcard": "",
            "cycle": 1,
        },
    }
    graph["9"]["inputs"]["images"] = ["41", 0]


def scene_text_prompt(prompt: str, scene_text: str) -> str:
    """Flux reads quoted text literally; everything else about the sign is left to the
    scene description so it looks like it belongs there."""
    return f'{prompt}, with a sign that reads "{scene_text.strip()}" in clear bold lettering'


def sdxl_workflow(
    prompt: str,
    width: int,
    height: int,
    lora: str | None,
    seed: int,
    steps: int,
    base_checkpoint: str,
    refiner_checkpoint: str | None = None,
    refiner_switch: float = 0.8,
    negative: str = DEFAULT_NEGATIVE,
    cfg: float = 6.5,
    hires_scale: float = 1.0,
    hires_denoise: float = 0.4,
    hires_steps: int = 12,
    face_detail: bool = False,
    face_detail_denoise: float = 0.45,
) -> dict[str, Any]:
    """Base-only graph when refiner_checkpoint is empty; base+refiner two-stage graph
    otherwise. refiner_switch is the fraction of steps the base model runs before
    handing the latent to the refiner for the remaining, detail-focused steps.
    hires_scale > 1.0 adds a further upscale + short low-denoise re-sample pass on top
    of whichever path produced the final latent, using that same stage's model/prompts."""
    model_ref: list[Any] = ["4", 0]
    clip_ref: list[Any] = ["4", 1]
    graph: dict[str, Any] = {
        "4": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": base_checkpoint}},
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

    graph["6"] = {"class_type": "CLIPTextEncode", "inputs": {"text": prompt, "clip": clip_ref}}
    graph["7"] = {"class_type": "CLIPTextEncode", "inputs": {"text": negative, "clip": clip_ref}}

    if not refiner_checkpoint:
        graph["3"] = {
            "class_type": "KSampler",
            "inputs": {
                "seed": seed,
                "steps": steps,
                "cfg": cfg,
                "sampler_name": "dpmpp_2m",
                "scheduler": "karras",
                "denoise": 1.0,
                "model": model_ref,
                "positive": ["6", 0],
                "negative": ["7", 0],
                "latent_image": ["5", 0],
            },
        }
        final_latent: list[Any] = ["3", 0]
        final_model, final_positive, final_negative = model_ref, ["6", 0], ["7", 0]
        final_vae: list[Any] = ["4", 2]
    else:
        switch_step = max(1, min(steps - 1, round(steps * refiner_switch)))
        graph["20"] = {
            "class_type": "CheckpointLoaderSimple",
            "inputs": {"ckpt_name": refiner_checkpoint},
        }
        graph["21"] = {
            "class_type": "CLIPTextEncode",
            "inputs": {"text": prompt, "clip": ["20", 1]},
        }
        graph["22"] = {
            "class_type": "CLIPTextEncode",
            "inputs": {"text": negative, "clip": ["20", 1]},
        }
        # Base composes steps [0, switch_step), leaves noise for the refiner to continue from.
        graph["3"] = {
            "class_type": "KSamplerAdvanced",
            "inputs": {
                "add_noise": "enable",
                "noise_seed": seed,
                "steps": steps,
                "cfg": cfg,
                "sampler_name": "dpmpp_2m",
                "scheduler": "karras",
                "start_at_step": 0,
                "end_at_step": switch_step,
                "return_with_leftover_noise": "enable",
                "model": model_ref,
                "positive": ["6", 0],
                "negative": ["7", 0],
                "latent_image": ["5", 0],
            },
        }
        # Refiner finishes steps [switch_step, steps) - the fine-detail pass.
        graph["23"] = {
            "class_type": "KSamplerAdvanced",
            "inputs": {
                "add_noise": "disable",
                "noise_seed": seed,
                "steps": steps,
                "cfg": cfg,
                "sampler_name": "dpmpp_2m",
                "scheduler": "karras",
                "start_at_step": switch_step,
                "end_at_step": 10000,
                "return_with_leftover_noise": "disable",
                "model": ["20", 0],
                "positive": ["21", 0],
                "negative": ["22", 0],
                "latent_image": ["3", 0],
            },
        }
        final_latent = ["23", 0]
        final_model, final_positive, final_negative = ["20", 0], ["21", 0], ["22", 0]
        final_vae = ["20", 2]

    if hires_scale > 1.0:
        graph["30"] = {
            "class_type": "LatentUpscaleBy",
            "inputs": {
                "samples": final_latent,
                "upscale_method": "bislerp",
                "scale_by": hires_scale,
            },
        }
        graph["31"] = {
            "class_type": "KSampler",
            "inputs": {
                "seed": seed,
                "steps": hires_steps,
                "cfg": cfg,
                "sampler_name": "dpmpp_2m",
                "scheduler": "karras",
                "denoise": hires_denoise,
                "model": final_model,
                "positive": final_positive,
                "negative": final_negative,
                "latent_image": ["30", 0],
            },
        }
        final_latent = ["31", 0]

    graph["8"] = {"class_type": "VAEDecode", "inputs": {"samples": final_latent, "vae": final_vae}}
    graph["9"] = {
        "class_type": "SaveImage",
        "inputs": {"filename_prefix": "ghost", "images": ["8", 0]},
    }
    if face_detail:
        final_clip = ["20", 1] if refiner_checkpoint else clip_ref
        face_detail_nodes(
            graph,
            seed=seed,
            denoise=face_detail_denoise,
            model=final_model,
            clip=final_clip,
            positive=final_positive,
            negative=final_negative,
        )
    return graph


class ComfyRenderer:
    """Talks to a ComfyUI instance. Same code serves the Legion and a burst GPU box."""

    def __init__(
        self,
        base_url: str,
        name: str,
        timeout: float,
        steps: int = 30,
        base_checkpoint: str = "sd_xl_base_1.0.safetensors",
        refiner_checkpoint: str = "",
        refiner_switch: float = 0.8,
        hires_scale: float = 1.0,
        hires_denoise: float = 0.4,
        hires_steps: int = 12,
        flux: dict[str, Any] | None = None,
        face_detail: bool = False,
        face_detail_denoise: float = 0.45,
    ) -> None:
        self.face_detail = face_detail
        self.face_detail_denoise = face_detail_denoise
        self.flux = flux  # {"unet", "t5", "clip_l", "vae", "steps"} or None when not installed
        self.base_url = base_url.rstrip("/")
        self.name = name
        self.timeout = timeout
        self.steps = steps
        self.base_checkpoint = base_checkpoint
        self.refiner_checkpoint = refiner_checkpoint or None
        self.refiner_switch = refiner_switch
        self.hires_scale = hires_scale
        self.hires_denoise = hires_denoise
        self.hires_steps = hires_steps

    def reachable(self) -> bool:
        try:
            r = httpx.get(f"{self.base_url}/system_stats", timeout=5.0)
            return r.status_code == 200
        except httpx.HTTPError:
            return False

    def render(
        self,
        prompt: str,
        width: int,
        height: int,
        lora: str | None,
        scene_text: str | None = None,
    ) -> bytes | None:
        """Never raises: any failure (unreachable, bad graph, timeout) degrades to None so
        the caller falls back to a flat colour block instead of failing the whole job.
        scene_text switches the one layer that needs legible in-photo words to Flux;
        without Flux installed it renders with SDXL and the words are simply absent."""
        try:
            return self._render(prompt, width, height, lora, scene_text)
        except (httpx.HTTPError, KeyError, ValueError) as exc:
            log.error("comfy render failed on %s: %s", self.name, exc)
            return None

    def _render(
        self, prompt: str, width: int, height: int, lora: str | None, scene_text: str | None
    ) -> bytes | None:
        client_id = uuid.uuid4().hex
        if scene_text and self.flux:
            graph = flux_workflow(
                scene_text_prompt(prompt, scene_text),
                width,
                height,
                seed=int(time.time()),
                steps=int(self.flux.get("steps", 4)),
                unet=self.flux["unet"],
                t5=self.flux["t5"],
                clip_l=self.flux["clip_l"],
                vae=self.flux["vae"],
            )
        else:
            graph = sdxl_workflow(
                prompt,
                width,
                height,
                lora,
                seed=int(time.time()),
                steps=self.steps,
                base_checkpoint=self.base_checkpoint,
                refiner_checkpoint=self.refiner_checkpoint,
                refiner_switch=self.refiner_switch,
                hires_scale=self.hires_scale,
                hires_denoise=self.hires_denoise,
                hires_steps=self.hires_steps,
                face_detail=self.face_detail,
                face_detail_denoise=self.face_detail_denoise,
            )
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
        renderer = ComfyRenderer(
            url,
            name,
            settings.inference_timeout_s,
            steps=settings.sdxl_steps,
            base_checkpoint=settings.sdxl_base_checkpoint,
            refiner_checkpoint=settings.sdxl_refiner_checkpoint,
            refiner_switch=settings.sdxl_refiner_switch,
            hires_scale=settings.sdxl_hires_scale,
            hires_denoise=settings.sdxl_hires_denoise,
            hires_steps=settings.sdxl_hires_steps,
            face_detail=settings.face_detail,
            face_detail_denoise=settings.face_detail_denoise,
            flux=(
                {
                    "unet": settings.flux_unet,
                    "t5": settings.flux_t5,
                    "clip_l": settings.flux_clip_l,
                    "vae": settings.flux_vae,
                    "steps": settings.flux_steps,
                }
                if settings.flux_unet
                else None
            ),
        )
        if renderer.reachable():
            return renderer
        log.warning("renderer %s at %s is not reachable", name, url)
    return NullRenderer()
