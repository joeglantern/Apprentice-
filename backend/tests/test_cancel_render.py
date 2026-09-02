"""Cancelling the wait on the GPU.

This is the part of a job where nearly all of its life is spent, so it is the part
that has to notice. It gets its own test because the bug it is guarding against was
real: the cancel check was added to the method holding the poll loop while the
parameter was added to the public wrapper that calls it, and every render after that
died on a NameError. Grepping for the name found both and looked fine. Calling it is
what catches it.
"""

from __future__ import annotations

import httpx
import pytest

from app.cancel import Cancelled
from app.inference import ComfyRenderer


class FakeResponse:
    def __init__(self, payload: object) -> None:
        self._payload = payload
        self.content = b"not-an-image"

    def raise_for_status(self) -> None:
        return None

    def json(self) -> object:
        return self._payload


class FakeClient:
    """Accepts the prompt, then never finishes it, so the poll loop keeps going."""

    def __init__(self, *a: object, **k: object) -> None:
        self.posted: list[str] = []

    def __enter__(self) -> FakeClient:
        return self

    def __exit__(self, *a: object) -> bool:
        return False

    def post(self, url: str, **kwargs: object) -> FakeResponse:
        self.posted.append(url)
        return FakeResponse({"prompt_id": "p1"})

    def get(self, url: str, **kwargs: object) -> FakeResponse:
        return FakeResponse({})  # still working


def _renderer() -> ComfyRenderer:
    return ComfyRenderer("http://legion:8188", "legion", timeout=30.0)


def test_a_render_stops_when_the_job_is_cancelled(monkeypatch: pytest.MonkeyPatch) -> None:
    client = FakeClient()
    monkeypatch.setattr(httpx, "Client", lambda *a, **k: client)

    with pytest.raises(Cancelled):
        _renderer().render("a poster", 1024, 1024, None, None, should_cancel=lambda: True)

    assert "/interrupt" in client.posted, "the GPU must be told to stop, not just abandoned"


def test_a_render_left_alone_keeps_waiting(monkeypatch: pytest.MonkeyPatch) -> None:
    """The check must not fire when nobody cancelled, or every render would die."""
    client = FakeClient()
    monkeypatch.setattr(httpx, "Client", lambda *a, **k: client)
    monkeypatch.setattr("app.inference.time.sleep", lambda _s: None)

    # Times out rather than cancelling: returns None, which the caller treats as a
    # failed render, and never raises.
    renderer = ComfyRenderer("http://legion:8188", "legion", timeout=0.05)
    assert renderer.render("a poster", 1024, 1024, None, None, should_cancel=lambda: False) is None
    assert "/interrupt" not in client.posted


def test_a_render_with_no_cancel_check_is_unaffected(monkeypatch: pytest.MonkeyPatch) -> None:
    """Callers that do not care about cancellation must not have to pass anything."""
    client = FakeClient()
    monkeypatch.setattr(httpx, "Client", lambda *a, **k: client)
    monkeypatch.setattr("app.inference.time.sleep", lambda _s: None)

    renderer = ComfyRenderer("http://legion:8188", "legion", timeout=0.05)
    assert renderer.render("a poster", 1024, 1024, None) is None
