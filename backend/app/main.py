"""FastAPI application factory."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.db import dispose_engine
from app.routes import checkpoints, health, ingest
from app.storage import get_storage


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    storage = get_storage()
    ensure = getattr(storage, "ensure_bucket", None)
    if ensure is not None:
        try:
            await ensure()
        except Exception:  # noqa: BLE001
            logging.getLogger(__name__).exception("object storage bucket check failed")
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
    app.include_router(checkpoints.router)
    if mount_realtime:
        # Imported lazily so tests without Redis can build the app.
        from app.realtime import socket_app

        app.mount("/socket.io", socket_app)
    return app


app = create_app()
