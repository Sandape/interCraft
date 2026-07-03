"""REQ-038 US1 P1 — Pydantic schemas per node.

`Schema` is the type-root alias used as the type hint for schema arguments.
Each node has an Input/Output pair registered in ``NODE_SCHEMAS``.

[ac-completed: AC-002]
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

# Schema is the type-root alias exposed by the package __init__.
Schema = type[BaseModel]


# ---------------------------------------------------------------------------
# interview.intake
# ---------------------------------------------------------------------------
class InterviewIntakeInput(BaseModel):
    """Input to the interview intake node."""

    user_id: str = Field(..., min_length=1)
    jd_text: str = Field(..., min_length=1)
    resume_summary: str = ""


class InterviewIntakeOutput(BaseModel):
    """Output of the interview intake node."""

    next_question: str = Field(..., min_length=1)
    topic: str = Field(..., min_length=1)
    difficulty: Literal["easy", "medium", "hard"] = "medium"


# ---------------------------------------------------------------------------
# interview.score
# ---------------------------------------------------------------------------
class InterviewScoreInput(BaseModel):
    """Input to the interview scoring node."""

    user_id: str = Field(..., min_length=1)
    transcript: str = Field(..., min_length=1)


class InterviewScoreOutput(BaseModel):
    """Output of the interview scoring node."""

    score: float = Field(..., ge=0.0, le=100.0)
    feedback: str = Field(..., min_length=1)


# ---------------------------------------------------------------------------
# error_coach.evaluate
# ---------------------------------------------------------------------------
class ErrorCoachEvalInput(BaseModel):
    """Input to the error-coach evaluate node."""

    user_id: str = Field(..., min_length=1)
    code_snippet: str = Field(..., min_length=1)


class ErrorCoachEvalOutput(BaseModel):
    """Output of the error-coach evaluate node."""

    severity: Literal["low", "medium", "high"]
    diagnosis: str = Field(..., min_length=1)
    score: float = Field(..., ge=0.0, le=100.0)


# All US1 P1 input/output pairs in one mapping for one-pass import by tests.
ALL_SCHEMAS: list[type[BaseModel]] = [
    InterviewIntakeInput,
    InterviewIntakeOutput,
    InterviewScoreInput,
    InterviewScoreOutput,
    ErrorCoachEvalInput,
    ErrorCoachEvalOutput,
]


__all__ = [
    "Schema",
    "InterviewIntakeInput",
    "InterviewIntakeOutput",
    "InterviewScoreInput",
    "InterviewScoreOutput",
    "ErrorCoachEvalInput",
    "ErrorCoachEvalOutput",
    "ALL_SCHEMAS",
]