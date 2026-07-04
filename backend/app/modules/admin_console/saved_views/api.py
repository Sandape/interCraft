"""REQ-044 CROSS — Saved Views FastAPI router (FR-006).

Mounted at ``/api/v1/admin-console/saved-views`` by :mod:`app.main`.

Auth: capability check via
:func:`app.modules.admin_console.auth.require_capability` with the
2 CROSS capability tokens (:data:`SAVED_VIEW_VIEW` +
:data:`SAVED_VIEW_CHANGE`).

Endpoints:

- ``GET    /api/v1/admin-console/saved-views`` — list views
  (filtered by workspace + role visibility, FR-006 AC-6.1 +
  AC-6.6).
- ``POST   /api/v1/admin-console/saved-views`` — create view +
  audit (FR-006 AC-6.2 + SC-009).
- ``GET    /api/v1/admin-console/saved-views/{id}`` — get detail
  with role-aware warnings (FR-006 AC-6.3 + EC-1 + EC-2).
- ``PATCH  /api/v1/admin-console/saved-views/{id}`` — update +
  optimistic lock audit (FR-006 AC-6.4 + EC-3 + SC-009).
- ``DELETE /api/v1/admin-console/saved-views/{id}`` — delete +
  audit (FR-006 AC-6.5 + SC-009).
- ``GET    /api/v1/admin-console/saved-views/health`` — module
  liveness.

Error mapping:

- 403 ``missing_capability`` (FR-031, SC-008).
- 403 ``saved_view_access_denied`` (EC-2 surface; deliberate
  leakage reduction — same code as ``missing_capability`` for
  cross-team consistency).
- 422 ``saved_view_version_conflict`` (EC-3).
- 404 ``saved_view_not_found`` (AC-6.3).
"""
from __future__ import annotations

from typing import Annotated
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status

from app.api.deps import get_current_user_id_optional as _resolve_user_id_from_jwt
from app.modules.admin_console.auth import (
    SAVED_VIEW_CHANGE,
    SAVED_VIEW_VIEW,
    require_capability,
    user_has_capability,
)
from app.modules.admin_console.saved_views import service
from app.modules.admin_console.saved_views.schemas import (
    SavedView,
    SavedViewCreateRequest,
    SavedViewCreateResponse,
    SavedViewDetailResponse,
    SavedViewListResponse,
    SavedViewUpdateRequest,
    WorkspaceId,
)

log = structlog.get_logger(__name__)

saved_views_router = APIRouter()


def _actor_handle(user_id: UUID) -> str:
    return f"@user:{str(user_id)[:8]}"


# ---------------------------------------------------------------------------
# Endpoint: GET /saved-views (FR-006 AC-6.1 + AC-6.6)
# ---------------------------------------------------------------------------


@saved_views_router.get(
    "",
    response_model=SavedViewListResponse,
    status_code=200,
    responses={
        200: {"description": "Saved views list (role-filtered)"},
        403: {"description": "Missing SAVED_VIEW_VIEW capability"},
    },
)
async def list_saved_views(
    workspace_id: Annotated[WorkspaceId, Query()],
    user_id: Annotated[UUID, Depends(_resolve_user_id_from_jwt)],
    cap: Annotated[bool, Depends(require_capability(SAVED_VIEW_VIEW))],
) -> SavedViewListResponse:
    """List saved views (FR-006 AC-6.1 + AC-6.6)."""
    log.info(
        "saved_views.list",
        workspace_id=workspace_id,
        actor=_actor_handle(user_id),
    )
    role = _infer_role(user_id)
    return service.list_views(
        workspace_id=workspace_id,
        caller_role=role,
    )


# ---------------------------------------------------------------------------
# Endpoint: POST /saved-views (FR-006 AC-6.2 + SC-009)
# ---------------------------------------------------------------------------


@saved_views_router.post(
    "",
    response_model=SavedViewCreateResponse,
    status_code=201,
    responses={
        201: {"description": "Saved view created + audit event written"},
        403: {"description": "Missing SAVED_VIEW_CHANGE capability"},
    },
)
async def create_saved_view(
    body: SavedViewCreateRequest,
    user_id: Annotated[UUID, Depends(_resolve_user_id_from_jwt)],
    cap: Annotated[bool, Depends(require_capability(SAVED_VIEW_CHANGE))],
) -> SavedViewCreateResponse:
    """Create a saved view (FR-006 AC-6.2 + SC-009)."""
    log.info(
        "saved_views.create",
        workspace_id=body.workspace_id,
        name=body.name,
        actor=_actor_handle(user_id),
    )
    return service.create_view(
        body=body,
        owner_user_id=str(user_id),
        caller_role=_infer_role(user_id),
    )


# ---------------------------------------------------------------------------
# Endpoint: GET /saved-views/{id} (FR-006 AC-6.3 + EC-1 + EC-2)
# ---------------------------------------------------------------------------


