"""REQ-051 — admin_console simplified auth (is_admin boolean check).

Replaces the REQ-044 6-role capability matrix with a single
``require_admin()`` FastAPI dependency that queries the DB
``users.is_admin`` column.

Public API:
- :func:`require_admin` — FastAPI dependency factory. Queries
  ``User.is_admin`` for the caller; raises HTTP 403 when not admin.
- :func:`get_caller_user_id_dep` — lazy resolver for the caller's
  user_id (delegates to admin_console.api.get_caller_user_id).
"""
from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import db_session_dep


async def require_admin(
    user_id: Annotated[UUID, Depends(lambda: get_caller_user_id_dep())],
    db: Annotated[AsyncSession, Depends(db_session_dep)],
) -> bool:
    """FastAPI dependency: raises HTTP 403 if the caller is not an admin.

    Usage::

        @router.get("/...")
        async def endpoint(_admin: Annotated[bool, Depends(require_admin)]):
            ...
    """
    from app.modules.auth.models import User

    result = await db.execute(
        select(User.is_admin).where(
            User.id == user_id,
            User.deleted_at.is_(None),
        )
    )
    is_admin = result.scalar()
    if not is_admin:
        raise _forbidden_admin_exception()
    return True


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


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


# Late-import to avoid circular dependency with api.py.
_caller_user_id_dep = None


def get_caller_user_id_dep():  # type: ignore[no-untyped-def]
    """Resolve the get_caller_user_id dependency lazily.

    Imported lazily to break the import cycle between
    :mod:`app.modules.admin_console.auth` and
    :mod:`app.modules.admin_console.api`.
    """
    global _caller_user_id_dep
    if _caller_user_id_dep is None:
        from app.modules.admin_console.api import get_caller_user_id

        _caller_user_id_dep = get_caller_user_id
    return _caller_user_id_dep


__all__ = [
    "get_caller_user_id_dep",
    "require_admin",
]
