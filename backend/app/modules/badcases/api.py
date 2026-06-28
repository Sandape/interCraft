"""REQ-033 US8 — badcase FastAPI router (T062).

Mount point: ``/api/v1/badcases`` (added in ``backend/app/main.py``,
prefix set there).

Endpoints (7):

- ``POST   /api/v1/badcases`` create
- ``GET    /api/v1/badcases`` list (filter by status / type / severity)
- ``GET    /api/v1/badcases/{badcase_id}`` read
- ``POST   /api/v1/badcases/{badcase_id}/classify`` — updates type + severity, appends CLASSIFY
- ``POST   /api/v1/badcases/{badcase_id}/close`` — sets CLOSED + closure_reason + closed_at
- ``POST   /api/v1/badcases/{badcase_id}/reject`` — sets REJECTED + reason
- ``POST   /api/v1/badcases/{badcase_id}/promote`` — writes candidate file, appends PROMOTE_CANDIDATE

Plus the ``GET /health`` placeholder from T022.

Auth
----

``require_reviewer`` is a stub dependency that returns ``user_id``. In
production this will resolve the user from the session cookie and
verify the reviewer role; for MVP a fixed ``user_id`` is returned so
the contract is end-to-end testable without auth infra. The dependency
is exported so tests can override it via ``app.dependency_overrides``.
Without overrides, ``require_reviewer`` raises HTTP 401.

Error mapping
-------------

``BadcaseTransitionError`` → HTTP 422 with ``{"error": code, "message": ...}``.
Validation errors from Pydantic → HTTP 422 via FastAPI's default.
Missing badcase → HTTP 404.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, AsyncIterator, List, Optional
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db_session_no_rls, set_rls_user_id
from app.modules.badcases import repository as repo
from app.modules.badcases import service as badcase_service
from app.modules.badcases.promotion import promote_to_golden_candidate
from app.modules.badcases.schemas import (
    BADCASE_SEVERITIES,
    BADCASE_SOURCES,
    BADCASE_STATUSES,
    BADCASE_TYPES,
    Badcase as BadcaseSchema,
    BadcaseReviewAction as BadcaseReviewActionSchema,
)

router = APIRouter()


# ---------------------------------------------------------------------------
# Auth stub (T062)
# ---------------------------------------------------------------------------


async def require_reviewer() -> UUID:
    """Stub reviewer auth dependency.

    MVP behaviour: always raises 401. Tests override this dependency
    via ``app.dependency_overrides[require_reviewer] = ...`` to inject
    a real ``user_id``. A production-grade resolver will land in a
    later US and replace this body.
    """
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="reviewer auth not configured for this environment",
    )


# ---------------------------------------------------------------------------
# DB session dependency with RLS pre-set
# ---------------------------------------------------------------------------


async def _db_session_with_rls(
    user_id: UUID = Depends(require_reviewer),
) -> AsyncIterator[AsyncSession]:
    """Yield an async session whose RLS GUC is bound to ``user_id``.

    Wraps :func:`app.core.db.get_db_session_no_rls` and explicitly
    ``SET LOCAL app.user_id`` so the badcase rows are scoped to the
    caller's user. The session commits on success and rolls back on
    exception (managed by the underlying context manager).
    """
    async for session in get_db_session_no_rls():
        await set_rls_user_id(session, user_id)
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        return


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------


class _BadcaseOut(BaseModel):
    """Lightweight projection — same shape as the schema's ``to_dict``."""

    model_config = ConfigDict(populate_by_name=True)

    badcase_id: str = Field(alias="badcaseId")
    type: str
    severity: str
    status: str
    source: str
    reviewer: Optional[str] = None
    privacy_class: str = Field(alias="privacyClass")
    redaction_status: str = Field(alias="redactionStatus")
    run_id: Optional[str] = Field(default=None, alias="runId")
    trace_id: Optional[str] = Field(default=None, alias="traceId")
    closure_reason: Optional[str] = Field(default=None, alias="closureReason")
    closed_at: Optional[str] = Field(default=None, alias="closedAt")
    created_at: str = Field(alias="createdAt")
    updated_at: str = Field(alias="updatedAt")


