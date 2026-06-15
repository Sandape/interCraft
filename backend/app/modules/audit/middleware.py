"""Phase 6 — Audit decorator `@audit_log` for automatic audit logging."""
from __future__ import annotations

import functools
from typing import Any, Callable, TypeVar
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.audit.service import AuditService

F = TypeVar("F", bound=Callable[..., Any])


def audit_log(action: str, resource_type: str, resource_id_param: str | None = None) -> Callable[[F], F]:
    """Decorator that writes an audit log entry after the wrapped function completes.

    Usage:
        @audit_log("update", "resume_branch", resource_id_param="branch_id")
        async def update_branch(branch_id: UUID, db: AsyncSession, user_id: UUID, ...):
            ...

    Args:
        action: Audit action type (e.g. "create", "update", "delete")
        resource_type: Resource type (e.g. "resume_branch", "interview_session")
        resource_id_param: Name of the function parameter that holds the resource ID.
                          If None, no resource_id is logged.
    """
    def decorator(func: F) -> F:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            result = await func(*args, **kwargs)

            # Try to extract db and user_id from kwargs
            db: AsyncSession | None = kwargs.get("db")
            user_id: UUID | None = kwargs.get("user_id")

            if db and user_id:
                resource_id = None
                if resource_id_param and resource_id_param in kwargs:
                    resource_id = kwargs[resource_id_param]

                audit_svc = AuditService(db)
                await audit_svc.log(
                    actor_id=user_id,
                    action=action,
                    resource_type=resource_type,
                    resource_id=resource_id,
                    new_values=result if isinstance(result, dict) else None,
                )

            return result
        return wrapper  # type: ignore[return-value]
    return decorator