@saved_views_router.get(
    "/{saved_view_id}",
    response_model=SavedViewDetailResponse,
    status_code=200,
    responses={
        200: {"description": "Saved view detail with role-aware warnings"},
        403: {"description": "Missing SAVED_VIEW_VIEW capability OR permission revoked"},
        404: {"description": "Saved view not found"},
    },
)
async def get_saved_view(
    saved_view_id: str,
    user_id: Annotated[UUID, Depends(_resolve_user_id_from_jwt)],
    cap: Annotated[bool, Depends(require_capability(SAVED_VIEW_VIEW))],
) -> SavedViewDetailResponse:
    """Get a saved view (FR-006 AC-6.3 + EC-1 + EC-2)."""
    log.info(
        "saved_views.get",
        saved_view_id=saved_view_id,
        actor=_actor_handle(user_id),
    )
    try:
        return service.get_view(
            saved_view_id=saved_view_id,
            caller_role=_infer_role(user_id),
        )
    except service.SavedViewNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "SAVED_VIEW_NOT_FOUND",
                "message": f"saved_view {saved_view_id} not found",
            },
        )
    except service.SavedViewAccessDeniedError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": "SAVED_VIEW_ACCESS_DENIED",
                "message": "permission revoked — shared_with no longer includes your role",
                "saved_view_id": saved_view_id,
            },
        )


# ---------------------------------------------------------------------------
# Endpoint: PATCH /saved-views/{id} (FR-006 AC-6.4 + EC-3 + SC-009)
# ---------------------------------------------------------------------------


@saved_views_router.patch(
    "/{saved_view_id}",
    response_model=SavedView,
    status_code=200,
    responses={
        200: {"description": "Saved view updated + audit event written"},
        403: {"description": "Missing SAVED_VIEW_CHANGE capability"},
        404: {"description": "Saved view not found"},
        422: {"description": "saved_view version conflict (EC-3)"},
    },
)
async def patch_saved_view(
    saved_view_id: str,
    body: SavedViewUpdateRequest,
    user_id: Annotated[UUID, Depends(_resolve_user_id_from_jwt)],
    cap: Annotated[bool, Depends(require_capability(SAVED_VIEW_CHANGE))],
) -> SavedView:
    """Update a saved view (FR-006 AC-6.4 + EC-3 + SC-009)."""
    log.info(
        "saved_views.patch",
        saved_view_id=saved_view_id,
        actor=_actor_handle(user_id),
    )
    try:
        return service.update_view(
            saved_view_id=saved_view_id,
            body=body,
            caller_role=_infer_role(user_id),
        )
    except service.SavedViewNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "SAVED_VIEW_NOT_FOUND",
                "message": f"saved_view {saved_view_id} not found",
            },
        )
    except service.SavedViewAccessDeniedError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": "SAVED_VIEW_ACCESS_DENIED",
                "message": "shared_with no longer includes your role",
                "saved_view_id": saved_view_id,
            },
        )
    except service.SavedViewVersionConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error": "SAVED_VIEW_VERSION_CONFLICT",
                "message": (
                    f"saved_view {saved_view_id} version conflict: "
                    f"expected={exc.expected} actual={exc.actual}"
                ),
                "expected_version": exc.expected,
                "actual_version": exc.actual,
            },
        )


# ---------------------------------------------------------------------------
# Endpoint: DELETE /saved-views/{id} (FR-006 AC-6.5 + SC-009)
# ---------------------------------------------------------------------------


@saved_views_router.delete(
    "/{saved_view_id}",
    status_code=204,
    responses={
        204: {"description": "Saved view deleted + audit event written"},
        403: {"description": "Missing SAVED_VIEW_CHANGE capability"},
        404: {"description": "Saved view not found"},
    },
)
async def delete_saved_view(
    saved_view_id: str,
    user_id: Annotated[UUID, Depends(_resolve_user_id_from_jwt)],
    cap: Annotated[bool, Depends(require_capability(SAVED_VIEW_CHANGE))],
) -> Response:
    """Delete a saved view (FR-006 AC-6.5 + SC-009)."""
    log.info(
        "saved_views.delete",
        saved_view_id=saved_view_id,
        actor=_actor_handle(user_id),
    )
    try:
        service.delete_view(
            saved_view_id=saved_view_id,
            caller_role=_infer_role(user_id),
        )
    except service.SavedViewNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "SAVED_VIEW_NOT_FOUND",
                "message": f"saved_view {saved_view_id} not found",
            },
        )
    except service.SavedViewAccessDeniedError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": "SAVED_VIEW_ACCESS_DENIED",
                "message": "shared_with no longer includes your role",
                "saved_view_id": saved_view_id,
            },
        )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------------------
# Endpoint: GET /health
# ---------------------------------------------------------------------------


@saved_views_router.get(
    "/health",
    status_code=200,
    responses={200: {"description": "Module liveness"}},
)
async def saved_views_health() -> dict[str, str]:
    return {"status": "ok", "module": "saved_views"}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _infer_role(user_id: UUID) -> str:
    """Return the caller's role string (best-effort).

    Uses :func:`app.modules.admin_console.auth.user_has_capability`
    to probe capability ownership — the saved_views endpoint doesn't
    need a full role-string, just enough to filter visibility. We
    probe ``SAVED_VIEW_CHANGE`` for pm / admin / operations /
    maintainer / owner (5 roles), then fall back to ``reviewer``,
    then ``viewer`` (FR-031 least-privilege). This is the same
    pattern US6 governance uses; saved_views reuses the auth layer's
    role-grants map rather than introducing a parallel hierarchy.
    """
    if user_has_capability(user_id, SAVED_VIEW_CHANGE):
        return "pm"
    if user_has_capability(user_id, SAVED_VIEW_VIEW):
        return "reviewer"
    return "viewer"


__all__ = ["saved_views_router"]