class _BadcaseCreateIn(BaseModel):
    type: str
    severity: str = "MEDIUM"
    source: str
    reviewer: Optional[str] = None
    privacy_class: str = Field(default="PUBLIC_METADATA", alias="privacyClass")
    redaction_status: str = Field(default="NOT_REQUIRED", alias="redactionStatus")
    run_id: Optional[UUID] = Field(default=None, alias="runId")
    trace_id: Optional[str] = Field(default=None, alias="traceId")

    @field_validator("type")
    @classmethod
    def _valid_type(cls, v: str) -> str:
        if v not in BADCASE_TYPES:
            raise ValueError(f"type must be one of {BADCASE_TYPES}")
        return v

    @field_validator("severity")
    @classmethod
    def _valid_severity(cls, v: str) -> str:
        if v not in BADCASE_SEVERITIES:
            raise ValueError(f"severity must be one of {BADCASE_SEVERITIES}")
        return v

    @field_validator("source")
    @classmethod
    def _valid_source(cls, v: str) -> str:
        if v not in BADCASE_SOURCES:
            raise ValueError(f"source must be one of {BADCASE_SOURCES}")
        return v


class _ClassifyIn(BaseModel):
    type: str
    severity: str
    reviewer: str

    @field_validator("type")
    @classmethod
    def _valid_type(cls, v: str) -> str:
        if v not in BADCASE_TYPES:
            raise ValueError(f"type must be one of {BADCASE_TYPES}")
        return v

    @field_validator("severity")
    @classmethod
    def _valid_severity(cls, v: str) -> str:
        if v not in BADCASE_SEVERITIES:
            raise ValueError(f"severity must be one of {BADCASE_SEVERITIES}")
        return v


class _CloseIn(BaseModel):
    closure_reason: str = Field(alias="closureReason")
    evidence_ref: str = Field(alias="evidenceRef")
    reviewer: str


class _RejectIn(BaseModel):
    reason: str
    reviewer: str


class _PromoteIn(BaseModel):
    redaction_audit_id: str = Field(alias="redactionAuditId")
    reviewer: str
    reason: str


