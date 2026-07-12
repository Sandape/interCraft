"""REQ-061 US10 — canonical operational Bad Case facade helpers.

Mounted at ``/api/v1/admin-console/ai/badcases`` (OpenAPI server base).
Legacy ``/api/v1/admin-console/badcases`` and ``/api/v1/badcases`` remain.
"""
from __future__ import annotations

from typing import Annotated, Any
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user_id_optional as _resolve_user_id_from_jwt
from app.core.db import get_db_session_no_rls, set_rls_user_id
from app.modules.admin_console.auth import require_admin
from app.modules.auth.ai_capabilities import AIAdminCapability, has_ai_admin_capability
from app.modules.badcases import repository as repo
from app.modules.badcases.impact import impact_to_dict, list_impacts
from app.modules.badcases.service import (
    BadcaseCommandError,
    badcase_summary,
    data_quality_block,
    execute_review_command,
)

log = structlog.get_logger(__name__)

operational_badcases_router = APIRouter()


class CompatibilityLinks(BaseModel):
    model_config = ConfigDict(extra="forbid")

    legacy_admin_badcases: str = "/api/v1/admin-console/badcases"
    legacy_domain_badcases: str = "/api/v1/badcases"
    canonical: str = "/api/v1/admin-console/ai/badcases"


COMPAT = CompatibilityLinks()


async def _session() -> Any:
    async for s in get_db_session_no_rls():
        yield s


def _require_quality_capability(roles: list[str] | None = None) -> None:
    roles = roles or ["admin"]
    if not has_ai_admin_capability(
        roles=roles, capability=AIAdminCapability.QUALITY_BADCASE_MANAGE.value
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": "missing_capability",
                "capability": AIAdminCapability.QUALITY_BADCASE_MANAGE.value,
            },
        )


@operational_badcases_router.get("/badcases/compatibility")
async def badcase_compatibility_links(
    _user_id: Annotated[UUID, Depends(_resolve_user_id_from_jwt)],
    _cap: Annotated[bool, Depends(require_admin)],
) -> CompatibilityLinks:
    """Explicit compatibility map for legacy consumers (T134)."""
    return COMPAT


@operational_badcases_router.get("/badcases")
async def list_operational_badcases(
    _user_id: Annotated[UUID, Depends(_resolve_user_id_from_jwt)],
    _cap: Annotated[bool, Depends(require_admin)],
    session: Annotated[AsyncSession, Depends(_session)],
    status_filter: str | None = Query(None, alias="status"),
    severity: str | None = None,
    category: str | None = None,
    capability: str | None = None,
    owner: str | None = None,
    source: str | None = None,
    privacy_class: str | None = None,
    point_treatment_status: str | None = None,
    sla_status: str | None = None,
    cursor: str | None = None,
    limit: int = Query(20, ge=1, le=100),
) -> dict[str, Any]:
    _require_quality_capability()
    rows = await repo.list_by_status(
        session,
        status=status_filter,
        severity=severity,
        category=category,
        owner=owner,
        source=source,
        privacy_class=privacy_class,
        point_treatment_status=point_treatment_status,
        sla_status=sla_status,
        capability=capability,
        cursor=cursor,
        limit=limit + 1,
    )
    next_cursor = None
    if len(rows) > limit:
        rows = rows[:limit]
        next_cursor = rows[-1].badcase_id
    return {
        "items": [badcase_summary(r) for r in rows],
        "next_cursor": next_cursor,
        "data_quality": data_quality_block(),
        "compatibility": COMPAT.model_dump(),
    }


@operational_badcases_router.get("/badcases/{badcase_id}")
async def get_operational_badcase(
    badcase_id: str,
    _user_id: Annotated[UUID, Depends(_resolve_user_id_from_jwt)],
    _cap: Annotated[bool, Depends(require_admin)],
    session: Annotated[AsyncSession, Depends(_session)],
) -> dict[str, Any]:
    _require_quality_capability()
    row = await repo.get_by_id_any_user(session, badcase_id=badcase_id)
    if row is None:
        raise HTTPException(status_code=404, detail={"error": "badcase_not_found"})
    actions = await repo.list_review_actions(session, badcase_id=badcase_id)
    impacts, _ = await list_impacts(session, badcase_id=badcase_id, limit=50)
    closure = await repo.get_closure_evidence(session, badcase_id=badcase_id)
    return {
        "badcase": badcase_summary(row),
        "user_visible_status": row.user_visible_status or "已提交",
        "root_cause": {"summary": row.root_cause_summary},
        "reproduction": {"summary": row.reproduction_summary},
        "affected_scope_summary": {
            "impact_count": len(impacts),
            "unknown_count": sum(1 for i in impacts if i.confidence == "unknown"),
        },
        "related_tasks": [
            impact_to_dict(i) for i in impacts if i.impact_kind == "task"
        ],
        "related_feedback": [],
        "behavior_versions": {},
        "privacy": {
            "privacy_class": badcase_summary(row)["privacy_class"],
            "redaction_status": row.redaction_status,
        },
        "owner_and_sla": {
            "owner": row.owner,
            "sla_status": row.sla_status,
            "sla_due_at": row.sla_due_at.isoformat() if row.sla_due_at else None,
        },
        "fix": {
            "fix_or_policy_version": (
                closure.fix_or_policy_version if closure else None
            )
        },
        "regression": {
            "regression_case_ref": closure.regression_case_ref if closure else None
        },
        "point_treatment": {"status": row.point_treatment_status},
        "user_notifications": [],
        "related_incidents": [],
        "data_quality": data_quality_block(),
        "compatibility": COMPAT.model_dump(),
        "action_count": len(actions),
    }


