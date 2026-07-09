from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Index, Integer, Numeric, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.core.ids import new_uuid_v7


class ObservabilityTrace(Base):
    __tablename__ = "observability_traces"
    __table_args__ = (
        Index("idx_observability_traces_user_started", "user_id", "started_at"),
        Index("idx_observability_traces_business_event", "business_event_id"),
        Index("idx_observability_traces_environment", "environment"),
        Index("idx_observability_traces_status", "status"),
    )

    trace_id: Mapped[str] = mapped_column(Text, primary_key=True)
    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    business_event_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    environment: Mapped[str] = mapped_column(Text, nullable=False, default="local")
    feature_area: Mapped[str] = mapped_column(Text, nullable=False)
    agent_name: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="running")
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    retention_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    version_context: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class ObservabilitySpan(Base):
    __tablename__ = "observability_spans"
    __table_args__ = (
        Index("idx_observability_spans_trace_started", "trace_id", "started_at"),
        Index("idx_observability_spans_parent", "parent_span_id"),
        Index("idx_observability_spans_node", "node_name"),
        Index("idx_observability_spans_user_started", "user_id", "started_at"),
    )

    span_id: Mapped[str] = mapped_column(Text, primary_key=True)
    trace_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("observability_traces.trace_id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    parent_span_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    agent_run_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    node_name: Mapped[str] = mapped_column(Text, nullable=False)
    span_kind: Mapped[str] = mapped_column(Text, nullable=False, default="node")
    status: Mapped[str] = mapped_column(Text, nullable=False, default="running")
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    input_payload_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    output_payload_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class ObservabilityPayload(Base):
    __tablename__ = "observability_payloads"
    __table_args__ = (
        Index("idx_observability_payloads_trace", "trace_id"),
        Index("idx_observability_payloads_span", "span_id"),
        Index("idx_observability_payloads_retention", "retention_expires_at"),
        Index("idx_observability_payloads_visibility", "visibility_mode"),
    )

    payload_id: Mapped[str] = mapped_column(Text, primary_key=True)
    trace_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("observability_traces.trace_id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    span_id: Mapped[str | None] = mapped_column(
        Text,
        ForeignKey("observability_spans.span_id", ondelete="SET NULL"),
        nullable=True,
    )
    payload_kind: Mapped[str] = mapped_column(Text, nullable=False)
    visibility_mode: Mapped[str] = mapped_column(Text, nullable=False, default="redacted")
    redacted_summary: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    shape: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    masked_raw: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    secret_scan_status: Mapped[str] = mapped_column(Text, nullable=False, default="passed")
    retention_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class LLMCallRecord(Base):
    __tablename__ = "llm_call_records"
    __table_args__ = (
        Index("idx_llm_call_records_trace", "trace_id"),
        Index("idx_llm_call_records_span", "span_id"),
        Index("idx_llm_call_records_model", "model"),
        Index("idx_llm_call_records_user_started", "user_id", "started_at"),
    )

    llm_call_id: Mapped[str] = mapped_column(Text, primary_key=True)
    trace_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("observability_traces.trace_id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    span_id: Mapped[str | None] = mapped_column(
        Text,
        ForeignKey("observability_spans.span_id", ondelete="SET NULL"),
        nullable=True,
    )
    provider: Mapped[str] = mapped_column(Text, nullable=False)
    model: Mapped[str] = mapped_column(Text, nullable=False)
    endpoint: Mapped[str] = mapped_column(Text, nullable=False)
    provider_request_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    request_payload_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    response_payload_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    prompt_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    completion_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    estimated_cost: Mapped[Decimal | None] = mapped_column(Numeric(12, 6), nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="success")
    safe_curl: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class ToolOperationRecord(Base):
    __tablename__ = "tool_operation_records"
    __table_args__ = (
        Index("idx_tool_operation_records_trace", "trace_id"),
        Index("idx_tool_operation_records_span", "span_id"),
        Index("idx_tool_operation_records_tool", "tool_name"),
        Index("idx_tool_operation_records_user_started", "user_id", "started_at"),
    )

    operation_id: Mapped[str] = mapped_column(Text, primary_key=True)
    trace_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("observability_traces.trace_id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    span_id: Mapped[str | None] = mapped_column(
        Text,
        ForeignKey("observability_spans.span_id", ondelete="SET NULL"),
        nullable=True,
    )
    tool_name: Mapped[str] = mapped_column(Text, nullable=False)
    operation_type: Mapped[str] = mapped_column(Text, nullable=False, default="tool")
    status: Mapped[str] = mapped_column(Text, nullable=False, default="success")
    input_payload_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    output_payload_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class EvalRun(Base):
    __tablename__ = "observability_eval_runs"
    __table_args__ = (
        Index("idx_observability_eval_runs_user_started", "user_id", "started_at"),
        Index("idx_observability_eval_runs_status", "status"),
    )

    eval_run_id: Mapped[str] = mapped_column(Text, primary_key=True)
    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="running")
    pass_rate: Mapped[Decimal | None] = mapped_column(Numeric(5, 4), nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class EvalCaseResult(Base):
    __tablename__ = "observability_eval_case_results"
    __table_args__ = (
        Index("idx_observability_eval_cases_run", "eval_run_id"),
        Index("idx_observability_eval_cases_trace", "trace_id"),
        Index("idx_observability_eval_cases_llm", "llm_call_id"),
        Index("idx_observability_eval_cases_badcase", "badcase_id"),
    )

    case_result_id: Mapped[str] = mapped_column(Text, primary_key=True)
    eval_run_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("observability_eval_runs.eval_run_id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    case_id: Mapped[str] = mapped_column(Text, nullable=False)
    verdict: Mapped[str] = mapped_column(Text, nullable=False, default="pending")
    score: Mapped[Decimal | None] = mapped_column(Numeric(6, 4), nullable=True)
    trace_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    llm_call_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    badcase_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    metrics: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class ObservabilityCoverageGap(Base):
    __tablename__ = "observability_coverage_gaps"
    __table_args__ = (
        Index("idx_observability_coverage_gaps_flow", "feature_area", "flow_name"),
        Index("idx_observability_coverage_gaps_severity", "severity"),
        Index("idx_observability_coverage_gaps_status", "status"),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=new_uuid_v7)
    feature_area: Mapped[str] = mapped_column(Text, nullable=False)
    flow_name: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[str] = mapped_column(Text, nullable=False, default="medium")
    status: Mapped[str] = mapped_column(Text, nullable=False, default="open")
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    accepted_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


__all__ = [
    "EvalCaseResult",
    "EvalRun",
    "LLMCallRecord",
    "ObservabilityCoverageGap",
    "ObservabilityPayload",
    "ObservabilitySpan",
    "ObservabilityTrace",
    "ToolOperationRecord",
]
