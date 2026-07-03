"""[AC-040-US1] FR-008 — Feature flag for three-layer state schema migration.

Per AC-8.1, the flag is read from the ``INTERVIEW_USE_V2_STATE_SCHEMA``
environment variable, defaulting to ``False`` so existing callers
continue to work against the legacy single-TypedDict ``InterviewGraphState``
for at least one release cycle (per AC-8.3 — see ``state.py`` for the
deprecation comment and TODO marker for release manager).

Per AC-8.2, the graph builder consults ``build_interview_state_schema()``
to pick between the legacy schema and the new three-layer
``InterviewOverallState``.
"""
from __future__ import annotations

import os


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


__all__ = [
    "INTERVIEW_USE_V2_STATE_SCHEMA",
    "build_interview_state_schema",
]
