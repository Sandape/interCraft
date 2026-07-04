"""REQ-044 US4 — Incidents & Badcases FastAPI router (FR-021~FR-023).

Mounted by ``app.main`` at two prefixes:

- ``/api/v1/admin-console/incidents`` (exported as ``incidents_router``)
  — incident list, detail, evidence, comments, status, audit trail.
- ``/api/v1/admin-console/badcases`` (exported as ``badcases_router``)
  — badcase list, detail, escalate.

Auth: capability check via :func:`app.modules.admin_console.auth.require_capability`
with the 4 new US4 capabilities (added to ``admin_console.auth`` role map):

- ``INCIDENT_VIEW`` — required for GET incident list / detail / evidence.
- ``INCIDENT_CHANGE`` — required for POST comment + PATCH status.
- ``BADCASE_VIEW`` — required for GET badcase list / detail.
- ``BADCASE_CHANGE`` — required for POST badcase escalate.

Role grants (mirrors US3 pattern):

- ``admin`` / ``owner`` / ``pm`` / ``operations`` / ``maintainer`` /
  ``reviewer`` → ``INCIDENT_VIEW`` + ``BADCASE_VIEW`` (read)
- ``operations`` + ``admin`` + ``owner`` → ``INCIDENT_CHANGE`` + ``BADCASE_CHANGE`` (write)
- ``pm`` + ``maintainer`` → ``INCIDENT_CHANGE`` (write incident)
- ``reviewer`` → ``BADCASE_CHANGE`` (write badcase)
- ``viewer`` → none (FR-031 least-privilege)

Endpoints:

- ``GET /incidents`` — incident list (FR-021, AC-21.1/21.2)
- ``GET /incidents/{id}`` — single incident detail (AC-21.3)
- ``GET /incidents/{id}/evidence`` — 8-type evidence list (FR-022, AC-22.1)
- ``GET /incidents/{id}/comments`` — comment list
- ``POST /incidents/{id}/comments`` — add comment (FR-022, AC-22.2, INCIDENT_CHANGE)
- ``PATCH /incidents/{id}/status`` — change status (EC-4, INCIDENT_CHANGE)
- ``GET /incidents/{id}/audit-trail`` — EC-4 audit trail
- ``GET /incidents/health`` — module liveness
- ``GET /badcases`` — badcase list (FR-023, AC-23.1)
- ``GET /badcases/{id}`` — single badcase detail
- ``POST /badcases/{id}/escalate`` — escalate to incident (FR-023, AC-23.4, BADCASE_CHANGE)
- ``GET /badcases/health`` — module liveness

Error mapping:

- 403 ``missing_capability`` (FR-031)
- 404 ``incident_not_found`` / ``badcase_not_found`` (404 envelope)
- 200 + empty data with explicit zero markers (FR-028 valid zero)
- 500 unexpected (default FastAPI handler)
"""
from __future__ import annotations

from typing import Annotated
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import get_current_user_id_optional as _resolve_user_id_from_jwt
from app.modules.admin_console.auth import require_capability
from app.modules.admin_console.incidents import service
from app.modules.admin_console.incidents.schemas import (
    AuditTrail,
    Badcase,
    BadcaseEscalateResponse,
    BadcaseListResponse,
    Comment,
    CommentCreateRequest,
    CommentListResponse,
    EvidenceLinkListResponse,
    Incident,
    IncidentListResponse,
    StatusChangeRequest,
)

log = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Capability tokens
# ---------------------------------------------------------------------------


INCIDENT_VIEW = "INCIDENT_VIEW"
INCIDENT_CHANGE = "INCIDENT_CHANGE"
BADCASE_VIEW = "BADCASE_VIEW"
BADCASE_CHANGE = "BADCASE_CHANGE"


# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------


incidents_router = APIRouter()
badcases_router = APIRouter()


# ---------------------------------------------------------------------------
# Helper: resolve actor handle (user_id or "unknown")
# ---------------------------------------------------------------------------


def _actor_handle(user_id: UUID) -> str:
    """Best-effort actor handle for the audit trail (EC-4)."""
    return f"@user:{str(user_id)[:8]}"


# ---------------------------------------------------------------------------
# Endpoint: GET /incidents (FR-021)
# ---------------------------------------------------------------------------


@incidents_router.get(
    "",
    response_model=IncidentListResponse,
    status_code=200,
    responses={
        200: {"description": "Incident list (10 FR-021 fields + EC-1/2/3 fields)"},
        403: {"description": "Missing INCIDENT_VIEW capability"},
    },
)
async def list_incidents(
    _user_id: Annotated[UUID, Depends(_resolve_user_id_from_jwt)],
    _cap: Annotated[bool, Depends(require_capability(INCIDENT_VIEW))],
) -> IncidentListResponse:
    """Return the incident list (FR-021 + EC-1/2/3)."""
    log.info("incidents.list.request")
    return service.list_incidents()


# ---------------------------------------------------------------------------
# Endpoint: GET /incidents/{id} (AC-21.3)
# ---------------------------------------------------------------------------


