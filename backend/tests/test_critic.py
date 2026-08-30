from __future__ import annotations

from typing import Any

import httpx
import pytest

from app.config import Settings
from app.critic import pick_best


def _settings(**kw: Any) -> Settings:
    base: dict[str, Any] = {
        "database_url": "sqlite://",
        "local_director_url": "http://ollama:11434",
        "critic_model": "qwen2.5vl:3b",
    }
    return Settings(**{**base, **kw})


def _fake_post(reply: Any) -> Any:
    def post(url: str, json: dict[str, Any], timeout: float) -> httpx.Response:
        post.calls.append(json)  # type: ignore[attr-defined]
        if isinstance(reply, Exception):
            raise reply
        return httpx.Response(
            200, json={"message": {"content": reply}}, request=httpx.Request("POST", url)
        )

    post.calls = []  # type: ignore[attr-defined]
    return post


def test_picks_the_index_the_model_names(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _fake_post('{"scores": [4, 9], "best": 1, "why": "cleaner sky"}')
    monkeypatch.setattr(httpx, "post", fake)
    best, why = pick_best([b"a", b"b"], "a poster", "bottom half", _settings())
    assert (best, why) == (1, "cleaner sky")
    sent = fake.calls[0]
    assert sent["model"] == "qwen2.5vl:3b" and len(sent["messages"][0]["images"]) == 2
    assert "bottom half" in sent["messages"][0]["content"]


def test_one_based_or_score_only_answers_still_resolve(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(httpx, "post", _fake_post('{"scores": [3, 8], "best": 2}'))
    assert pick_best([b"a", b"b"], "x", "left half", _settings())[0] == 1
    monkeypatch.setattr(httpx, "post", _fake_post('{"scores": [9, 2]}'))
    assert pick_best([b"a", b"b"], "x", "left half", _settings())[0] == 0


def test_failure_or_off_keeps_the_first_candidate(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(httpx, "post", _fake_post(httpx.ConnectError("down")))
    assert pick_best([b"a", b"b"], "x", "left half", _settings()) == (0, "")
    monkeypatch.setattr(httpx, "post", _fake_post("not json"))
    assert pick_best([b"a", b"b"], "x", "left half", _settings()) == (0, "")
    assert pick_best([b"a", b"b"], "x", "left half", _settings(critic_model="")) == (0, "")
    assert pick_best([b"a"], "x", "left half", _settings()) == (0, "")
