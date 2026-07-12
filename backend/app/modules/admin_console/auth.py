"""REQ-051 — admin_console simplified auth (is_admin boolean check).

Replaces the REQ-044 6-role capability matrix with a single
``require_admin()`` FastAPI dependency that queries the DB
``users.is_admin`` column.
"""
from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import db_session_dep

__all__ = [
    "require_admin",
]


async def require_admin(
    request: Request,
    db: Annotated[AsyncSession, Depends(db_session_dep)],
) -> bool:
    """FastAPI dependency: raises HTTP 403 if the caller is not an admin.

    Resolves the caller user_id from the JWT bearer token and checks
    ``users.is_admin``.
    """
    from app.modules.auth.models import User

    auth = request.headers.get("Authorization", "")
    if not auth.lower().startswith("bearer "):
        raise _forbidden_admin_exception()
    from app.core.security import decode_token
    try:
        payload = decode_token(auth.split(" ", 1)[1], expected_type="access")
        jwt_user_id = UUID(str(payload.sub))
    except Exception:
        raise _forbidden_admin_exception()

    result = await db.execute(
        select(User.is_admin).where(
            User.id == jwt_user_id,
            User.deleted_at.is_(None),
        )
    )
    is_admin = result.scalar()
    if not is_admin:
        raise _forbidden_admin_exception()
    return True


def _forbidden_admin_exception() -> HTTPException:
    """Standard 403 response for non-admin callers."""
    return HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail={
            "error": "ADMIN_REQUIRED",
            "message": "需要管理员权限",
            "capability": "admin_required",
        },
    )