class _ReviewActionOut(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    action_type: str = Field(alias="actionType")
    actor_role: str = Field(alias="actorRole")
    reason: Optional[str] = None
    evidence_ref: Optional[str] = Field(default=None, alias="evidenceRef")
    created_at: str = Field(alias="createdAt")


class _BadcaseDetailOut(BaseModel):
    """Badcase + its full audit log."""

    model_config = ConfigDict(populate_by_name=True)

    badcase: dict[str, Any]
    review_actions: List[dict[str, Any]] = Field(default_factory=list, alias="reviewActions")


class _ListOut(BaseModel):
    items: List[dict[str, Any]]
    page: int
    page_size: int = Field(alias="pageSize")


class _PromoteOut(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    badcase: dict[str, Any]
    candidate_path: str = Field(alias="candidatePath")


# ---------------------------------------------------------------------------
# Helpers — row → dict projection
# ---------------------------------------------------------------------------


def _row_to_dict(row: Any) -> dict[str, Any]:
    """Project an ORM ``Badcase`` row to a JSON-safe dict (camelCase)."""
    return {
        "badcaseId": row.badcase_id,
        "type": row.type,
        "severity": row.severity,
        "status": row.status,
        "source": row.source,
        "reviewer": row.reviewer,
        "privacyClass": row.privacy_class,
        "redactionStatus": row.redaction_status,
        "runId": str(row.run_id) if row.run_id else None,
        "traceId": row.trace_id,
        "closureReason": row.closure_reason,
        "closedAt": row.closed_at.isoformat() if row.closed_at else None,
        "createdAt": row.created_at.isoformat() if row.created_at else None,
        "updatedAt": row.updated_at.isoformat() if row.updated_at else None,
    }


def _action_to_dict(row: Any) -> dict[str, Any]:
    """Project an ORM ``BadcaseReviewAction`` row to a JSON-safe dict."""
    return {
        "actionType": row.action_type,
        "actorRole": row.actor_role,
        "reason": row.reason,
        "evidenceRef": row.evidence_ref,
        "createdAt": row.created_at.isoformat() if row.created_at else None,
    }


def _badcase_error_response(err: badcase_service.BadcaseTransitionError) -> dict[str, Any]:
    """Map a ``BadcaseTransitionError`` to a 422-shaped error payload."""
    return {
        "error": err.code,
        "message": str(err),
    }


# ---------------------------------------------------------------------------
# /health (placeholder from T022 — preserved)
# ---------------------------------------------------------------------------


@router.get("/health", status_code=200)
async def health() -> dict[str, str]:
    """Process-local liveness check."""
    return {"status": "ok", "module": "badcases", "stage": "us8"}


# ---------------------------------------------------------------------------
# POST /api/v1/badcases — create
# ---------------------------------------------------------------------------


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_badcase(
    payload: _BadcaseCreateIn,
    db: AsyncSession = Depends(_db_session_with_rls),
    user_id: UUID = Depends(require_reviewer),
) -> dict[str, Any]:
    """Create a new badcase. Auto-generates ``badcaseId`` and the initial
    CREATE review action. Returns ``{badcase, reviewActions}``.
    """
    badcase_id = f"badcase-{uuid4()}"
    row = await repo.create(
        db,
        user_id=user_id,
        badcase_id=badcase_id,
        type=payload.type,
        source=payload.source,
        privacy_class=payload.privacy_class,
        severity=payload.severity,
        reviewer=payload.reviewer,
        redaction_status=payload.redaction_status,
        run_id=payload.run_id,
        trace_id=payload.trace_id,
    )
    await repo.add_review_action(
        db,
        badcase_id=badcase_id,
        action_type="CREATE",
        actor_role="BADCASE_REVIEWER",
        reason=payload.reviewer or "unknown",
        evidence_ref=None,
    )
    actions = await repo.list_review_actions(db, badcase_id=badcase_id)
    return {"badcase": _row_to_dict(row), "reviewActions": [_action_to_dict(a) for a in actions]}


# ---------------------------------------------------------------------------
# GET /api/v1/badcases — list
# ---------------------------------------------------------------------------


@router.get("")
async def list_badcases(
    status_filter: Optional[str] = Query(default=None, alias="status"),
    type_filter: Optional[str] = Query(default=None, alias="type"),
    severity_filter: Optional[str] = Query(default=None, alias="severity"),
    page: int = Query(default=1, ge=1),
    page_size: Optional[int] = Query(
        default=None,
        ge=1,
        le=200,
        alias="pageSize",
        description="Page size (1-200). Defaults to 50 when omitted.",
    ),
    page_size_snake: Optional[int] = Query(
        default=None, ge=1, le=200, alias="page_size",
        description="Snake-case alias for pageSize.",
    ),
    db: AsyncSession = Depends(_db_session_with_rls),
    user_id: UUID = Depends(require_reviewer),
) -> dict[str, Any]:
    """List badcases with optional ``status`` / ``type`` / ``severity`` filters.

    Returns ``{items, page, pageSize}``.
    """
    effective_page_size = page_size if page_size is not None else (
        page_size_snake if page_size_snake is not None else 50
    )
    rows = await repo.list_by_status(
        db,
        user_id=user_id,
        status=status_filter,
        type=type_filter,
        severity=severity_filter,
        page=page,
        page_size=effective_page_size,
    )
    return {
        "items": [_row_to_dict(r) for r in rows],
        "page": page,
        "pageSize": effective_page_size,
    }


# ---------------------------------------------------------------------------
# GET /api/v1/badcases/{badcase_id} — read
# ---------------------------------------------------------------------------


@router.get("/{badcase_id}")
async def get_badcase(
    badcase_id: str,
    db: AsyncSession = Depends(_db_session_with_rls),
    user_id: UUID = Depends(require_reviewer),
) -> dict[str, Any]:
    """Read one badcase + its review log."""
    row = await repo.get(db, badcase_id=badcase_id, user_id=user_id)
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"badcase {badcase_id!r} not found",
        )
    actions = await repo.list_review_actions(db, badcase_id=badcase_id)
    return {"badcase": _row_to_dict(row), "reviewActions": [_action_to_dict(a) for a in actions]}


# ---------------------------------------------------------------------------
# POST /api/v1/badcases/{badcase_id}/classify
# ---------------------------------------------------------------------------


@router.post("/{badcase_id}/classify")
async def classify_badcase(
    badcase_id: str,
    payload: _ClassifyIn,
    db: AsyncSession = Depends(_db_session_with_rls),
    user_id: UUID = Depends(require_reviewer),
) -> dict[str, Any]:
    """Re-classify a badcase (changes type/severity + sets status=TRIAGED).

    Appends a CLASSIFY review action.
    """
    row = await repo.get(db, badcase_id=badcase_id, user_id=user_id)
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"badcase {badcase_id!r} not found",
        )
    schema = _to_schema(row)
    try:
        updated = badcase_service.transition(
            schema,
            new_status="TRIAGED",
            reviewer=payload.reviewer,
        )
    except badcase_service.BadcaseTransitionError as err:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=_badcase_error_response(err),
        )
    new_row = await repo.update_status(
        db,
        badcase_id=badcase_id,
        user_id=user_id,
        new_status=updated.status,
        reviewer=updated.reviewer,
        closure_reason=updated.closure_reason,
        closed_at=updated.closed_at,
    )
    # Persist type/severity changes via a tiny SQL update.
    from sqlalchemy import update as _update
    from app.modules.badcases.models import Badcase as _BadcaseModel
    await db.execute(
        _update(_BadcaseModel)
        .where(_BadcaseModel.badcase_id == badcase_id)
        .values(type=payload.type, severity=payload.severity)
    )
    await repo.add_review_action(
        db,
        badcase_id=badcase_id,
        action_type="CLASSIFY",
        actor_role="BADCASE_REVIEWER",
        reason=f"type={payload.type}, severity={payload.severity}",
        evidence_ref=None,
    )
    refreshed = await repo.get(db, badcase_id=badcase_id, user_id=user_id)
    actions = await repo.list_review_actions(db, badcase_id=badcase_id)
    return {
        "badcase": _row_to_dict(refreshed),
        "reviewActions": [_action_to_dict(a) for a in actions],
    }


