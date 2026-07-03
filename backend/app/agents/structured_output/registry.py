"""REQ-038 US1 P1 — Structured-output registry.

STRUCTURED_NODES is the canonical list of node IDs that must use the
structured-output API. NODE_SCHEMAS is the bidirectional mapping every
test (AC-002) asserts against.

US1 P1 (in scope, this round):
    - interview.intake
    - interview.score
    - error_coach.evaluate

Deferred (US2+):
    - planner_generate            (deferred_for=US2)
    - report                      (deferred_for=US2)
    - question_gen                (deferred_for=US3)
    - general_coach.intent        (deferred_for=US3)
    - resume_optimize.suggest_blocks (deferred_for=US4)
    - ability_diagnose.generate_insight (deferred_for=US4)

[ac-completed: AC-001]
"""
from __future__ import annotations

from app.agents.structured_output.schemas import (
    ErrorCoachEvalInput,
    ErrorCoachEvalOutput,
    InterviewIntakeInput,
    InterviewIntakeOutput,
    InterviewScoreInput,
    InterviewScoreOutput,
)

STRUCTURED_NODES: list[str] = [
    "interview.intake",        # US1 P1
    "interview.score",         # US1 P1
    "error_coach.evaluate",    # US1 P1
    # deferred_for=US2+
    # "planner_generate",
    # "report",
    # deferred_for=US3+
    # "question_gen",
    # "general_coach.intent",
    # deferred_for=US4+
    # "resume_optimize.suggest_blocks",
    # "ability_diagnose.generate_insight",
]


# Bidirectional mapping: every node ID MUST appear here. AC-002 assertion
# `set(NODE_SCHEMAS.keys()) == set(STRUCTURED_NODES)` depends on that.
NODE_SCHEMAS: dict[str, tuple[type, type]] = {
    "interview.intake": (InterviewIntakeInput, InterviewIntakeOutput),
    "interview.score": (InterviewScoreInput, InterviewScoreOutput),
    "error_coach.evaluate": (ErrorCoachEvalInput, ErrorCoachEvalOutput),
}


def get_input_schema(node_id: str) -> type:
    """Return the input schema class for a node ID."""
    if node_id not in NODE_SCHEMAS:
        raise KeyError(
            f"Unknown structured node '{node_id}'. "
            f"Available: {', '.join(sorted(NODE_SCHEMAS))}"
        )
    return NODE_SCHEMAS[node_id][0]


def get_output_schema(node_id: str) -> type:
    """Return the output schema class for a node ID."""
    if node_id not in NODE_SCHEMAS:
        raise KeyError(
            f"Unknown structured node '{node_id}'. "
            f"Available: {', '.join(sorted(NODE_SCHEMAS))}"
        )
    return NODE_SCHEMAS[node_id][1]


# ---------------------------------------------------------------------------
# US4: Free-form and deferred node registries
# ---------------------------------------------------------------------------

FREE_FORM_NODES: tuple[str, ...] = (
    "error_coach.hint_ladder",
    "general_coach.respond",
)

DEFERRED_STRUCTURED_NODES: tuple[str, ...] = (
    "interview.question_gen",
    "interview.report",
    "general_coach.intent",
    "resume_optimize.diff_jd",
    "resume_optimize.suggest_blocks",
    "ability_diagnose.generate_insight",
)


__all__ = [
    "STRUCTURED_NODES",
    "NODE_SCHEMAS",
    "FREE_FORM_NODES",
    "DEFERRED_STRUCTURED_NODES",
    "get_input_schema",
    "get_output_schema",
]