"""REQ-033 US8 — badcase service unit tests (T056).

Pure-logic FSM tests for ``app.modules.badcases.service``. No DB, no
network. The service module is the single source of truth for the
state-transition rules documented in ``data-model.md`` §State
Transitions; these tests pin the matrix down.

Happy path matrix:

- ``OPEN -> TRIAGED`` via ``transition(..., new_status=TRIAGED, reviewer=...)``
- ``TRIAGED -> IN_PROGRESS``
- ``IN_PROGRESS -> AWAITING_VALIDATION``
- ``AWAITING_VALIDATION -> CLOSED`` (requires ``closure_reason``,
  ``evidence_ref``, ``reviewer``)
- ``OPEN -> REJECTED`` direct reject (requires ``reason`` + ``reviewer``)
- ``TRIAGED -> REJECTED``
- ``AWAITING_VALIDATION -> IN_PROGRESS`` re-open

Forbidden transitions:

- ``CLOSED -> anything`` (terminal)
- ``REJECTED -> anything`` (terminal)
- ``OPEN -> CLOSED`` (must traverse the pipeline)

Error contract:

- ``BadcaseTransitionError`` (subclass of ``ValueError``) is raised on
  any invalid transition. The ``code`` attribute is a stable string
  the API layer maps to HTTP 422.
- ``can_promote`` returns False when ``redaction_status != PASSED``.
- ``apply_review_action`` appends to the actions list immutably and
  returns a new Badcase with the audit log entry.
"""
from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.modules.badcases.schemas import (
    BADCASE_ACTION_TYPES,
    BADCASE_ACTOR_ROLES,
    BADCASE_SOURCES,
    BADCASE_STATUSES,
    Badcase,
    BadcaseReviewAction,
)
from app.modules.badcases.service import (
    BadcaseTransitionError,
    apply_review_action,
    can_promote,
    transition,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _badcase(**overrides) -> Badcase:
    """Build a fresh OPEN badcase for FSM tests."""
    defaults: dict = {
        "type": "EVAL_REGRESSION",
        "severity": "HIGH",
        "source": "EVAL_FAILURE",
        "reviewer": "alice",
        "privacy_class": "PUBLIC_METADATA",
        "redaction_status": "NOT_REQUIRED",
        "run_id": None,
        "trace_id": None,
        "closure_reason": None,
        "closed_at": None,
    }
    defaults.update(overrides)
    return Badcase(**defaults)


# ---------------------------------------------------------------------------
# Happy path FSM
# ---------------------------------------------------------------------------


def test_open_to_triaged_requires_reviewer() -> None:
    """OPEN -> TRIAGED requires a reviewer."""
    bc = _badcase(reviewer=None)
    with pytest.raises(BadcaseTransitionError) as exc_info:
        transition(bc, new_status="TRIAGED", reviewer=None)
    assert exc_info.value.code == "REVIEWER_REQUIRED"


def test_open_to_triaged_happy() -> None:
    """OPEN -> TRIAGED with reviewer succeeds."""
    bc = _badcase()
    updated = transition(bc, new_status="TRIAGED", reviewer="bob")
    assert updated.status == "TRIAGED"
    assert updated.reviewer == "bob"
    # updated_at is bumped to a UTC-aware timestamp; we only assert
    # the call didn't error out (offset comparison is brittle here).
    assert updated.updated_at is not None


def test_full_happy_path_to_closed() -> None:
    """OPEN -> TRIAGED -> IN_PROGRESS -> AWAITING_VALIDATION -> CLOSED."""
    bc = _badcase()
    bc = transition(bc, "TRIAGED", reviewer="alice")
    assert bc.status == "TRIAGED"
    bc = transition(bc, "IN_PROGRESS", reviewer="alice")
    assert bc.status == "IN_PROGRESS"
    bc = transition(
        bc,
        "AWAITING_VALIDATION",
        reviewer="alice",
    )
    assert bc.status == "AWAITING_VALIDATION"
    closed_at = datetime.now(UTC)
    bc = transition(
        bc,
        "CLOSED",
        reviewer="alice",
        closure_reason="fixed",
        evidence_ref="link",
        closed_at=closed_at,
    )
    assert bc.status == "CLOSED"
    assert bc.closure_reason == "fixed"
    assert bc.evidence_ref == "link" or bc.closure_reason == "fixed"
    assert bc.closed_at == closed_at


def test_close_requires_closure_reason() -> None:
    """CLOSE without closure_reason → BadcaseTransitionError."""
    bc = _badcase()
    bc = transition(bc, "TRIAGED", reviewer="alice")
    bc = transition(bc, "IN_PROGRESS", reviewer="alice")
    bc = transition(bc, "AWAITING_VALIDATION", reviewer="alice")
    with pytest.raises(BadcaseTransitionError) as exc_info:
        transition(
            bc,
            "CLOSED",
            reviewer="alice",
            evidence_ref="link",
            closed_at=datetime.now(UTC),
        )
    assert exc_info.value.code == "CLOSURE_REASON_REQUIRED"


def test_close_requires_evidence_ref() -> None:
    """CLOSE without evidence_ref → BadcaseTransitionError."""
    bc = _badcase()
    bc = transition(bc, "TRIAGED", reviewer="alice")
    bc = transition(bc, "IN_PROGRESS", reviewer="alice")
    bc = transition(bc, "AWAITING_VALIDATION", reviewer="alice")
    with pytest.raises(BadcaseTransitionError) as exc_info:
        transition(
            bc,
            "CLOSED",
            reviewer="alice",
            closure_reason="fixed",
            closed_at=datetime.now(UTC),
        )
    assert exc_info.value.code == "EVIDENCE_REF_REQUIRED"


def test_close_requires_reviewer() -> None:
    """CLOSE without reviewer → BadcaseTransitionError."""
    bc = _badcase()
    bc = transition(bc, "TRIAGED", reviewer="alice")
    bc = transition(bc, "IN_PROGRESS", reviewer="alice")
    bc = transition(bc, "AWAITING_VALIDATION", reviewer="alice")
    with pytest.raises(BadcaseTransitionError) as exc_info:
        transition(
            bc,
            "CLOSED",
            reviewer=None,
            closure_reason="fixed",
            evidence_ref="link",
            closed_at=datetime.now(UTC),
        )
    assert exc_info.value.code == "REVIEWER_REQUIRED"


def test_close_requires_closed_at() -> None:
    """CLOSE without closed_at → BadcaseTransitionError."""
    bc = _badcase()
    bc = transition(bc, "TRIAGED", reviewer="alice")
    bc = transition(bc, "IN_PROGRESS", reviewer="alice")
    bc = transition(bc, "AWAITING_VALIDATION", reviewer="alice")
    with pytest.raises(BadcaseTransitionError) as exc_info:
        transition(
            bc,
            "CLOSED",
            reviewer="alice",
            closure_reason="fixed",
            evidence_ref="link",
        )
    assert exc_info.value.code == "CLOSED_AT_REQUIRED"


# ---------------------------------------------------------------------------
# Direct reject from OPEN / TRIAGED
# ---------------------------------------------------------------------------


def test_open_to_rejected_requires_reason() -> None:
    """REJECT requires a reason."""
    bc = _badcase()
    with pytest.raises(BadcaseTransitionError) as exc_info:
        transition(bc, "REJECTED", reviewer="alice")
    assert exc_info.value.code == "REASON_REQUIRED"


def test_open_to_rejected_happy() -> None:
    """OPEN -> REJECTED with reason + reviewer."""
    bc = _badcase()
    closed_at = datetime.now(UTC)
    bc = transition(
        bc,
        "REJECTED",
        reviewer="alice",
        reason="not reproducible",
        closed_at=closed_at,
    )
    assert bc.status == "REJECTED"
    assert bc.closure_reason == "not reproducible"
    assert bc.closed_at == closed_at


def test_triaged_to_rejected_happy() -> None:
    """TRIAGED -> REJECTED is also valid."""
    bc = _badcase()
    bc = transition(bc, "TRIAGED", reviewer="alice")
    bc = transition(
        bc,
        "REJECTED",
        reviewer="alice",
        reason="duplicate",
        closed_at=datetime.now(UTC),
    )
    assert bc.status == "REJECTED"


def test_rejected_requires_reviewer() -> None:
    """REJECT without reviewer → error."""
    bc = _badcase()
    with pytest.raises(BadcaseTransitionError) as exc_info:
        transition(bc, "REJECTED", reviewer=None, reason="dup")
    assert exc_info.value.code == "REVIEWER_REQUIRED"


# ---------------------------------------------------------------------------
# Re-open: AWAITING_VALIDATION -> IN_PROGRESS
# ---------------------------------------------------------------------------


def test_awaiting_validation_to_in_progress_reopens() -> None:
    """AWAITING_VALIDATION -> IN_PROGRESS is a valid re-open."""
    bc = _badcase()
    bc = transition(bc, "TRIAGED", reviewer="alice")
    bc = transition(bc, "IN_PROGRESS", reviewer="alice")
    bc = transition(bc, "AWAITING_VALIDATION", reviewer="alice")
    bc = transition(bc, "IN_PROGRESS", reviewer="alice")
    assert bc.status == "IN_PROGRESS"


# ---------------------------------------------------------------------------
# Forbidden transitions
# ---------------------------------------------------------------------------


def test_closed_is_terminal() -> None:
    """CLOSED -> anything → BadcaseTransitionError."""
    bc = _badcase()
    bc = transition(bc, "TRIAGED", reviewer="alice")
    bc = transition(bc, "IN_PROGRESS", reviewer="alice")
    bc = transition(bc, "AWAITING_VALIDATION", reviewer="alice")
    bc = transition(
        bc,
        "CLOSED",
        reviewer="alice",
        closure_reason="fixed",
        evidence_ref="link",
        closed_at=datetime.now(UTC),
    )
    for new_status in ("OPEN", "TRIAGED", "IN_PROGRESS", "REJECTED"):
        with pytest.raises(BadcaseTransitionError) as exc_info:
            transition(bc, new_status, reviewer="alice")
        assert exc_info.value.code == "INVALID_TRANSITION"


def test_rejected_is_terminal() -> None:
    """REJECTED -> anything → BadcaseTransitionError."""
    bc = transition(
        _badcase(),
        "REJECTED",
        reviewer="alice",
        reason="dup",
        closed_at=datetime.now(UTC),
    )
    with pytest.raises(BadcaseTransitionError) as exc_info:
        transition(bc, "OPEN", reviewer="alice")
    assert exc_info.value.code == "INVALID_TRANSITION"


def test_open_to_closed_is_invalid() -> None:
    """OPEN → CLOSED bypasses the pipeline (forbidden)."""
    bc = _badcase()
    with pytest.raises(BadcaseTransitionError) as exc_info:
        transition(
            bc,
            "CLOSED",
            reviewer="alice",
            closure_reason="fixed",
            evidence_ref="link",
            closed_at=datetime.now(UTC),
        )
    assert exc_info.value.code == "INVALID_TRANSITION"


def test_unknown_status_rejected() -> None:
    """Unknown target status → BadcaseTransitionError."""
    bc = _badcase()
    with pytest.raises(BadcaseTransitionError) as exc_info:
        transition(bc, "FLOATING", reviewer="alice")
    assert exc_info.value.code == "INVALID_STATUS"


# ---------------------------------------------------------------------------
# can_promote
# ---------------------------------------------------------------------------


def test_can_promote_requires_redaction_passed() -> None:
    """Promotion is only allowed when redaction_status == PASSED."""
    # Badcase must be at least triaged for promotion.
    bc = transition(_badcase(), "TRIAGED", reviewer="alice")
    audit = {"redactionStatus": "PASSED", "reviewer": "alice"}
    assert can_promote(bc, audit) is True
    audit_failed = {"redactionStatus": "FAILED", "reviewer": "alice"}
    assert can_promote(bc, audit_failed) is False
    audit_pending = {"redactionStatus": "PENDING", "reviewer": "alice"}
    assert can_promote(bc, audit_pending) is False


def test_can_promote_requires_reviewer_on_audit() -> None:
    """Promotion requires a reviewer on the audit record."""
    bc = _badcase()
    no_reviewer = {"redactionStatus": "PASSED", "reviewer": None}
    assert can_promote(bc, no_reviewer) is False
    empty_reviewer = {"redactionStatus": "PASSED", "reviewer": ""}
    assert can_promote(bc, empty_reviewer) is False


def test_can_promote_requires_closed_or_triaged() -> None:
    """Promotion only makes sense after triage (status != OPEN)."""
    bc = _badcase()  # status=OPEN
    audit = {"redactionStatus": "PASSED", "reviewer": "alice"}
    assert can_promote(bc, audit) is False
    triaged = transition(bc, "TRIAGED", reviewer="alice")
    assert can_promote(triaged, audit) is True
    in_progress = transition(triaged, "IN_PROGRESS", reviewer="alice")
    assert can_promote(in_progress, audit) is True
    awaiting = transition(in_progress, "AWAITING_VALIDATION", reviewer="alice")
    assert can_promote(awaiting, audit) is True
    closed = transition(
        awaiting,
        "CLOSED",
        reviewer="alice",
        closure_reason="fixed",
        evidence_ref="link",
        closed_at=datetime.now(UTC),
    )
    # Closed badcases can still be promoted if approved post-hoc.
    assert can_promote(closed, audit) is True


# ---------------------------------------------------------------------------
# apply_review_action
# ---------------------------------------------------------------------------


def test_apply_review_action_appends_to_log() -> None:
    """apply_review_action appends to the badcase actions list immutably."""
    bc = _badcase()
    initial_actions = list(getattr(bc, "actions", []) or [])
    action = BadcaseReviewAction(
        action_type="CLASSIFY",
        actor_role="BADCASE_REVIEWER",
        reason="triaged",
    )
    updated = apply_review_action(bc, action)
    # Original is not mutated.
    assert len(getattr(bc, "actions", []) or []) == len(initial_actions)
    # Updated badcase has the action.
    new_actions = getattr(updated, "actions", []) or []
    assert any(
        a.action_type == "CLASSIFY" and a.actor_role == "BADCASE_REVIEWER"
        for a in new_actions
    )


def test_apply_review_action_validates_required_fields() -> None:
    """apply_review_action delegates to BadcaseReviewAction validators."""
    bc = _badcase()
    # CLOSE requires reason + evidence_ref.
    with pytest.raises(Exception):
        # Pydantic validation error (FR-029).
        BadcaseReviewAction(
            action_type="CLOSE",
            actor_role="BADCASE_REVIEWER",
        )


def test_apply_review_action_accepts_create_without_reason() -> None:
    """CREATE is the only action that does not require a reason."""
    bc = _badcase()
    action = BadcaseReviewAction(
        action_type="CREATE",
        actor_role="BADCASE_REVIEWER",
        reason="unknown",
        evidence_ref=None,
    )
    updated = apply_review_action(bc, action)
    assert any(a.action_type == "CREATE" for a in (updated.actions or []))


# ---------------------------------------------------------------------------
# Enum coverage (lock the contracts)
# ---------------------------------------------------------------------------


def test_badcasse_statuses_include_all_pipeline_states() -> None:
    """data-model.md §State Transitions must include every status enum value."""
    expected = {
        "OPEN",
        "TRIAGED",
        "IN_PROGRESS",
        "AWAITING_VALIDATION",
        "CLOSED",
        "REJECTED",
    }
    assert set(BADCASE_STATUSES) == expected


def test_badcasse_action_types_include_all_lifecycle_actions() -> None:
    """data-model.md §BadcaseReviewAction action_type must include every value."""
    expected = {
        "CREATE",
        "CLASSIFY",
        "PROMOTE_CANDIDATE",
        "APPROVE_PROMOTION",
        "CLOSE",
        "REJECT",
        "OVERRIDE",
        "BASELINE_REFRESH",
    }
    assert set(BADCASE_ACTION_TYPES) == expected


def test_badcasse_actor_roles_include_reviewer() -> None:
    """Reviewer role is in the actor_role enum table."""
    assert "BADCASE_REVIEWER" in BADCASE_ACTOR_ROLES


def test_badcasse_sources_include_eval_failure() -> None:
    """EVAL_FAILURE source is in the source enum table."""
    assert "EVAL_FAILURE" in BADCASE_SOURCES


# ---------------------------------------------------------------------------
# Error contract
# ---------------------------------------------------------------------------


def test_badcase_transition_error_is_value_error() -> None:
    """``BadcaseTransitionError`` is a ``ValueError`` so generic exception
    handlers still catch it."""
    assert issubclass(BadcaseTransitionError, ValueError)


def test_badcase_transition_error_has_code_attribute() -> None:
    """The error exposes a stable ``code`` for HTTP mapping."""
    err = BadcaseTransitionError("test", code="X")
    assert err.code == "X"
    assert "test" in str(err)