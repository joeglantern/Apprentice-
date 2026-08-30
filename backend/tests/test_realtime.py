"""connect()/join() are gated by an agent token, same as every REST route - a client
must present a valid token to connect at all, and can only join the progress room
for a job it actually requested, never any job_id it happens to know or guess."""

from __future__ import annotations

from typing import Any

import pytest

import app.realtime as realtime
from app.models import Job, utcnow


class _FakeSocketSessions:
    """Stands in for python-socketio's Redis-backed per-sid session store, so these
    tests don't need a live Redis - connect()/join() only ever call these three
    methods on `sio`, never anything manager-specific."""

    def __init__(self) -> None:
        self.saved: dict[str, dict[str, Any]] = {}
        self.rooms: dict[str, set[str]] = {}

    async def save_session(self, sid: str, data: dict[str, Any]) -> None:
        self.saved[sid] = data

    async def get_session(self, sid: str) -> dict[str, Any]:
        return self.saved.get(sid, {})

    async def enter_room(self, sid: str, room: str) -> None:
        self.rooms.setdefault(sid, set()).add(room)


@pytest.fixture
def fake_sio(monkeypatch):  # noqa: ANN001, ANN201
    fake = _FakeSocketSessions()
    monkeypatch.setattr(realtime.sio, "save_session", fake.save_session)
    monkeypatch.setattr(realtime.sio, "get_session", fake.get_session)
    monkeypatch.setattr(realtime.sio, "enter_room", fake.enter_room)
    return fake


@pytest.fixture
def db(session_maker, monkeypatch):  # noqa: ANN001, ANN201
    monkeypatch.setattr(realtime, "session_factory", lambda: session_maker)
    return session_maker


async def _make_job(db, job_id: str, requested_by: str) -> None:  # noqa: ANN001
    async with db() as s:
        s.add(
            Job(
                job_id=job_id,
                prompt="a poster",
                aesthetic_version="baseline",
                width=1600,
                height=900,
                requested_by=requested_by,
                created_at=utcnow(),
                updated_at=utcnow(),
            )
        )
        await s.commit()


async def test_connect_accepts_a_valid_token(fake_sio) -> None:  # noqa: ANN001
    ok = await realtime.connect("sid-1", {}, {"token": "token-a"})
    assert ok is True
    assert fake_sio.saved["sid-1"] == {"agent_id": "mac-m4"}


async def test_connect_rejects_a_bad_or_missing_token(fake_sio) -> None:  # noqa: ANN001
    assert await realtime.connect("sid-1", {}, {"token": "not-a-real-token"}) is False
    assert await realtime.connect("sid-2", {}, {}) is False
    assert await realtime.connect("sid-3", {}, None) is False
    assert fake_sio.saved == {}


async def test_join_admits_the_jobs_own_requester(fake_sio, db) -> None:  # noqa: ANN001
    await _make_job(db, "job-1", requested_by="mac-m4")
    await realtime.connect("sid-1", {}, {"token": "token-a"})
    await realtime.join("sid-1", {"room": "job-1"})
    assert fake_sio.rooms.get("sid-1") == {"job-1"}


async def test_join_refuses_another_agents_job(fake_sio, db) -> None:  # noqa: ANN001
    await _make_job(db, "job-1", requested_by="mac-m4")
    await realtime.connect("sid-1", {}, {"token": "token-b"})  # a different agent
    await realtime.join("sid-1", {"room": "job-1"})
    assert fake_sio.rooms.get("sid-1") is None


async def test_join_refuses_a_job_that_does_not_exist(fake_sio, db) -> None:  # noqa: ANN001
    await realtime.connect("sid-1", {}, {"token": "token-a"})
    await realtime.join("sid-1", {"room": "no-such-job"})
    assert fake_sio.rooms.get("sid-1") is None


async def test_join_normalises_room_case(fake_sio, db) -> None:  # noqa: ANN001
    """job_id is always stored lowercase (uuid.uuid4()); read_job/read_raster both
    lower() the incoming id before the lookup and join() must match that convention,
    not silently miss a room whose case doesn't happen to match."""
    await _make_job(db, "job-1", requested_by="mac-m4")
    await realtime.connect("sid-1", {}, {"token": "token-a"})
    await realtime.join("sid-1", {"room": "JOB-1"})
    assert fake_sio.rooms.get("sid-1") == {"job-1"}
