"""Strict, versioned schemas for REQ-059 model and HTTP boundaries."""
from __future__ import annotations

from enum import StrEnum
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class AnalysisMode(StrEnum):
    GENERAL = "general"
    JOB_FIT = "job_fit"


class GapCoverage(StrEnum):
    COVERED = "covered"
    WEAK = "weak"
    EVIDENCE_NOT_SHOWN = "evidence_not_shown"
    MISSING_EVIDENCE = "missing_evidence"
    REAL_GAP = "real_gap"
    UNKNOWN = "unknown"


class SourceRef(StrictModel):
    source_id: str = Field(min_length=1)
    source_type: Literal["root_resume", "current_resume", "confirmed_supplement"]
    anchor: str = Field(min_length=1)
    content_hash: str = Field(min_length=8)
    excerpt: str | None = None


class RequirementEvidence(StrictModel):
    requirement_id: str = Field(min_length=1)
    priority: Literal["hard", "important", "nice"]
    coverage: GapCoverage
    confidence: float = Field(ge=0, le=1)
    evidence_refs: list[SourceRef] = Field(default_factory=list)
    explanation: str = Field(min_length=1)


class EvidenceMapOutput(StrictModel):
    requirements: list[RequirementEvidence] = Field(default_factory=list)


class JobRequirement(StrictModel):
    requirement_id: str = Field(min_length=1)
    text: str = Field(min_length=1)
    priority: Literal["hard", "important", "nice"]
    category: Literal[
        "hard_requirements",
        "experience_evidence",
        "skills_keywords",
        "outcomes_quantification",
        "responsibility_relevance",
        "expression_readability",
    ]


class JobParseOutput(StrictModel):
    position: str = Field(min_length=1)
    requirements: list[JobRequirement]
    jd_quality: float = Field(ge=0, le=1)
    quality_reasons: list[str] = Field(default_factory=list)


class DraftRewrite(StrictModel):
    source_ref: str = Field(min_length=1)
    text: str = Field(min_length=1)
    source_refs: list[str] = Field(min_length=1)
    reason: str = Field(min_length=1)


class DraftOutput(StrictModel):
    summary: str
    summary_source_refs: list[str] = Field(default_factory=list)
    rewrites: list[DraftRewrite] = Field(default_factory=list)
    omitted_source_refs: list[str] = Field(default_factory=list)


class AISuggestionOutput(StrictModel):
    suggestion_id: str
    priority: Literal["high", "medium", "low"]
    kind: Literal["rewrite", "add_evidence", "quantify", "reorder", "remove", "manual_review"]
    action_mode: Literal["direct", "needs_supplement", "needs_judgment", "do_not_write"]
    title: str
    explanation: str
    source_refs: list[str] = Field(default_factory=list)
    requirement_refs: list[str] = Field(default_factory=list)
    source_ref: str | None = None
    replacement_text: str | None = None


class SuggestionListOutput(StrictModel):
    suggestions: list[AISuggestionOutput] = Field(default_factory=list)


class ErrorEnvelope(StrictModel):
    code: str
    message: str
    retryable: bool = False
    details: dict[str, object] = Field(default_factory=dict)


class AnalysisRunIn(StrictModel):
    mode: AnalysisMode
    client_version: int = Field(ge=0)
    job_id: UUID | None = None
    force: bool = False


class FeedbackIn(StrictModel):
    analysis_id: UUID
    suggestion_id: UUID | None = None
    change_set_id: UUID | None = None
    category: Literal[
        "helpful", "not_applicable", "repeated", "poor_wording", "fact_error", "other"
    ]
    comment: str | None = Field(default=None, max_length=1000)


class SuggestionStatusIn(StrictModel):
    action: Literal["ignore", "defer", "open", "reopen"]
    reason: str | None = Field(default=None, max_length=500)


class ConfirmSupplementIn(StrictModel):
    resume_id: UUID
    question_id: str = Field(min_length=1)
    text: str = ""
    scope: Literal["derived_only", "root", "discard"]
    confirmed: bool = True


class PreviewBatchIn(StrictModel):
    analysis_id: UUID
    suggestion_ids: list[UUID] = Field(min_length=1, max_length=50)
    client_version: int = Field(ge=0)


class ApplyBatchIn(StrictModel):
    preview_token: str = Field(min_length=20)
    client_version: int = Field(ge=0)


class UndoChangeSetIn(StrictModel):
    client_version: int = Field(ge=0)
