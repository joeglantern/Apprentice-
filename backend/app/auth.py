"""Per-agent bearer tokens. Enough for a two person project; swap for device certs if it grows."""

from __future__ import annotations

import secrets

from fastapi import Depends, HTTPException, Query, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import Settings, get_settings

_bearer = HTTPBearer(auto_error=False)


def agent_for_token(presented: str, settings: Settings) -> str | None:
    """Public: also used by realtime.py to authenticate the Socket.IO handshake."""
    presented_bytes = presented.encode("utf-8", errors="replace")
    for token, agent_id in settings.agent_token_map().items():
        if secrets.compare_digest(presented_bytes, token.encode("utf-8", errors="replace")):
            return agent_id
    return None


def verify_agent_token(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    token: str | None = Query(
        default=None,
        description=(
            "Same agent token as the Authorization header, as a fallback for contexts "
            "that cannot set custom headers - e.g. an <img>/SVG href loading a raster."
        ),
    ),
    settings: Settings = Depends(get_settings),
) -> str:
    """Returns the agent_id for a valid token, else 401. The header is checked first;
    the query param exists only because react-native-svg's Image href (and a plain
    <img> tag) cannot carry an Authorization header - never rely on it over the header
    when both are available, and never log a URL containing it."""
    if credentials is not None and credentials.scheme.lower() == "bearer":
        agent_id = agent_for_token(credentials.credentials, settings)
        if agent_id is not None:
            return agent_id
    if token is not None:
        agent_id = agent_for_token(token, settings)
        if agent_id is not None:
            return agent_id
    raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing or invalid agent token")
