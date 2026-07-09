"""[REQ-048 US3 T064] Unit test for adaptive termination logic.

AC-14 (R12) coverage: score >= 8.0 连续 3 题 + current >= effective_max - 3
触发提前生成报告. Hard floor: current < HARD_MIN (7) MUST NOT terminate,
even when the score-window condition is met.

Also exercises the 3 boundary cases explicitly called out in tasks.md T064:
1. 中等 10 题档, current=7 + 3 consecutive ≥8.0 → terminate.
2. 深入 15 题档, current=12 + 3 consecutive ≥8.0 → terminate.
3. Hard floor 7, current=6 + 3 consecutive ≥8.0 → MUST NOT terminate.

The router predicate is importable from
``app.agents.interview.effective_max.should_terminate_adaptive`` —
created in T067 (Batch C). TDD red phase: ``ModuleNotFoundError`` is
expected at this stage.
"""
from __future__ import annotations

import pytest

from app.agents.interview.effective_max import (
    ADAPTIVE_TERMINATION_THRESHOLD,
    ADAPTIVE_TERMINATION_WINDOW,
    HARD_MIN_QUESTIONS_FULL,
    should_terminate_adaptive,
)


# ---------------------------------------------------------------------------
# Constants locked.
# ---------------------------------------------------------------------------


def test_adaptive_constants_locked() -> None:
    """Per FR-021 / FR-022: threshold = 8.0, window = 3 consecutive."""
    assert ADAPTIVE_TERMINATION_THRESHOLD == 8.0
    assert ADAPTIVE_TERMINATION_WINDOW == 3
    assert HARD_MIN_QUESTIONS_FULL == 7


# ---------------------------------------------------------------------------
# AC-14 — boundary cases (tasks.md T064 explicit enumeration)
# ---------------------------------------------------------------------------


def test_termination_medium_10_questions_earliest_at_7() -> None:
    """AC-14: medium 10 题档, current=7 + last 3 scores all >= 8.0 → terminate.

    effective_max - 3 = 10 - 3 = 7. current=7 meets the floor.
    """
    assert should_terminate_adaptive(
        current_question=7,
        effective_max=10,
        recent_scores=[8.0, 8.5, 9.0],
    ) is True


def test_termination_deep_15_questions_earliest_at_12() -> None:
    """AC-14: deep 15 题档, current=12 + last 3 scores all >= 8.0 → terminate.

    effective_max - 3 = 15 - 3 = 12. current=12 meets the floor.
    """
    assert should_terminate_adaptive(
        current_question=12,
        effective_max=15,
        recent_scores=[8.0, 8.5, 9.0],
    ) is True


def test_termination_hard_floor_7_blocks_termination_at_current_6() -> None:
    """AC-14: hard lower bound 7 — current=6 + 3 consecutive ≥8.0 → MUST NOT terminate.

    Even when the score-window is met, the hard floor of 7 questions blocks
    early termination. This protects report sample size (R6 plan.md).
    """
    assert should_terminate_adaptive(
        current_question=6,
        effective_max=10,
        recent_scores=[8.0, 8.5, 9.0],
    ) is False


def test_termination_hard_floor_7_still_blocks_when_below_floor() -> None:
    """current=5 with even perfect scores MUST NOT terminate."""
    assert should_terminate_adaptive(
        current_question=5,
        effective_max=15,
        recent_scores=[10.0, 10.0, 10.0],
    ) is False


def test_termination_hard_floor_7_at_floor_with_perfect_scores_terminates() -> None:
    """current=7 (exactly at floor) + 3 consecutive ≥8.0 → terminate.

    This is the boundary case: once we hit 7 we can terminate if scores warrant.
    """
    assert should_terminate_adaptive(
        current_question=7,
        effective_max=10,
        recent_scores=[9.0, 9.0, 9.0],
    ) is True


# ---------------------------------------------------------------------------
# Score-window condition — 3 consecutive ≥ 8.0.
# ---------------------------------------------------------------------------


def test_termination_score_window_requires_3_consecutive() -> None:
    """Two consecutive high scores is not enough — need 3."""
    assert should_terminate_adaptive(
        current_question=10,
        effective_max=10,
        recent_scores=[8.0, 9.0],  # only 2
    ) is False


