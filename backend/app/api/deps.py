"""Common FastAPI dependencies (auth + db + ws)."""
from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Annotated
from uuid import UUID

import jwt as pyjwt
from fastapi import Depends, Header, Query, Request, WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db_session
from app.core.exceptions import (
    TokenInvalidError,
    TokenMissingError,
)
from app.core.logging import bind_request_context
from app.core.security import decode_token
from app.modules.auth.models import User
from app.modules.sessions.service import is_session_alive


async def db_session_dep() -> AsyncGenerator[AsyncSession, None]:
    """Per-request session WITHOUT user context (RLS gated via get_db_session)."""
    async for s in get_db_session():
        yield s


async def db_session_user_dep(
    user_id: Annotated[UUID | None, Depends(get_current_user_id_optional)],
) -> AsyncGenerator[AsyncSession, None]:
    """Per-request session WITH user_id bound (RLS effective)."""
    if user_id is None:
        async for s in get_db_session():
            yield s
    else:
        async for s in get_db_session(user_id=user_id):
            yield s


async def get_current_user_id_optional(
    request: Request,
    authorization: Annotated[str | None, Header()] = None,
) -> UUID | None:
    """Decode JWT and bind user_id to request state. Returns None when unauthenticated."""
    if not authorization or not authorization.lower().startswith("bearer "):
        return None
    token = authorization.split(" ", 1)[1].strip()
    if not token:
        return None
    try:
        payload = decode_token(token, expected_type="access")
    except pyjwt.PyJWTError:
        return None
    user_id = UUID(payload.sub)
    session_id = payload.session_id
    request.state.user_id = user_id
    request.state.session_id = session_id
    bind_request_context(user_id=str(user_id))
    return user_id


async def get_current_user_id(
    user_id: Annotated[UUID, Depends(get_current_user_id_optional)],
) -> UUID:
    if user_id is None:
        raise TokenMissingError()
    return user_id


async def get_current_user(
    request: Request,
    user_id: Annotated[UUID, Depends(get_current_user_id)],
    db: Annotated[AsyncSession, Depends(db_session_user_dep)],
):
    """Return the User row for the current request. Enforces liveness of session."""
    from sqlalchemy import select

    result = await db.execute(select(User).where(User.id == user_id, User.deleted_at.is_(None)))
    user = result.scalar_one_or_none()
    if user is None:
        raise TokenInvalidError()
    session_id = getattr(request.state, "session_id", None)
    if not await is_session_alive(db, session_id):
        raise TokenInvalidError()
    return user


# ---- WebSocket auth dependency ----


async def get_current_user_ws(
    websocket: WebSocket,
    token: Annotated[str | None, Query()] = None,
) -> str:
    """Extract and validate JWT from WS query params, return user_id string.

    The token is logged with the last 4 chars masked.
    """
    if not token:
        await websocket.close(code=4001, reason="Missing token")
        raise WebSocketDisconnect(code=4001)

    masked = token[:4] + "***" + token[-4:] if len(token) > 8 else "***"
    try:
        payload = decode_token(token, expected_type="access")
    except pyjwt.PyJWTError:
        await websocket.close(code=4001, reason="Invalid token")
        raise WebSocketDisconnect(code=4001)

    user_id = payload.sub
    bind_request_context(user_id=user_id)
    return user_id


__all__ = [
    "db_session_dep",
    "db_session_user_dep",
    "get_current_user",
    "get_current_user_id",
    "get_current_user_id_optional",
    "get_current_user_ws",
]
