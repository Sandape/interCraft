"""REQ-061 US10 — Bad Case intake from feedback / quality / points / incidents (T133)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.badcases import repository as repo
from app.modules.badcases.impact import upsert_impact

INTAKE_SOURCES = frozenset(
    {
        "USER_FEEDBACK",
        "EVAL_FAILURE",
        "QUALITY_GATE",
        "SAFETY_FAILURE",
        "POINT_ANOMALY",
        "INCIDENT",
        "MANUAL_INSPECTION",
        "MANUAL_ENTRY",
    }
)

_SEVERITY_BY_SOURCE = {
    "SAFETY_FAILURE": "P0",
    "POINT_ANOMALY": "P1",
    "QUALITY_GATE": "P1",
    "EVAL_FAILURE": "P2",
    "USER_FEEDBACK": "P2",
    "INCIDENT": "P1",
    "MANUAL_INSPECTION": "P3",
    "MANUAL_ENTRY": "P3",
}

_SLA_HOURS = {"P0": 0.25, "P1": 1.0, "P2": 48.0, "P3": 168.0}


def _sla_due(severity: str, now: datetime) -> datetime | None:
    hours = _SLA_HOURS.get(severity)
    if hours is None:
        return None
    return now + timedelta(hours=hours)


def _map_type(source: str, category: str | None) -> str:
    if category and category.upper() in {
        "RESUME_DIAGNOSIS_QUALITY",
        "MOCK_INTERVIEW_QUALITY",
        "AI_RELIABILITY",
        "AI_COST_LATENCY",
        "PRODUCT_FUNNEL_UX",
        "DATA_QUALITY",
        "PRIVACY_REDACTION",
        "EVAL_REGRESSION",
    }:
        return category.upper()
    if source in {"EVAL_FAILURE", "QUALITY_GATE"}:
        return "EVAL_REGRESSION"
    if source == "SAFETY_FAILURE":
        return "PRIVACY_REDACTION"
    if source == "POINT_ANOMALY":
        return "AI_COST_LATENCY"
    return "DATA_QUALITY"


async def intake_badcase(
    session: AsyncSession,
    *,
    user_id: UUID,
    source: str,
    category: str | None = None,
    severity: str | None = None,
    privacy_class: str = "INTERNAL_METADATA",
    capability: str | None = None,
    task_id: str | None = None,
    feedback_ref: str | None = None,
    point_event_ref: str | None = None,
    incident_ref: str | None = None,
    reason: str | None = None,
    content_authorized: bool = False,
    actor: str = "AUTOMATION",
) -> dict[str, Any]:
    """Create or link a Bad Case from an intake signal.

    Metadata-only feedback is always accepted even when
    ``content_authorized`` is False (FR-111).
    """
    src = source.upper()
    if src not in INTAKE_SOURCES and src not in {
        "EVAL_FAILURE",
        "STAGING_TRACE",
        "USER_FEEDBACK",
        "PM_REVIEW",
        "MANUAL_ENTRY",
    }:
        # Normalize unknown automation sources into MANUAL_ENTRY bucket for DB CHECK
        mapped_source = "MANUAL_ENTRY"
    else:
        # Map 061 intake sources onto 033 CHECK-compatible source values
        source_map = {
            "QUALITY_GATE": "EVAL_FAILURE",
            "SAFETY_FAILURE": "EVAL_FAILURE",
            "POINT_ANOMALY": "PM_REVIEW",
            "INCIDENT": "PM_REVIEW",
            "MANUAL_INSPECTION": "MANUAL_ENTRY",
        }
        mapped_source = source_map.get(src, src if src in {
            "EVAL_FAILURE",
            "STAGING_TRACE",
            "USER_FEEDBACK",
            "PM_REVIEW",
            "MANUAL_ENTRY",
        } else "MANUAL_ENTRY")

    now = datetime.now(timezone.utc)
    sev = severity or _SEVERITY_BY_SOURCE.get(src, "P2")
    # Persist P-severity when allowed by 0060 CHECK; fall back for pre-migration
    persist_severity = sev if sev.startswith("P") else sev
    bc_type = _map_type(src, category)
    badcase_id = f"badcase-{uuid4()}"
    caps = [capability] if capability else []

    row = await repo.create(
        session,
        user_id=user_id,
        badcase_id=badcase_id,
        type=bc_type,
        source=mapped_source,
        privacy_class=privacy_class if privacy_class in {
            "PUBLIC_METADATA",
            "INTERNAL_METADATA",
            "SENSITIVE_USER_CONTENT",
            "SECRET",
            "REDACTED_SUMMARY",
            "UNKNOWN",
        } else "INTERNAL_METADATA",
        severity=persist_severity if persist_severity in {
            "LOW", "MEDIUM", "HIGH", "CRITICAL", "P0", "P1", "P2", "P3"
        } else "MEDIUM",
        status="OPEN",
        reviewer=None,
        category=category or src.lower(),
        owner=None,
        capabilities=caps,
        first_seen_at=now,
        last_seen_at=now,
        point_treatment_status="pending" if point_event_ref else "not_required",
        sla_status="within_sla",
        sla_due_at=_sla_due(sev, now),
        user_visible_status="已提交",
        data_completeness="partial",
    )

    await repo.add_review_action(
        session,
        badcase_id=badcase_id,
        action_type="INTAKE",
        actor_role="AUTOMATION",
        actor=actor,
        reason=reason or f"intake from {src}",
        from_status=None,
        to_status="OPEN",
        expected_version=1,
        resulting_version=1,
        payload={
            "intake_source": src,
            "feedback_ref": feedback_ref,
            "task_id": task_id,
            "incident_ref": incident_ref,
            "content_authorized": content_authorized,
        },
    )

    if task_id:
        await upsert_impact(
            session,
            badcase_id=badcase_id,
            impact_kind="task",
            subject_ref=str(task_id),
            confidence="confirmed",
            actor=actor,
            update_reason="intake",
            user_id=user_id,
        )
    if point_event_ref:
        await upsert_impact(
            session,
            badcase_id=badcase_id,
            impact_kind="point_event",
            subject_ref=str(point_event_ref),
            confidence="possible",
            actor=actor,
            update_reason="intake",
            user_id=user_id,
        )

    if content_authorized:
        from app.modules.badcases.evidence import grant_content_authorization

        await grant_content_authorization(
            session,
            badcase_id=badcase_id,
            owner_user_id=user_id,
            purpose="badcase_review",
            permitted_content_classes=["user_content"],
            permitted_fields=["input_snapshot", "output_snapshot"],
            privacy_class="restricted",
        )

    return {
        "badcase_id": badcase_id,
        "status": row.status,
        "severity": row.severity,
        "source": mapped_source,
        "intake_source": src,
        "content_authorized": content_authorized,
        "version": int(getattr(row, "version", 1) or 1),
        "sla_due_at": row.sla_due_at.isoformat() if getattr(row, "sla_due_at", None) else None,
    }


__all__ = ["INTAKE_SOURCES", "intake_badcase"]