def test_termination_score_window_breaks_on_low_score() -> None:
    """A score < 8.0 breaks the consecutive run."""
    assert should_terminate_adaptive(
        current_question=10,
        effective_max=10,
        recent_scores=[8.0, 7.5, 9.0],  # middle score breaks the window
    ) is False


def test_termination_score_exactly_at_threshold_qualifies() -> None:
    """Score == 8.0 (exactly threshold) counts as a qualifying score."""
    assert should_terminate_adaptive(
        current_question=12,
        effective_max=15,
        recent_scores=[8.0, 8.0, 8.0],
    ) is True


def test_termination_score_just_below_threshold_fails() -> None:
    """Score == 7.99 < 8.0 → window fails."""
    assert should_terminate_adaptive(
        current_question=12,
        effective_max=15,
        recent_scores=[8.0, 8.0, 7.99],
    ) is False


# ---------------------------------------------------------------------------
# Edge: empty scores list.
# ---------------------------------------------------------------------------


def test_termination_empty_scores_does_not_terminate() -> None:
    """No scores yet → cannot meet window condition."""
    assert should_terminate_adaptive(
        current_question=10,
        effective_max=10,
        recent_scores=[],
    ) is False


# ---------------------------------------------------------------------------
# current_question < effective_max - 3 blocks termination (window floor)
# ---------------------------------------------------------------------------


def test_termination_current_below_window_floor_does_not_terminate() -> None:
    """Even with high scores, current < effective_max - 3 blocks."""
    # effective_max=15 → effective_max - 3 = 12. current=11 < 12.
    assert should_terminate_adaptive(
        current_question=11,
        effective_max=15,
        recent_scores=[9.0, 9.0, 9.0],
    ) is False


def test_termination_at_window_floor_terminates() -> None:
    """current == effective_max - 3 + high scores → terminate."""
    # effective_max=15 → floor=12. current=12.
    assert should_terminate_adaptive(
        current_question=12,
        effective_max=15,
        recent_scores=[9.0, 9.0, 9.0],
    ) is True


# ---------------------------------------------------------------------------
# Hard min via effective_max clamping.
# ---------------------------------------------------------------------------


def test_termination_hard_min_in_effective_max_blocks_below_7() -> None:
    """If effective_max somehow equals 7, current=6 must not terminate."""
    # Hypothetical: planner=5 → effective_max floors to 7.
    # current=6 + perfect scores must not terminate because 6 < 7.
    assert should_terminate_adaptive(
        current_question=6,
        effective_max=7,
        recent_scores=[10.0, 10.0, 10.0],
    ) is False


# ---------------------------------------------------------------------------
# Parametrized matrix covering all 3 task.md T064 explicit cases + extras.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("current_question", "effective_max", "recent_scores", "expected"),
    [
        # Task.md T064 explicit cases:
        (7, 10, [8.0, 8.5, 9.0], True),    # medium 10 — earliest
        (12, 15, [8.0, 8.5, 9.0], True),   # deep 15 — earliest
        (6, 10, [8.0, 8.5, 9.0], False),   # hard floor — blocked
        # Below floor cases:
        (5, 15, [10.0, 10.0, 10.0], False),
        (1, 10, [9.0, 9.0, 9.0], False),
        # Above window floor but score not met:
        (10, 10, [7.0, 7.0, 7.0], False),
        (12, 15, [8.0, 7.5, 9.0], False),
        # Score window:
        (10, 10, [8.0, 9.0], False),       # only 2
        (10, 10, [8.0, 8.0, 7.99], False), # just below
        # Boundary at hard floor:
        (7, 10, [9.0, 9.0, 9.0], True),
        (7, 10, [8.0, 8.0, 8.0], True),
    ],
)
def test_termination_matrix(
    current_question: int, effective_max: int, recent_scores: list[float], expected: bool
) -> None:
    """AC-14 termination matrix (10 cases)."""
    assert (
        should_terminate_adaptive(
            current_question=current_question,
            effective_max=effective_max,
            recent_scores=recent_scores,
        )
        is expected
    )