# ---------------------------------------------------------------------------
# POST /api/v1/badcases/{badcase_id}/close
# ---------------------------------------------------------------------------


@router.post("/{badcase_id}/close")
async def close_badcase(
    badcase_id: str,
    payload: _CloseIn,
    db: AsyncSession = Depends(_db_session_with_rls),
    user_id: UUID = Depends(require_reviewer),
) -> dict[str, Any]:
    """Close a badcase (sets status=CLOSED + closure_reason + closed_at).

    Appends a CLOSE review action.
    """
    row = await repo.get(db, badcase_id=badcase_id, user_id=user_id)
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"badcase {badcase_id!r} not found",
        )
    schema = _to_schema(row)
    closed_at = datetime.now(timezone.utc)
    try:
        updated = badcase_service.transition(
            schema,
            new_status="CLOSED",
            reviewer=payload.reviewer,
            closure_reason=payload.closure_reason,
            evidence_ref=payload.evidence_ref,
            closed_at=closed_at,
        )
    except badcase_service.BadcaseTransitionError as err:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=_badcase_error_response(err),
        )
    await repo.update_status(
        db,
        badcase_id=badcase_id,
        user_id=user_id,
        new_status=updated.status,
        reviewer=updated.reviewer,
        closure_reason=updated.closure_reason,
        closed_at=updated.closed_at,
    )
    await repo.add_review_action(
        db,
        badcase_id=badcase_id,
        action_type="CLOSE",
        actor_role="BADCASE_REVIEWER",
        reason=payload.closure_reason,
        evidence_ref=payload.evidence_ref,
    )
    refreshed = await repo.get(db, badcase_id=badcase_id, user_id=user_id)
    actions = await repo.list_review_actions(db, badcase_id=badcase_id)
    return {
        "badcase": _row_to_dict(refreshed),
        "reviewActions": [_action_to_dict(a) for a in actions],
    }