@incidents_router.get(
    "/{incident_id}",
    response_model=Incident,
    status_code=200,
    responses={
        200: {"description": "Single incident detail (10 FR-021 fields + EC-2 cross-link)"},
        403: {"description": "Missing INCIDENT_VIEW capability"},
        404: {"description": "Incident not found"},
    },
)
async def get_incident(
    incident_id: str,
    _user_id: Annotated[UUID, Depends(_resolve_user_id_from_jwt)],
    _cap: Annotated[bool, Depends(require_capability(INCIDENT_VIEW))],
) -> Incident:
    """Return a single incident by id (AC-21.3)."""
    log.info("incidents.get.request", incident_id=incident_id)
    inc = service.get_incident(incident_id)
    if inc is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "INCIDENT_NOT_FOUND",
                "message": f"未找到 incident_id={incident_id}",
                "incident_id": incident_id,
            },
        )
    return inc


# ---------------------------------------------------------------------------
# Endpoint: GET /incidents/{id}/evidence (FR-022, AC-22.1)
# ---------------------------------------------------------------------------


@incidents_router.get(
    "/{incident_id}/evidence",
    response_model=EvidenceLinkListResponse,
    status_code=200,
    responses={
        200: {"description": "8-type evidence link list (FR-022)"},
        403: {"description": "Missing INCIDENT_VIEW capability"},
    },
)
async def get_incident_evidence(
    incident_id: str,
    _user_id: Annotated[UUID, Depends(_resolve_user_id_from_jwt)],
    _cap: Annotated[bool, Depends(require_capability(INCIDENT_VIEW))],
) -> EvidenceLinkListResponse:
    """Return the 8-type evidence link list (FR-022 + AC-22.1)."""
    log.info("incidents.evidence.request", incident_id=incident_id)
    return service.get_incident_evidence(incident_id)


# ---------------------------------------------------------------------------
# Endpoint: GET /incidents/{id}/comments
# ---------------------------------------------------------------------------


@incidents_router.get(
    "/{incident_id}/comments",
    response_model=CommentListResponse,
    status_code=200,
    responses={
        200: {"description": "Comment list for the incident"},
        403: {"description": "Missing INCIDENT_VIEW capability"},
    },
)
async def list_incident_comments(
    incident_id: str,
    _user_id: Annotated[UUID, Depends(_resolve_user_id_from_jwt)],
    _cap: Annotated[bool, Depends(require_capability(INCIDENT_VIEW))],
) -> CommentListResponse:
    """Return the comment list (FR-022)."""
    log.info("incidents.comments.list.request", incident_id=incident_id)
    return service.list_incident_comments(incident_id)


# ---------------------------------------------------------------------------
# Endpoint: POST /incidents/{id}/comments (FR-022, AC-22.2)
# ---------------------------------------------------------------------------


@incidents_router.post(
    "/{incident_id}/comments",
    response_model=Comment,
    status_code=201,
    responses={
        201: {"description": "Comment added"},
        403: {"description": "Missing INCIDENT_CHANGE capability"},
        404: {"description": "Incident not found"},
    },
)
async def add_incident_comment(
    incident_id: str,
    body: CommentCreateRequest,
    user_id: Annotated[UUID, Depends(_resolve_user_id_from_jwt)],
    _cap: Annotated[bool, Depends(require_capability(INCIDENT_CHANGE))],
) -> Comment:
    """Add a comment to the incident (FR-022 + AC-22.2)."""
    log.info("incidents.comments.add.request", incident_id=incident_id)
    try:
        return service.add_incident_comment(
            incident_id=incident_id,
            actor=_actor_handle(user_id),
            body=body.body,
            reason=body.reason,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "INCIDENT_NOT_FOUND",
                "message": str(exc),
                "incident_id": incident_id,
            },
        )


# ---------------------------------------------------------------------------
# Endpoint: PATCH /incidents/{id}/status (EC-4)
# ---------------------------------------------------------------------------


@incidents_router.patch(
    "/{incident_id}/status",
    response_model=AuditTrail,
    status_code=200,
    responses={
        200: {"description": "Status changed + audit trail returned"},
        403: {"description": "Missing INCIDENT_CHANGE capability"},
        404: {"description": "Incident not found"},
    },
)
async def change_incident_status(
    incident_id: str,
    body: StatusChangeRequest,
    user_id: Annotated[UUID, Depends(_resolve_user_id_from_jwt)],
    _cap: Annotated[bool, Depends(require_capability(INCIDENT_CHANGE))],
) -> AuditTrail:
    """Change incident status and return the full audit trail (EC-4)."""
    log.info(
        "incidents.status.change.request",
        incident_id=incident_id,
        new_status=body.new_status,
    )
    try:
        service.change_incident_status(
            incident_id=incident_id,
            actor=_actor_handle(user_id),
            new_status=body.new_status,
            new_owner=body.new_owner,
            reason=body.reason,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "INCIDENT_NOT_FOUND",
                "message": str(exc),
                "incident_id": incident_id,
            },
        )
    entries = service.get_incident_audit_trail(incident_id)
    return AuditTrail(
        incident_id=incident_id,
        entries=entries,
        total=len(entries),
    )


