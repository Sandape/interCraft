"""REQ-044 US3 — AI Operations Pydantic v2 schemas (FR-016~FR-020).

Schema surface:

- :class:`FeatureArea` — Literal of the 4 PM-monitored AI feature
  areas (FR-016).
- :class:`VersionDimension` — Literal of the 4 version selector
  dimensions (FR-017).
- :class:`KPIBundle` — workspace header 4 KPI tiles (FR-016).
- :class:`VolumeByFeatureRow` + :class:`VolumeByFeatureResponse` —
  AI task volume per feature_area (FR-016).
- :class:`FailureCategory` — Literal of the 5 FR-016 categories.
- :class:`FailureCategoryBreakdown` + :class:`FailureCategoryResponse`
  — per-category counts (FR-016).
- :class:`LatencyBandEntry` + :class:`LatencyBands` — p50/p95/p99 per
  feature_area (FR-016).
- :class:`TokenUsageRow` + :class:`TokenUsageResponse` — input vs
  output tokens per feature_area (FR-016).
- :class:`CostFeatureBreakdown` + :class:`CostSummaryResponse` — total
  + per-area USD cost (FR-016).
- :class:`VersionSelectorChoice` — single dimension selection (FR-017).
- :class:`AIQualityIssue` — single link entity (FR-018).
- :class:`AIQualityIssueListResponse` — list envelope.
- :class:`CostQualityFlag` — cost-quality tradeoff flag (FR-019).
- :class:`EvalRunSummary` + :class:`BadcaseRow` +
  :class:`EvalBadcaseSummary` — eval + badcase surface (FR-020).

Validation invariants locked by AC matrix:

- ``feature_area`` MUST be one of the 4 FR-016 areas.
- ``version_dimension`` MUST be one of the 4 FR-017 dimensions.
- ``failure_category`` MUST be one of the 5 FR-016 categories.
- Quality issue MUST carry all 8 FR-018 link fields
  (eval_verdict + badcase_id + affected_feature_area +
  affected_journey_step + owner + status + recommended_action +
  feature_area_dimension).
- CostQualityFlag MUST carry cost_delta_pct + quality_delta_pct +
  severity + linked model/prompt/feature_area/cohort.
- EvalBadcaseSummary MUST carry total_eval_runs + pass_rate +
  open_badcases + recent_badcases[≥5].
"""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

# ---------------------------------------------------------------------------
# Feature area + version dimension enums
# ---------------------------------------------------------------------------

#: The 4 PM-monitored AI feature areas (FR-016).
#: ``resume_render`` mirrors RESUME v2 RENDER section blocks
#: (post REQ-032 v2); the other 3 are seeded by REQ-033.
FeatureArea = Literal[
    "resume_optimize",  # 简历优化
    "mock_interview",   # 模拟面试
    "error_coach",      # 错误本反馈
    "resume_render",    # 简历 v2 渲染
]

#: 4 version selector dimensions (FR-017).
VersionDimension = Literal[
    "prompt_fingerprint",  # AI prompt 指纹
    "rubric_version",      # 评分 rubric 版本
    "model",               # LLM 模型
    "app_version",         # 应用版本
]

#: 5 failure categories (FR-016).
FailureCategory = Literal[
    "timeout",
    "token_limit",
    "parse_error",
    "eval_failed",
    "api_5xx",
]


# ---------------------------------------------------------------------------
# FR-016: KPI tiles (workspace header)
# ---------------------------------------------------------------------------


class KPIBundle(BaseModel):
    """4 workspace-header KPI tiles (FR-016 + AC-16.1).

    All values are positive; ``success_rate`` and ``quality_score`` are
    clamped to [0, 1]. ``freshness_at`` is ISO 8601 or the literal
    ``"unknown"`` sentinel per FR-028 (Edge Case line 317).
    """

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    total_volume: int = Field(default=0, ge=0)
    success_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    p95_latency_ms: float = Field(default=0.0, ge=0.0)
    total_cost_usd: float = Field(default=0.0, ge=0.0)
    freshness_at: str = Field(default="unknown", max_length=64)
    is_estimate: bool = Field(default=True)


