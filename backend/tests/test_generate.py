from __future__ import annotations

import io
from typing import Any

import pytest
from httpx import AsyncClient

from app.config import Settings
from app.director import DesignPlan, PlanElement, heuristic_plan
from app.generation import SyncStorage, run_generation
from app.inference import NullRenderer, sdxl_workflow
from app.layout import heuristic_layout
from app.profile import build_profile
from tests.conftest import AUTH_A, AUTH_B, FakeStorage, make_payload

PROFILE = build_profile([make_payload(), make_payload()])


def test_profile_from_payloads() -> None:
    assert PROFILE["sample_size"] == 2
    assert PROFILE["dominant_colours"][0]["value"] in {"#1A1A1A", "#F2A623"}
    assert PROFILE["text_alignment"][0]["value"] == "left"
    assert PROFILE["fonts"][0]["value"] == "Neue Haas Grotesk"
    assert PROFILE["type_size_ratio"]["headline_median"] == 0.04
    assert 0 < PROFILE["margin_ratio"] < 0.2


def test_heuristic_plan_and_layout_follow_profile() -> None:
    plan = heuristic_plan("Summer jazz festival poster, Friday night", 1600, 900, PROFILE)
    assert plan.source == "heuristic"
    assert plan.palette_intent[0] in {"#1A1A1A", "#F2A623"}
    layout = heuristic_layout(plan, PROFILE)
    kinds = [layer["type"] for layer in layout["layers"]]
    assert kinds[0] == "shape" and "image" in kinds and kinds.count("text") == 2
    ids = [layer["layer_id"] for layer in layout["layers"]]
    assert ids == sorted(ids) and [layer["z_index"] for layer in layout["layers"]] == list(
        range(len(ids))
    )
    headline = next(layer for layer in layout["layers"] if layer["name"] == "headline")
    assert headline["typography"]["font_size"] == 64  # 0.04 of 1600 from the profile
    assert headline["align"] == "left"
    assert headline["bbox"]["x"] == int(1600 * PROFILE["margin_ratio"])
    for layer in layout["layers"]:
        b = layer["bbox"]
        assert 0 <= b["x"] and b["x"] + b["width"] <= 1600
        assert 0 <= b["y"] and b["y"] + b["height"] <= 900


def test_layout_portrait_puts_image_on_top() -> None:
    plan = heuristic_plan("Album cover", 900, 1600, None)
    layout = heuristic_layout(plan, None)
    image = next(layer for layer in layout["layers"] if layer["type"] == "image")
    headline = next(layer for layer in layout["layers"] if layer["name"] == "headline")
    assert image["bbox"]["y"] < headline["bbox"]["y"]


def test_layout_text_stays_readable_on_a_low_contrast_palette() -> None:
    """Regression: a director-picked palette of two close warm tones (real case, e.g.
    #EB7F35 on #F2AC6F) must not produce near-invisible text."""
    from app.layout import _contrast_ratio

    plan = heuristic_plan("Concert poster", 1080, 1350, None)
    plan.palette_intent = ["#EB7F35", "#F2AC6F"]
    layout = heuristic_layout(plan, None)
    bg = next(layer for layer in layout["layers"] if layer["type"] == "shape")["color"]["hex"]
    for layer in layout["layers"]:
        if layer["type"] != "text":
            continue
        text_colour = layer["color"]["hex"]
        against = layer.get("background", {}).get("hex", bg)
        assert _contrast_ratio(text_colour, against) >= 4.5, layer["name"]


BASE_CKPT = "sd_xl_base_1.0.safetensors"


def test_sdxl_workflow_wires_lora() -> None:
    graph = sdxl_workflow(
        "a poster",
        1024,
        576,
        "style-lora-v1.safetensors",
        seed=1,
        steps=20,
        base_checkpoint=BASE_CKPT,
    )
    assert graph["10"]["inputs"]["lora_name"] == "style-lora-v1.safetensors"
    assert graph["3"]["inputs"]["model"] == ["10", 0]
    assert graph["6"]["inputs"]["text"].startswith("ghoststyle, ")
    plain = sdxl_workflow("a poster", 1024, 576, None, seed=1, steps=20, base_checkpoint=BASE_CKPT)
    assert "10" not in plain and plain["3"]["inputs"]["model"] == ["4", 0]
    assert plain["3"]["class_type"] == "KSampler"  # single-stage when no refiner configured
    assert "worst quality" in plain["7"]["inputs"]["text"]  # default negative prompt


