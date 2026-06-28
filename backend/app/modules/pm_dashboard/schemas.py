"""REQ-033 US1 + US2 + US3 + US4 — PM Dashboard filter and response envelope schemas (T070, T086, T095, T105).

Pydantic v2 schemas for the PM Dashboard V1 endpoints:

- ``DashboardFilter`` — shared filter envelope (date range + version
  dimensions) per ``contracts/pm-dashboard-api.md`` §Shared Request Filters.
- ``PanelResponse[T]`` — generic panel envelope; carries ``metric_id``,
  ``unit``, ``freshness_at``, ``quality_flags`` so PM can distinguish
  current facts from stale or missing data (FR-009).
- ``OverviewPanelData`` — the 8 FR-002 overview fields (UV,
  registered_users, active_users, completed_ai_tasks, ai_success_rate,
  total_tokens, estimated_cost, open_badcases).
- ``FunnelPanelData`` + ``FunnelStep`` — the core funnel rows with per-step
  conversion rates.
- ``ResumeDiagnosisPanelData`` — US2 5 core resume diagnosis metrics.
- ``MockInterviewPanelData`` — US3 5 core mock interview metrics.
- ``AIOperationsPanelData`` — US4 7 core AI operations metrics.
- ``QualityFlags`` — version-field unknowns, sampled data, delayed
  ingestion, partial data.

The schemas deliberately default missing version fields to
``"unknown"`` (not None) per SC-010 / FR-038 — the dashboard must surface
"unknown" instead of silently omitting fields.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Generic, Optional, TypeVar
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from pydantic.alias_generators import to_camel

from app.modules.telemetry_contracts.schemas import ENVIRONMENTS, RELEASE_STAGES

T = TypeVar("T")


# ---------------------------------------------------------------------------
# DashboardFilter
# ---------------------------------------------------------------------------


class DashboardFilter(BaseModel):
    """Shared filter envelope for all PM dashboard endpoints.

    All endpoints accept these query params unless noted otherwise.
    Required: ``date_range_start`` + ``date_range_end``. Optional: every
    version dimension listed in ``contracts/pm-dashboard-api.md``.
    """

    model_config = ConfigDict(
        extra="forbid",
        populate_by_name=True,
        str_strip_whitespace=True,
        alias_generator=to_camel,
    )

    date_range_start: datetime = Field(
        ...,
        description="Inclusive ISO 8601 lower bound for the period.",
    )
    date_range_end: datetime = Field(
        ...,
        description="Exclusive ISO 8601 upper bound for the period.",
    )
    environment: Optional[str] = Field(default=None)
    release_stage: Optional[str] = Field(default=None)
    app_version: Optional[str] = Field(default=None)
    prompt_fingerprint: Optional[str] = Field(default=None)
    rubric_version: Optional[str] = Field(default=None)
    model: Optional[str] = Field(default=None)
    experiment_id: Optional[str] = Field(default=None)
    graph: Optional[str] = Field(default=None)
    node: Optional[str] = Field(default=None)

    @field_validator("environment")
    @classmethod
    def _valid_environment(cls, v: Optional[str]) -> Optional[str]:
        if v is None or v == "" or v == "unknown":
            return v
        if v not in ENVIRONMENTS and v.lower() not in (
            "local",
            "ci",
            "staging",
            "production",
        ):
            raise ValueError(f"environment must be one of {ENVIRONMENTS}, got {v!r}")
        # Normalize lowercase to uppercase canonical form.
        return v.upper() if v.upper() in ENVIRONMENTS else v

    @field_validator("release_stage")
    @classmethod
    def _valid_release_stage(cls, v: Optional[str]) -> Optional[str]:
        if v is None or v == "":
            return v
        if v not in RELEASE_STAGES and v.lower() not in (
            "development",
            "release_candidate",
            "production",
            "unknown",
        ):
            raise ValueError(
                f"release_stage must be one of {RELEASE_STAGES}, got {v!r}"
            )
        return v

    @model_validator(mode="after")
    def _date_range_consistent(self) -> "DashboardFilter":
        """``date_range_end`` must be strictly after ``date_range_start``.

        Service-layer may relax this for empty queries, but at the schema
        boundary we surface the inconsistency as 422.
        """
        if self.date_range_end <= self.date_range_start:
            raise ValueError(
                "date_range_end must be strictly after date_range_start"
            )
        return self

    def to_dimensions(self) -> dict[str, str]:
        """Project to a ``dimensions`` dict for snapshot storage."""
        out: dict[str, str] = {}
        for field in (
            "environment",
            "release_stage",
            "app_version",
            "prompt_fingerprint",
            "rubric_version",
            "model",
            "experiment_id",
            "graph",
            "node",
        ):
            v = getattr(self, field)
            if v:
                out[field] = v
        return out


# ---------------------------------------------------------------------------
# QualityFlags + PanelResponse
# ---------------------------------------------------------------------------


class QualityFlags(BaseModel):
    """Quality flags surfaced on every panel response (FR-009).

    - ``missing_version_fields`` — list of dimension names whose value is
      "unknown" or absent for the period. SC-010 requires these be
      surfaced, not hidden.
    - ``sampled_data`` — true if the metric was computed from a sampled
      subset, not the full population.
    - ``delayed_ingestion`` — true if the freshness lag exceeds the metric
      definition's target.
    - ``partial_data`` — true if the period has zero rows (empty state)
      OR the data source was incomplete.
    """

    model_config = ConfigDict(
        extra="forbid",
        populate_by_name=True,
        alias_generator=to_camel,
    )

    missing_version_fields: list[str] = Field(default_factory=list)
    sampled_data: bool = Field(default=False)
    delayed_ingestion: bool = Field(default=False)
    partial_data: bool = Field(default=False)

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump(by_alias=True)


class PanelResponse(BaseModel, Generic[T]):
    """Generic panel envelope.

    Every endpoint returns one or more ``PanelResponse`` rows. The
    ``data`` field carries the panel-specific payload (Overview / Funnel
    / Resume Diagnosis / etc.).
    """

    model_config = ConfigDict(
        extra="forbid",
        populate_by_name=True,
        alias_generator=to_camel,
    )

    metric_id: str
    display_name: str
    value: float = Field(default=0.0)
    unit: str = Field(default="count")
    period_start: datetime
    period_end: datetime
    dimensions: dict[str, str] = Field(default_factory=dict)
    numerator: Optional[float] = Field(default=None)
    denominator: Optional[float] = Field(default=None)
    source_of_truth: str = Field(default="unknown")
    freshness_at: str = Field(default="unknown")
    quality_flags: QualityFlags = Field(default_factory=QualityFlags)
    data: T


# ---------------------------------------------------------------------------
# Overview panel payload (FR-002)
# ---------------------------------------------------------------------------


class OverviewPanelData(BaseModel):
    """The 8 FR-002 overview fields.

    Defaults are zero (not None) so an empty dashboard renders cleanly.
    """

    model_config = ConfigDict(
        extra="forbid",
        populate_by_name=True,
        alias_generator=to_camel,
    )

    uv: int = Field(default=0, ge=0)
    registered_users: int = Field(default=0, ge=0)
    active_users: int = Field(default=0, ge=0)
    completed_ai_tasks: int = Field(default=0, ge=0)
    ai_success_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    total_tokens: int = Field(default=0, ge=0)
    estimated_cost: float = Field(default=0.0, ge=0.0)
    open_badcases: int = Field(default=0, ge=0)
    is_estimate: bool = Field(default=True)

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump(by_alias=True)


# ---------------------------------------------------------------------------
# Funnel panel payload (FR-006)
# ---------------------------------------------------------------------------


class FunnelStep(BaseModel):
    """One step in the core funnel.

    ``conversion_from_previous`` is the conversion from the previous
    step (0..1). ``conversion_from_entry`` is the conversion from the
    funnel entry. ``largest_drop_off`` flags the step with the biggest
    drop-off vs. previous.
    """

    model_config = ConfigDict(
        extra="forbid",
        populate_by_name=True,
        alias_generator=to_camel,
    )

    step_name: str
    step_order: int = Field(ge=0)
    count: int = Field(default=0, ge=0)
    conversion_from_previous: float = Field(default=0.0, ge=0.0, le=1.0)
    conversion_from_entry: float = Field(default=0.0, ge=0.0, le=1.0)
    largest_drop_off: bool = Field(default=False)

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump(by_alias=True)


class FunnelPanelData(BaseModel):
    """The funnel panel payload: ordered steps + totals.

    Total entry = first step's count. Total completion = last step's
    count. Empty funnel renders with ``steps=[]`` and totals=0.
    """

    model_config = ConfigDict(
        extra="forbid",
        populate_by_name=True,
        alias_generator=to_camel,
    )

    steps: list[FunnelStep] = Field(default_factory=list)
    total_entry: int = Field(default=0, ge=0)
    total_completion: int = Field(default=0, ge=0)

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump(by_alias=True)


# ---------------------------------------------------------------------------
# Resume Diagnosis panel payload (US2 T086)
# ---------------------------------------------------------------------------


class ResumeDiagnosisPanelData(BaseModel):
    """The 5 core resume diagnosis metrics per US2 (FR for US2).

    Privacy: only counts + rates + aggregate scores are surfaced. No raw
    resume content (``resume_text``, ``resume_url``, ``diagnosis_markdown``,
    etc.) appears in this payload.

    Fields:

    - ``success_count`` — number of diagnoses that completed with SUCCESS.
    - ``total_count`` — number of diagnoses started (denominator for
      ``success_rate``).
    - ``success_rate`` — ``success_count / total_count`` in [0.0, 1.0].
      0.0 when ``total_count == 0``.
    - ``report_views`` — number of report-view events.
    - ``suggestions_shown`` — number of suggestion-shown events.
    - ``suggestions_accepted`` — number of suggestion-accepted events.
    - ``acceptance_rate`` — ``suggestions_accepted / suggestions_shown``
      in [0.0, 1.0]. 0.0 when ``suggestions_shown == 0``.
    - ``score_delta_before`` — average score before diagnosis in [0, 100].
    - ``score_delta_after`` — average score after diagnosis in [0, 100].
    - ``score_delta`` — ``score_delta_after - score_delta_before`` in
      [-100, 100]. 0.0 when no rows.
    """

    model_config = ConfigDict(
        extra="forbid",
        populate_by_name=True,
        alias_generator=to_camel,
    )

    success_count: int = Field(default=0, ge=0)
    total_count: int = Field(default=0, ge=0)
    success_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    report_views: int = Field(default=0, ge=0)
    suggestions_shown: int = Field(default=0, ge=0)
    suggestions_accepted: int = Field(default=0, ge=0)
    acceptance_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    score_delta_before: float = Field(default=0.0, ge=0.0, le=100.0)
    score_delta_after: float = Field(default=0.0, ge=0.0, le=100.0)
    score_delta: float = Field(default=0.0, ge=-100.0, le=100.0)

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump(by_alias=True)


# ---------------------------------------------------------------------------
# Mock Interview panel payload (US3 T095)
# ---------------------------------------------------------------------------


class MockInterviewPanelData(BaseModel):
    """The 5 core mock interview metrics per US3 (FR for US3).

    Privacy: only counts + rates + average question count are surfaced.
    No raw interview content (``interview_questions``, ``interview_answers``,
    ``interview_transcript``, ``interview_audio``, ``raw_interview``,
    ``feedback_text``, ``report_text``, ``report_markdown``) appears in
    this payload.

    Fields:

    - ``starts`` — number of ``interview.started`` events in window.
    - ``completions`` — number of ``interview.completed`` events in window.
    - ``completion_rate`` — ``completions / starts`` in [0.0, 1.0]. 0.0
      when ``starts == 0``.
    - ``avg_question_count`` — average ``metadata.question_count`` over
      completed sessions. 0.0 when no completed sessions.
    - ``report_views`` — number of ``interview.report_viewed`` events in
      window.
    - ``retries`` — number of ``interview.retry`` events in window.
    - ``failure_rate`` — ``failures / starts`` in [0.0, 1.0]. 0.0 when
      ``starts == 0``.
    - ``failure_categories`` — count of failures bucketed by
      ``metadata.failure_category`` (e.g. ``{"timeout": 6,
      "llm_error": 6}``). Empty dict when no failures.
    """

    model_config = ConfigDict(
        extra="forbid",
        populate_by_name=True,
        alias_generator=to_camel,
    )

    starts: int = Field(default=0, ge=0)
    completions: int = Field(default=0, ge=0)
    completion_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    avg_question_count: float = Field(default=0.0, ge=0.0)
    report_views: int = Field(default=0, ge=0)
    retries: int = Field(default=0, ge=0)
    failure_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    failure_categories: dict[str, int] = Field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump(by_alias=True)


# ---------------------------------------------------------------------------
# AI Operations panel payload (US4 T105)
# ---------------------------------------------------------------------------


class AIOperationsPanelData(BaseModel):
    """The 7 core AI operations metrics per US4 (FR for US4).

    Privacy: only counts + rates + aggregates are surfaced. No raw AI
    content (no ``prompt_text``, ``completion_text``, ``system_prompt``,
    ``messages``, ``tool_calls``, ``request_body``, ``response_body``,
    or ``raw_response``). Per-call prompts/responses live in the
    ``ai_invocation_records`` table for ops triage; the panel reports
    the count + aggregate cost + latency, never the content.

    Fields:

    - ``call_count`` — total AI invocations in window (any status).
    - ``success_count`` — invocations with ``status='SUCCESS'`` in window.
    - ``failure_count`` — invocations with status != 'SUCCESS' in window.
    - ``success_rate`` — ``success_count / call_count`` clamped to [0, 1].
    - ``failure_rate`` — ``failure_count / call_count`` clamped to [0, 1].
    - ``retry_count`` — invocations where ``retry_count > 0`` in window.
    - ``p50_latency_ms`` — 50th-percentile ``latency_ms`` in window.
    - ``p95_latency_ms`` — 95th-percentile ``latency_ms`` in window.
    - ``p99_latency_ms`` — 99th-percentile ``latency_ms`` in window.
    - ``estimated_cost`` — sum of ``estimated_cost`` in window, labeled
      as estimate per FR-008 (see ``is_estimate`` below).
    - ``total_tokens`` — sum of ``prompt_tokens + completion_tokens`` in
      window.
    - ``prompt_tokens`` — sum of ``prompt_tokens`` in window.
    - ``completion_tokens`` — sum of ``completion_tokens`` in window.
    - ``is_estimate`` — always True (FR-008: cost is not billing).
    - ``model_breakdown`` — top-5 models by call count, ``{model: count}``.
    - ``graph_breakdown`` — top-5 graphs by call count, ``{graph: count}``.
    - ``node_breakdown`` — top-5 nodes by call count, ``{node: count}``.
    - ``prompt_fingerprint_breakdown`` — top-5 prompt fingerprints by
      call count, ``{fingerprint: count}``.
    """

    model_config = ConfigDict(
        extra="forbid",
        populate_by_name=True,
        alias_generator=to_camel,
    )

    call_count: int = Field(default=0, ge=0)
    success_count: int = Field(default=0, ge=0)
    failure_count: int = Field(default=0, ge=0)
    success_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    failure_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    retry_count: int = Field(default=0, ge=0)
    p50_latency_ms: float = Field(default=0.0, ge=0.0)
    p95_latency_ms: float = Field(default=0.0, ge=0.0)
    p99_latency_ms: float = Field(default=0.0, ge=0.0)
    estimated_cost: float = Field(default=0.0, ge=0.0)
    total_tokens: int = Field(default=0, ge=0)
    prompt_tokens: int = Field(default=0, ge=0)
    completion_tokens: int = Field(default=0, ge=0)
    is_estimate: bool = Field(default=True)
    model_breakdown: dict[str, int] = Field(default_factory=dict)
    graph_breakdown: dict[str, int] = Field(default_factory=dict)
    node_breakdown: dict[str, int] = Field(default_factory=dict)
    prompt_fingerprint_breakdown: dict[str, int] = Field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump(by_alias=True)


# ---------------------------------------------------------------------------
# Convenience typed aliases (Pydantic generics)
# ---------------------------------------------------------------------------


OverviewPanel = PanelResponse[OverviewPanelData]
FunnelPanel = PanelResponse[FunnelPanelData]
ResumeDiagnosisPanel = PanelResponse[ResumeDiagnosisPanelData]  # US2 T086
MockInterviewPanel = PanelResponse[MockInterviewPanelData]  # US3 T095
AIOperationsPanel = PanelResponse[AIOperationsPanelData]  # US4 T105


# ---------------------------------------------------------------------------
# Outgoing API envelope (top-level wrapper)
# ---------------------------------------------------------------------------


class PanelsEnvelope(BaseModel):
    """Top-level response wrapper for overview endpoint.

    Multiple PanelResponse rows are returned under ``panels``. The
    ``freshness_at`` + ``request_id`` are surfaced at the envelope level
    so callers don't need to walk every panel.
    """

    model_config = ConfigDict(
        extra="forbid",
        populate_by_name=True,
        alias_generator=to_camel,
    )

    panels: list[PanelResponse[Any]]
    freshness_at: str
    request_id: str = Field(default_factory=lambda: str(uuid4()))


class PanelEnvelope(BaseModel):
    """Top-level response wrapper for funnel endpoint (single panel)."""

    model_config = ConfigDict(
        extra="forbid",
        populate_by_name=True,
        alias_generator=to_camel,
    )

    panel: PanelResponse[Any]
    freshness_at: str
    request_id: str = Field(default_factory=lambda: str(uuid4()))


# ---------------------------------------------------------------------------
# Error shape (mirrors contracts/pm-dashboard-api.md §Error Shape)
# ---------------------------------------------------------------------------


class DashboardError(BaseModel):
    """Structured error payload returned on validation / 4xx errors."""

    model_config = ConfigDict(
        extra="forbid",
        populate_by_name=True,
        alias_generator=to_camel,
    )

    code: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


class DashboardErrorEnvelope(BaseModel):
    """Wrapper for the structured error response."""

    model_config = ConfigDict(
        extra="forbid",
        populate_by_name=True,
        alias_generator=to_camel,
    )

    error: DashboardError


__all__ = [
    "AIOperationsPanel",  # US4 T105
    "AIOperationsPanelData",  # US4 T105
    "DashboardError",
    "DashboardErrorEnvelope",
    "DashboardFilter",
    "FunnelPanel",
    "FunnelPanelData",
    "FunnelStep",
    "MockInterviewPanel",
    "MockInterviewPanelData",
    "OverviewPanel",
    "OverviewPanelData",
    "PanelEnvelope",
    "PanelResponse",
    "PanelsEnvelope",
    "QualityFlags",
    "ResumeDiagnosisPanel",
    "ResumeDiagnosisPanelData",
]  # US2 T086 + US3 T095 + US4 T105