class KPIBundleResponse(BaseModel):
    """Envelope for GET /ai-operations/kpis."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    kpis: KPIBundle
    freshness_at: str = Field(default="unknown", max_length=64)


# ---------------------------------------------------------------------------
# FR-016: AI task volume by feature_area (bar chart)
# ---------------------------------------------------------------------------


class VolumeByFeatureRow(BaseModel):
    """One row in the volume-by-feature chart (FR-016)."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    feature_area: FeatureArea
    call_count: int = Field(default=0, ge=0)
    success_count: int = Field(default=0, ge=0)
    failure_count: int = Field(default=0, ge=0)


class VolumeByFeatureResponse(BaseModel):
    """Envelope for GET /ai-operations/volume-by-feature."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    rows: list[VolumeByFeatureRow] = Field(default_factory=list)
    total: int = Field(default=0, ge=0)
    freshness_at: str = Field(default="unknown", max_length=64)


# ---------------------------------------------------------------------------
# FR-016: Failure categories (pie / breakdown)
# ---------------------------------------------------------------------------


class FailureCategoryBreakdown(BaseModel):
    """One row in the failure-category breakdown (FR-016)."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    category: FailureCategory
    count: int = Field(default=0, ge=0)
    share: float = Field(default=0.0, ge=0.0, le=1.0)


class FailureCategoryResponse(BaseModel):
    """Envelope for GET /ai-operations/failure-categories."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    breakdown: list[FailureCategoryBreakdown] = Field(default_factory=list)
    total: int = Field(default=0, ge=0)
    freshness_at: str = Field(default="unknown", max_length=64)


# ---------------------------------------------------------------------------
# FR-016: Latency bands (p50/p95/p99 per feature_area)
# ---------------------------------------------------------------------------


class LatencyBandEntry(BaseModel):
    """One percentile row per feature_area (FR-016)."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    feature_area: FeatureArea
    p50_latency_ms: float = Field(default=0.0, ge=0.0)
    p95_latency_ms: float = Field(default=0.0, ge=0.0)
    p99_latency_ms: float = Field(default=0.0, ge=0.0)


class LatencyBands(BaseModel):
    """Envelope for GET /ai-operations/latency-bands."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    entries: list[LatencyBandEntry] = Field(default_factory=list)
    freshness_at: str = Field(default="unknown", max_length=64)


# ---------------------------------------------------------------------------
# FR-016: Token usage (input vs output per feature_area)
# ---------------------------------------------------------------------------


class TokenUsageRow(BaseModel):
    """One row in the token-usage stacked bar (FR-016)."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    feature_area: FeatureArea
    prompt_tokens: int = Field(default=0, ge=0)
    completion_tokens: int = Field(default=0, ge=0)
    total_tokens: int = Field(default=0, ge=0)


class TokenUsageResponse(BaseModel):
    """Envelope for GET /ai-operations/token-usage."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    rows: list[TokenUsageRow] = Field(default_factory=list)
    total_tokens: int = Field(default=0, ge=0)
    freshness_at: str = Field(default="unknown", max_length=64)


# ---------------------------------------------------------------------------
# FR-016: Cost summary (total + per-area breakdown)
# ---------------------------------------------------------------------------


class CostFeatureBreakdown(BaseModel):
    """One row in the per-area cost breakdown (FR-016)."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    feature_area: FeatureArea
    cost_usd: float = Field(default=0.0, ge=0.0)
    share: float = Field(default=0.0, ge=0.0, le=1.0)


