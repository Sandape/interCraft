"""REQ-044 US7 — Review Snapshots FastAPI router.

Mounted at ``/api/v1/admin-console/review-snapshots`` by :mod:`app.main`.

Auth: capability check via :func:`app.modules.admin_console.auth.require_capability`
with the new US7 capability ``REVIEW_SNAPSHOT``.

Endpoints:

- ``POST /api/v1/admin-console/review-snapshots`` — generate snapshot
  (FR-029 AC-29.1).
- ``GET /api/v1/admin-console/review-snapshots`` — list snapshots.
- ``GET /api/v1/admin-console/review-snapshots/{id}`` — get snapshot
  with fresh current_values + delta (FR-030 AC-30.1).
- ``PUT /api/v1/admin-console/review-snapshots/{id}`` — 405 immutable
  (AC-30.4).
- ``PATCH /api/v1/admin-console/review-snapshots/{id}`` — 405 immutable
  (AC-30.4).
- ``DELETE /api/v1/admin-console/review-snapshots/{id}`` — 405 immutable
  (AC-30.4).
- ``GET /api/v1/admin-console/review-snapshots/health`` — module
  liveness.

Error mapping:

- 403 ``missing_capability`` (FR-031, SC-008).
- 422 ``snapshot_blocked_expired`` (EC-3).
- 404 ``snapshot_not_found``.
- 405 ``snapshot_immutable`` (AC-30.4).
"""
from __future__ import annotations

from typing import Annotated
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, Response, status

from app.api.deps import get_current_user_id_optional as _resolve_user_id_from_jwt
from app.modules.admin_console.auth import (
    REVIEW_SNAPSHOT,
    require_capability,
)
from app.modules.admin_console.review_snapshots import service
from app.modules.admin_console.review_snapshots.schemas import (
    ReviewSnapshotListResponse,
    ReviewSnapshotRequest,
    ReviewSnapshotResponse,
)

log = structlog.get_logger(__name__)

# Re-export for callers that import from this module.
REVIEW_SNAPSHOT = REVIEW_SNAPSHOT  # noqa: F811

review_snapshots_router = APIRouter()


def _actor_handle(user_id: UUID) -> str:
    return f"@user:{str(user_id)[:8]}"


# ---------------------------------------------------------------------------
# Endpoint: POST /review-snapshots (FR-029 AC-29.1 + EC-3)
# ---------------------------------------------------------------------------


@review_snapshots_router.post(
    "",
    response_model=ReviewSnapshotResponse,
    status_code=201,
    responses={
        201: {"description": "Snapshot generated + audit event written"},
        403: {"description": "Missing REVIEW_SNAPSHOT capability"},
        422: {"description": "snapshot blocked: period contains expired records (EC-3)"},
    },
)
async def create_review_snapshot(
    body: ReviewSnapshotRequest,
    user_id: Annotated[UUID, Depends(_resolve_user_id_from_jwt)],
    _cap: Annotated[bool, Depends(require_capability(REVIEW_SNAPSHOT))],
) -> ReviewSnapshotResponse:
    """Generate a review snapshot (FR-029)."""
    log.info(
        "review_snapshots.create",
        workspace=body.workspace,
        comparison_period=body.comparison_period,
        format=body.format,
    )
    try:
        return service.generate_snapshot(
            workspace=body.workspace,
            filters=body.filters,
            comparison_period=body.comparison_period,
            annotations=body.annotations,
            actor=_actor_handle(user_id),
            fmt=body.format,
        )
    except service.SnapshotBlockedError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error": "SNAPSHOT_BLOCKED_EXPIRED",
                "message": "snapshot period contains expired records (EC-3)",
                "expired_record_ids": exc.expired_record_ids,
            },
        )


# ---------------------------------------------------------------------------
# Endpoint: GET /review-snapshots (FR-029)
# ---------------------------------------------------------------------------


