from __future__ import annotations

import io
from datetime import datetime, timedelta
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

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
    layers = layout["layers"]
    kinds = [layer["type"] for layer in layers]
    # Poster recipe: full-bleed image first, scrim over the text zone, then type.
    assert kinds[0] == "image" and layers[0]["bbox"] == {
        "x": 0,
        "y": 0,
        "width": 1600,
        "height": 900,
    }
    assert "no text" in layers[0]["image_prompt"]
    scrim = next(layer for layer in layers if layer["name"] == "scrim")
    assert 0 < scrim["color"]["opacity"] < 1
    names = [layer["name"] for layer in layers]
    assert {"caption", "headline", "subhead", "cta", "accent bar"} <= set(names)
    ids = [layer["layer_id"] for layer in layers]
    assert ids == sorted(ids) and [layer["z_index"] for layer in layers] == list(range(len(ids)))
    headline = next(layer for layer in layers if layer["name"] == "headline")
    # The profile's 0.04 is below the poster floor of 0.075, so the floor wins.
    assert headline["typography"]["font_size"] == 120
    assert headline["typography"]["font_weight"] == 800
    assert headline["align"] == "left"
    assert headline["bbox"]["x"] == int(900 * PROFILE["margin_ratio"])
    caption = next(layer for layer in layers if layer["name"] == "caption")
    assert (
        caption["text"] == caption["text"].upper() and caption["typography"]["letter_spacing"] > 0
    )
    cta = next(layer for layer in layers if layer["name"] == "cta")
    assert "background" in cta and cta["bbox"]["width"] < headline["bbox"]["width"]
    # Stack reads top to bottom in the order a poster does.
    ys = [
        next(layer for layer in layers if layer["name"] == n)["bbox"]["y"]
        for n in ("caption", "headline", "subhead", "cta")
    ]
    assert ys == sorted(ys)
    for layer in layers:
        b = layer["bbox"]
        assert 0 <= b["x"] and b["x"] + b["width"] <= 1600
        assert 0 <= b["y"] and b["y"] + b["height"] <= 900


def test_layout_portrait_puts_text_zone_at_the_bottom() -> None:
    plan = heuristic_plan("Album cover", 900, 1600, None)
    layout = heuristic_layout(plan, None)
    scrim = next(layer for layer in layout["layers"] if layer["name"] == "scrim")
    headline = next(layer for layer in layout["layers"] if layer["name"] == "headline")
    assert scrim["bbox"]["width"] == 900 and scrim["bbox"]["y"] > 0
    assert headline["bbox"]["y"] > 1600 * 0.42


def test_layout_logo_becomes_a_wordmark_not_the_word_logo() -> None:
    plan = heuristic_plan("Poster", 1600, 900, None)
    plan.elements.append(PlanElement(role="logo", content="Savanna Grill logo", priority=5))
    layout = heuristic_layout(plan, None)
    mark = next(layer for layer in layout["layers"] if layer["name"] == "wordmark")
    assert mark["text"] == "SAVANNA GRILL"
    assert mark["bbox"]["y"] < 100


def test_layout_text_stays_readable_on_a_low_contrast_palette() -> None:
    """Regression: a director-picked palette of two close warm tones (real case, e.g.
    #EB7F35 on #F2AC6F) must not produce near-invisible text."""
    from app.layout import _blend, _contrast_ratio

    plan = heuristic_plan("Concert poster", 1080, 1350, None)
    plan.palette_intent = ["#EB7F35", "#F2AC6F"]
    layout = heuristic_layout(plan, None)
    scrim = next(layer for layer in layout["layers"] if layer["name"] == "scrim")["color"]
    on_scrim = _blend(scrim["hex"], scrim["opacity"])
    for layer in layout["layers"]:
        if layer["type"] != "text":
            continue
        text_colour = layer["color"]["hex"]
        against = layer.get("background", {}).get("hex", on_scrim)
        minimum = 3.0 if layer["name"] == "caption" else 4.5
        assert _contrast_ratio(text_colour, against) >= minimum, layer["name"]


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
    assert "espresso" in prompt and "no text" in prompt and lora == "style-lora-v1.safetensors"
    assert (w, h) == (1024, 576)  # full bleed: the render keeps the canvas aspect


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


