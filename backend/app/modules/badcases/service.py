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


__all__ = [
    "BadcaseTransitionError",
    "apply_review_action",
    "can_promote",
    "capture_current_trace_id",
    "promote_with_trace_evidence",
    "transition",
]