@review_snapshots_router.get(
    "",
    response_model=ReviewSnapshotListResponse,
    status_code=200,
    responses={
        200: {"description": "List of generated snapshots"},
        403: {"description": "Missing REVIEW_SNAPSHOT capability"},
    },
)
async def list_review_snapshots(
    _user_id: Annotated[UUID, Depends(_resolve_user_id_from_jwt)],
    _cap: Annotated[bool, Depends(require_capability(REVIEW_SNAPSHOT))],
) -> ReviewSnapshotListResponse:
    """List review snapshots (FR-029)."""
    log.info("review_snapshots.list")
    return service.list_snapshots()


# ---------------------------------------------------------------------------
# Endpoint: GET /review-snapshots/{id} (FR-030 AC-30.1)
# ---------------------------------------------------------------------------


@review_snapshots_router.get(
    "/{snapshot_id}",
    response_model=ReviewSnapshotResponse,
    status_code=200,
    responses={
        200: {"description": "Snapshot with fresh current_values + delta"},
        403: {"description": "Missing REVIEW_SNAPSHOT capability"},
        404: {"description": "snapshot not found"},
    },
)
async def get_review_snapshot(
    snapshot_id: str,
    _user_id: Annotated[UUID, Depends(_resolve_user_id_from_jwt)],
    _cap: Annotated[bool, Depends(require_capability(REVIEW_SNAPSHOT))],
) -> ReviewSnapshotResponse:
    """Get a snapshot with re-fetched current values + delta (FR-030)."""
    log.info("review_snapshots.get", snapshot_id=snapshot_id)
    try:
        return service.get_snapshot_with_delta(snapshot_id)
    except service.SnapshotNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "SNAPSHOT_NOT_FOUND",
                "message": f"snapshot {snapshot_id} not found",
            },
        )


# ---------------------------------------------------------------------------
# AC-30.4 — Snapshot immutable (PUT/PATCH/DELETE 405)
# ---------------------------------------------------------------------------


def _snapshot_immutable_response(snapshot_id: str) -> HTTPException:
    """Build the 405 immutable response with SNAPSHOT_IMMUTABLE error code."""
    return HTTPException(
        status_code=status.HTTP_405_METHOD_NOT_ALLOWED,
        detail={
            "error": "SNAPSHOT_IMMUTABLE",
            "message": (
                f"snapshot {snapshot_id} is immutable (FR-030 AC-30.4). "
                "Generate a new snapshot instead."
            ),
            "snapshot_id": snapshot_id,
        },
    )


@review_snapshots_router.put(
    "/{snapshot_id}",
    status_code=405,
    responses={
        405: {"description": "snapshot immutable — generate a new one"},
    },
)
async def put_review_snapshot(snapshot_id: str) -> Response:
    """PUT is forbidden (AC-30.4)."""
    log.warning("review_snapshots.put.405", snapshot_id=snapshot_id)
    raise _snapshot_immutable_response(snapshot_id)


@review_snapshots_router.patch(
    "/{snapshot_id}",
    status_code=405,
    responses={
        405: {"description": "snapshot immutable — generate a new one"},
    },
)
async def patch_review_snapshot(snapshot_id: str) -> Response:
    """PATCH is forbidden (AC-30.4)."""
    log.warning("review_snapshots.patch.405", snapshot_id=snapshot_id)
    raise _snapshot_immutable_response(snapshot_id)


@review_snapshots_router.delete(
    "/{snapshot_id}",
    status_code=405,
    responses={
        405: {"description": "snapshot immutable — generate a new one"},
    },
)
async def delete_review_snapshot(snapshot_id: str) -> Response:
    """DELETE is forbidden (AC-30.4)."""
    log.warning("review_snapshots.delete.405", snapshot_id=snapshot_id)
    raise _snapshot_immutable_response(snapshot_id)


# ---------------------------------------------------------------------------
# Endpoint: GET /health
# ---------------------------------------------------------------------------


@review_snapshots_router.get(
    "/health",
    status_code=200,
    responses={200: {"description": "Module liveness"}},
)
async def review_snapshots_health() -> dict[str, str]:
    return {"status": "ok", "module": "review_snapshots"}


__all__ = [
    "REVIEW_SNAPSHOT",
    "review_snapshots_router",
]