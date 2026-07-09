"""REQ-033 US8 — badcase repository (T060).

Async CRUD + search helpers for the ``badcases`` and
``badcase_review_actions`` tables. Mirrors the
``telemetry_contracts.repository`` style (thin wrapper over
``AsyncSession``; caller is responsible for setting the
``app.user_id`` GUC before invoking these helpers).

Functions:

- :func:`create` — INSERT a new badcase row.
- :func:`get` — SELECT by ``badcase_id``.
- :func:`list_by_status` — SELECT with status + optional type/severity
  filters + pagination.
- :func:`update_status` — UPDATE status + closure fields.
- :func:`add_evidence` — convenience for adding an evidence review
  action (CLOSE / OVERRIDE / BASELINE_REFRESH).
- :func:`add_review_action` — append a row to the audit log.

The schema created by migration 0024 enables per-user RLS on
``badcases`` and a parent-EXISTS policy on
``badcase_review_actions``. Tests must set ``app.user_id`` via
``app.core.db.set_user_guc_for_session`` BEFORE calling these helpers.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.ids import new_uuid_v7
from app.modules.badcases.models import Badcase, BadcaseReviewAction

logger = structlog.get_logger(__name__)


# ── badcases ─────────────────────────────────────────────────────────────────


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
) -> Badcase:
    """INSERT one Badcase row and return the persisted ORM instance."""
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
    session: AsyncSession, *, badcase_id: str, user_id: UUID
) -> Badcase | None:
    """Return the Badcase with ``badcase_id`` for ``user_id``, or None."""
    stmt = select(Badcase).where(
        Badcase.badcase_id == badcase_id,
        Badcase.user_id == user_id,
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def list_by_status(
    session: AsyncSession,
    *,
    user_id: UUID,
    status: str | None = None,
    type: str | None = None,
    severity: str | None = None,
    page: int = 1,
    page_size: int = 50,
) -> list[Badcase]:
    """SELECT badcases with optional status / type / severity filters.

    Pagination uses 1-indexed ``page`` and ``page_size`` (default 50).
    Ordered by ``created_at DESC`` so fresh badcases surface first.
    """
    page = max(1, int(page))
    page_size = max(1, min(int(page_size), 200))
    offset = (page - 1) * page_size

    stmt = select(Badcase).where(Badcase.user_id == user_id)
    if status:
        stmt = stmt.where(Badcase.status == status)
    if type:
        stmt = stmt.where(Badcase.type == type)
    if severity:
        stmt = stmt.where(Badcase.severity == severity)
    stmt = stmt.order_by(Badcase.created_at.desc()).limit(page_size).offset(offset)
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
    """Same as ``list_by_status`` but without type/severity filters.

    The API exposes ``status`` / ``type`` / ``severity`` query params;
    the CLI exposes only ``status``. Both share this lower-level
    helper.
    """
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
    user_id: UUID,
    new_status: str,
    reviewer: str | None = None,
    closure_reason: str | None = None,
    closed_at: datetime | None = None,
    redaction_status: str | None = None,
) -> Badcase | None:
    """UPDATE the badcase's status (and optional closure / redaction fields).

    Returns the updated row, or ``None`` if no matching row exists for
    ``user_id``. The caller is responsible for ensuring the FSM
    transition is valid (see ``app.modules.badcases.service``).
    """
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
    await session.flush()
    logger.info(
        "badcase.status_updated",
        badcase_id=badcase_id,
        new_status=new_status,
        reviewer=reviewer,
    )
    return row


# ── badcase_review_actions ──────────────────────────────────────────────────


async def add_review_action(
    session: AsyncSession,
    *,
    badcase_id: str,
    action_type: str,
    actor_role: str = "BADCASE_REVIEWER",
    reason: str | None = None,
    evidence_ref: str | None = None,
) -> BadcaseReviewAction:
    """Append one row to the badcase lifecycle audit log."""
    row = BadcaseReviewAction(
        id=new_uuid_v7(),
        badcase_id=badcase_id,
        action_type=action_type,
        actor_role=actor_role,
        reason=reason,
        evidence_ref=evidence_ref,
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


async def add_evidence(
    session: AsyncSession,
    *,
    badcase_id: str,
    action_type: str,
    actor_role: str = "BADCASE_REVIEWER",
    reason: str | None = None,
    evidence_ref: str | None = None,
) -> BadcaseReviewAction:
    """Alias of :func:`add_review_action` kept for semantic clarity."""
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
    """Return all review actions for ``badcase_id``, ordered chronologically."""
    stmt = (
        select(BadcaseReviewAction)
        .where(BadcaseReviewAction.badcase_id == badcase_id)
        .order_by(BadcaseReviewAction.created_at.asc())
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


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


__all__ = [
    "add_evidence",
    "add_review_action",
    "build_promotion_audit_row",
    "create",
    "get",
    "list_all",
    "list_by_status",
    "list_review_actions",
    "update_status",
]
