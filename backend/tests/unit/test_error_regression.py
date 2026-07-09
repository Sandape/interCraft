"""[REQ-048 US6 T105] Unit test for regression path.

Validates AC-27 (US6):
- A ``mastered`` error question that gets a low re-score (<6) MUST
  regress to ``practicing`` (mastered → practicing reverse migration).
  (Spec calls this "reviewing"; production uses "practicing".)
- An analytics event ``drill_resink_completed`` is written with
  ``regression_detected=True``.

Mirrors the production reduce_status() validator + analytics event path.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pytest

from app.modules.errors.service import (
    STATUS_FREQUENCY,
    reduce_status,
)


@dataclass
class _ErrorRow:
    id: str
    user_id: str
    source_session_id: str | None
    source_question_id: str | None
    dimension: str
    question_text: str
    score: int | None
    status: str
    frequency: int
    last_practiced_at: str | None = None


@dataclass
class _AnalyticsEvent:
    user_id: str
    event_type: str
    payload: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Regression transition logic
# ---------------------------------------------------------------------------


def _apply_regression(row: _ErrorRow, new_score: int, analytics: list[_AnalyticsEvent]) -> _ErrorRow:
    """Regression path: mastered → practicing when raw_score < 6.

    Per A-007 risk + FR-041, the state machine MUST allow mastered →
    practicing (reverse migration) so the user can re-enter the practice
    cycle when they re-fail a previously-mastered question.
    """
    regression_detected = False
    if row.status == "mastered" and new_score < 6:
        regression_detected = True
        target_status, target_freq = reduce_status(
            current_status="mastered",
            target_status="practicing",
            current_frequency=row.frequency,
            target_frequency=1,
        )
        new_row = _ErrorRow(
            id=row.id,
            user_id=row.user_id,
            # AC-29: source_session_id stays immutable.
            source_session_id=row.source_session_id,
            source_question_id=row.source_question_id,
            dimension=row.dimension,
            question_text=row.question_text,
            score=new_score,
            status=target_status,
            frequency=target_freq,
            last_practiced_at="2026-07-07T12:00:00+00:00",
        )
    else:
        new_row = row

    if regression_detected:
        analytics.append(
            _AnalyticsEvent(
                user_id=row.user_id,
                event_type="drill_resink_completed",
                payload={
                    "source_question_id": row.source_question_id,
                    "old_status": "mastered",
                    "new_status": new_row.status,
                    "new_frequency": new_row.frequency,
                    "regression_detected": True,
                },
            )
        )
    else:
        analytics.append(
            _AnalyticsEvent(
                user_id=row.user_id,
                event_type="drill_resink_completed",
                payload={
                    "source_question_id": row.source_question_id,
                    "old_status": row.status,
                    "new_status": new_row.status,
                    "new_frequency": new_row.frequency,
                    "regression_detected": False,
                },
            )
        )

    return new_row


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_mastered_to_practicing_regression() -> None:
    """AC-27: status=mastered + raw_score=4 → status=practicing."""
    row = _ErrorRow(
        id="q-A",
        user_id="u-A",
        source_session_id="S1",
        source_question_id="qid-A",
        dimension="tech_depth",
        question_text="问题 A",
        score=9,
        status="mastered",
        frequency=0,
    )
    analytics: list[_AnalyticsEvent] = []
    out = _apply_regression(row, new_score=4, analytics=analytics)
    assert out.status == "practicing"
    assert out.score == 4
    assert out.frequency == 1  # reset back to learning range


def test_mastered_to_practicing_emits_regression_analytics() -> None:
    """AC-27 analytics: drill_resink_completed with regression_detected=true."""
    row = _ErrorRow(
        id="q-B",
        user_id="u-B",
        source_session_id="S1",
        source_question_id="qid-B",
        dimension="distributed_systems",
        question_text="问题 B",
        score=8,
        status="mastered",
        frequency=0,
    )
    analytics: list[_AnalyticsEvent] = []
    _apply_regression(row, new_score=3, analytics=analytics)
    assert len(analytics) == 1
    evt = analytics[0]
    assert evt.event_type == "drill_resink_completed"
    assert evt.payload["regression_detected"] is True
    assert evt.payload["old_status"] == "mastered"
    assert evt.payload["new_status"] == "practicing"
    assert evt.payload["source_question_id"] == "qid-B"


def test_non_mastered_status_does_not_trigger_regression() -> None:
    """practicing + low score is NOT a regression (it's just a wrong answer)."""
    row = _ErrorRow(
        id="q-C",
        user_id="u-C",
        source_session_id="S1",
        source_question_id="qid-C",
        dimension="tech_depth",
        question_text="问题 C",
        score=5,
        status="practicing",
        frequency=2,
    )
    analytics: list[_AnalyticsEvent] = []
    out = _apply_regression(row, new_score=4, analytics=analytics)
    assert out.status == "practicing"
    # No regression event because the user was already in the practice cycle.
    assert analytics[0].payload["regression_detected"] is False


def test_mastered_high_score_does_not_trigger_regression() -> None:
    """mastered + high score → no regression (still mastered)."""
    row = _ErrorRow(
        id="q-D",
        user_id="u-D",
        source_session_id="S1",
        source_question_id="qid-D",
        dimension="tech_depth",
        question_text="问题 D",
        score=8,
        status="mastered",
        frequency=0,
    )
    analytics: list[_AnalyticsEvent] = []
    out = _apply_regression(row, new_score=9, analytics=analytics)
    assert out.status == "mastered"
    assert analytics[0].payload["regression_detected"] is False


def test_regression_does_not_change_source_session_id() -> None:
    """AC-29 cross-check: regression must keep source_session_id unchanged."""
    row = _ErrorRow(
        id="q-E",
        user_id="u-E",
        source_session_id="S-original",
        source_question_id="qid-E",
        dimension="tech_depth",
        question_text="问题 E",
        score=10,
        status="mastered",
        frequency=0,
    )
    analytics: list[_AnalyticsEvent] = []
    out = _apply_regression(row, new_score=3, analytics=analytics)
    assert out.source_session_id == "S-original", (
        f"regression path leaked source_session_id: {out.source_session_id!r}"
    )


def test_regression_frequency_constraints() -> None:
    """Reduce_status enforces frequency=1 for practicing (status_fresh check)."""
    # practicing has no explicit freq rule in STATUS_FREQUENCY (it's a tuple),
    # but the transition must still go through the validator.
    new_status, new_freq = reduce_status(
        current_status="mastered",
        target_status="practicing",
        current_frequency=0,
        target_frequency=1,
    )
    assert new_status == "practicing"
    assert new_freq == 1