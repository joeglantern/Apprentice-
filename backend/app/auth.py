"""Per-agent bearer tokens. Enough for a two person project; swap for device certs if it grows."""

from __future__ import annotations

import secrets

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import Settings, get_settings

_bearer = HTTPBearer(auto_error=False)


def verify_agent_token(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    settings: Settings = Depends(get_settings),
) -> str:
    """Returns the agent_id for a valid token, else 401."""
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing agent token")
    presented = credentials.credentials
    for token, agent_id in settings.agent_token_map().items():
        if secrets.compare_digest(presented, token):
            return agent_id
    raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid agent token")
