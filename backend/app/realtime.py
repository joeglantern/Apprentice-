"""Socket.IO server for generation progress. Backed by Redis so Celery workers can emit.

Every other route in this API sits behind an agent token; a job's progress room must
too, or anyone who reaches this endpoint could watch (and read the plan/prompt of)
any job by guessing or reusing a job_id, with no credential at all. connect() checks
the token, join() then re-checks that the connecting agent actually owns the room
it's asking to join."""

from __future__ import annotations

from typing import Any

import socketio

from app.auth import agent_for_token
from app.config import get_settings
from app.db import session_factory
from app.models import Job

_settings = get_settings()

mgr = socketio.AsyncRedisManager(_settings.redis_url)
sio = socketio.AsyncServer(
    async_mode="asgi",
    client_manager=mgr,
    cors_allowed_origins=(
        "*" if _settings.cors_origins == "*" else _settings.cors_origins.split(",")
    ),
)
socket_app = socketio.ASGIApp(sio, socketio_path="socket.io")


@sio.event
async def connect(sid: str, environ: dict[str, Any], auth: dict[str, Any] | None) -> bool:
    token = (auth or {}).get("token")
    agent_id = agent_for_token(str(token), _settings) if token else None
    if agent_id is None:
        return False  # rejects the handshake outright, no room is ever reachable
    await sio.save_session(sid, {"agent_id": agent_id})
    return True


@sio.event
async def join(sid: str, data: dict[str, Any]) -> None:
    room = str(data.get("room", "")).strip()
    if not room:
        return
    session = await sio.get_session(sid)
    async with session_factory()() as db:
        job = await db.get(Job, room)
    if job is not None and job.requested_by == session.get("agent_id"):
        await sio.enter_room(sid, room)


@sio.event
async def leave(sid: str, data: dict[str, Any]) -> None:
    room = str(data.get("room", "")).strip()
    if room:
        await sio.leave_room(sid, room)


def worker_emitter() -> socketio.RedisManager:
    """Write-only manager for use from Celery tasks (a separate process)."""
    return socketio.RedisManager(_settings.redis_url, write_only=True)
