from __future__ import annotations

import json

import pytest

from app.config import Settings
from app.director import heuristic_plan, plan_design

PROFILE = {"dominant_colours": [{"value": "#111111"}, {"value": "#EEEEEE"}]}


def _settings(**overrides: object) -> Settings:
    base = {"database_url": "sqlite://", "anthropic_api_key": ""}
    base.update(overrides)
    return Settings(**base)  # type: ignore[arg-type]


async def test_no_backend_configured_uses_heuristic() -> None:
    plan = await plan_design("A poster for a jazz night", 1600, 900, PROFILE, _settings())
    assert plan.source == "heuristic"
    assert plan == heuristic_plan("A poster for a jazz night", 1600, 900, PROFILE)


async def test_local_backend_used_when_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    import app.director as director_mod

    good_plan = {
        "rationale": "A short rationale from the local model.",
        "canvas": {"width": 1, "height": 1},
        "mood": ["bold", "warm"],
        "palette_intent": ["#111111"],
        "elements": [
            {"role": "headline", "content": "Jazz Night", "priority": 1, "notes": ""},
            {"role": "image", "content": "a saxophonist", "priority": 2, "notes": ""},
        ],
    }

    async def fake_call(settings, user_text, schema) -> str:  # noqa: ANN001, ARG001
        assert "Jazz night" in user_text
        assert "properties" in schema
        assert "Today's date:" in user_text
        assert "never a past date" in user_text
        return json.dumps(good_plan)

    monkeypatch.setattr(director_mod, "_call_local_director", fake_call)
    settings = _settings(local_director_url="http://legion:11434")
    plan = await plan_design("Jazz night poster", 1600, 900, PROFILE, settings)
    assert plan.source == "director"
    assert plan.canvas == {"width": 1600, "height": 900}  # overwritten, not trusted from the model
    assert plan.rationale == good_plan["rationale"]


async def test_local_backend_failure_falls_back_to_heuristic(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import httpx

    import app.director as director_mod

    async def broken(settings, user_text, schema) -> str:  # noqa: ANN001, ARG001
        raise httpx.ConnectError("down")

    monkeypatch.setattr(director_mod, "_call_local_director", broken)
    settings = _settings(local_director_url="http://legion:11434")
    plan = await plan_design("Jazz night poster", 1600, 900, PROFILE, settings)
    assert plan.source == "heuristic"


async def test_local_backend_retries_once_before_falling_back(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A bad first response (real behaviour observed from the local model) should not
    waste the whole generation on the heuristic plan if a retry would have worked."""
    import app.director as director_mod

    good_plan = {
        "rationale": "Recovered on the second try.",
        "canvas": {"width": 1, "height": 1},
        "mood": ["bold"],
        "palette_intent": ["#111111"],
        "elements": [
            {"role": "headline", "content": "Second Try", "priority": 1, "notes": ""},
            {"role": "image", "content": "a picture", "priority": 2, "notes": ""},
        ],
    }
    calls = {"n": 0}

    async def flaky(settings, user_text, schema) -> str:  # noqa: ANN001, ARG001
        calls["n"] += 1
        if calls["n"] == 1:
            return "not json at all"
        return json.dumps(good_plan)

    monkeypatch.setattr(director_mod, "_call_local_director", flaky)
    settings = _settings(local_director_url="http://legion:11434")
    plan = await plan_design("Jazz night poster", 1600, 900, PROFILE, settings)
    assert calls["n"] == 2
    assert plan.source == "director"
    assert plan.rationale == "Recovered on the second try."


async def test_local_backend_connection_error_does_not_retry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A connection failure is unlikely to succeed on an immediate retry - fall back
    straight away rather than doubling the wait on an unreachable model."""
    import httpx

    import app.director as director_mod

    calls = {"n": 0}

    async def broken(settings, user_text, schema) -> str:  # noqa: ANN001, ARG001
        calls["n"] += 1
        raise httpx.ConnectError("down")

    monkeypatch.setattr(director_mod, "_call_local_director", broken)
    settings = _settings(local_director_url="http://legion:11434")
    plan = await plan_design("Jazz night poster", 1600, 900, PROFILE, settings)
    assert calls["n"] == 1
    assert plan.source == "heuristic"


async def test_local_backend_bad_json_falls_back_to_heuristic(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import app.director as director_mod

    async def bad(settings, user_text, schema) -> str:  # noqa: ANN001, ARG001
        return "not json at all"

    monkeypatch.setattr(director_mod, "_call_local_director", bad)
    settings = _settings(local_director_url="http://legion:11434")
    plan = await plan_design("Jazz night poster", 1600, 900, PROFILE, settings)
    assert plan.source == "heuristic"


def test_design_plan_default_palette_matches_layout() -> None:
    from app.director import DEFAULT_PALETTE
    from app.layout import heuristic_layout

    plan = heuristic_plan("x", 1600, 900, None)
    assert plan.palette_intent == DEFAULT_PALETTE
    layout = heuristic_layout(plan, None)
    scrim = next(layer for layer in layout["layers"] if layer["name"] == "scrim")
    assert scrim["color"]["hex"] == DEFAULT_PALETTE[0]  # the darkest default colour


def test_brand_kit_binds_palette_typeface_and_logo_in_the_heuristic_fallback() -> None:
    import asyncio

    from app.config import Settings
    from app.director import BrandKit, plan_design

    kit = BrandKit(
        name="Umoja Threads", palette=["dark (#1A2B3C)", "bad", "#F2A623"], typeface="bebas"
    )
    assert kit.palette == ["#1A2B3C", "#F2A623"]
    settings = Settings(database_url="sqlite://")  # no director backends configured
    plan = asyncio.run(plan_design("New drop poster", 1080, 1350, None, settings, kit))
    assert plan.palette_intent == ["#1A2B3C", "#F2A623"]
    assert plan.typeface == "bebas"
    assert any(e.role == "logo" and e.content == "Umoja Threads" for e in plan.elements)


def test_brand_text_reaches_the_model_prompt() -> None:
    from app.director import BrandKit, _user_text

    text = _user_text("x", 1080, 1350, None, BrandKit(name="Kaldi", palette=["#112233"]))
    assert "binding" in text and "'Kaldi'" in text and "#112233" in text
    assert _user_text("x", 1080, 1350, None).count("Brand kit") == 0
