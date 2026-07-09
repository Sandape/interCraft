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

from sqlalchemy import DateTime, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class Badcase(Base):
    """Stub: full table definition ships in 033 US8 (T058)."""

    __tablename__ = "badcases"
    __table_args__ = {"extend_existing": True}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True)
    source: Mapped[str] = mapped_column(String(64))
    type: Mapped[str] = mapped_column(String(64))
    severity: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(32), default="OPEN")
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    failure_reason: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )


class BadcaseReviewAction(Base):
    """Stub: append-only audit log row."""

    __tablename__ = "badcase_review_actions"
    __table_args__ = {"extend_existing": True}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    badcase_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True)
    actor_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    action: Mapped[str] = mapped_column(String(64))
    notes: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


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
