"""Shared REQ-045 LLM Ops eval schemas.

These models are intentionally persistence-neutral. ORM tables and local
reports can map to them, but CI/local eval artifacts remain canonical.
"""
from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator, model_validator

UNAVAILABLE = "unavailable"


class Environment(StrEnum):
    LOCAL = "LOCAL"
    CI = "CI"
    STAGING = "STAGING"
    PRODUCTION = "PRODUCTION"


class RepresentationLevel(StrEnum):
    FULL_CONTENT = "FULL_CONTENT"
    REDACTED = "REDACTED"
    METADATA_ONLY = "METADATA_ONLY"
    BLOCKED = "BLOCKED"


class ExportDestination(StrEnum):
    LOCAL_ARTIFACT = "LOCAL_ARTIFACT"
    LANGSMITH = "LANGSMITH"
    OTLP_GENERIC = "OTLP_GENERIC"


class ExportStatus(StrEnum):
    DISABLED = "DISABLED"
    PENDING = "PENDING"
    SYNCED = "SYNCED"
    FAILED = "FAILED"
    PARTIAL = "PARTIAL"


class EvalCaseLifecycle(StrEnum):
    GOLDEN = "GOLDEN"
    CANDIDATE = "CANDIDATE"
    REPORT_ONLY = "REPORT_ONLY"
    DEPRECATED = "DEPRECATED"
    REJECTED = "REJECTED"


class EvalRunStatus(StrEnum):
    CREATED = "CREATED"
    RUNNING = "RUNNING"
    PASSED = "PASSED"
    FAILED = "FAILED"
    INCOMPLETE = "INCOMPLETE"
    ERROR = "ERROR"


class JudgeCalibrationStatus(StrEnum):
    DRAFT = "DRAFT"
    REPORT_ONLY = "REPORT_ONLY"
    CALIBRATED = "CALIBRATED"
    WAIVED = "WAIVED"
    BLOCKING_ENABLED = "BLOCKING_ENABLED"
    BLOCKING_DISABLED = "BLOCKING_DISABLED"


class ProposalStatus(StrEnum):
    DRAFT = "DRAFT"
    READY_FOR_COMPARISON = "READY_FOR_COMPARISON"
    COMPARED = "COMPARED"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    APPLIED = "APPLIED"


class ProposalType(StrEnum):
    PROMPT = "PROMPT"
    RUBRIC = "RUBRIC"
    DATASET = "DATASET"
    EVALUATOR = "EVALUATOR"


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _new_id(prefix: str) -> str:
    return f"{prefix}-{uuid4()}"


class Req045Model(BaseModel):
    model_config = ConfigDict(use_enum_values=False, extra="forbid")


class TraceRunReference(Req045Model):
    trace_run_ref_id: str = Field(default_factory=lambda: _new_id("trace-ref"))
    run_id: str
    case_id: str | None = None
    trace_id: str | None = None
    span_id: str | None = None
    artifact_ref: str | None = None
    langsmith_url: HttpUrl | str | None = None
    entrypoint: str | None = None
    created_at: datetime = Field(default_factory=_utc_now)

    @field_validator("trace_id")
    @classmethod
    def _validate_trace_id(cls, value: str | None) -> str | None:
        if value in (None, "", UNAVAILABLE):
            return None
        if len(value) != 32 or not all(c in "0123456789abcdef" for c in value):
            raise ValueError("trace_id must be 32 lowercase hex characters")
        return value

    @field_validator("span_id")
    @classmethod
    def _validate_span_id(cls, value: str | None) -> str | None:
        if value in (None, "", UNAVAILABLE):
            return None
        if len(value) != 16 or not all(c in "0123456789abcdef" for c in value):
            raise ValueError("span_id must be 16 lowercase hex characters")
        return value

    @property
    def trace_id_display(self) -> str:
        return self.trace_id or UNAVAILABLE

    @property
    def artifact_ref_display(self) -> str:
        return self.artifact_ref or UNAVAILABLE

    @property
    def langsmith_url_display(self) -> str:
        return str(self.langsmith_url) if self.langsmith_url else UNAVAILABLE


class EvalRunRecord(Req045Model):
    run_id: str = Field(default_factory=lambda: _new_id("eval-run"))
    suite: str
    environment: Environment
    status: EvalRunStatus
    source_revision: str = UNAVAILABLE
    branch: str | None = None
    dataset_version: str
    prompt_fingerprint: str = UNAVAILABLE
    rubric_version: str = UNAVAILABLE
    model_version: str = UNAVAILABLE
    started_at: datetime = Field(default_factory=_utc_now)
    finished_at: datetime | None = None
    aggregate_pass_rate: float | None = Field(default=None, ge=0.0, le=1.0)
    known_regression_recall: float | None = Field(default=None, ge=0.0, le=1.0)
    token_usage: dict[str, int] = Field(default_factory=dict)
    cost_usd: float | None = Field(default=None, ge=0.0)
    latency_ms: int | None = Field(default=None, ge=0)
    local_artifacts: dict[str, str] = Field(default_factory=dict)
    langsmith_export_status: ExportStatus = ExportStatus.DISABLED
    export_policy_decision_id: str | None = None

    @model_validator(mode="after")
    def _require_revision_for_nonlocal(self) -> "EvalRunRecord":
        if self.environment in {Environment.CI, Environment.STAGING, Environment.PRODUCTION}:
            if self.source_revision in ("", UNAVAILABLE):
                raise ValueError("source_revision is required for CI/staging/production")
        return self