async def test_raster_route_accepts_the_query_param_fallback(
    client: AsyncClient,
    storage: FakeStorage,
    session_maker: async_sessionmaker[AsyncSession],
) -> None:
    """The raster route is the one place a ?token= query param must work - it's loaded
    by react-native-svg's Image href, which can't set an Authorization header. A bad
    query token must still 401, and a good header must still work with no query token
    at all (every other route's behaviour, unchanged by this route's extra fallback)."""
    from app.models import Job

    storage.objects["renders/job-raster-1/L02.png"] = (b"\x89PNG-fake", "image/png")
    async with session_maker() as session:
        session.add(
            Job(
                job_id="33333333-3333-4333-8333-333333333333",
                prompt="a poster",
                aesthetic_version="baseline",
                width=1600,
                height=900,
                requested_by="mac-m4",
                status="done",
                result={
                    "canvas_width": 1600,
                    "canvas_height": 900,
                    "aesthetic_version": "baseline",
                    "renderer": "legion",
                    "layers": [
                        {
                            "layer_id": "L02",
                            "name": "hero visual",
                            "type": "image",
                            "z_index": 1,
                            "bbox": {"x": 0, "y": 0, "width": 100, "height": 100},
                            "raster_key": "renders/job-raster-1/L02.png",
                        }
                    ],
                },
            )
        )
        await session.commit()

    job_id = "33333333-3333-4333-8333-333333333333"
    r = await client.get(f"/generate/{job_id}/raster/L02", params={"token": "token-a"})
    assert r.status_code == 200
    assert r.content == b"\x89PNG-fake"
    r = await client.get(f"/generate/{job_id}/raster/L02", params={"token": "not-a-real-token"})
    assert r.status_code == 401
    r = await client.get(f"/generate/{job_id}/raster/L02", headers=AUTH_A)
    assert r.status_code == 200  # the header alone, with no query token, still works


async def test_list_jobs_scoped_to_agent(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    import app.routes.generate as gen_mod

    monkeypatch.setattr(gen_mod, "enqueue_generation", lambda job_id: None)
    await client.post("/generate", json={"prompt": "poster for agent a"}, headers=AUTH_A)
    await client.post("/generate", json={"prompt": "poster for agent b"}, headers=AUTH_B)

    r = await client.get("/generate", headers=AUTH_A)
    assert r.status_code == 200
    jobs = r.json()
    assert len(jobs) == 1
    assert jobs[0]["prompt"] == "poster for agent a"

    r = await client.get("/generate", headers=AUTH_B)
    assert [j["prompt"] for j in r.json()] == ["poster for agent b"]


async def test_list_jobs_newest_first_and_limit(
    client: AsyncClient,
    session_maker: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import app.routes.generate as gen_mod
    from app.models import Job

    monkeypatch.setattr(gen_mod, "enqueue_generation", lambda job_id: None)
    for i in range(3):
        await client.post("/generate", json={"prompt": f"poster {i}"}, headers=AUTH_A)

    # Give each row a distinct, known created_at so ordering is asserted for real,
    # not by accident of three inserts happening within the same test.
    async with session_maker() as session:
        rows = (await session.exec(select(Job).where(Job.requested_by == "mac-m4"))).all()
        by_prompt = {row.prompt: row for row in rows}
        for i in range(3):
            row = by_prompt[f"poster {i}"]
            row.created_at = datetime(2026, 1, 1) + timedelta(hours=i)
            session.add(row)
        await session.commit()

    r = await client.get("/generate", headers=AUTH_A)
    assert [j["prompt"] for j in r.json()] == ["poster 2", "poster 1", "poster 0"]

    r = await client.get("/generate", params={"limit": 2}, headers=AUTH_A)
    assert [j["prompt"] for j in r.json()] == ["poster 2", "poster 1"]

    r = await client.get("/generate", params={"limit": 0}, headers=AUTH_A)
    assert len(r.json()) == 1  # clamped to at least 1, never "no limit" / empty


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