# ---------------------------------------------------------------------------
# POST /api/v1/badcases/{badcase_id}/reject
# ---------------------------------------------------------------------------


@router.post("/{badcase_id}/reject")
async def reject_badcase(
    badcase_id: str,
    payload: _RejectIn,
    db: AsyncSession = Depends(_db_session_with_rls),
    user_id: UUID = Depends(require_reviewer),
) -> dict[str, Any]:
    """Reject a badcase (sets status=REJECTED + reason + closed_at).

    Appends a REJECT review action.
    """
    row = await repo.get(db, badcase_id=badcase_id, user_id=user_id)
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"badcase {badcase_id!r} not found",
        )
    schema = _to_schema(row)
    closed_at = datetime.now(timezone.utc)
    try:
        updated = badcase_service.transition(
            schema,
            new_status="REJECTED",
            reviewer=payload.reviewer,
            reason=payload.reason,
            closed_at=closed_at,
        )
    except badcase_service.BadcaseTransitionError as err:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=_badcase_error_response(err),
        )
    await repo.update_status(
        db,
        badcase_id=badcase_id,
        user_id=user_id,
        new_status=updated.status,
        reviewer=updated.reviewer,
        closure_reason=updated.closure_reason,
        closed_at=updated.closed_at,
    )
    await repo.add_review_action(
        db,
        badcase_id=badcase_id,
        action_type="REJECT",
        actor_role="BADCASE_REVIEWER",
        reason=payload.reason,
        evidence_ref=None,
    )
    refreshed = await repo.get(db, badcase_id=badcase_id, user_id=user_id)
    actions = await repo.list_review_actions(db, badcase_id=badcase_id)
    return {
        "badcase": _row_to_dict(refreshed),
        "reviewActions": [_action_to_dict(a) for a in actions],
    }


# ---------------------------------------------------------------------------
# POST /api/v1/badcases/{badcase_id}/promote
# ---------------------------------------------------------------------------


@router.post("/{badcase_id}/promote")
async def promote_badcase(
    badcase_id: str,
    payload: _PromoteIn,
    db: AsyncSession = Depends(_db_session_with_rls),
    user_id: UUID = Depends(require_reviewer),
) -> dict[str, Any]:
    """Promote a badcase to a golden-case candidate.

    Writes a ``<badcase_id>.candidate.json`` to the configured golden
    directory and appends a ``PROMOTE_CANDIDATE`` review action.
    Does NOT refresh the eval baseline — that lives in the US5
    override-record flow.
    """
    row = await repo.get(db, badcase_id=badcase_id, user_id=user_id)
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"badcase {badcase_id!r} not found",
        )
    candidate_path = promote_to_golden_candidate(
        row,
        redaction_audit_id=payload.redaction_audit_id,
        reviewer=payload.reviewer,
        reason=payload.reason,
    )
    await repo.add_review_action(
        db,
        badcase_id=badcase_id,
        action_type="PROMOTE_CANDIDATE",
        actor_role="BADCASE_REVIEWER",
        reason=payload.reason,
        evidence_ref=payload.redaction_audit_id,
    )
    refreshed = await repo.get(db, badcase_id=badcase_id, user_id=user_id)
    actions = await repo.list_review_actions(db, badcase_id=badcase_id)
    return {
        "badcase": _row_to_dict(refreshed),
        "candidatePath": str(candidate_path),
        "reviewActions": [_action_to_dict(a) for a in actions],
    }


# ---------------------------------------------------------------------------
# ORM → Pydantic schema helper
# ---------------------------------------------------------------------------


def _to_schema(row: Any) -> BadcaseSchema:
    """Project an ORM row to the Pydantic ``Badcase`` value object."""
    return BadcaseSchema(
        badcase_id=row.badcase_id,
        type=row.type,
        severity=row.severity,
        status=row.status,
        source=row.source,
        reviewer=row.reviewer,
        privacy_class=row.privacy_class,
        redaction_status=row.redaction_status,
        run_id=row.run_id,
        trace_id=row.trace_id,
        closure_reason=row.closure_reason,
        closed_at=row.closed_at,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


__all__ = ["require_reviewer", "router"]