class CostSummaryResponse(BaseModel):
    """Envelope for GET /ai-operations/cost-summary.

    ``last_reconciled_at`` is the ISO 8601 timestamp of the last
    cost-rate table reconciliation; the seed uses ``_earlier_iso(7)``
    so EC-3 can be observed. When the seed date is older than the
    ``COST_RECONCILIATION_STALE_DAYS`` threshold, the frontend renders
    the "cost estimate outdated" flag.
    """

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    total_cost_usd: float = Field(default=0.0, ge=0.0)
    by_feature: list[CostFeatureBreakdown] = Field(default_factory=list)
    last_reconciled_at: str = Field(default="unknown", max_length=64)
    is_estimate: bool = Field(default=True)
    stale: bool = Field(
        default=False,
        description="True if last_reconciled_at is older than the 14d stale threshold (EC-3).",
    )
    freshness_at: str = Field(default="unknown", max_length=64)


# ---------------------------------------------------------------------------
# FR-017: Version selector (4 dimensions)
# ---------------------------------------------------------------------------


class VersionSelectorChoice(BaseModel):
    """One dimension selection (FR-017 + AC-17.1).

    Frontend sends a single dimension + value back to the backend when
    the PM toggles the version selector. The value is a free-form
    fingerprint / version label (NOT a Literal) since legacy rows may
    carry arbitrary fingerprint strings (EC-2). The seed surfaces
    known + unknown values.
    """

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    dimension: VersionDimension
    value: str = Field(..., min_length=1, max_length=128)


class VersionDimensionAvailability(BaseModel):
    """Per-dimension availability (FR-017 + EC-2).

    Each dimension carries a list of known values + an ``unknown_count``
    so the UI can render "version unknown" explicitly for legacy rows
    (Edge Case line 322). NOT silent-fallback to the baseline.
    """

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    dimension: VersionDimension
    known_values: list[str] = Field(default_factory=list)
    unknown_count: int = Field(default=0, ge=0)


class VersionSelectorResponse(BaseModel):
    """Envelope for GET /ai-operations/version-selector (FR-017)."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    dimensions: list[VersionDimensionAvailability] = Field(default_factory=list)
    baseline_label: str = Field(default="last 7 days", max_length=64)
    freshness_at: str = Field(default="unknown", max_length=64)


# ---------------------------------------------------------------------------
# FR-018: AI quality issue with 8 link fields
# ---------------------------------------------------------------------------


AIQualityIssueStatus = Literal[
    "open",        # newly detected, no owner assigned
    "reviewing",   # owner assigned, awaiting decision
    "regressing",  # quality is going down vs previous period
    "resolved",    # closed after evaluation + fix
    "wont_fix",    # owner decided not to act
]


class AIQualityIssue(BaseModel):
    """A single AI quality issue with 8 link fields (FR-018 + AC-18.1/18.2).

    Each link is intentionally narrowed so the PM drawer can show all
    8 fields in a single read. The schema deliberately avoids raw
    prompt / completion payloads (FR-032 privacy) — only identifiers +
    verdicts + recommended actions.
    """

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    issue_id: str = Field(..., min_length=1, max_length=64)
    title: str = Field(..., min_length=1, max_length=256)
    # FR-018 8 link fields
    eval_verdict: str = Field(..., min_length=1, max_length=128)
    badcase_id: str = Field(..., min_length=1, max_length=64)
    affected_feature_area: FeatureArea
    affected_journey_step: str = Field(..., min_length=1, max_length=128)
    owner: str = Field(..., min_length=1, max_length=128)
    status: AIQualityIssueStatus
    recommended_action: str = Field(..., min_length=1, max_length=512)
    # Extra context (NOT part of the 8 link set)
    feature_area_dimension: FeatureArea
    detected_at: str = Field(..., min_length=1, max_length=64)
    severity: Literal["critical", "high", "medium", "low"] = "medium"
    freshness_at: str = Field(default="unknown", max_length=64)
    # Deep-link hrefs for drilldown
    badcase_detail_href: str = Field(default="", max_length=512)
    eval_detail_href: str = Field(default="", max_length=512)


class AIQualityIssueListResponse(BaseModel):
    """Envelope for GET /ai-operations/quality-issues."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    issues: list[AIQualityIssue] = Field(default_factory=list)
    total: int = Field(default=0, ge=0)
    freshness_at: str = Field(default="unknown", max_length=64)


