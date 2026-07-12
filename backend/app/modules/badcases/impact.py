"""REQ-061 US10 — Bad Case impact link helpers (T131)."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.ids import new_uuid_v7
from app.modules.badcases.models import BadcaseImpactLink

IMPACT_KINDS = frozenset(
    {"task", "user", "behavior_version", "point_event", "cost_event"}
)
CONFIDENCES = frozenset({"confirmed", "possible", "excluded", "unknown"})


class ImpactError(ValueError):
    def __init__(self, message: str, *, code: str) -> None:
        super().__init__(message)
        self.code = code


async def upsert_impact(
    session: AsyncSession,
    *,
    badcase_id: str,
    impact_kind: str,
    subject_ref: str,
    confidence: str,
    evidence_refs: list[dict[str, Any]] | None = None,
    actor: str | None = None,
    update_reason: str | None = None,
    user_id: UUID | None = None,
) -> BadcaseImpactLink:
    if impact_kind not in IMPACT_KINDS:
        raise ImpactError(f"invalid impact_kind {impact_kind!r}", code="INVALID_IMPACT_KIND")
    if confidence not in CONFIDENCES:
        raise ImpactError(f"invalid confidence {confidence!r}", code="INVALID_CONFIDENCE")

    stmt = select(BadcaseImpactLink).where(
        BadcaseImpactLink.badcase_id == badcase_id,
        BadcaseImpactLink.impact_kind == impact_kind,
        BadcaseImpactLink.subject_ref == subject_ref,
    )
    existing = (await session.execute(stmt)).scalar_one_or_none()
    now = datetime.now(timezone.utc)
    if existing is None:
        row = BadcaseImpactLink(
            id=new_uuid_v7(),
            badcase_id=badcase_id,
            user_id=user_id,
            impact_kind=impact_kind,
            subject_ref=subject_ref,
            confidence=confidence,
            evidence_refs=list(evidence_refs or []),
            version=1,
            update_reason=update_reason,
            actor=actor,
            first_seen_at=now,
            last_updated_at=now,
        )
        session.add(row)
        await session.flush()
        return row

    # Append-preserving: bump version and retain history via version field
    # (full confidence history is recorded as review actions by the service).
    existing.confidence = confidence
    existing.evidence_refs = list(evidence_refs or existing.evidence_refs or [])
    existing.version = int(existing.version or 1) + 1
    existing.update_reason = update_reason
    existing.actor = actor
    existing.last_updated_at = now
    if user_id is not None:
        existing.user_id = user_id
    await session.flush()
    return existing


async def list_impacts(
    session: AsyncSession,
    *,
    badcase_id: str,
    impact_kind: str | None = None,
    confidence: str | None = None,
    cursor: str | None = None,
    limit: int = 50,
) -> tuple[list[BadcaseImpactLink], str | None]:
    limit = max(1, min(int(limit), 200))
    stmt = select(BadcaseImpactLink).where(BadcaseImpactLink.badcase_id == badcase_id)
    if impact_kind:
        stmt = stmt.where(BadcaseImpactLink.impact_kind == impact_kind)
    if confidence:
        stmt = stmt.where(BadcaseImpactLink.confidence == confidence)
    if cursor:
        # cursor = ISO last_updated_at|id
        stmt = stmt.where(BadcaseImpactLink.id > cursor)  # type: ignore[arg-type]
    stmt = stmt.order_by(
        BadcaseImpactLink.last_updated_at.desc(), BadcaseImpactLink.id.asc()
    ).limit(limit + 1)
    rows = list((await session.execute(stmt)).scalars().all())
    next_cursor: str | None = None
    if len(rows) > limit:
        rows = rows[:limit]
        next_cursor = str(rows[-1].id)
    return rows, next_cursor


def impact_to_dict(row: BadcaseImpactLink) -> dict[str, Any]:
    return {
        "impact_id": str(row.id),
        "impact_kind": row.impact_kind,
        "subject_ref": row.subject_ref,
        "confidence": row.confidence,
        "first_seen_at": row.first_seen_at.isoformat() if row.first_seen_at else None,
        "last_updated_at": (
            row.last_updated_at.isoformat() if row.last_updated_at else None
        ),
        "evidence_refs": list(row.evidence_refs or []),
        "version": int(row.version or 1),
    }


__all__ = [
    "CONFIDENCES",
    "IMPACT_KINDS",
    "ImpactError",
    "impact_to_dict",
    "list_impacts",
    "upsert_impact",
]
