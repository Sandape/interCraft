"""REQ-033 — consolidated ORM models (REB-032 v2 MVP import stub).

The real models (Badcase, BadcaseReviewAction, TelemetrySpan,
PMDashboardSnapshot, etc.) are defined in their respective modules
per the FOUNDATION consolidation (T020). For the REB-032 v2 MVP we
only need this module to import cleanly so the badcases + pm_dashboard
shims can re-export from here. The full table definitions + Alembic
migrations ship via the 033 US phases.

We declare minimal table shells so the import chain stays green.
Runtime SQL is exercised through Alembic-migrated tables in the real
schema; the stubs below are intentionally not registered with the
shared ``Base.metadata`` so they don't shadow the production DDL.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import Boolean, DateTime, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class Badcase(Base):
    """Production Bad Case row (migration 0024 + 0060 extensions).

    Aligned with ``badcases`` DDL: stable ``badcase_id``, privacy/redaction,
    optimistic ``version``, closure evidence refs, SLA/owner fields.
    """

    __tablename__ = "badcases"
    __table_args__ = {"extend_existing": True}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    badcase_id: Mapped[str] = mapped_column(String(128), unique=True, nullable=False, index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True, nullable=False)
    type: Mapped[str] = mapped_column(String(64), nullable=False)
    severity: Mapped[str] = mapped_column(String(32), nullable=False, default="MEDIUM")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="OPEN")
    source: Mapped[str] = mapped_column(String(64), nullable=False)
    reviewer: Mapped[str | None] = mapped_column(String(128), nullable=True)
    privacy_class: Mapped[str] = mapped_column(String(32), nullable=False, default="UNKNOWN")
    redaction_status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="NOT_REQUIRED"
    )
    run_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    trace_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    closure_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # REQ-061 US10 extensions (migration 0060)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    category: Mapped[str | None] = mapped_column(String(128), nullable=True)
    owner: Mapped[str | None] = mapped_column(String(128), nullable=True)
    capabilities: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    first_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    point_treatment_status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="unknown"
    )
    sla_status: Mapped[str] = mapped_column(String(32), nullable=False, default="within_sla")
    sla_due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    user_visible_status: Mapped[str | None] = mapped_column(String(64), nullable=True)
    root_cause_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    reproduction_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    data_completeness: Mapped[str] = mapped_column(
        String(32), nullable=False, default="partial"
    )
    merged_into_badcase_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    recurrence_of_badcase_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    closure_evidence: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )


class BadcaseReviewAction(Base):
    """Append-only review/audit action (migration 0024 + 0060)."""

    __tablename__ = "badcase_review_actions"
    __table_args__ = {"extend_existing": True}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    badcase_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    action_type: Mapped[str] = mapped_column(String(64), nullable=False)
    actor_role: Mapped[str] = mapped_column(String(64), nullable=False, default="BADCASE_REVIEWER")
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    evidence_ref: Mapped[str | None] = mapped_column(Text, nullable=True)
    # REQ-061 US10 extensions
    actor: Mapped[str | None] = mapped_column(String(128), nullable=True)
    from_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    to_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    expected_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    resulting_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    idempotency_key: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    evidence_refs: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow
    )


class BadcaseImpactLink(Base):
    """Versioned affected-scope link (REQ-061 US10 / T131)."""

    __tablename__ = "badcase_impact_links"
    __table_args__ = {"extend_existing": True}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    badcase_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True, index=True)
    impact_kind: Mapped[str] = mapped_column(String(32), nullable=False)
    subject_ref: Mapped[str] = mapped_column(String(256), nullable=False)
    confidence: Mapped[str] = mapped_column(String(32), nullable=False, default="unknown")
    evidence_refs: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    update_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    actor: Mapped[str | None] = mapped_column(String(128), nullable=True)
    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow
    )
    last_updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow
    )


class BadcaseContentAuthorization(Base):
    """Per-owner content consent; merge must not union across users."""

    __tablename__ = "badcase_content_authorizations"
    __table_args__ = {"extend_existing": True}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    badcase_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    owner_user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    permitted_content_classes: Mapped[list[Any]] = mapped_column(
        JSONB, nullable=False, default=list
    )
    permitted_fields: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    purpose: Mapped[str] = mapped_column(Text, nullable=False)
    privacy_class: Mapped[str] = mapped_column(String(32), nullable=False, default="restricted")
    snapshot_ref: Mapped[str | None] = mapped_column(String(256), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow
    )


class BadcaseClosureEvidence(Base):
    """One-to-one closure gate projection for P0/P1 (and recommended for all)."""

    __tablename__ = "badcase_closure_evidence"
    __table_args__ = {"extend_existing": True}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    badcase_id: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    fix_or_policy_version: Mapped[str | None] = mapped_column(String(256), nullable=True)
    regression_case_ref: Mapped[str | None] = mapped_column(String(256), nullable=True)
    passing_evaluation_ref: Mapped[str | None] = mapped_column(String(256), nullable=True)
    point_treatment_ref: Mapped[str | None] = mapped_column(String(256), nullable=True)
    user_notification_ref: Mapped[str | None] = mapped_column(String(256), nullable=True)
    complete: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow
    )


class AIInvocationRecord(Base):
    """AI invocation log row (033 US1)."""

    __tablename__ = "ai_invocation_records"
    __table_args__ = {"extend_existing": True}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    invocation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), unique=True, nullable=False)
    run_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    trace_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True)
    graph: Mapped[str] = mapped_column(String(128), nullable=False)
    node: Mapped[str] = mapped_column(String(128), nullable=False)
    model: Mapped[str] = mapped_column(String(64), nullable=False)
    prompt_fingerprint: Mapped[str] = mapped_column(String(128), nullable=False)
    prompt_tokens: Mapped[int] = mapped_column(Integer, default=0)
    completion_tokens: Mapped[int] = mapped_column(Integer, default=0)
    estimated_cost: Mapped[Decimal | None] = mapped_column(Numeric(12, 6), nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(16), default="SUCCESS")
    error_category: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


class ProductFunnelEvent(Base):
    """Stub: product funnel event row (033 US1)."""

    __tablename__ = "product_events"
    __table_args__ = {"extend_existing": True}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True)
    event_name: Mapped[str] = mapped_column(String(128), index=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)


class LLMOpsEvalRun(Base):
    __tablename__ = "llm_ops_eval_runs"
    __table_args__ = {"extend_existing": True}

    run_id: Mapped[str] = mapped_column(Text, primary_key=True)
    suite: Mapped[str] = mapped_column(Text, nullable=False)
    environment: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    source_revision: Mapped[str] = mapped_column(Text, nullable=False)
    branch: Mapped[str | None] = mapped_column(Text, nullable=True)
    dataset_version: Mapped[str] = mapped_column(Text, nullable=False)
    prompt_fingerprint: Mapped[str] = mapped_column(Text, nullable=False, default="unavailable")
    rubric_version: Mapped[str] = mapped_column(Text, nullable=False, default="unavailable")
    model_version: Mapped[str] = mapped_column(Text, nullable=False, default="unavailable")
    aggregate_pass_rate: Mapped[Decimal | None] = mapped_column(Numeric(5, 4), nullable=True)
    known_regression_recall: Mapped[Decimal | None] = mapped_column(Numeric(5, 4), nullable=True)
    token_usage: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    cost_usd: Mapped[Decimal | None] = mapped_column(Numeric(12, 6), nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    local_artifacts: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    langsmith_export_status: Mapped[str] = mapped_column(String(32), nullable=False, default="DISABLED")
    export_policy_decision_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


class LLMOpsEvalCaseResult(Base):
    __tablename__ = "llm_ops_eval_case_results"
    __table_args__ = {"extend_existing": True}

    case_result_id: Mapped[str] = mapped_column(Text, primary_key=True)
    case_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    run_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    lifecycle: Mapped[str] = mapped_column(String(32), nullable=False)
    graph: Mapped[str] = mapped_column(Text, nullable=False)
    node: Mapped[str] = mapped_column(Text, nullable=False)
    passed: Mapped[bool] = mapped_column(default=False)
    failure_reasons: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    deterministic_metrics: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    artifact_ref: Mapped[str] = mapped_column(Text, nullable=False, default="unavailable")
    trace_run_ref_id: Mapped[str | None] = mapped_column(Text, nullable=True, index=True)
    langsmith_run_url: Mapped[str] = mapped_column(Text, nullable=False, default="unavailable")
    judge_verdict_ids: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


class LLMOpsTraceRunRef(Base):
    __tablename__ = "llm_ops_trace_run_refs"
    __table_args__ = {"extend_existing": True}

    trace_run_ref_id: Mapped[str] = mapped_column(Text, primary_key=True)
    run_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    case_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    trace_id: Mapped[str | None] = mapped_column(Text, nullable=True, index=True)
    span_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    artifact_ref: Mapped[str | None] = mapped_column(Text, nullable=True)
    langsmith_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    entrypoint: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


class LLMOpsLangSmithRef(Base):
    __tablename__ = "llm_ops_langsmith_refs"
    __table_args__ = {"extend_existing": True}

    langsmith_ref_id: Mapped[str] = mapped_column(Text, primary_key=True)
    run_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    project: Mapped[str] = mapped_column(Text, nullable=False)
    dataset_name: Mapped[str] = mapped_column(Text, nullable=False)
    dataset_version: Mapped[str] = mapped_column(Text, nullable=False)
    experiment_name: Mapped[str] = mapped_column(Text, nullable=False)
    experiment_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    sync_status: Mapped[str] = mapped_column(String(32), nullable=False)
    synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_code: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


class LLMOpsJudgeVerdict(Base):
    __tablename__ = "llm_ops_judge_verdicts"
    __table_args__ = {"extend_existing": True}

    verdict_id: Mapped[str] = mapped_column(Text, primary_key=True)
    run_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    case_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    rubric_id: Mapped[str] = mapped_column(Text, nullable=False)
    rubric_version: Mapped[str] = mapped_column(Text, nullable=False)
    judge_model: Mapped[str] = mapped_column(Text, nullable=False)
    score: Mapped[Decimal | None] = mapped_column(Numeric(6, 4), nullable=True)
    confidence: Mapped[Decimal | None] = mapped_column(Numeric(5, 4), nullable=True)
    rationale_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    disagreement_markers: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    is_blocking: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


class LLMOpsExportDecision(Base):
    __tablename__ = "llm_ops_export_decisions"
    __table_args__ = {"extend_existing": True}

    decision_id: Mapped[str] = mapped_column(Text, primary_key=True)
    destination: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    environment: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    representation_level: Mapped[str] = mapped_column(String(32), nullable=False)
    policy_version: Mapped[str] = mapped_column(Text, nullable=False)
    owner: Mapped[str | None] = mapped_column(Text, nullable=True)
    access_scope: Mapped[str | None] = mapped_column(Text, nullable=True)
    retention_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    allowed_content_classes: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    blocked_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    sample_rate: Mapped[Decimal | None] = mapped_column(Numeric(5, 4), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


class LLMOpsBadcaseCandidate(Base):
    __tablename__ = "llm_ops_badcase_candidates"
    __table_args__ = {"extend_existing": True}

    candidate_id: Mapped[str] = mapped_column(Text, primary_key=True)
    source_badcase_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    source_trace_run_ref_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    case_id: Mapped[str | None] = mapped_column(Text, nullable=True, index=True)
    lifecycle: Mapped[str] = mapped_column(String(32), nullable=False)
    owner: Mapped[str] = mapped_column(Text, nullable=False)
    review_status: Mapped[str] = mapped_column(String(32), nullable=False, default="PENDING")
    export_policy_decision_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    approval_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class LLMOpsPromptProposal(Base):
    __tablename__ = "llm_ops_prompt_proposals"
    __table_args__ = {"extend_existing": True}

    proposal_id: Mapped[str] = mapped_column(Text, primary_key=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    source_run_ids: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    source_case_ids: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    target_graph: Mapped[str] = mapped_column(Text, nullable=False)
    target_node: Mapped[str] = mapped_column(Text, nullable=False)
    proposal_type: Mapped[str] = mapped_column(String(32), nullable=False)
    candidate_fingerprint: Mapped[str] = mapped_column(Text, nullable=False)
    expected_impact: Mapped[str] = mapped_column(Text, nullable=False)
    comparison_run_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    approval_owner: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


__all__ = [
    "Badcase",
    "BadcaseReviewAction",
    "AIInvocationRecord",
    "LLMOpsBadcaseCandidate",
    "LLMOpsEvalCaseResult",
    "LLMOpsEvalRun",
    "LLMOpsExportDecision",
    "LLMOpsJudgeVerdict",
    "LLMOpsLangSmithRef",
    "LLMOpsPromptProposal",
    "LLMOpsTraceRunRef",
    "ProductFunnelEvent",
]
