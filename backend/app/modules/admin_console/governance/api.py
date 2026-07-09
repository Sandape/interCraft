"""REQ-044 US6 — Governance / Audit / Export / Retention FastAPI router.

Mounted at ``/api/v1/admin-console/governance`` by :mod:`app.main`
(US6 wiring block; added in this US).

Auth: admin-only via :func:`app.modules.admin_console.auth.require_admin`.

Endpoints:

- ``GET /api/v1/admin-console/governance/access-matrix`` — 5x8x6 matrix
- ``POST /api/v1/admin-console/governance/reveal-requests`` — submit reveal
- ``GET /api/v1/admin-console/governance/reveal-requests`` — list reveals
- ``GET /api/v1/admin-console/governance/audit-events`` — audit log
- ``POST /api/v1/admin-console/governance/exports`` — create export
- ``GET /api/v1/admin-console/governance/retention-policy`` — list policies
- ``PUT /api/v1/admin-console/governance/retention-policy`` — update one
- ``GET /api/v1/admin-console/governance/health`` — module liveness

Error mapping:

- 403 ``admin_required``
- 422 ``reveal_reason_too_short`` / ``export_blocked_expired`` (FR-033/035)
- 404 ``policy_not_found``
- 200 + empty data with explicit ``valid_zero`` markers (FR-028)
- 500 unexpected (default FastAPI handler)
"""
from __future__ import annotations

from typing import Annotated
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import get_current_user_id_optional as _resolve_user_id_from_jwt
from app.modules.admin_console.auth import require_admin
from app.modules.admin_console.governance import service
from app.modules.admin_console.governance.schemas import (
    AccessMatrixResponse,
    AuditAction,
    AuditEventListResponse,
    ExportRequestCreate,
    ExportResponse,
    RevealRequest,
    RevealRequestCreate,
    RevealRequestListResponse,
    RetentionPolicy,
    RetentionPolicyResponse,
    RetentionPolicyUpdate,
    WorkspaceId,
)

log = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

governance_router = APIRouter()


# ---------------------------------------------------------------------------
# Helper: actor handle (EC-4 audit granularity)
# ---------------------------------------------------------------------------


def _actor_handle(user_id: UUID) -> str:
    return f"@user:{str(user_id)[:8]}"


# ---------------------------------------------------------------------------
# Endpoint: GET /access-matrix (FR-031 AC-31.1)
# ---------------------------------------------------------------------------


@governance_router.get(
    "/access-matrix",
    response_model=AccessMatrixResponse,
    status_code=200,
    responses={
        200: {"description": "5x8x6 RBAC matrix (FR-031)"},
        403: {"description": "Admin required"},
    },
)
async def get_access_matrix(
    _user_id: Annotated[UUID, Depends(_resolve_user_id_from_jwt)],
    _cap: Annotated[bool, Depends(require_admin)],
) -> AccessMatrixResponse:
    """Return the 5x8x6 RBAC matrix (FR-031)."""
    log.info("governance.access_matrix.request")
    return service.get_access_matrix()


# ---------------------------------------------------------------------------
# Endpoint: POST /reveal-requests (FR-033 AC-33.1)
# ---------------------------------------------------------------------------


@governance_router.post(
    "/reveal-requests",
    response_model=RevealRequest,
    status_code=201,
    responses={
        201: {"description": "Reveal request created + audit event written"},
        403: {"description": "Admin required"},
        422: {"description": "reveal reason too short (<20 chars)"},
    },
)
async def create_reveal_request(
    body: RevealRequestCreate,
    user_id: Annotated[UUID, Depends(_resolve_user_id_from_jwt)],
    cap: Annotated[bool, Depends(require_admin)],
) -> RevealRequest:
    """Submit a sensitive reveal request (FR-033)."""
    log.info(
        "governance.reveal.create",
        target_type=body.target_type,
        target_id=body.target_id,
        reason_len=len(body.reason),
    )
    try:
        return service.create_reveal_request(
            body=body,
            actor=_actor_handle(user_id),
            has_reveal_capability=bool(cap),
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error": "REVEAL_REASON_TOO_SHORT",
                "message": str(exc),
                "min_length": service.MIN_REASON_LENGTH,
            },
        )


# ---------------------------------------------------------------------------
# Endpoint: GET /reveal-requests (FR-033 AC-33.2)
# ---------------------------------------------------------------------------


