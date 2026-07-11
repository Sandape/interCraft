"""REQ-033 / REQ-061 badcase repository.

Async CRUD for ``badcases``, ``badcase_review_actions``, and US10
companion tables. Callers must set ``app.user_id`` GUC when RLS applies.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.ids import new_uuid_v7
from app.modules.badcases.models import (
    Badcase,
    BadcaseClosureEvidence,
    BadcaseReviewAction,
)

logger = structlog.get_logger(__name__)


async def create(
    session: AsyncSession,
    *,
    user_id: UUID,
    badcase_id: str,
    type: str,
    source: str,
    privacy_class: str,
    severity: str = "MEDIUM",
    status: str = "OPEN",
    reviewer: str | None = None,
    redaction_status: str = "NOT_REQUIRED",
    run_id: UUID | None = None,
    trace_id: str | None = None,
    closure_reason: str | None = None,
    closed_at: datetime | None = None,
    category: str | None = None,
    owner: str | None = None,
    capabilities: list[str] | None = None,
    first_seen_at: datetime | None = None,
    last_seen_at: datetime | None = None,
    point_treatment_status: str = "unknown",
    sla_status: str = "within_sla",
    sla_due_at: datetime | None = None,
    user_visible_status: str | None = None,
    root_cause_summary: str | None = None,
    reproduction_summary: str | None = None,
    data_completeness: str = "partial",
    merged_into_badcase_id: str | None = None,
    recurrence_of_badcase_id: str | None = None,
    closure_evidence: dict[str, Any] | None = None,
    version: int = 1,
) -> Badcase:
    """INSERT one Badcase row and return the persisted ORM instance."""
    now = datetime.utcnow()
    row = Badcase(
        id=new_uuid_v7(),
        user_id=user_id,
        badcase_id=badcase_id,
        type=type,
        severity=severity,
        status=status,
        source=source,
        reviewer=reviewer,
        privacy_class=privacy_class,
        redaction_status=redaction_status,
        run_id=run_id,
        trace_id=trace_id,
        closure_reason=closure_reason,
        closed_at=closed_at,
        version=version,
        category=category,
        owner=owner,
        capabilities=list(capabilities or []),
        first_seen_at=first_seen_at or now,
        last_seen_at=last_seen_at or now,
        point_treatment_status=point_treatment_status,
        sla_status=sla_status,
        sla_due_at=sla_due_at,
        user_visible_status=user_visible_status,
        root_cause_summary=root_cause_summary,
        reproduction_summary=reproduction_summary,
        data_completeness=data_completeness,
        merged_into_badcase_id=merged_into_badcase_id,
        recurrence_of_badcase_id=recurrence_of_badcase_id,
        closure_evidence=dict(closure_evidence or {}),
    )
    session.add(row)
    await session.flush()
    logger.info(
        "badcase.created",
        badcase_id=badcase_id,
        user_id=str(user_id),
        type=type,
        severity=severity,
        source=source,
    )
    return row


async def get(
    session: AsyncSession, *, badcase_id: str, user_id: UUID | None = None
) -> Badcase | None:
    """Return the Badcase with ``badcase_id`` (optionally scoped to user)."""
    stmt = select(Badcase).where(Badcase.badcase_id == badcase_id)
    if user_id is not None:
        stmt = stmt.where(Badcase.user_id == user_id)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def get_by_id_any_user(
    session: AsyncSession, *, badcase_id: str
) -> Badcase | None:
    return await get(session, badcase_id=badcase_id, user_id=None)


async def list_by_status(
    session: AsyncSession,
    *,
    user_id: UUID | None = None,
    status: str | None = None,
    type: str | None = None,
    severity: str | None = None,
    category: str | None = None,
    owner: str | None = None,
    source: str | None = None,
    privacy_class: str | None = None,
    point_treatment_status: str | None = None,
    sla_status: str | None = None,
    capability: str | None = None,
    page: int = 1,
    page_size: int = 50,
    cursor: str | None = None,
    limit: int | None = None,
) -> list[Badcase]:
    """SELECT badcases with optional filters + pagination/cursor."""
    if limit is not None:
        page_size = max(1, min(int(limit), 200))
        page = 1
    else:
        page = max(1, int(page))
        page_size = max(1, min(int(page_size), 200))
    offset = (page - 1) * page_size

    stmt = select(Badcase)
    if user_id is not None:
        stmt = stmt.where(Badcase.user_id == user_id)
    if status:
        stmt = stmt.where(Badcase.status == status)
    if type:
        stmt = stmt.where(Badcase.type == type)
    if severity:
        stmt = stmt.where(Badcase.severity == severity)
    if category:
        stmt = stmt.where(Badcase.category == category)
    if owner:
        stmt = stmt.where(Badcase.owner == owner)
    if source:
        stmt = stmt.where(Badcase.source == source)
    if privacy_class:
        stmt = stmt.where(Badcase.privacy_class == privacy_class)
    if point_treatment_status:
        stmt = stmt.where(Badcase.point_treatment_status == point_treatment_status)
    if sla_status:
        stmt = stmt.where(Badcase.sla_status == sla_status)
    if capability:
        stmt = stmt.where(Badcase.capabilities.contains([capability]))
    if cursor:
        stmt = stmt.where(Badcase.badcase_id < cursor)

    stmt = stmt.order_by(Badcase.created_at.desc(), Badcase.badcase_id.desc())
    stmt = stmt.limit(page_size).offset(offset if cursor is None else 0)
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def list_all(
    session: AsyncSession,
    *,
    user_id: UUID,
    status: str | None = None,
    page: int = 1,
    page_size: int = 50,
) -> list[Badcase]:
    return await list_by_status(
        session,
        user_id=user_id,
        status=status,
        page=page,
        page_size=page_size,
    )


async def update_status(
    session: AsyncSession,
    *,
    badcase_id: str,
    user_id: UUID | None = None,
    new_status: str,
    reviewer: str | None = None,
    closure_reason: str | None = None,
    closed_at: datetime | None = None,
    redaction_status: str | None = None,
    bump_version: bool = True,
) -> Badcase | None:
    row = await get(session, badcase_id=badcase_id, user_id=user_id)
    if row is None:
        return None
    row.status = new_status
    if reviewer is not None:
        row.reviewer = reviewer
    if closure_reason is not None:
        row.closure_reason = closure_reason
    if closed_at is not None:
        row.closed_at = closed_at
    if redaction_status is not None:
        row.redaction_status = redaction_status
    if bump_version:
        row.version = int(getattr(row, "version", 1) or 1) + 1
    row.updated_at = datetime.utcnow()
    await session.flush()
    logger.info(
        "badcase.status_updated",
        badcase_id=badcase_id,
        new_status=new_status,
        reviewer=reviewer,
    )
    return row


async def save(session: AsyncSession, row: Badcase) -> Badcase:
    row.updated_at = datetime.utcnow()
    await session.flush()
    return row


async def add_review_action(
    session: AsyncSession,
    *,
    badcase_id: str,
    action_type: str,
    actor_role: str = "BADCASE_REVIEWER",
    reason: str | None = None,
    evidence_ref: str | None = None,
    actor: str | None = None,
    from_status: str | None = None,
    to_status: str | None = None,
    expected_version: int | None = None,
    resulting_version: int | None = None,
    idempotency_key: str | None = None,
    payload: dict[str, Any] | None = None,
    evidence_refs: list[Any] | None = None,
) -> BadcaseReviewAction:
    """Append one row to the badcase lifecycle audit log."""
    row = BadcaseReviewAction(
        id=new_uuid_v7(),
        badcase_id=badcase_id,
        action_type=action_type,
        actor_role=actor_role,
        reason=reason,
        evidence_ref=evidence_ref,
        actor=actor,
        from_status=from_status,
        to_status=to_status,
        expected_version=expected_version,
        resulting_version=resulting_version,
        idempotency_key=idempotency_key,
        payload=dict(payload or {}),
        evidence_refs=list(evidence_refs or []),
    )
    session.add(row)
    await session.flush()
    logger.info(
        "badcase.review_action",
        badcase_id=badcase_id,
        action_type=action_type,
        actor_role=actor_role,
    )
    return row


async def find_action_by_idempotency(
    session: AsyncSession, *, idempotency_key: str
) -> BadcaseReviewAction | None:
    stmt = select(BadcaseReviewAction).where(
        BadcaseReviewAction.idempotency_key == idempotency_key
    )
    return (await session.execute(stmt)).scalar_one_or_none()


async def add_evidence(
    session: AsyncSession,
    *,
    badcase_id: str,
    action_type: str,
    actor_role: str = "BADCASE_REVIEWER",
    reason: str | None = None,
    evidence_ref: str | None = None,
) -> BadcaseReviewAction:
    return await add_review_action(
        session,
        badcase_id=badcase_id,
        action_type=action_type,
        actor_role=actor_role,
        reason=reason,
        evidence_ref=evidence_ref,
    )


async def list_review_actions(
    session: AsyncSession,
    *,
    badcase_id: str,
) -> list[BadcaseReviewAction]:
    stmt = (
        select(BadcaseReviewAction)
        .where(BadcaseReviewAction.badcase_id == badcase_id)
        .order_by(BadcaseReviewAction.created_at.asc())
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def upsert_closure_evidence(
    session: AsyncSession,
    *,
    badcase_id: str,
    fix_or_policy_version: str | None = None,
    regression_case_ref: str | None = None,
    passing_evaluation_ref: str | None = None,
    point_treatment_ref: str | None = None,
    user_notification_ref: str | None = None,
) -> BadcaseClosureEvidence:
    stmt = select(BadcaseClosureEvidence).where(
        BadcaseClosureEvidence.badcase_id == badcase_id
    )
    row = (await session.execute(stmt)).scalar_one_or_none()
    if row is None:
        row = BadcaseClosureEvidence(
            id=new_uuid_v7(),
            badcase_id=badcase_id,
        )
        session.add(row)
    if fix_or_policy_version is not None:
        row.fix_or_policy_version = fix_or_policy_version
    if regression_case_ref is not None:
        row.regression_case_ref = regression_case_ref
    if passing_evaluation_ref is not None:
        row.passing_evaluation_ref = passing_evaluation_ref
    if point_treatment_ref is not None:
        row.point_treatment_ref = point_treatment_ref
    if user_notification_ref is not None:
        row.user_notification_ref = user_notification_ref
    row.complete = all(
        [
            row.fix_or_policy_version,
            row.regression_case_ref,
            row.passing_evaluation_ref,
            row.point_treatment_ref,
            row.user_notification_ref,
        ]
    )
    row.updated_at = datetime.utcnow()
    await session.flush()
    return row


async def get_closure_evidence(
    session: AsyncSession, *, badcase_id: str
) -> BadcaseClosureEvidence | None:
    stmt = select(BadcaseClosureEvidence).where(
        BadcaseClosureEvidence.badcase_id == badcase_id
    )
    return (await session.execute(stmt)).scalar_one_or_none()


def build_promotion_audit_row(
    *,
    badcase_id: str,
    lifecycle: str,
    dataset_version: str,
    export_policy_decision_id: str | None = None,
    reviewer: str,
    reason: str,
) -> dict[str, Any]:
    return {
        "badcase_id": badcase_id,
        "action_type": "PROMOTE_CANDIDATE",
        "actor_role": "BADCASE_REVIEWER",
        "reason": reason,
        "evidence_ref": export_policy_decision_id,
        "metadata": {
            "lifecycle": lifecycle,
            "dataset_version": dataset_version,
            "reviewer": reviewer,
        },
    }


def orm_required_fields() -> frozenset[str]:
    """Fields the ORM must expose to match migration 0024 + 0060 (T126)."""
    return frozenset(
        {
            "id",
            "badcase_id",
            "user_id",
            "type",
            "severity",
            "status",
            "source",
            "reviewer",
            "privacy_class",
            "redaction_status",
            "run_id",
            "trace_id",
            "closure_reason",
            "closed_at",
            "version",
            "category",
            "owner",
            "capabilities",
            "first_seen_at",
            "last_seen_at",
            "point_treatment_status",
            "sla_status",
            "closure_evidence",
            "created_at",
            "updated_at",
        }
    )


__all__ = [
    "add_evidence",
    "add_review_action",
    "build_promotion_audit_row",
    "create",
    "find_action_by_idempotency",
    "get",
    "get_by_id_any_user",
    "get_closure_evidence",
    "list_all",
    "list_by_status",
    "list_review_actions",
    "orm_required_fields",
    "save",
    "update_status",
    "upsert_closure_evidence",
]
