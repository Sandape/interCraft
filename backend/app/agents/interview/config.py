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
- ``ERROR_THRESHOLD = 60`` (R4'' 轮 3 修订) — the value carried over from
  the legacy ``score.py:21`` constant ``ERROR_THRESHOLD = 6`` was wrong
  by an order of magnitude; the new constant is in 0–100 scale, matching
  the actual LLM score range used by the score prompt.
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

#: Maximum number of interview questions in a session (US2 AC-4.5).
MAX_QUESTIONS = 5

#: Score below which an answer is auto-sunk to the error_questions book
#: (US2 AC-4.5). Value 60 = 0–100 scale, matching the LLM score prompt.
#: (Legacy ``score.py:21`` declared ``ERROR_THRESHOLD = 6`` which was a
#: 0–10 scale; this constant supersedes it and lives at the agent-config
#: level so all score-routing code reads the same value.)
ERROR_THRESHOLD = 60

#: Maximum number of node-internal retries for ``sink_error`` (US2 AC-4.7a).
#: Independent of ``retry_graph_op`` retries — this is a per-node backoff
#: for transient ``OperationalError`` from the DB.
SINK_ERROR_MAX_RETRIES = 3


__all__ = [
    "ERROR_THRESHOLD",
    "INTERVIEW_USE_V2_NODE_SPLIT",
    "INTERVIEW_USE_V2_STATE_SCHEMA",
    "MAX_QUESTIONS",
    "SINK_ERROR_MAX_RETRIES",
    "build_interview_state_schema",
]