@governance_router.get(
    "/reveal-requests",
    response_model=RevealRequestListResponse,
    status_code=200,
    responses={
        200: {"description": "Reveal-request audit list (FR-033)"},
        403: {"description": "Admin required"},
    },
)
async def list_reveal_requests(
    _user_id: Annotated[UUID, Depends(_resolve_user_id_from_jwt)],
    _cap: Annotated[bool, Depends(require_admin)],
) -> RevealRequestListResponse:
    """List reveal requests (FR-033 AC-33.2)."""
    log.info("governance.reveal.list")
    return service.list_reveal_requests()


# ---------------------------------------------------------------------------
# Endpoint: GET /audit-events (FR-034 AC-34.2 / AC-34.4)
# ---------------------------------------------------------------------------


@governance_router.get(
    "/audit-events",
    response_model=AuditEventListResponse,
    status_code=200,
    responses={
        200: {"description": "Audit log viewer (FR-034, 11 actions)"},
        403: {"description": "Admin required"},
    },
)
async def list_audit_events(
    _user_id: Annotated[UUID, Depends(_resolve_user_id_from_jwt)],
    _cap: Annotated[bool, Depends(require_admin)],
    actor: str | None = None,
    action: AuditAction | None = None,
) -> AuditEventListResponse:
    """List audit events (FR-034)."""
    log.info("governance.audit.list", actor=actor, action=action)
    return service.list_audit_events(actor=actor, action=action)


# ---------------------------------------------------------------------------
# Endpoint: POST /exports (FR-035 AC-35.1)
# ---------------------------------------------------------------------------


@governance_router.post(
    "/exports",
    response_model=ExportResponse,
    status_code=201,
    responses={
        201: {"description": "Export created (6 fields + audit metadata)"},
        403: {"description": "Admin required"},
        422: {"description": "export blocked: period contains expired records (EC-2)"},
    },
)
async def create_export(
    body: ExportRequestCreate,
    user_id: Annotated[UUID, Depends(_resolve_user_id_from_jwt)],
    _cap: Annotated[bool, Depends(require_admin)],
) -> ExportResponse:
    """Create an export (FR-035)."""
    log.info(
        "governance.export.create",
        workspace=body.workspace,
        format=body.format,
    )
    try:
        return service.create_export(
            body=body,
            actor=_actor_handle(user_id),
        )
    except service.ExportBlockedError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error": "EXPORT_BLOCKED_EXPIRED",
                "message": "export period contains expired records (EC-2)",
                "expired_record_ids": exc.expired_record_ids,
            },
        )


# ---------------------------------------------------------------------------
# Endpoint: GET /retention-policy (FR-036 AC-36.1)
# ---------------------------------------------------------------------------


@governance_router.get(
    "/retention-policy",
    response_model=RetentionPolicyResponse,
    status_code=200,
    responses={
        200: {"description": "Retention policy list (FR-036)"},
        403: {"description": "Admin required"},
    },
)
async def list_retention_policies(
    _user_id: Annotated[UUID, Depends(_resolve_user_id_from_jwt)],
    _cap: Annotated[bool, Depends(require_admin)],
) -> RetentionPolicyResponse:
    """List retention policies (FR-036 AC-36.1)."""
    log.info("governance.retention.list")
    return service.list_retention_policies()


# ---------------------------------------------------------------------------
# Endpoint: PUT /retention-policy (FR-036 AC-36.2 + EC-3 + EC-4)
# ---------------------------------------------------------------------------


@governance_router.put(
    "/retention-policy",
    response_model=RetentionPolicy,
    status_code=200,
    responses={
        200: {"description": "Retention updated + cache invalidated + self-audit"},
        403: {"description": "Admin required"},
    },
)
async def update_retention_policy(
    body: RetentionPolicyUpdate,
    user_id: Annotated[UUID, Depends(_resolve_user_id_from_jwt)],
    _cap: Annotated[bool, Depends(require_admin)],
) -> RetentionPolicy:
    """Update retention policy + invalidate cache (EC-3) + self-audit (EC-4)."""
    log.info(
        "governance.retention.update",
        workspace_field=body.workspace_field,
        retention_days=body.retention_days,
        action=body.action,
    )
    return service.update_retention_policy(
        body=body,
        actor=_actor_handle(user_id),
    )


# ---------------------------------------------------------------------------
# Endpoint: GET /health
# ---------------------------------------------------------------------------


@governance_router.get(
    "/health",
    status_code=200,
    responses={200: {"description": "Module liveness"}},
)
async def governance_health() -> dict[str, str]:
    return {"status": "ok", "module": "governance"}


__all__ = ["governance_router"]