# ---------------------------------------------------------------------------
# Endpoint: GET /incidents/{id}/audit-trail
# ---------------------------------------------------------------------------


@incidents_router.get(
    "/{incident_id}/audit-trail",
    response_model=AuditTrail,
    status_code=200,
    responses={
        200: {"description": "EC-4 audit trail"},
        403: {"description": "Missing INCIDENT_VIEW capability"},
    },
)
async def get_incident_audit_trail(
    incident_id: str,
    _user_id: Annotated[UUID, Depends(_resolve_user_id_from_jwt)],
    _cap: Annotated[bool, Depends(require_capability(INCIDENT_VIEW))],
) -> AuditTrail:
    """Return the full audit trail for the incident (EC-4)."""
    log.info("incidents.audit_trail.request", incident_id=incident_id)
    entries = service.get_incident_audit_trail(incident_id)
    return AuditTrail(
        incident_id=incident_id,
        entries=entries,
        total=len(entries),
    )


# ---------------------------------------------------------------------------
# Endpoint: GET /incidents/health
# ---------------------------------------------------------------------------


@incidents_router.get(
    "/health",
    status_code=200,
    responses={200: {"description": "Module liveness"}},
)
async def incidents_health() -> dict[str, str]:
    """Module liveness check (parity with /command-center/health)."""
    return {"status": "ok", "module": "incidents"}


# ---------------------------------------------------------------------------
# Endpoint: GET /badcases (FR-023, AC-23.1)
# ---------------------------------------------------------------------------


@badcases_router.get(
    "",
    response_model=BadcaseListResponse,
    status_code=200,
    responses={
        200: {"description": "Badcase list (10 FR-023 fields)"},
        403: {"description": "Missing BADCASE_VIEW capability"},
    },
)
async def list_badcases(
    _user_id: Annotated[UUID, Depends(_resolve_user_id_from_jwt)],
    _cap: Annotated[bool, Depends(require_capability(BADCASE_VIEW))],
) -> BadcaseListResponse:
    """Return the badcase list (FR-023 + AC-23.1)."""
    log.info("badcases.list.request")
    return service.list_badcases()


# ---------------------------------------------------------------------------
# Endpoint: GET /badcases/{id}
# ---------------------------------------------------------------------------


@badcases_router.get(
    "/{badcase_id}",
    response_model=Badcase,
    status_code=200,
    responses={
        200: {"description": "Single badcase detail"},
        403: {"description": "Missing BADCASE_VIEW capability"},
        404: {"description": "Badcase not found"},
    },
)
async def get_badcase(
    badcase_id: str,
    _user_id: Annotated[UUID, Depends(_resolve_user_id_from_jwt)],
    _cap: Annotated[bool, Depends(require_capability(BADCASE_VIEW))],
) -> Badcase:
    """Return a single badcase by id."""
    log.info("badcases.get.request", badcase_id=badcase_id)
    bc = service.get_badcase(badcase_id)
    if bc is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "BADCASE_NOT_FOUND",
                "message": f"未找到 badcase_id={badcase_id}",
                "badcase_id": badcase_id,
            },
        )
    return bc


# ---------------------------------------------------------------------------
# Endpoint: POST /badcases/{id}/escalate (FR-023, AC-23.4)
# ---------------------------------------------------------------------------


@badcases_router.post(
    "/{badcase_id}/escalate",
    response_model=BadcaseEscalateResponse,
    status_code=201,
    responses={
        201: {"description": "Badcase escalated to incident"},
        403: {"description": "Missing BADCASE_CHANGE capability"},
        404: {"description": "Badcase not found"},
    },
)
async def escalate_badcase(
    badcase_id: str,
    user_id: Annotated[UUID, Depends(_resolve_user_id_from_jwt)],
    _cap: Annotated[bool, Depends(require_capability(BADCASE_CHANGE))],
) -> BadcaseEscalateResponse:
    """Escalate the badcase to a new incident (FR-023 + AC-23.4)."""
    log.info("badcases.escalate.request", badcase_id=badcase_id)
    try:
        return service.escalate_badcase_to_incident(
            badcase_id=badcase_id,
            actor=_actor_handle(user_id),
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "BADCASE_NOT_FOUND",
                "message": str(exc),
                "badcase_id": badcase_id,
            },
        )


# ---------------------------------------------------------------------------
# Endpoint: GET /badcases/health
# ---------------------------------------------------------------------------


@badcases_router.get(
    "/health",
    status_code=200,
    responses={200: {"description": "Module liveness"}},
)
async def badcases_health() -> dict[str, str]:
    """Module liveness check."""
    return {"status": "ok", "module": "badcases"}


__all__ = [
    "BADCASE_CHANGE",
    "BADCASE_VIEW",
    "INCIDENT_CHANGE",
    "INCIDENT_VIEW",
    "badcases_router",
    "incidents_router",
]
