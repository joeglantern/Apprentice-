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
    assert layout["layers"][0]["color"]["hex"] == DEFAULT_PALETTE[1]
