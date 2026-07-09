"""[REQ-048 US3 T067/T068] effective_max + adaptive termination helpers.

Pure functions extracted from the agent config so that:
1. They can be unit-tested without spinning up the graph.
2. The hard envelope + adaptive termination logic stays in one place
   that ``question_gen``, ``_route_after_score_llm``, and the planner
   prompt all share.

Constants mirror plan.md R-6 + spec.md SC-020/021/022 + FR-021..FR-023.

Public API:

- ``MIN_QUESTIONS_FULL`` / ``MAX_QUESTIONS_FULL`` — soft envelope [7, 15].
- ``HARD_MIN_QUESTIONS_FULL`` / ``HARD_MAX_QUESTIONS_FULL`` — same as the
  soft envelope for US3 (no override). Kept as named constants so future
  features can widen the hard envelope without breaking the formula.
- ``ADAPTIVE_TERMINATION_THRESHOLD`` — score threshold (8.0).
- ``ADAPTIVE_TERMINATION_WINDOW`` — number of consecutive scores (3).
- ``compute_effective_max(user_choice, planner_recommended)`` — formula
  ``max(7, min(user_choice, planner_recommended))`` per FR-023.
- ``compute_planner_recommended(focus_area_count)`` — heuristic
  ``focus_area_count × 4`` (midpoint of [3, 5]) clamped to [7, 15].
- ``compute_effective_max_for_legacy(stored_max_questions)`` — legacy
  default (5 or None) → 7. Used by AC-15.
- ``should_terminate_adaptive(current_question, effective_max, recent_scores)``
  — bool predicate that ``_route_after_score_llm`` consults to early-stop.
"""
from __future__ import annotations

from typing import Iterable

# ---------------------------------------------------------------------------
# Constants (FR-023 + FR-021 + FR-022).
# ---------------------------------------------------------------------------

#: Soft envelope — the user choice & planner_recommended must land here.
MIN_QUESTIONS_FULL: int = 7
#: Upper bound of the soft envelope.
MAX_QUESTIONS_FULL: int = 15
#: Hard minimum — effective_max can never go below this (R6 plan.md).
#: Same value as MIN for US3, kept as a named constant for future flexibility.
HARD_MIN_QUESTIONS_FULL: int = 7
#: Hard maximum — effective_max can never exceed this (R6 plan.md).
HARD_MAX_QUESTIONS_FULL: int = 15

#: Adaptive termination — score threshold for the rolling window.
ADAPTIVE_TERMINATION_THRESHOLD: float = 8.0
#: Adaptive termination — number of consecutive scores required.
ADAPTIVE_TERMINATION_WINDOW: int = 3


def _clamp(value: int, lo: int, hi: int) -> int:
    return max(lo, min(value, hi))


def compute_effective_max(user_choice: int, planner_recommended: int) -> int:
    """FR-023 — effective_max = max(HARD_MIN, min(user_choice, planner_recommended)).

    Per AC-12a / AC-12b the boundary cases are:
    - user=10, planner=5  → 7  (planner below floor — clamped up).
    - user=15, planner=20 → 15 (planner above cap — clamped down).

    The formula applies ``min(user_choice, planner_recommended)`` and
    then clamps the result to [HARD_MIN, HARD_MAX], so any input is
    accepted as long as the *result* lands in the envelope.

    Parameters
    ----------
    user_choice : int
        The user's chosen档位 (10 or 15 per FR-022).
    planner_recommended : int
        The planner's recommendation derived from focus_areas × [3, 5]
        题 per FR-023. May be outside the envelope — the formula
        clamps it. ``compute_planner_recommended`` always returns a
        clamped value, but this helper accepts raw values too so
        AC-12a boundary assertions (5 and 20) work directly.

    Returns
    -------
    int
        The clamped effective question count, in [HARD_MIN, HARD_MAX].

    Raises
    ------
    ValueError
        If ``user_choice`` is outside the soft envelope (the user
        cannot pick outside [7, 15] — that's a contract violation).
        ``planner_recommended`` is clamped, not validated, so the
        boundary cases AC-12a (5, 20) work.
    """
    if not (MIN_QUESTIONS_FULL <= user_choice <= MAX_QUESTIONS_FULL):
        raise ValueError(
            f"user_choice={user_choice} out of envelope "
            f"[{MIN_QUESTIONS_FULL}, {MAX_QUESTIONS_FULL}]"
        )
    return _clamp(
        min(user_choice, planner_recommended),
        HARD_MIN_QUESTIONS_FULL,
        HARD_MAX_QUESTIONS_FULL,
    )


