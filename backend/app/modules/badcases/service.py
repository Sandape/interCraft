"""REQ-033 US8 — badcase lifecycle FSM service (T061).

Pure-logic state-transition rules for badcases (data-model.md §State
Transitions). No DB, no network. The API and CLI layers call into
this module so the FSM is enforced in exactly one place.

State machine
-------------

.. code-block:: text

    OPEN -> TRIAGED -> IN_PROGRESS -> AWAITING_VALIDATION -> CLOSED
    OPEN -> REJECTED
    TRIAGED -> REJECTED
    AWAITING_VALIDATION -> IN_PROGRESS   (re-open)

``CLOSED`` and ``REJECTED`` are terminal — no transitions out.

Required fields per target status
---------------------------------

- ``CLOSED`` — ``closure_reason`` + ``evidence_ref`` + ``reviewer`` +
  ``closed_at``. (FR-029)
- ``REJECTED`` — ``reason`` + ``reviewer`` + ``closed_at``. (FR-029)
- ``TRIAGED`` / ``IN_PROGRESS`` / ``AWAITING_VALIDATION`` —
  ``reviewer`` only. (FR-026 / FR-027)

Errors
------

:class:`BadcaseTransitionError` carries a stable ``code`` attribute
the API layer maps to HTTP 422. Codes:

- ``REVIEWER_REQUIRED`` — ``reviewer`` missing for any non-OPEN target.
- ``REASON_REQUIRED`` — ``reason`` missing for ``REJECTED``.
- ``CLOSURE_REASON_REQUIRED`` — missing for ``CLOSED``.
- ``EVIDENCE_REF_REQUIRED`` — missing for ``CLOSED``.
- ``CLOSED_AT_REQUIRED`` — missing for ``CLOSED`` / ``REJECTED``.
- ``INVALID_TRANSITION`` — terminal state or pipeline bypass.
- ``INVALID_STATUS`` — unknown target status.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping, Optional

from app.modules.badcases.schemas import (
    BADCASE_STATUSES,
    Badcase,
    BadcaseReviewAction,
)


# ---------------------------------------------------------------------------
# REQ-033 US7 (T128) — badcase evidence trace linking
# ---------------------------------------------------------------------------


#: Literal sentinel for missing trace_id in badcase evidence_ref.
#: Matches the eval report convention so downstream consumers can
#: treat the field uniformly.
_TRACE_UNAVAILABLE: str = "unavailable"


def capture_current_trace_id() -> str:
    """Return the active OTel trace id hex, or ``"unavailable"``.

    Thin wrapper around the observability helper so service.py does
    not import ``app.observability`` directly (the observability
    module is optional infrastructure — keeping the import inside a
    function makes the service usable in lightweight test contexts).
    """
    try:
        from app.observability.tracing import (
            extract_trace_id_from_span_or_unavailable,
        )

        return extract_trace_id_from_span_or_unavailable()
    except Exception:  # pragma: no cover — fail-open per FR-017
        return _TRACE_UNAVAILABLE


def promote_with_trace_evidence(
    badcase: Badcase,
    *,
    reviewer: str,
    reason: Optional[str] = None,
    closure_reason: Optional[str] = None,
    evidence_ref: Optional[str] = None,
    closed_at: Optional[datetime] = None,
    auto_capture_trace: bool = True,
) -> Badcase:
    """Promote a badcase through the FSM and stamp the current trace id.

    REQ-033 US7 (T128): when ``auto_capture_trace=True`` (default)
    and the caller did not provide an explicit ``evidence_ref``,
    the function captures the active OTel trace id and prepends
    it to the evidence_ref as ``trace:<id>`` so the badcase row
    is linked back to the originating trace. When no trace is
    active, ``trace:unavailable`` is recorded — never silent
    omission, per US7 T123 contract.

    The transition itself is delegated to :func:`transition` so
    the FSM rules (REVIEWER_REQUIRED / CLOSURE_REASON_REQUIRED /
    etc.) still apply. This function only adds evidence
    enrichment; it does NOT change FSM rules.

    Parameters
    ----------
    badcase:
        The badcase to transition (typically ``badcase.status ==
        'AWAITING_VALIDATION'`` when promoting to ``CLOSED``).
    reviewer, reason, closure_reason, evidence_ref, closed_at:
        Same as :func:`transition`.
    auto_capture_trace:
        When True and ``evidence_ref`` is not supplied, prepend
        the active trace id. Set to False to skip trace capture
        (e.g. legacy callers or unit tests that don't want the
        side effect).
    """
    if auto_capture_trace and not evidence_ref:
        trace_id = capture_current_trace_id()
        evidence_ref = f"trace:{trace_id}"
    return transition(
        badcase,
        "CLOSED",
        reviewer=reviewer,
        reason=reason,
        closure_reason=closure_reason,
        evidence_ref=evidence_ref,
        closed_at=closed_at,
    )


class BadcaseTransitionError(ValueError):
    """Raised when a state transition violates the FSM or required fields.

    Subclasses ``ValueError`` so generic exception handlers in the
    FastAPI / CLI layers still catch it. The ``code`` attribute is a
    stable string the API maps to HTTP 422.
    """

    def __init__(self, message: str, *, code: str) -> None:
        super().__init__(message)
        self.code = code


# ---------------------------------------------------------------------------
# Allowed transitions
# ---------------------------------------------------------------------------

_ALLOWED_TRANSITIONS: frozenset[tuple[str, str]] = frozenset(
    {
        ("OPEN", "TRIAGED"),
        ("OPEN", "REJECTED"),
        ("TRIAGED", "IN_PROGRESS"),
        ("TRIAGED", "REJECTED"),
        ("IN_PROGRESS", "AWAITING_VALIDATION"),
        ("IN_PROGRESS", "TRIAGED"),  # back-step allowed
        ("AWAITING_VALIDATION", "IN_PROGRESS"),  # re-open
        ("AWAITING_VALIDATION", "CLOSED"),
    }
)

_TERMINAL_STATUSES: frozenset[str] = frozenset({"CLOSED", "REJECTED"})


# ---------------------------------------------------------------------------
# transition
# ---------------------------------------------------------------------------


def transition(
    badcase: Badcase,
    new_status: str,
    *,
    reviewer: Optional[str],
    reason: Optional[str] = None,
    closure_reason: Optional[str] = None,
    evidence_ref: Optional[str] = None,
    closed_at: Optional[datetime] = None,
) -> Badcase:
    """Validate and apply a state transition; return a new Badcase.

    The input ``badcase`` is NOT mutated (Pydantic models are
    immutable-by-default; we ``model_copy`` to produce the updated
    instance).
    """
    if new_status not in BADCASE_STATUSES:
        raise BadcaseTransitionError(
            f"unknown status {new_status!r}; expected one of {BADCASE_STATUSES}",
            code="INVALID_STATUS",
        )

    current = badcase.status
    if current in _TERMINAL_STATUSES:
        raise BadcaseTransitionError(
            f"cannot transition from terminal status {current!r}",
            code="INVALID_TRANSITION",
        )

    if (current, new_status) not in _ALLOWED_TRANSITIONS:
        raise BadcaseTransitionError(
            f"transition {current} -> {new_status} is not allowed by the FSM",
            code="INVALID_TRANSITION",
        )

    # Field-level requirements per target status.
    if not reviewer:
        raise BadcaseTransitionError(
            f"reviewer is required when transitioning to {new_status!r}",
            code="REVIEWER_REQUIRED",
        )

    if new_status == "REJECTED":
        if not reason:
            raise BadcaseTransitionError(
                "reason is required when transitioning to REJECTED",
                code="REASON_REQUIRED",
            )
        if closed_at is None:
            raise BadcaseTransitionError(
                "closed_at is required when transitioning to REJECTED",
                code="CLOSED_AT_REQUIRED",
            )

    if new_status == "CLOSED":
        if not closure_reason:
            raise BadcaseTransitionError(
                "closure_reason is required when transitioning to CLOSED",
                code="CLOSURE_REASON_REQUIRED",
            )
        if not evidence_ref:
            raise BadcaseTransitionError(
                "evidence_ref is required when transitioning to CLOSED",
                code="EVIDENCE_REF_REQUIRED",
            )
        if closed_at is None:
            raise BadcaseTransitionError(
                "closed_at is required when transitioning to CLOSED",
                code="CLOSED_AT_REQUIRED",
            )

    # Build the updated instance. We use model_copy so callers can rely
    # on Pydantic's immutability semantics and so the review log entry
    # stays in sync with the parent.
    update_kwargs: dict[str, Any] = {
        "status": new_status,
        "reviewer": reviewer,
        "updated_at": datetime.now(timezone.utc),
    }
    if new_status == "REJECTED":
        update_kwargs["closure_reason"] = reason
        update_kwargs["closed_at"] = closed_at
    if new_status == "CLOSED":
        update_kwargs["closure_reason"] = closure_reason
        update_kwargs["evidence_ref"] = evidence_ref
        update_kwargs["closed_at"] = closed_at
    updated = badcase.model_copy(update=update_kwargs)
    return updated


# ---------------------------------------------------------------------------
# can_promote
# ---------------------------------------------------------------------------


def can_promote(
    badcase: Badcase,
    redaction_audit: Mapping[str, Any],
) -> bool:
    """Return ``True`` iff the badcase can be promoted to a golden case.

    Requirements:

    - ``redaction_audit['redactionStatus'] == 'PASSED'``
    - ``redaction_audit['reviewer']`` is set (non-empty).
    - ``badcase.status`` is NOT ``OPEN`` (must be at least triaged).
    - ``badcase.status`` is NOT ``REJECTED`` (rejected badcases cannot
      become golden cases).
    """
    if badcase.status == "OPEN":
        return False
    if badcase.status == "REJECTED":
        return False
    if str(redaction_audit.get("redactionStatus", "")) != "PASSED":
        return False
    reviewer = redaction_audit.get("reviewer")
    if not reviewer or (isinstance(reviewer, str) and not reviewer.strip()):
        return False
    return True


# ---------------------------------------------------------------------------
# apply_review_action
# ---------------------------------------------------------------------------


def apply_review_action(
    badcase: Badcase,
    action: BadcaseReviewAction,
) -> Badcase:
    """Append a ``BadcaseReviewAction`` to the badcase's audit log.

    Returns a new Badcase with the action attached. The input
    ``badcase`` is not mutated. The action's required-field
    validation runs in ``BadcaseReviewAction``'s Pydantic validators,
    so this function does not re-check.
    """
    existing = list(getattr(badcase, "actions", []) or [])
    existing.append(action)
    return badcase.model_copy(update={"actions": existing})


# ---------------------------------------------------------------------------
# REQ-061 US10 — typed review commands (T132)
# ---------------------------------------------------------------------------

from uuid import UUID, uuid4  # noqa: E402

from sqlalchemy.ext.asyncio import AsyncSession  # noqa: E402

from app.modules.badcases import repository as _repo  # noqa: E402
from app.modules.badcases.impact import upsert_impact  # noqa: E402
from app.modules.badcases.models import Badcase as BadcaseORM  # noqa: E402

TYPED_ACTION_TYPES = frozenset(
    {
        "CLASSIFY",
        "ASSIGN",
        "MERGE",
        "ADD_NOTE",
        "ESCALATE_INCIDENT",
        "RECORD_POINT_TREATMENT",
        "PROMOTE_REGRESSION",
        "MARK_UNREPRODUCIBLE",
        "CLOSE",
        "INTAKE",
    }
)

_P0_P1 = frozenset({"P0", "P1", "CRITICAL", "HIGH"})

_SLA_ASSIGN_HOURS = {"P0": 0.25, "P1": 1.0, "CRITICAL": 0.25, "HIGH": 1.0}


class BadcaseCommandError(BadcaseTransitionError):
    """Raised for version conflicts, closure gates, and terminal recurrence."""


def _severity_is_p0_p1(severity: str) -> bool:
    return severity in _P0_P1 or severity.startswith("P0") or severity.startswith("P1")


def missing_closure_fields(evidence: Mapping[str, Any] | None) -> list[str]:
    required = (
        "fix_or_policy_version",
        "regression_case_ref",
        "passing_evaluation_ref",
        "point_treatment_ref",
        "user_notification_ref",
    )
    evidence = evidence or {}
    return [k for k in required if not evidence.get(k)]


def evaluate_sla_status(
    *,
    severity: str,
    owner: str | None,
    created_at: datetime | None,
    now: datetime | None = None,
) -> str:
    now = now or datetime.now(timezone.utc)
    hours = _SLA_ASSIGN_HOURS.get(severity)
    if hours is None:
        return "within_sla"
    if owner:
        return "within_sla"
    if created_at is None:
        return "at_risk"
    created = created_at if created_at.tzinfo else created_at.replace(tzinfo=timezone.utc)
    elapsed = (now - created).total_seconds() / 3600.0
    if elapsed >= hours:
        return "breached"
    if elapsed >= hours * 0.7:
        return "at_risk"
    return "within_sla"


def _action_to_timeline(action: Any, *, privacy_class: str = "metadata") -> dict[str, Any]:
    return {
        "action_id": str(action.id),
        "action_type": action.action_type,
        "occurred_at": action.created_at.isoformat() if action.created_at else None,
        "recorded_at": action.created_at.isoformat() if action.created_at else None,
        "actor": action.actor or action.actor_role or "unknown",
        "reason": action.reason or "",
        "from_status": action.from_status,
        "to_status": action.to_status,
        "expected_version": int(action.expected_version or 1),
        "resulting_version": int(action.resulting_version or 1),
        "evidence_refs": list(action.evidence_refs or []),
        "privacy_class": privacy_class,
    }


def badcase_summary(row: BadcaseORM) -> dict[str, Any]:
    caps = list(row.capabilities or [])
    return {
        "badcase_id": row.badcase_id,
        "status": row.status,
        "severity": row.severity,
        "category": row.category or row.type,
        "capabilities": caps,
        "owner": row.owner,
        "privacy_class": _map_privacy_out(row.privacy_class),
        "first_seen_at": (
            row.first_seen_at.isoformat()
            if row.first_seen_at
            else row.created_at.isoformat()
            if row.created_at
            else None
        ),
        "last_seen_at": (
            row.last_seen_at.isoformat()
            if row.last_seen_at
            else row.updated_at.isoformat()
            if row.updated_at
            else None
        ),
        "task_count": 0,
        "user_count": None,
        "user_count_status": "unknown",
        "point_treatment_status": row.point_treatment_status or "unknown",
        "sla_status": row.sla_status or "within_sla",
        "version": int(row.version or 1),
        "data_completeness": row.data_completeness or "partial",
    }


def _map_privacy_out(privacy_class: str) -> str:
    mapping = {
        "PUBLIC_METADATA": "metadata",
        "INTERNAL_METADATA": "metadata",
        "REDACTED_SUMMARY": "redacted",
        "SENSITIVE_USER_CONTENT": "restricted",
        "SECRET": "restricted",
        "UNKNOWN": "metadata",
        "metadata": "metadata",
        "redacted": "redacted",
        "restricted": "restricted",
    }
    return mapping.get(privacy_class, "metadata")


def data_quality_block(*, unknown_count: int = 0) -> dict[str, Any]:
    return {
        "fresh_at": datetime.now(timezone.utc).isoformat(),
        "coverage_percent": 100.0,
        "unknown_count": unknown_count,
        "seed_or_mock_count": 0,
    }


async def execute_review_command(
    session: AsyncSession,
    *,
    badcase_id: str,
    command: Mapping[str, Any],
    actor: str,
    idempotency_key: str | None = None,
    user_id: UUID | None = None,
) -> dict[str, Any]:
    action_type = str(command.get("action_type") or "")
    if action_type not in TYPED_ACTION_TYPES:
        raise BadcaseCommandError(
            f"unknown action_type {action_type!r}",
            code="INVALID_ACTION_TYPE",
        )
    if not command.get("reason"):
        raise BadcaseCommandError("reason is required", code="REASON_REQUIRED")

    expected_version = int(command.get("expected_version") or 0)
    if expected_version < 1:
        raise BadcaseCommandError(
            "expected_version must be >= 1", code="EXPECTED_VERSION_REQUIRED"
        )

    if idempotency_key:
        prior = await _repo.find_action_by_idempotency(
            session, idempotency_key=idempotency_key
        )
        if prior is not None:
            row = await _repo.get(session, badcase_id=prior.badcase_id, user_id=user_id)
            if row is None:
                row = await _repo.get_by_id_any_user(session, badcase_id=prior.badcase_id)
            return {
                "badcase_id": prior.badcase_id,
                "action": _action_to_timeline(prior),
                "resulting_badcase": badcase_summary(row) if row else {},
                "audit_event_id": str(prior.id),
                "idempotent_replay": True,
            }

    row = await _repo.get(session, badcase_id=badcase_id, user_id=user_id)
    if row is None:
        row = await _repo.get_by_id_any_user(session, badcase_id=badcase_id)
    if row is None:
        raise BadcaseCommandError("badcase not found", code="NOT_FOUND")

    if row.status in {"CLOSED", "REJECTED", "MERGED"}:
        raise BadcaseCommandError(
            f"cannot mutate terminal status {row.status!r}; create a linked recurrence",
            code="TERMINAL_STATE",
        )

    current_version = int(row.version or 1)
    if expected_version != current_version:
        raise BadcaseCommandError(
            f"version conflict: expected {expected_version}, current {current_version}",
            code="VERSION_CONFLICT",
        )

    from_status = row.status
    to_status = from_status
    payload = dict(command)

    if action_type == "CLASSIFY":
        row.category = str(command["category"])
        row.severity = str(command["severity"])
        row.sla_status = evaluate_sla_status(
            severity=row.severity, owner=row.owner, created_at=row.created_at
        )
        if from_status == "OPEN":
            to_status = "TRIAGED"
            row.status = to_status
        if not row.reviewer:
            row.reviewer = actor

    elif action_type == "ASSIGN":
        row.owner = str(command["owner"])
        row.sla_status = evaluate_sla_status(
            severity=row.severity, owner=row.owner, created_at=row.created_at
        )
        if from_status in {"OPEN", "TRIAGED"}:
            to_status = "IN_PROGRESS"
            row.status = to_status

    elif action_type == "MERGE":
        canonical = str(command["canonical_badcase_id"])
        if canonical == badcase_id:
            raise BadcaseCommandError(
                "cannot merge a badcase into itself", code="INVALID_MERGE"
            )
        canonical_row = await _repo.get_by_id_any_user(session, badcase_id=canonical)
        if canonical_row is None:
            raise BadcaseCommandError(
                "canonical badcase not found", code="CANONICAL_NOT_FOUND"
            )
        row.merged_into_badcase_id = canonical
        row.user_visible_status = "已合并"
        to_status = "MERGED"
        row.status = to_status
        await upsert_impact(
            session,
            badcase_id=canonical,
            impact_kind="task",
            subject_ref=f"merged:{badcase_id}",
            confidence="confirmed",
            actor=actor,
            update_reason="merge",
            evidence_refs=[command.get("root_cause_match_evidence") or {}],
        )

    elif action_type == "ADD_NOTE":
        payload["note"] = str(command["note"])

    elif action_type == "ESCALATE_INCIDENT":
        payload["incident_ref"] = str(command["incident_ref"])
        row.user_visible_status = "审核中"

    elif action_type == "RECORD_POINT_TREATMENT":
        row.point_treatment_status = str(command["treatment_status"])
        for pref in command.get("point_event_refs") or []:
            await upsert_impact(
                session,
                badcase_id=badcase_id,
                impact_kind="point_event",
                subject_ref=str(pref),
                confidence="confirmed",
                actor=actor,
                update_reason="point_treatment",
                user_id=user_id,
            )

    elif action_type == "PROMOTE_REGRESSION":
        payload["regression_case_ref"] = str(command["regression_case_ref"])
        payload["redaction_audit_ref"] = str(command["redaction_audit_ref"])
        await _repo.upsert_closure_evidence(
            session,
            badcase_id=badcase_id,
            regression_case_ref=str(command["regression_case_ref"]),
        )

    elif action_type == "MARK_UNREPRODUCIBLE":
        row.user_visible_status = "无法复现"
        row.reproduction_summary = str(command.get("user_visible_message") or "")
        payload["required_user_information"] = list(
            command.get("required_user_information") or []
        )

    elif action_type == "CLOSE":
        evidence = {
            "fix_or_policy_version": command.get("fix_or_policy_version"),
            "regression_case_ref": command.get("regression_case_ref"),
            "passing_evaluation_ref": command.get("passing_evaluation_ref"),
            "point_treatment_ref": command.get("point_treatment_ref"),
            "user_notification_ref": command.get("user_notification_ref"),
        }
        missing = missing_closure_fields(evidence)
        if missing:
            raise BadcaseCommandError(
                f"closure evidence incomplete: {', '.join(missing)}",
                code="CLOSURE_EVIDENCE_REQUIRED",
            )
        closure = await _repo.upsert_closure_evidence(
            session, badcase_id=badcase_id, **evidence
        )
        row.closure_evidence = {
            "fix_or_policy_version": closure.fix_or_policy_version,
            "regression_case_ref": closure.regression_case_ref,
            "passing_evaluation_ref": closure.passing_evaluation_ref,
            "point_treatment_ref": closure.point_treatment_ref,
            "user_notification_ref": closure.user_notification_ref,
            "complete": closure.complete,
        }
        row.closure_reason = str(command["closure_reason"])
        row.closed_at = datetime.now(timezone.utc)
        row.reviewer = actor
        row.user_visible_status = "已解决"
        to_status = "CLOSED"
        row.status = to_status

    resulting_version = current_version + 1
    row.version = resulting_version
    row.last_seen_at = datetime.now(timezone.utc)
    await _repo.save(session, row)

    action = await _repo.add_review_action(
        session,
        badcase_id=badcase_id,
        action_type=action_type,
        actor_role="BADCASE_REVIEWER",
        actor=actor,
        reason=str(command["reason"]),
        from_status=from_status,
        to_status=to_status,
        expected_version=expected_version,
        resulting_version=resulting_version,
        idempotency_key=idempotency_key,
        payload=payload,
        evidence_refs=list(command.get("evidence_refs") or []),
    )

    return {
        "badcase_id": badcase_id,
        "action": _action_to_timeline(action),
        "resulting_badcase": badcase_summary(row),
        "audit_event_id": str(action.id),
        "idempotent_replay": False,
    }


async def create_recurrence(
    session: AsyncSession,
    *,
    terminal_badcase_id: str,
    user_id: UUID,
    reason: str,
    actor: str,
) -> BadcaseORM:
    terminal = await _repo.get_by_id_any_user(session, badcase_id=terminal_badcase_id)
    if terminal is None:
        raise BadcaseCommandError("badcase not found", code="NOT_FOUND")
    if terminal.status not in {"CLOSED", "REJECTED", "MERGED"}:
        raise BadcaseCommandError(
            "recurrence only allowed from terminal states",
            code="NOT_TERMINAL",
        )
    new_id = f"badcase-{uuid4()}"
    now = datetime.now(timezone.utc)
    row = await _repo.create(
        session,
        user_id=user_id,
        badcase_id=new_id,
        type=terminal.type,
        source=terminal.source,
        privacy_class=terminal.privacy_class,
        severity=terminal.severity,
        status="OPEN",
        category=terminal.category,
        capabilities=list(terminal.capabilities or []),
        first_seen_at=now,
        last_seen_at=now,
        recurrence_of_badcase_id=terminal_badcase_id,
        data_completeness="partial",
        user_visible_status="已提交",
    )
    await _repo.add_review_action(
        session,
        badcase_id=new_id,
        action_type="INTAKE",
        actor=actor,
        reason=reason,
        to_status="OPEN",
        expected_version=1,
        resulting_version=1,
        payload={"recurrence_of": terminal_badcase_id},
    )
    return row


__all__ = [
    "BadcaseCommandError",
    "BadcaseTransitionError",
    "TYPED_ACTION_TYPES",
    "apply_review_action",
    "badcase_summary",
    "can_promote",
    "capture_current_trace_id",
    "create_recurrence",
    "data_quality_block",
    "evaluate_sla_status",
    "execute_review_command",
    "missing_closure_fields",
    "promote_with_trace_evidence",
    "transition",
]
