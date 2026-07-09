"""[AC-040-US1/US2] FR-008 — Feature flags + shared constants for the Interview agent.

US-1 (AC-8.1):
- ``INTERVIEW_USE_V2_STATE_SCHEMA`` selects between the legacy
  ``InterviewGraphState`` and the new three-layer schema
  (``InterviewInputState`` / ``InterviewOverallState`` / ``InterviewOutputState``).

US-2 (AC-8.1):
- ``INTERVIEW_USE_V2_NODE_SPLIT`` selects between the legacy single-node
  ``score`` and the new split ``score_llm`` + ``sink_error`` (FR-004).
- The two flags are independent: ``NODE_SPLIT`` is NOT aliased to
  ``STATE_SCHEMA``. All four combinations (False/False, False/True,
  True/False, True/True) are reachable and produce a usable graph.
- ``ERROR_THRESHOLD = 6`` matches the 0-10 score range used by the score
  prompt and the ``error_questions.score`` database constraint.
- ``MAX_QUESTIONS`` is referenced here so the US-2 routing function
  ``_route_after_score_llm`` has a single source of truth.
"""
from __future__ import annotations

import os


# ---------------------------------------------------------------------------
# Feature flags (FR-008 / US1 AC-8.1 / US2 AC-8.1).
# ---------------------------------------------------------------------------


def INTERVIEW_USE_V2_STATE_SCHEMA() -> bool:
    """Return the current value of the three-layer state schema flag.

    Reads ``INTERVIEW_USE_V2_STATE_SCHEMA`` from the environment. The
    default is ``False`` (legacy schema) to preserve backward compatibility
    during the dual-track period.

    Accepted truthy values: ``"true"``, ``"1"``, ``"yes"`` (case-insensitive).
    All other values (including unset) yield ``False``.
    """
    raw = os.environ.get("INTERVIEW_USE_V2_STATE_SCHEMA", "").strip().lower()
    return raw in ("true", "1", "yes")


def INTERVIEW_USE_V2_NODE_SPLIT() -> bool:
    """Return the current value of the node-split flag (US2 AC-8.1).

    Reads ``INTERVIEW_USE_V2_NODE_SPLIT`` from the environment. The
    default is ``False`` so existing callers continue to use the legacy
    single-node ``score`` path for at least one release cycle (AC-8.3).

    Per US2 R11'' (round 3): this flag is **independent** from
    ``INTERVIEW_USE_V2_STATE_SCHEMA``. The two flags are read on
    independent lines (no shared ``if/elif`` chain) so any combination
    is reachable.

    Accepted truthy values: ``"true"``, ``"1"``, ``"yes"`` (case-insensitive).
    All other values (including unset) yield ``False``.
    """
    raw = os.environ.get("INTERVIEW_USE_V2_NODE_SPLIT", "").strip().lower()
    return raw in ("true", "1", "yes")


def build_interview_state_schema() -> type:
    """Pick the state schema to use for the Interview graph.

    Returns
    -------
    type
        ``InterviewOverallState`` (the three-layer overall state) when
        ``INTERVIEW_USE_V2_STATE_SCHEMA`` is true; otherwise the legacy
        ``InterviewGraphState``.
    """
    # Local imports to avoid circular dependency at module load
    if INTERVIEW_USE_V2_STATE_SCHEMA():
        from app.agents.interview.state import InterviewOverallState

        return InterviewOverallState
    from app.agents.interview.state import InterviewGraphState

    return InterviewGraphState


# ---------------------------------------------------------------------------
# Shared constants (US2 AC-4.5).
# ---------------------------------------------------------------------------

#: DEPRECATED — legacy 5-question interview (US2 AC-4.5). US3 introduces
#: the 7-15 envelope via ``app.agents.interview.effective_max``. This
#: constant is retained for callers that still reference it (the legacy
#: quick_drill mode still uses 5 — but that's sourced from
#: ``error_question_ids`` length, not from MAX_QUESTIONS).
MAX_QUESTIONS = 5

#: REQ-048 US3 T067 — re-export the US3 envelope constants so callers
#: can read them from either ``config`` or ``effective_max`` module.
from app.agents.interview.effective_max import (
    ADAPTIVE_TERMINATION_THRESHOLD as _ADAPTIVE_TERMINATION_THRESHOLD,
    ADAPTIVE_TERMINATION_WINDOW as _ADAPTIVE_TERMINATION_WINDOW,
    HARD_MAX_QUESTIONS_FULL as _HARD_MAX_QUESTIONS_FULL,
    HARD_MIN_QUESTIONS_FULL as _HARD_MIN_QUESTIONS_FULL,
    MAX_QUESTIONS_FULL as _MAX_QUESTIONS_FULL,
    MIN_QUESTIONS_FULL as _MIN_QUESTIONS_FULL,
)

MIN_QUESTIONS_FULL = _MIN_QUESTIONS_FULL
MAX_QUESTIONS_FULL = _MAX_QUESTIONS_FULL
HARD_MIN_QUESTIONS_FULL = _HARD_MIN_QUESTIONS_FULL
HARD_MAX_QUESTIONS_FULL = _HARD_MAX_QUESTIONS_FULL
ADAPTIVE_TERMINATION_THRESHOLD = _ADAPTIVE_TERMINATION_THRESHOLD
ADAPTIVE_TERMINATION_WINDOW = _ADAPTIVE_TERMINATION_WINDOW

#: Score below which an answer is auto-sunk to the error_questions book
#: (US2 AC-4.5). Value 6 = low score on the 0-10 scale used by the score
#: prompt, interview reports, ability dimensions, and error_questions.
ERROR_THRESHOLD = 6

#: Maximum number of node-internal retries for ``sink_error`` (US2 AC-4.7a).
#: Independent of ``retry_graph_op`` retries — this is a per-node backoff
#: for transient ``OperationalError`` from the DB.
SINK_ERROR_MAX_RETRIES = 3


__all__ = [
    "ADAPTIVE_TERMINATION_THRESHOLD",
    "ADAPTIVE_TERMINATION_WINDOW",
    "ERROR_THRESHOLD",
    "HARD_MAX_QUESTIONS_FULL",
    "HARD_MIN_QUESTIONS_FULL",
    "INTERVIEW_USE_V2_NODE_SPLIT",
    "INTERVIEW_USE_V2_STATE_SCHEMA",
    "MAX_QUESTIONS",
    "MAX_QUESTIONS_FULL",
    "MIN_QUESTIONS_FULL",
    "SINK_ERROR_MAX_RETRIES",
    "build_interview_state_schema",
]