def compute_planner_recommended(focus_area_count: int) -> int:
    """FR-023 — derive planner_recommended from focus_areas count.

    Heuristic: ``focus_area_count × 4`` (midpoint of [3, 5] questions
    per focus area), clamped to the [7, 15] envelope. With 0 focus_areas
    we fall back to the hard minimum (defensive default).

    Examples
    --------
    >>> compute_planner_recommended(2)
    8
    >>> compute_planner_recommended(3)
    12
    >>> compute_planner_recommended(4)
    15  # 16 capped to hard max
    >>> compute_planner_recommended(5)
    15  # 20 capped to hard max
    """
    if focus_area_count <= 0:
        return HARD_MIN_QUESTIONS_FULL
    raw = focus_area_count * 4
    return _clamp(raw, HARD_MIN_QUESTIONS_FULL, HARD_MAX_QUESTIONS_FULL)


def compute_effective_max_for_legacy(stored_max_questions: int | None) -> int:
    """AC-15 — backfill for legacy sessions (R12).

    Legacy sessions stored ``max_questions=5`` before migration 0028.
    The new effective_max formula floors to 7 anyway, but this helper
    makes the intent explicit and returns 7 regardless of whether the
    stored value is 5 or NULL.
    """
    if stored_max_questions is None:
        return HARD_MIN_QUESTIONS_FULL
    # Whatever the legacy stored value (5, 10, etc.), the new effective
    # envelope clamps it to [7, 15]. Legacy 5 → 7. Legacy 10 → 10.
    return _clamp(stored_max_questions, HARD_MIN_QUESTIONS_FULL, HARD_MAX_QUESTIONS_FULL)


def _consecutive_high_scores(recent_scores: Iterable[float]) -> bool:
    """True iff the last ADAPTIVE_TERMINATION_WINDOW scores are >= threshold."""
    scores = list(recent_scores)
    if len(scores) < ADAPTIVE_TERMINATION_WINDOW:
        return False
    window = scores[-ADAPTIVE_TERMINATION_WINDOW:]
    return all(s >= ADAPTIVE_TERMINATION_THRESHOLD for s in window)


def should_terminate_adaptive(
    current_question: int,
    effective_max: int,
    recent_scores: Iterable[float],
) -> bool:
    """AC-14 — adaptive termination predicate.

    Returns True iff:
    - The last ADAPTIVE_TERMINATION_WINDOW scores are all >= threshold.
    - current_question >= HARD_MIN_QUESTIONS_FULL (hard floor, blocks early).
    - current_question >= effective_max - ADAPTIVE_TERMINATION_WINDOW.

    The hard floor check ensures that even a candidate with perfect scores
    cannot terminate below 7 questions — protects report sample size.
    """
    if current_question < HARD_MIN_QUESTIONS_FULL:
        return False
    if current_question < effective_max - ADAPTIVE_TERMINATION_WINDOW:
        return False
    return _consecutive_high_scores(recent_scores)


__all__ = [
    "ADAPTIVE_TERMINATION_THRESHOLD",
    "ADAPTIVE_TERMINATION_WINDOW",
    "HARD_MAX_QUESTIONS_FULL",
    "HARD_MIN_QUESTIONS_FULL",
    "MAX_QUESTIONS_FULL",
    "MIN_QUESTIONS_FULL",
    "compute_effective_max",
    "compute_effective_max_for_legacy",
    "compute_planner_recommended",
    "should_terminate_adaptive",
]