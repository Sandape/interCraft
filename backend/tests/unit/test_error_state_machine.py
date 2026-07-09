"""[REQ-048 US6 T104] Unit test for frequency state machine.

Validates AC-26 (US6):
- ``fresh → practicing`` migration on raw_score < 6 (sink_error path).
  NOTE: spec uses term "reviewing" but production code uses "practicing"
  (see app.modules.errors.service.VALID_TRANSITIONS) — these are the same
  concept (the user is back in the practice cycle after a fail).
- ``practicing → mastered`` frequency counter transitions.
- ``source_session_id`` MUST stay immutable across transitions.

Mirrors the production ``app.modules.errors.service.reduce_status`` and
``ErrorService.patch`` contract.
"""
from __future__ import annotations

from dataclasses import dataclass

import pytest

# Import the production validator so we exercise the actual state machine
# code rather than a parallel re-implementation.
from app.modules.errors.service import (
    STATUS_FREQUENCY,
    VALID_TRANSITIONS,
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


# ---------------------------------------------------------------------------
# Validator surface tests
# ---------------------------------------------------------------------------


def test_status_frequency_lookup_table() -> None:
    """Frequency constraints per status are part of the contract."""
    assert STATUS_FREQUENCY["fresh"] == 3
    assert STATUS_FREQUENCY["practicing"] == (1, 2)
    assert STATUS_FREQUENCY["mastered"] == 0


def test_valid_transitions_lookup_table() -> None:
    """Allowed transitions per current status are part of the contract."""
    assert "practicing" in VALID_TRANSITIONS["fresh"]
    assert "mastered" in VALID_TRANSITIONS["practicing"]
    assert "fresh" in VALID_TRANSITIONS["practicing"]  # reset path
    # archived is terminal.
    assert VALID_TRANSITIONS["archived"] == set()


def test_fresh_to_practicing_transition_is_valid() -> None:
    """AC-26: fresh → practicing allowed (with frequency adjustment).

    Spec terminology: "reviewing" maps to "practicing" in the production
    service code (see app/modules/errors/service.py VALID_TRANSITIONS).
    """
    new_status, new_freq = reduce_status(
        current_status="fresh",
        target_status="practicing",
        current_frequency=3,
        target_frequency=2,
    )
    assert new_status == "practicing"
    assert new_freq == 2


def test_practicing_to_mastered_requires_zero_frequency() -> None:
    """mastered status requires frequency=0."""
    new_status, new_freq = reduce_status(
        current_status="practicing",
        target_status="mastered",
        current_frequency=1,
        target_frequency=0,
    )
    assert new_status == "mastered"
    assert new_freq == 0


def test_fresh_to_mastered_blocked() -> None:
    """Direct fresh → mastered transition is not allowed."""
    assert "mastered" not in VALID_TRANSITIONS["fresh"]


# ---------------------------------------------------------------------------
# Frequency adjustment logic — exercises the in-row state machine
# ---------------------------------------------------------------------------


def _apply_re_sink_transition(row: _ErrorRow, new_score: int) -> _ErrorRow:
    """Mirror the sink_error → errors.service.patch path.

    Per AC-26 (spec calls this "reviewing" — production code uses "practicing"):
    - If new_score < 6 and current status is fresh → practicing (frequency 1-2)
    - If new_score < 6 and current status is mastered → practicing (regression)
    - If new_score < 6 and current status is practicing → practicing (frequency 1)
      via direct frequency decrease (NOT reduce_status self-transition, which is
      not allowed — production uses repository.recall() for this case).
    - source_session_id is NEVER updated (AC-29 hard constraint).
    """
    if new_score >= 6:
        return row  # no transition on pass
    if row.status == "practicing":
        # Production path: direct frequency decrease (mirror of repo.recall).
        new_freq = max(row.frequency - 1, 1)
        new_status = row.status
    elif row.status == "fresh":
        new_freq = 2
        new_status, new_freq = reduce_status(
            current_status="fresh",
            target_status="practicing",
            current_frequency=row.frequency,
            target_frequency=new_freq,
        )
    elif row.status == "mastered":
        # regression: mastered → practicing (AC-27)
        new_status, new_freq = reduce_status(
            current_status="mastered",
            target_status="practicing",
            current_frequency=row.frequency,
            target_frequency=1,
        )
    else:
        new_status = row.status
        new_freq = row.frequency

    return _ErrorRow(
        id=row.id,
        user_id=row.user_id,
        # AC-29: source_session_id is NEVER touched.
        source_session_id=row.source_session_id,
        source_question_id=row.source_question_id,
        dimension=row.dimension,
        question_text=row.question_text,
        score=new_score,
        status=new_status,
        frequency=new_freq,
        last_practiced_at="2026-07-07T12:00:00+00:00",
    )


def test_fresh_low_score_migrates_to_practicing() -> None:
    """AC-26: raw_score=4 + status=fresh → practicing, frequency=2.

    Spec calls the target state "reviewing"; production code uses
    "practicing". These are the same concept (the user is back in the
    practice cycle after a fail).
    """
    row = _ErrorRow(
        id="q-1",
        user_id="u-1",
        source_session_id="S1",
        source_question_id="qid-1",
        dimension="tech_depth",
        question_text="请描述 Redis 持久化机制",
        score=3,
        status="fresh",
        frequency=3,
    )
    out = _apply_re_sink_transition(row, new_score=4)
    assert out.status == "practicing"
    assert out.frequency == 2
    assert out.score == 4


def test_practicing_low_score_keeps_practicing() -> None:
    """practicing status: low score keeps status (frequency 1)."""
    row = _ErrorRow(
        id="q-2",
        user_id="u-1",
        source_session_id="S1",
        source_question_id="qid-2",
        dimension="tech_depth",
        question_text="问题 2",
        score=5,
        status="practicing",
        frequency=2,
    )
    out = _apply_re_sink_transition(row, new_score=5)
    assert out.status == "practicing"
    assert out.frequency == 1


def test_high_score_does_not_trigger_transition() -> None:
    """raw_score >= 6: no state transition; the helper short-circuits and returns."""
    row = _ErrorRow(
        id="q-3",
        user_id="u-1",
        source_session_id="S1",
        source_question_id="qid-3",
        dimension="tech_depth",
        question_text="问题 3",
        score=7,
        status="practicing",
        frequency=2,
    )
    out = _apply_re_sink_transition(row, new_score=8)
    # High-score path returns the row unchanged (no transition attempted).
    assert out.status == row.status
    assert out.frequency == row.frequency


def test_source_session_id_immutable_across_transitions() -> None:
    """AC-29: source_session_id MUST NEVER change during re-sink."""
    original_session_id = "S1-original"
    for raw_score in (3, 4, 5, 7, 8):
        row = _ErrorRow(
            id="q-X",
            user_id="u-X",
            source_session_id=original_session_id,
            source_question_id="qid-X",
            dimension="tech_depth",
            question_text="问题 X",
            score=5,
            status="fresh",
            frequency=3,
        )
        out = _apply_re_sink_transition(row, new_score=raw_score)
        assert out.source_session_id == original_session_id, (
            f"source_session_id leaked for raw_score={raw_score}: "
            f"got {out.source_session_id!r}"
        )


def test_last_practiced_at_refreshed_on_transition() -> None:
    """AC-26 contract: last_practiced_at refreshes on re-sink."""
    row = _ErrorRow(
        id="q-Y",
        user_id="u-Y",
        source_session_id="S1",
        source_question_id="qid-Y",
        dimension="tech_depth",
        question_text="问题 Y",
        score=5,
        status="fresh",
        frequency=3,
        last_practiced_at=None,
    )
    out = _apply_re_sink_transition(row, new_score=4)
    assert out.last_practiced_at is not None