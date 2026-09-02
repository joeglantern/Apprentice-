"""Titles: which signal is used, and what happens when the model is not there."""

from __future__ import annotations

import httpx
import pytest

from app import titles
from app.config import Settings


def settings() -> Settings:
    return Settings(
        agent_tokens="app:t",
        local_director_url="http://legion:11434",
        chat_model="qwen3:8b",
    )


def poster_plan(headline: str) -> dict:
    return {
        "elements": [
            {"role": "subhead", "content": "where the city meets the music", "priority": 2},
            {"role": "headline", "content": headline, "priority": 1},
        ]
    }


async def test_poster_uses_its_own_headline_and_asks_no_model(monkeypatch):
    """The director already wrote the piece's name; spending a call to summarise the
    brief instead would be both slower and worse."""

    async def boom(*a, **k):
        raise AssertionError("a poster with a headline must not call the model")

    monkeypatch.setattr(titles, "_ask_local", boom)
    got = await titles.make_title("poster for a rooftop jazz night", poster_plan("Rooftop Vibes"), "poster", settings())
    assert got == "Rooftop Vibes"


async def test_headline_longer_than_a_name_is_not_used(monkeypatch):
    """A headline can be a paragraph wearing a headline's role."""
    monkeypatch.setattr(titles, "_ask_local", _async("Jazz On The Roof"))
    plan = poster_plan("a" * 200)
    assert await titles.make_title("brief", plan, "poster", settings()) == "Jazz On The Roof"


async def test_image_and_logo_ask_the_model(monkeypatch):
    seen: list[str] = []

    async def fake(prompt, _s):
        seen.append(prompt)
        return "Orange Urus At Dusk"

    monkeypatch.setattr(titles, "_ask_local", fake)
    got = await titles.make_title("generate a lambo image orange in color a urus", None, "image", settings())
    assert got == "Orange Urus At Dusk"
    assert seen == ["generate a lambo image orange in color a urus"]


async def test_falls_back_to_the_brief_when_the_model_is_down(monkeypatch):
    async def unreachable(*a, **k):
        return None

    monkeypatch.setattr(titles, "_ask_local", unreachable)
    got = await titles.make_title("a very good poster about nothing at all", None, "image", settings())
    assert got == "a very good poster about nothing at all"


async def test_unreachable_model_never_raises(monkeypatch):
    """A naming problem must not surface as a failed job."""

    class Boom:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def post(self, *a, **k):
            raise httpx.ConnectError("no route")

    monkeypatch.setattr(httpx, "AsyncClient", lambda **k: Boom())
    assert await titles._ask_local("anything", settings()) is None


@pytest.mark.parametrize(
    "raw,expected",
    [
        ('"Rooftop Vibes"', "Rooftop Vibes"),
        ("Rooftop Vibes.", "Rooftop Vibes"),
        ("  Rooftop   Vibes  ", "Rooftop Vibes"),
        ("one two three four five six seven eight nine", "one two three four five six seven"),
    ],
)
def test_clean_strips_what_small_models_add_back(raw, expected):
    assert titles._clean(raw) == expected


def test_from_prompt_trims_on_a_word_boundary():
    long = "a Kenyan bodybuilder lifting weights while halfway immersed in a pond with vegetation"
    got = titles.from_prompt(long)
    assert len(got) <= titles.MAX_CHARS
    assert long.startswith(got)
    # cut between words, so the name never ends mid-word
    assert long[len(got)] == " "


def test_short_prompt_is_left_alone():
    assert titles.from_prompt("orange urus at dusk") == "orange urus at dusk"


def _async(value):
    async def run(*a, **k):
        return value

    return run


def test_worker_can_actually_call_its_titler(monkeypatch):
    """A regression guard with teeth.

    The titling call was once added to the worker while the function it calls was
    not, which grepping for the name could not catch (the call site matched) and no
    test exercised. Every render that followed finished and then died with a
    NameError at the last line. This imports the module and calls the thing.
    """
    from app import worker

    async def fake(prompt, plan, kind, settings):
        return "Ember Lane"

    monkeypatch.setattr(worker, "make_title", fake)
    assert worker._title_for("a logo for a coffee roaster", {}, "logo") == "Ember Lane"


def test_worker_titler_survives_a_broken_model(monkeypatch):
    from app import worker

    async def boom(*a, **k):
        raise RuntimeError("ollama is on fire")

    monkeypatch.setattr(worker, "make_title", boom)
    # The render already succeeded; naming must not turn that into a failed job.
    assert worker._title_for("a very long brief about a poster", {}, "poster")