# ---------------------------------------------------------------------------
# FR-019: Cost-quality tradeoff flag
# ---------------------------------------------------------------------------


class CostQualityFlag(BaseModel):
    """Cost-vs-quality tradeoff signal (FR-019 + AC-19.1/19.2/19.3).

    ``cost_delta_pct`` is the percentage change vs the previous period.
    ``quality_delta_pct`` is the percentage change in the weighted
    success-rate vs the previous period. When
    ``cost_delta_pct > threshold`` AND ``quality_delta_pct < 0`` (cost
    up + quality down), the seed surfaces
    ``severity == "critical"`` so the UI renders the red banner.
    """

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    flagged: bool
    severity: Literal["critical", "high", "medium", "low", "info"] = "info"
    cost_delta_pct: float = Field(ge=-1.0, le=10.0)
    quality_delta_pct: float = Field(ge=-1.0, le=1.0)
    cost_per_quality_delta_usd: float = Field(default=0.0, ge=0.0)
    message: str = Field(default="", max_length=512)
    # Linked dimensions for AC-19.2
    linked_model: str = Field(..., min_length=1, max_length=128)
    linked_prompt: str = Field(..., min_length=1, max_length=128)
    linked_feature_area: FeatureArea
    linked_cohort: str = Field(..., min_length=1, max_length=64)
    window_start: str = Field(..., min_length=1, max_length=64)
    window_end: str = Field(..., min_length=1, max_length=64)


# ---------------------------------------------------------------------------
# FR-020: Eval + badcase summary (read-only mirror)
# ---------------------------------------------------------------------------


class EvalRunSummary(BaseModel):
    """Recent eval run + pass_rate summary (FR-020 + AC-20.1).

    Per US3 the eval layer is READ-ONLY: this surfaces high-level
    counts (total_eval_runs + pass_rate) so PM does not have to open
    developer-only logs.
    """

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    total_runs: int = Field(default=0, ge=0)
    pass_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    open_runs: int = Field(default=0, ge=0)


class BadcaseRow(BaseModel):
    """One recent badcase row (FR-020 + AC-20.2)."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    badcase_id: str = Field(..., min_length=1, max_length=64)
    feature_area: FeatureArea
    eval_verdict: str = Field(..., min_length=1, max_length=128)
    status: str = Field(..., min_length=1, max_length=64)
    opened_at: str = Field(..., min_length=1, max_length=64)
    owner: str = Field(default="@pm-oncall", max_length=128)


class EvalBadcaseSummary(BaseModel):
    """Workspace eval + badcase summary card (FR-020 + AC-20.1/20.2).

    ``recent_badcases`` MUST have ≥5 entries (AC-20.2). The seed
    surfaces 6 so the UI doesn't have to special-case empty.
    """

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    eval_run_summary: EvalRunSummary
    open_badcases_count: int = Field(default=0, ge=0)
    recent_badcases: list[BadcaseRow] = Field(default_factory=list, min_length=5)
    freshness_at: str = Field(default="unknown", max_length=64)


__all__ = [
    "AIQualityIssue",
    "AIQualityIssueListResponse",
    "AIQualityIssueStatus",
    "BadcaseRow",
    "CostFeatureBreakdown",
    "CostQualityFlag",
    "CostSummaryResponse",
    "EvalBadcaseSummary",
    "EvalRunSummary",
    "FailureCategory",
    "FailureCategoryBreakdown",
    "FailureCategoryResponse",
    "FeatureArea",
    "KPIBundle",
    "KPIBundleResponse",
    "LatencyBandEntry",
    "LatencyBands",
    "TokenUsageResponse",
    "TokenUsageRow",
    "VersionDimension",
    "VersionDimensionAvailability",
    "VersionSelectorChoice",
    "VersionSelectorResponse",
    "VolumeByFeatureResponse",
    "VolumeByFeatureRow",
]