class EvalCaseResultRecord(Req045Model):
    case_result_id: str = Field(default_factory=lambda: _new_id("case-result"))
    case_id: str
    run_id: str
    lifecycle: EvalCaseLifecycle
    graph: str
    node: str
    passed: bool
    failure_reasons: list[str] = Field(default_factory=list)
    deterministic_metrics: dict[str, Any] = Field(default_factory=dict)
    expected_fidelity_pass: bool | None = None
    artifact_ref: str = UNAVAILABLE
    trace_run_ref_id: str | None = None
    langsmith_run_url: str = UNAVAILABLE
    judge_verdict_ids: list[str] = Field(default_factory=list)

    @property
    def blocks_merge(self) -> bool:
        return self.lifecycle == EvalCaseLifecycle.GOLDEN and not self.passed


class LangSmithExperimentRefRecord(Req045Model):
    langsmith_ref_id: str = Field(default_factory=lambda: _new_id("langsmith-ref"))
    run_id: str
    project: str
    dataset_name: str
    dataset_version: str
    experiment_name: str
    experiment_url: str | None = None
    sync_status: ExportStatus
    synced_at: datetime | None = None
    error_code: str | None = None
    error_message: str | None = None

    @model_validator(mode="after")
    def _require_url_when_synced(self) -> "LangSmithExperimentRefRecord":
        if self.sync_status == ExportStatus.SYNCED and not self.experiment_url:
            raise ValueError("experiment_url is required when sync_status is SYNCED")
        return self


class ExportPolicyDecisionRecord(Req045Model):
    decision_id: str = Field(default_factory=lambda: _new_id("export-decision"))
    destination: ExportDestination
    environment: Environment
    representation_level: RepresentationLevel
    policy_version: str
    owner: str | None = None
    access_scope: str | None = None
    retention_days: int | None = Field(default=None, ge=0)
    allowed_content_classes: list[str] = Field(default_factory=list)
    blocked_reason: str | None = None
    sample_rate: float = Field(default=1.0, ge=0.0, le=1.0)
    created_at: datetime = Field(default_factory=_utc_now)
    secret_classes_blocked: bool = True

    @model_validator(mode="after")
    def _validate_full_content_langsmith_policy(self) -> "ExportPolicyDecisionRecord":
        full_prod_langsmith = (
            self.destination == ExportDestination.LANGSMITH
            and self.environment == Environment.PRODUCTION
            and self.representation_level == RepresentationLevel.FULL_CONTENT
        )
        if full_prod_langsmith:
            missing = [
                name
                for name, value in (
                    ("owner", self.owner),
                    ("access_scope", self.access_scope),
                    ("retention_days", self.retention_days),
                    ("policy_version", self.policy_version),
                )
                if value in (None, "")
            ]
            if not self.allowed_content_classes:
                missing.append("allowed_content_classes")
            if missing:
                raise ValueError(
                    "production full-content LangSmith export missing "
                    + ", ".join(missing)
                )
        if (
            self.destination == ExportDestination.OTLP_GENERIC
            and self.representation_level == RepresentationLevel.FULL_CONTENT
        ):
            raise ValueError("OTLP_GENERIC cannot receive FULL_CONTENT AI payloads")
        return self

    @property
    def is_external(self) -> bool:
        return self.destination in {ExportDestination.LANGSMITH, ExportDestination.OTLP_GENERIC}


class JudgeRubricRecord(Req045Model):
    rubric_id: str = Field(default_factory=lambda: _new_id("rubric"))
    name: str
    version: str
    dimensions: list[str]
    scale: dict[str, Any]
    judge_model: str
    calibration_status: JudgeCalibrationStatus
    human_label_count: int = Field(default=0, ge=0)
    agreement_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    owner: str
    waiver_reason: str | None = None
    created_at: datetime = Field(default_factory=_utc_now)
    updated_at: datetime = Field(default_factory=_utc_now)

    @model_validator(mode="after")
    def _blocking_requires_calibration_or_waiver(self) -> "JudgeRubricRecord":
        if self.calibration_status == JudgeCalibrationStatus.BLOCKING_ENABLED:
            calibrated = self.human_label_count >= 30 and self.agreement_rate >= 0.80
            waived = bool(self.waiver_reason)
            if not calibrated and not waived:
                raise ValueError("blocking judge rubric requires calibration or waiver")
        return self


class PromptImprovementProposalRecord(Req045Model):
    proposal_id: str = Field(default_factory=lambda: _new_id("proposal"))
    status: ProposalStatus
    source_run_ids: list[str]
    source_case_ids: list[str]
    target_graph: str
    target_node: str
    proposal_type: ProposalType
    candidate_fingerprint: str
    expected_impact: str
    comparison_run_id: str | None = None
    approval_owner: str | None = None
    created_at: datetime = Field(default_factory=_utc_now)
    updated_at: datetime = Field(default_factory=_utc_now)

    @model_validator(mode="after")
    def _approval_requires_evidence(self) -> "PromptImprovementProposalRecord":
        if self.status in {ProposalStatus.APPROVED, ProposalStatus.APPLIED}:
            if not self.comparison_run_id:
                raise ValueError("approved/applied prompt proposals require comparison_run_id")
            if not self.approval_owner:
                raise ValueError("approved/applied prompt proposals require approval_owner")
        return self


__all__ = [
    "UNAVAILABLE",
    "Environment",
    "EvalCaseLifecycle",
    "EvalCaseResultRecord",
    "EvalRunRecord",
    "EvalRunStatus",
    "ExportDestination",
    "ExportPolicyDecisionRecord",
    "ExportStatus",
    "JudgeCalibrationStatus",
    "JudgeRubricRecord",
    "LangSmithExperimentRefRecord",
    "PromptImprovementProposalRecord",
    "ProposalStatus",
    "ProposalType",
    "RepresentationLevel",
    "TraceRunReference",
]
