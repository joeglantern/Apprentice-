"""FastAPI application factory."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.db import dispose_engine
from app.routes import health, ingest


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    yield
    await dispose_engine()


def create_app(*, mount_realtime: bool = True) -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="Ghost Agent API", version="0.1.0", lifespan=lifespan)
    origins = ["*"] if settings.cors_origins == "*" else settings.cors_origins.split(",")
    app.add_middleware(
        CORSMiddleware, allow_origins=origins, allow_methods=["*"], allow_headers=["*"]
    )
    app.include_router(health.router)
    app.include_router(ingest.router)
    if mount_realtime:
        # Imported lazily so tests without Redis can build the app.
        from app.realtime import socket_app

        app.mount("/socket.io", socket_app)
    return app


app = create_app()