def test_sdxl_workflow_two_stage_refiner() -> None:
    graph = sdxl_workflow(
        "a poster",
        1024,
        576,
        None,
        seed=1,
        steps=30,
        base_checkpoint=BASE_CKPT,
        refiner_checkpoint="sd_xl_refiner_1.0.safetensors",
        refiner_switch=0.8,
    )
    assert graph["4"]["inputs"]["ckpt_name"] == BASE_CKPT
    assert graph["20"]["inputs"]["ckpt_name"] == "sd_xl_refiner_1.0.safetensors"
    base_stage = graph["3"]
    assert base_stage["class_type"] == "KSamplerAdvanced"
    assert base_stage["inputs"]["start_at_step"] == 0
    assert base_stage["inputs"]["end_at_step"] == 24  # 30 * 0.8
    assert base_stage["inputs"]["return_with_leftover_noise"] == "enable"
    refiner_stage = graph["23"]
    assert refiner_stage["inputs"]["add_noise"] == "disable"
    assert refiner_stage["inputs"]["start_at_step"] == 24
    assert refiner_stage["inputs"]["model"] == ["20", 0]
    assert refiner_stage["inputs"]["latent_image"] == ["3", 0]
    assert graph["8"]["inputs"]["samples"] == ["23", 0]
    assert graph["8"]["inputs"]["vae"] == ["20", 2]


def test_sdxl_workflow_hires_fix_disabled_by_default() -> None:
    graph = sdxl_workflow("x", 512, 512, None, seed=1, steps=20, base_checkpoint=BASE_CKPT)
    assert "30" not in graph and "31" not in graph
    assert graph["8"]["inputs"]["samples"] == ["3", 0]


def test_sdxl_workflow_hires_fix_single_stage() -> None:
    graph = sdxl_workflow(
        "x",
        512,
        512,
        None,
        seed=1,
        steps=20,
        base_checkpoint=BASE_CKPT,
        hires_scale=1.5,
        hires_denoise=0.4,
        hires_steps=10,
    )
    assert graph["30"]["class_type"] == "LatentUpscaleBy"
    assert graph["30"]["inputs"]["samples"] == ["3", 0]
    assert graph["30"]["inputs"]["scale_by"] == 1.5
    assert graph["31"]["class_type"] == "KSampler"
    assert graph["31"]["inputs"]["denoise"] == 0.4
    assert graph["31"]["inputs"]["steps"] == 10
    assert graph["31"]["inputs"]["model"] == ["4", 0]  # base model, no refiner in this graph
    assert graph["31"]["inputs"]["latent_image"] == ["30", 0]
    assert graph["8"]["inputs"]["samples"] == ["31", 0]
    assert graph["8"]["inputs"]["vae"] == ["4", 2]


def test_sdxl_workflow_hires_fix_after_refiner_uses_refiner_model() -> None:
    graph = sdxl_workflow(
        "x",
        512,
        512,
        None,
        seed=1,
        steps=20,
        base_checkpoint=BASE_CKPT,
        refiner_checkpoint="r.safetensors",
        hires_scale=1.5,
    )
    assert graph["30"]["inputs"]["samples"] == ["23", 0]  # the refiner's output, not the base's
    assert graph["31"]["inputs"]["model"] == ["20", 0]  # refiner model, not base
    assert graph["31"]["inputs"]["positive"] == ["21", 0]
    assert graph["8"]["inputs"]["vae"] == ["20", 2]


def test_sdxl_workflow_refiner_switch_is_clamped() -> None:
    graph = sdxl_workflow(
        "x",
        512,
        512,
        None,
        seed=1,
        steps=5,
        base_checkpoint=BASE_CKPT,
        refiner_checkpoint="r.safetensors",
        refiner_switch=0.0,
    )
    assert graph["3"]["inputs"]["end_at_step"] == 1  # never 0, base always does at least one step


def test_comfy_render_degrades_to_none_on_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    """A ComfyUI/network failure must not raise out of render() - the caller falls back
    to a flat colour block rather than failing the whole job."""
    from app.inference import ComfyRenderer

    def boom(self: ComfyRenderer, *a: Any, **kw: Any) -> None:
        import httpx

        raise httpx.ConnectError("down")

    monkeypatch.setattr(ComfyRenderer, "_render", boom)
    renderer = ComfyRenderer("http://legion:8188", "legion", timeout=1.0)
    assert renderer.render("a poster", 512, 512, None) is None


class FakeRenderer:
    name = "fake"

    def __init__(self) -> None:
        self.calls: list[tuple[str, int, int, str | None]] = []

    def render(self, prompt: str, width: int, height: int, lora: str | None) -> bytes | None:
        self.calls.append((prompt, width, height, lora))
        return b"\x89PNG-fake"


def test_run_generation_with_fake_renderer(storage: FakeStorage) -> None:
    settings = Settings(database_url="sqlite://", anthropic_api_key="")
    renderer = FakeRenderer()
    stages: list[str] = []
    plan, result = run_generation(
        job_id="11111111-1111-4111-8111-111111111111",
        prompt="Launch poster for a new espresso bar",
        width=1600,
        height=900,
        aesthetic_version="style-lora-v1",
        lora_file="style-lora-v1.safetensors",
        profile=PROFILE,
        settings=settings,
        renderer=renderer,
        storage=SyncStorage(storage),
        progress=lambda stage, data: stages.append(stage),
    )
    assert plan.source == "heuristic"
    assert stages[:3] == ["planning", "layout", "render"]
    image = next(layer for layer in result["layers"] if layer["type"] == "image")
    assert image["raster_key"] in storage.objects
    assert image["raster_url"].endswith(f"/raster/{image['layer_id']}")
    prompt, w, h, lora = renderer.calls[0]
    assert "espresso" in prompt and lora == "style-lora-v1.safetensors"
    assert w % 64 == 0 and h % 64 == 0 and max(w, h) <= 1024


