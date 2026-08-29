"""Socket.IO server for generation progress. Backed by Redis so Celery workers can emit."""

from __future__ import annotations

from typing import Any

import socketio

from app.config import get_settings

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
async def join(sid: str, data: dict[str, Any]) -> None:
    room = str(data.get("room", "")).strip()
    if room:
        await sio.enter_room(sid, room)


@sio.event
async def leave(sid: str, data: dict[str, Any]) -> None:
    room = str(data.get("room", "")).strip()
    if room:
        await sio.leave_room(sid, room)


def worker_emitter() -> socketio.RedisManager:
    """Write-only manager for use from Celery tasks (a separate process)."""
    return socketio.RedisManager(_settings.redis_url, write_only=True)
