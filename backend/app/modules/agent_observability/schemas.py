from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field


class CoverageFlow(BaseModel):
    feature_area: str
    flow_name: str
    coverage: str = "covered"
    entrypoint: str = "centralized_agent_runner"


class CoverageGap(BaseModel):
    feature_area: str
    flow_name: str
    reason: str
    severity: str
    status: str = "open"


class CoverageReport(BaseModel):
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    environment: str
    covered_flows: list[CoverageFlow]
    gaps: list[CoverageGap]

    @property
    def covered_count(self) -> int:
        return len(self.covered_flows)

    @property
    def gap_count(self) -> int:
        return len(self.gaps)

    @property
    def high_severity_gap_count(self) -> int:
        return sum(
            1
            for gap in self.gaps
            if gap.severity.lower() == "high" and gap.status.lower() not in {"accepted", "closed"}
        )

    def to_contract_dict(self) -> dict[str, Any]:
        payload = self.model_dump(mode="json")
        payload["covered_count"] = self.covered_count
        payload["gap_count"] = self.gap_count
        payload["high_severity_gap_count"] = self.high_severity_gap_count
        return payload


class PayloadRevealBody(BaseModel):
    reason: str
    visibility_mode: str = "masked_raw"


class TraceSearchFilters(BaseModel):
    q: str | None = None
    cursor: str | None = None
    limit: int = Field(default=25, ge=1, le=100)
    feature_area: str | None = None
    status: str | None = None
    eval_status: str | None = None
    badcase_status: str | None = None
    privacy_class: str | None = None


class TraceSearchRow(BaseModel):
    trace_id: str
    started_at: str
    duration_ms: int
    status: str
    feature_area: str
    business_run_id: str
    agent_name: str
    llm_call_count: int
    total_tokens: int
    estimated_cost: float
    eval_status: str
    badcase_status: str
    source_revision: str
    privacy_class: str
    next_node: str = "complete"


class TraceSearchResponse(BaseModel):
    items: list[TraceSearchRow]
    next_cursor: str | None = None
    freshness_at: str


class TraceSummary(BaseModel):
    trace_id: str
    business_run_id: str
    feature_area: str
    status: str
    started_at: str
    duration_ms: int
    total_tokens: int = 0
    estimated_cost: float = 0.0
    eval_status: str = "not_run"


class TraceSpan(BaseModel):
    span_id: str
    parent_span_id: str | None
    span_kind: str
    name: str
    status: str
    duration_ms: int
    node_name: str | None = None
    input_payload_id: str | None = None
    output_payload_id: str | None = None
    state_diff_payload_id: str | None = None


class TraceHierarchySummary(BaseModel):
    root_span_id: str | None
    node_path: list[str]
    span_count: int
    llm_call_count: int
    tool_operation_count: int = 0


class TraceLinks(BaseModel):
    eval_case_ids: list[str]
    badcase_ids: list[str]


class TraceDetailResponse(BaseModel):
    trace: TraceSummary
    spans: list[TraceSpan]
    hierarchy: TraceHierarchySummary
    links: TraceLinks
    visibility_mode: str


__all__ = [
    "CoverageFlow",
    "CoverageGap",
    "CoverageReport",
    "PayloadRevealBody",
    "TraceDetailResponse",
    "TraceHierarchySummary",
    "TraceLinks",
    "TraceSearchFilters",
    "TraceSearchResponse",
    "TraceSearchRow",
    "TraceSpan",
    "TraceSummary",
]