@operational_badcases_router.get("/badcases/{badcase_id}/timeline")
async def list_operational_timeline(
    badcase_id: str,
    _user_id: Annotated[UUID, Depends(_resolve_user_id_from_jwt)],
    _cap: Annotated[bool, Depends(require_admin)],
    session: Annotated[AsyncSession, Depends(_session)],
    cursor: str | None = None,
    limit: int = Query(100, ge=1, le=200),
) -> dict[str, Any]:
    _require_quality_capability()
    actions = await repo.list_review_actions(session, badcase_id=badcase_id)
    items = []
    for a in actions:
        items.append(
            {
                "action_id": str(a.id),
                "action_type": a.action_type,
                "occurred_at": a.created_at.isoformat() if a.created_at else None,
                "recorded_at": a.created_at.isoformat() if a.created_at else None,
                "actor": a.actor or a.actor_role,
                "reason": a.reason or "",
                "from_status": a.from_status,
                "to_status": a.to_status,
                "expected_version": int(a.expected_version or 1),
                "resulting_version": int(a.resulting_version or 1),
                "evidence_refs": list(a.evidence_refs or []),
                "privacy_class": "metadata",
            }
        )
    if cursor:
        items = [i for i in items if i["action_id"] > cursor]
    next_cursor = None
    if len(items) > limit:
        items = items[:limit]
        next_cursor = items[-1]["action_id"]
    return {
        "badcase_id": badcase_id,
        "items": items,
        "next_cursor": next_cursor,
        "data_quality": data_quality_block(),
    }


@operational_badcases_router.get("/badcases/{badcase_id}/impacts")
async def list_operational_impacts(
    badcase_id: str,
    _user_id: Annotated[UUID, Depends(_resolve_user_id_from_jwt)],
    _cap: Annotated[bool, Depends(require_admin)],
    session: Annotated[AsyncSession, Depends(_session)],
    impact_kind: str | None = None,
    confidence: str | None = None,
    cursor: str | None = None,
    limit: int = Query(50, ge=1, le=200),
) -> dict[str, Any]:
    _require_quality_capability()
    rows, next_cursor = await list_impacts(
        session,
        badcase_id=badcase_id,
        impact_kind=impact_kind,
        confidence=confidence,
        cursor=cursor,
        limit=limit,
    )
    unknown = sum(1 for r in rows if r.confidence == "unknown")
    return {
        "items": [impact_to_dict(r) for r in rows],
        "next_cursor": next_cursor,
        "data_quality": data_quality_block(unknown_count=unknown),
    }


@operational_badcases_router.get("/badcases/{badcase_id}/actions")
async def list_operational_actions(
    badcase_id: str,
    _user_id: Annotated[UUID, Depends(_resolve_user_id_from_jwt)],
    _cap: Annotated[bool, Depends(require_admin)],
    session: Annotated[AsyncSession, Depends(_session)],
    cursor: str | None = None,
    limit: int = Query(100, ge=1, le=200),
) -> dict[str, Any]:
    _require_quality_capability()
    actions = await repo.list_review_actions(session, badcase_id=badcase_id)
    items = []
    for a in actions:
        items.append(
            {
                "action_id": str(a.id),
                "action_type": a.action_type,
                "occurred_at": a.created_at.isoformat() if a.created_at else None,
                "recorded_at": a.created_at.isoformat() if a.created_at else None,
                "actor": a.actor or a.actor_role,
                "reason": a.reason or "",
                "from_status": a.from_status,
                "to_status": a.to_status,
                "expected_version": int(a.expected_version or 1),
                "resulting_version": int(a.resulting_version or 1),
                "evidence_refs": list(a.evidence_refs or []),
                "privacy_class": "metadata",
            }
        )
    if cursor:
        items = [i for i in items if i["action_id"] > cursor]
    next_cursor = None
    if len(items) > limit:
        items = items[:limit]
        next_cursor = items[-1]["action_id"]
    return {
        "items": items,
        "next_cursor": next_cursor,
        "data_quality": data_quality_block(),
    }


@operational_badcases_router.post("/badcases/{badcase_id}/actions", status_code=201)
async def create_operational_action(
    badcase_id: str,
    body: dict[str, Any],
    user_id: Annotated[UUID, Depends(_resolve_user_id_from_jwt)],
    _cap: Annotated[bool, Depends(require_admin)],
    session: Annotated[AsyncSession, Depends(_session)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> dict[str, Any]:
    _require_quality_capability()
    if not idempotency_key or len(idempotency_key) < 8:
        raise HTTPException(
            status_code=422,
            detail={"error": "idempotency_key_required", "code": "IDEMPOTENCY_KEY_REQUIRED"},
        )
    try:
        await set_rls_user_id(session, user_id)
        receipt = await execute_review_command(
            session,
            badcase_id=badcase_id,
            command=body,
            actor=f"user:{user_id}",
            idempotency_key=idempotency_key,
            user_id=None,  # admin facade is cross-tenant via no-RLS + capability
        )
        await session.commit()
        return receipt
    except BadcaseCommandError as exc:
        await session.rollback()
        code = getattr(exc, "code", "COMMAND_ERROR")
        status_code = (
            status.HTTP_409_CONFLICT
            if code in {"VERSION_CONFLICT", "TERMINAL_STATE", "CLOSURE_EVIDENCE_REQUIRED"}
            else status.HTTP_422_UNPROCESSABLE_ENTITY
        )
        if code == "NOT_FOUND":
            status_code = status.HTTP_404_NOT_FOUND
        raise HTTPException(
            status_code=status_code,
            detail={"error": code, "message": str(exc), "code": code},
        ) from exc


__all__ = ["COMPAT", "CompatibilityLinks", "operational_badcases_router"]
