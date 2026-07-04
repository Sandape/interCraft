"""REQ-039 B1 — admin_console capability auth.

The MVP uses an in-process capability table seeded by tests / dev
fixtures. A production-grade resolver (RBAC + DB-backed user roles +
``UserCapability`` join) ships in a later US; for B1 we only need
the public API:

- :func:`require_capability(capability_name)` — FastAPI dependency
  factory. Returns ``True`` when the caller holds the capability;
  raises HTTP 403 otherwise.
- :func:`user_has_capability(user_id, capability_name)` — direct
  helper used by service-layer code that needs to gate side-effects.

Demo user ``demo@intercraft.io`` is seeded with ``admin`` role +
``REPLAY_TRIGGER`` + ``TASK_TAG`` capabilities per IC-6 (memory
``req_log_center_shipped.md``).

The capability map is process-local for B1; the API is designed so
the in-memory dict can be swapped for a DB-backed lookup without
touching the call sites.
"""
from __future__ import annotations

from threading import Lock
from typing import Annotated, Iterable
from uuid import UUID

from fastapi import Depends, HTTPException, status

# Capability tokens (FR-009 / FR-020 / FR-031 / REQ-044 US1 / US2 / US3).
REPLAY_TRIGGER = "REPLAY_TRIGGER"
TASK_TAG = "TASK_TAG"
COMMAND_CENTER_VIEW = "COMMAND_CENTER_VIEW"
# REQ-044 US2 — Product Analytics workspace (FR-011~FR-015)
PRODUCT_ANALYTICS_VIEW = "PRODUCT_ANALYTICS_VIEW"
USER_LOOKUP = "USER_LOOKUP"
# REQ-044 US3 — AI Operations workspace (FR-016~FR-020)
AI_OPERATIONS_VIEW = "AI_OPERATIONS_VIEW"

# Default role -> capability grants.
# FR-031 least-privilege: command-center view is granted to
# pm / owner / admin; reviewer + viewer / operations get a separate
# grant when their workspaces are wired (Phase 2 batch 2).
_ROLE_GRANTS: dict[str, frozenset[str]] = {
    "admin": frozenset(
        {
            REPLAY_TRIGGER,
            TASK_TAG,
            COMMAND_CENTER_VIEW,
            PRODUCT_ANALYTICS_VIEW,
            USER_LOOKUP,
            AI_OPERATIONS_VIEW,
        }
    ),
    "owner": frozenset(
        {
            REPLAY_TRIGGER,
            TASK_TAG,
            COMMAND_CENTER_VIEW,
            PRODUCT_ANALYTICS_VIEW,
            USER_LOOKUP,
            AI_OPERATIONS_VIEW,
        }
    ),
    "pm": frozenset(
        {
            COMMAND_CENTER_VIEW,
            PRODUCT_ANALYTICS_VIEW,
            USER_LOOKUP,
            AI_OPERATIONS_VIEW,
        }
    ),
    "reviewer": frozenset(
        {
            COMMAND_CENTER_VIEW,
            PRODUCT_ANALYTICS_VIEW,
            AI_OPERATIONS_VIEW,
        }
    ),
    "viewer": frozenset(),
    "operations": frozenset(
        {
            COMMAND_CENTER_VIEW,
            PRODUCT_ANALYTICS_VIEW,
            USER_LOOKUP,
            AI_OPERATIONS_VIEW,
        }
    ),
    "maintainer": frozenset(
        {
            REPLAY_TRIGGER,
            TASK_TAG,
            COMMAND_CENTER_VIEW,
            PRODUCT_ANALYTICS_VIEW,
            AI_OPERATIONS_VIEW,
        }
    ),
}

# User -> role overrides (e.g. seeded by tests / demo seed).
_user_roles: dict[UUID, str] = {}
_default_role: str = "viewer"
_lock = Lock()


def grant_role(user_id: UUID, role: str) -> None:
    """Assign a role to ``user_id``. Test / seed helper."""
    with _lock:
        _user_roles[user_id] = role


def revoke_role(user_id: UUID) -> None:
    """Clear the role for ``user_id``. Test helper."""
    with _lock:
        _user_roles.pop(user_id, None)


def reset_for_tests() -> None:
    """Clear all role assignments. Test helper."""
    with _lock:
        _user_roles.clear()


def set_default_role(role: str) -> None:
    """Set the default role for users without an explicit assignment."""
    global _default_role
    with _lock:
        _default_role = role


def user_has_capability(user_id: UUID, capability: str) -> bool:
    """Return True when the user holds the capability via role grants."""
    with _lock:
        role = _user_roles.get(user_id, _default_role)
    return capability in _ROLE_GRANTS.get(role, frozenset())


def user_capabilities(user_id: UUID) -> frozenset[str]:
    """Return the full capability set for ``user_id``."""
    with _lock:
        role = _user_roles.get(user_id, _default_role)
    return _ROLE_GRANTS.get(role, frozenset())


def require_capability(capability: str):  # type: ignore[no-untyped-def]
    """FastAPI dependency factory.

    Usage::

        @router.post(...)
        async def endpoint(_: bool = Depends(require_capability(REPLAY_TRIGGER))):
            ...
    """

    async def _dep(
        user_id: Annotated[UUID, Depends(get_caller_user_id_dep())],
    ) -> bool:
        if not user_has_capability(user_id, capability):
            raise _missing_capability_exception(capability)
        return True

    return _dep


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


def ensure_capabilities(user_id: UUID, capabilities: Iterable[str]) -> None:
    """Raise HTTP 403 on first missing capability. Service-layer helper."""
    for cap in capabilities:
        if not user_has_capability(user_id, cap):
            raise _missing_capability_exception(cap)


def _missing_capability_exception(capability: str) -> HTTPException:
    """Build the standard 403 body for a missing capability (FR-009 / FR-020)."""
    return HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail={
            "error": "MISSING_CAPABILITY",
            "message": f"需要 {capability} 权限",
            "capability": capability,
        },
    )


__all__ = [
    "AI_OPERATIONS_VIEW",
    "COMMAND_CENTER_VIEW",
    "PRODUCT_ANALYTICS_VIEW",
    "REPLAY_TRIGGER",
    "TASK_TAG",
    "USER_LOOKUP",
    "ensure_capabilities",
    "grant_role",
    "require_capability",
    "reset_for_tests",
    "revoke_role",
    "set_default_role",
    "user_capabilities",
    "user_has_capability",
]