def test_run_generation_null_renderer_falls_back_to_colour(storage: FakeStorage) -> None:
    settings = Settings(database_url="sqlite://")
    plan, result = run_generation(
        job_id="22222222-2222-4222-8222-222222222222",
        prompt="Event flyer",
        width=1200,
        height=1200,
        aesthetic_version="baseline",
        lora_file=None,
        profile=None,
        settings=settings,
        renderer=NullRenderer(),
        storage=SyncStorage(storage),
        progress=lambda stage, data: None,
    )
    image = next(layer for layer in result["layers"] if layer["type"] == "image")
    assert "raster_key" not in image and image["color"]["opacity"] == 0.35
    assert storage.objects == {}


async def test_generate_routes(client: AsyncClient, monkeypatch: pytest.MonkeyPatch) -> None:
    import app.routes.generate as gen_mod

    queued: list[str] = []
    monkeypatch.setattr(gen_mod, "enqueue_generation", lambda job_id: queued.append(job_id))

    r = await client.get("/aesthetics", headers=AUTH_A)
    assert r.status_code == 200
    assert r.json()[-1]["version"] == "baseline"

    r = await client.post("/generate", json={"prompt": "Poster for a jazz night"}, headers=AUTH_A)
    assert r.status_code == 202, r.text
    job_id = r.json()["job_id"]
    assert queued == [job_id]

    r = await client.get(f"/generate/{job_id}", headers=AUTH_A)
    assert r.status_code == 200
    assert r.json()["status"] == "queued" and r.json()["result"] is None

    r = await client.post(
        "/generate", json={"prompt": "x", "aesthetic_version": "missing-v9"}, headers=AUTH_A
    )
    assert r.status_code == 422  # prompt too short
    r = await client.post(
        "/generate",
        json={"prompt": "long enough", "aesthetic_version": "missing-v9"},
        headers=AUTH_A,
    )
    assert r.status_code == 404
    r = await client.get(f"/generate/{job_id}/raster/L02", headers=AUTH_A)
    assert r.status_code == 404
    assert (await client.post("/generate", json={"prompt": "no auth here"})).status_code == 401

    # A different agent (e.g. holding the collector's token, not the app's) may not
    # read this job or its renders, even with a valid token of its own.
    r = await client.get(f"/generate/{job_id}", headers=AUTH_B)
    assert r.status_code == 404
    r = await client.get(f"/generate/{job_id}/raster/L01", headers=AUTH_B)
    assert r.status_code == 404


def test_design_plan_schema_roundtrip() -> None:
    plan = DesignPlan(
        rationale="r",
        canvas={"width": 10, "height": 10},
        mood=["a"],
        palette_intent=["#000000"],
        elements=[
            PlanElement(role="headline", content="Hi", priority=1),
            PlanElement(role="image", content="a picture", priority=2),
        ],
    )
    data: dict[str, Any] = plan.model_dump()
    assert DesignPlan.model_validate(data) == plan


def test_design_plan_requires_an_image_element() -> None:
    with pytest.raises(Exception, match="image"):
        DesignPlan(
            rationale="r",
            canvas={"width": 10, "height": 10},
            mood=["a"],
            palette_intent=["#000000"],
            elements=[PlanElement(role="headline", content="Hi", priority=1)],
        )
    assert isinstance(io.BytesIO(b""), io.BytesIO)


def test_design_plan_extracts_hex_and_drops_non_colours() -> None:
    """Regression: real local-model output mixed a colour-name-wrapped hex, a bare
    mood word, and a genuinely malformed value into palette_intent - all three were
    observed live. The plan (real headline, rationale, elements) must survive; only
    the unusable palette entries should be dropped, not the whole plan."""
    plan = DesignPlan(
        rationale="r",
        canvas={"width": 10, "height": 10},
        mood=["a"],
        palette_intent=["Dark Navy (#1C1C1C)", "Vibrant", "cool tones with blue and white"],
        elements=[PlanElement(role="image", content="a picture", priority=1)],
    )
    assert plan.palette_intent == ["#1C1C1C"]


def test_design_plan_empty_palette_is_fine() -> None:
    """If nothing in palette_intent contains a real hex code, the field ends up empty
    rather than failing the plan - layout.py's DEFAULT_PALETTE fallback handles it."""
    plan = DesignPlan(
        rationale="r",
        canvas={"width": 10, "height": 10},
        mood=["a"],
        palette_intent=["Vibrant", "Modern"],
        elements=[PlanElement(role="image", content="a picture", priority=1)],
    )
    assert plan.palette_intent == []


def test_layout_never_crashes_on_a_malformed_hex_defensively() -> None:
    """Belt-and-suspenders: even if a DesignPlan is ever built bypassing the schema
    validator, heuristic_layout must degrade gracefully, not raise."""
    from app.layout import _relative_luminance

    assert _relative_luminance("#zz1234") == 0.5
    assert _relative_luminance("#fff") == 0.5
