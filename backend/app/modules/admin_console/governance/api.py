"""REQ-044 US6 — Governance / Audit / Export / Retention FastAPI router.

Mounted at ``/api/v1/admin-console/governance`` by :mod:`app.main`
(US6 wiring block; added in this US).

Auth: capability check via :func:`app.modules.admin_console.auth.require_capability`
with the 6 US6 capabilities (added to ``admin_console.auth`` role map):

- ``RBAC_VIEW`` — GET access-matrix (FR-031 AC-31.1)
- ``SENSITIVE_REVEAL`` — POST reveal-requests (FR-033 + EC-1)
- ``AUDIT_VIEW`` — GET audit-events + reveal-requests list (FR-034)
- ``EXPORT`` — POST exports (FR-035)
- ``GOVERNANCE_VIEW`` — GET retention-policy (FR-036)
- ``GOVERNANCE_CHANGE`` — PUT retention-policy (FR-036 + EC-4)

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

- 403 ``missing_capability`` (FR-031, SC-008)
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
from app.modules.admin_console.auth import (
    BADCASE_CHANGE,
    BADCASE_VIEW,
    COMMAND_CENTER_VIEW,
    INCIDENT_CHANGE,
    INCIDENT_VIEW,
    AI_OPERATIONS_VIEW,
    PRODUCT_ANALYTICS_VIEW,
    REPLAY_TRIGGER,
    TASK_TAG,
    USER_LOOKUP,
    grant_role,
    require_capability,
    set_default_role,
)
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
# Capability tokens (US6 additions to the role map)
# ---------------------------------------------------------------------------

RBAC_VIEW = "RBAC_VIEW"               # FR-031 AC-31.1
SENSITIVE_REVEAL = "SENSITIVE_REVEAL"  # FR-033 AC-33.1
AUDIT_VIEW = "AUDIT_VIEW"             # FR-034 AC-34.4
EXPORT = "EXPORT"                     # FR-035 AC-35.1
GOVERNANCE_VIEW = "GOVERNANCE_VIEW"    # FR-036 AC-36.1
GOVERNANCE_CHANGE = "GOVERNANCE_CHANGE"  # FR-036 AC-36.2 + EC-4


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
        403: {"description": "Missing RBAC_VIEW capability"},
    },
)
async def get_access_matrix(
    _user_id: Annotated[UUID, Depends(_resolve_user_id_from_jwt)],
    _cap: Annotated[bool, Depends(require_capability(RBAC_VIEW))],
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
        403: {"description": "Missing SENSITIVE_REVEAL capability"},
        422: {"description": "reveal reason too short (<20 chars)"},
    },
)
async def create_reveal_request(
    body: RevealRequestCreate,
    user_id: Annotated[UUID, Depends(_resolve_user_id_from_jwt)],
    cap: Annotated[bool, Depends(require_capability(SENSITIVE_REVEAL))],
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
        403: {"description": "Missing AUDIT_VIEW capability"},
    },
)
async def list_reveal_requests(
    _user_id: Annotated[UUID, Depends(_resolve_user_id_from_jwt)],
    _cap: Annotated[bool, Depends(require_capability(AUDIT_VIEW))],
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
        403: {"description": "Missing AUDIT_VIEW capability"},
    },
)
async def list_audit_events(
    _user_id: Annotated[UUID, Depends(_resolve_user_id_from_jwt)],
    _cap: Annotated[bool, Depends(require_capability(AUDIT_VIEW))],
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
        403: {"description": "Missing EXPORT capability"},
        422: {"description": "export blocked: period contains expired records (EC-2)"},
    },
)
async def create_export(
    body: ExportRequestCreate,
    user_id: Annotated[UUID, Depends(_resolve_user_id_from_jwt)],
    _cap: Annotated[bool, Depends(require_capability(EXPORT))],
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
        403: {"description": "Missing GOVERNANCE_VIEW capability"},
    },
)
async def list_retention_policies(
    _user_id: Annotated[UUID, Depends(_resolve_user_id_from_jwt)],
    _cap: Annotated[bool, Depends(require_capability(GOVERNANCE_VIEW))],
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
        403: {"description": "Missing GOVERNANCE_CHANGE capability"},
    },
)
async def update_retention_policy(
    body: RetentionPolicyUpdate,
    user_id: Annotated[UUID, Depends(_resolve_user_id_from_jwt)],
    _cap: Annotated[bool, Depends(require_capability(GOVERNANCE_CHANGE))],
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


__all__ = [
    "AUDIT_VIEW",
    "EXPORT",
    "GOVERNANCE_CHANGE",
    "GOVERNANCE_VIEW",
    "RBAC_VIEW",
    "SENSITIVE_REVEAL",
    "governance_router",
]
