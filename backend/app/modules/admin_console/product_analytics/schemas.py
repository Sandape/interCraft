"""REQ-044 US2 — Product Analytics Pydantic v2 schemas (FR-011~FR-015).

Schema surface:

- :class:`QuestionTab` — Literal of the 7 FR-011 question tabs.
- :class:`QuestionTemplate` — single template card (id + tab + title +
  description + required cohort + required period).
- :class:`QuestionTemplateListResponse` — list envelope.
- :class:`FunnelStep` — one funnel step (FR-012).
- :class:`FunnelResponse` — funnel rows + entry conversion +
  comparison_period delta + time-to-convert P50/CI (FR-012).
- :class:`CohortSegment` — reusable cohort definition (FR-013).
- :class:`CohortListResponse` — cohort list envelope.
- :class:`FeatureAdoptionMetric` — 5-metric grid row (FR-014).
- :class:`FeatureAdoptionRow` — feature-level aggregation of 5 metrics.
- :class:`FeatureAdoptionResponse` — feature-adoption list envelope.
- :class:`UserVisibilityLevel` — Literal of full/masked/hidden
  (FR-015 + FR-031).
- :class:`UserPrivacySafeField` — typed field row with visibility level.
- :class:`UserPrivacySafe` — privacy-safe user profile (FR-015).

Validation invariants locked by AC matrix:

- 7 question tabs MUST cover FR-011 enumeration.
- Funnel step MUST carry count + step_conversion + drop_off.
- Funnel MUST carry entry_conversion + comparison_period_delta.
- Cohort MUST carry id/name/definition/population/owner/last_computed_at.
- FeatureAdoption MUST carry 5 metrics (discovery/first_use/repeat/
  frequency_avg/downstream_success_rate).
- UserPrivacySafe MUST NOT include any field named ``raw_resume``,
  ``raw_interview_answer``, ``raw_prompt``, ``raw_model_output``,
  ``resume_content``, ``interview_answers``, ``prompts``,
  ``model_outputs``, ``secrets``, ``tokens``, ``passwords``,
  ``credentials`` (FR-032 + AC-15.4).
"""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

# ---------------------------------------------------------------------------
# Question tabs (FR-011)
# ---------------------------------------------------------------------------


QuestionTab = Literal[
    "activation",  # 激活: 用户首次进入关键路径的转化
    "funnel",  # 漏斗: 步骤间转化 + drop-off
    "retention",  # 留存: cohort 在 T+N 时间窗口的回访率
    "adoption",  # 功能采用: discovery + first use + repeat + frequency + outcome
    "journey",  # 用户路径: 关键节点序列
    "release",  # 版本对比: release 间的指标 delta
    "experiment",  # 实验对比: experiment_id 间的指标 delta
]


# ---------------------------------------------------------------------------
# Question templates (FR-011)
# ---------------------------------------------------------------------------


class QuestionTemplate(BaseModel):
    """A single question-first template card (FR-011).

    A template is a curated question PM can ask with one click. The
    actual aggregation logic is owned by ``service.list_question_templates``
    which returns ≥3 templates per tab (AC-11.2).
    """

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    template_id: str = Field(..., min_length=1, max_length=64)
    tab: QuestionTab
    title: str = Field(..., min_length=1, max_length=160)
    description: str = Field(..., min_length=1, max_length=512)
    required_cohort_id: Optional[str] = Field(default=None, max_length=64)
    required_period_days: int = Field(default=7, ge=1, le=180)
    metric_id: str = Field(..., min_length=1, max_length=128)
    owner: str = Field(..., min_length=1, max_length=128)
    freshness_at: str = Field(default="unknown", max_length=64)


class QuestionTemplateListResponse(BaseModel):
    """Envelope for GET /product-analytics/question-templates."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    templates: list[QuestionTemplate] = Field(default_factory=list)
    total: int = Field(ge=0)
    freshness_at: str = Field(default="unknown")


# ---------------------------------------------------------------------------
# Funnel (FR-012)
# ---------------------------------------------------------------------------


class FunnelStep(BaseModel):
    """One funnel step row (FR-012).

    ``count`` is the number of users who reached this step.
    ``step_conversion`` is the conversion from the previous step
    (0..1, optional if first step).
    ``drop_off`` is the drop-off from the previous step (0..1,
    optional if first step).
    """

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    step_name: str = Field(..., min_length=1, max_length=64)
    count: int = Field(ge=0)
    step_conversion: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    drop_off: Optional[float] = Field(default=None, ge=0.0, le=1.0)


class TimeToConvertBand(BaseModel):
    """Time-to-convert summary band (FR-012).

    ``p50_seconds`` is the median time-to-convert (seconds).
    ``ci95_lower_seconds`` + ``ci95_upper_seconds`` define the 95%
    confidence interval.
    ``sample_size`` is the number of converted users in the cohort;
    a sample_size below the FR-028 / EC-3 threshold should be
    rendered with an "Insufficient data" badge.
    """

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    p50_seconds: float = Field(ge=0.0)
    ci95_lower_seconds: float = Field(ge=0.0)
    ci95_upper_seconds: float = Field(ge=0.0)
    sample_size: int = Field(ge=0)


class FunnelComparisonDelta(BaseModel):
    """Comparison-period delta (FR-012).

    ``comparison_period_label`` is the human label (e.g. "前 7 天").
    ``step_conversion_delta`` is the per-step conversion delta vs the
    comparison period (0..1, signed). Aggregated at the response
    envelope level for the headline metric.
    """

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    comparison_period_label: str = Field(..., min_length=1, max_length=64)
    step_conversion_delta: float = Field(ge=-1.0, le=1.0)


class FunnelResponse(BaseModel):
    """Funnel payload (FR-012).

    ``entry_conversion`` is the share of total users who entered the
    first step (0..1).
    ``steps`` is the ordered list of 5 funnel rows (AC-12.1).
    ``time_to_convert`` is the optional P50 + CI band (AC-12.3).
    ``comparison_delta`` is the optional comparison-period delta
    (AC-12.2).
    ``cohort_id`` + ``cohort_population`` + ``last_computed_at`` are
    surfaced per AC-13.3.
    """

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    funnel_id: str = Field(..., min_length=1, max_length=64)
    steps: list[FunnelStep] = Field(..., min_length=1)
    entry_conversion: float = Field(ge=0.0, le=1.0)
    comparison_delta: Optional[FunnelComparisonDelta] = None
    time_to_convert: Optional[TimeToConvertBand] = None
    cohort_id: Optional[str] = Field(default=None, max_length=64)
    cohort_population: int = Field(default=0, ge=0)
    last_computed_at: str = Field(default="unknown", max_length=64)
    freshness_at: str = Field(default="unknown", max_length=64)


# ---------------------------------------------------------------------------
# Cohort (FR-013)
# ---------------------------------------------------------------------------


class CohortSegment(BaseModel):
    """Reusable cohort / segment definition (FR-013).

    ``definition`` is a structured (or human-readable) definition; for
    Phase 1 we ship the curated string, for Phase 2 batch 2 we will
    ship the SQL/JSON definition.
    ``population`` is the last-computed population size.
    ``last_computed_at`` is the ISO 8601 timestamp OR ``"unknown"``
    per FR-028.
    """

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    id: str = Field(..., min_length=1, max_length=64)
    name: str = Field(..., min_length=1, max_length=160)
    definition: str = Field(..., min_length=1, max_length=1024)
    population: int = Field(ge=0)
    owner: str = Field(..., min_length=1, max_length=128)
    last_computed_at: str = Field(default="unknown", max_length=64)
    stale: bool = Field(
        default=False,
        description="True if the cohort definition has changed since last computation (EC-2).",
    )


class CohortListResponse(BaseModel):
    """Envelope for GET /product-analytics/cohorts."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    cohorts: list[CohortSegment] = Field(default_factory=list)
    total: int = Field(ge=0)
    freshness_at: str = Field(default="unknown", max_length=64)


# ---------------------------------------------------------------------------
# Feature adoption (FR-014)
# ---------------------------------------------------------------------------


class FeatureAdoptionMetric(BaseModel):
    """One metric within the 5-metric grid (FR-014).

    Discovery / first use / repeat / frequency / downstream outcome.
    Each carries current value + comparison_period delta + sample_size.
    ``insufficient_data`` is True when sample_size < threshold (EC-3).
    """

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    metric_name: Literal[
        "discovery_users",
        "first_use_users",
        "repeat_users",
        "frequency_avg",
        "downstream_success_rate",
    ]
    current_value: float = Field(ge=0.0)
    unit: str = Field(default="count", min_length=1, max_length=32)
    comparison_delta: float = Field(default=0.0, ge=-1.0, le=1.0)
    sample_size: int = Field(ge=0)
    insufficient_data: bool = Field(default=False)


class FeatureAdoptionRow(BaseModel):
    """Feature-level aggregation of 5 metrics (FR-014)."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    feature_id: str = Field(..., min_length=1, max_length=64)
    feature_name: str = Field(..., min_length=1, max_length=160)
    metrics: list[FeatureAdoptionMetric] = Field(..., min_length=5, max_length=5)
    cohort_id: Optional[str] = Field(default=None, max_length=64)
    cohort_population: int = Field(default=0, ge=0)
    last_computed_at: str = Field(default="unknown", max_length=64)
    freshness_at: str = Field(default="unknown", max_length=64)


class FeatureAdoptionResponse(BaseModel):
    """Envelope for GET /product-analytics/feature-adoption."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    features: list[FeatureAdoptionRow] = Field(default_factory=list)
    total: int = Field(ge=0)
    freshness_at: str = Field(default="unknown", max_length=64)


# ---------------------------------------------------------------------------
# User privacy-safe profile (FR-015 + FR-031 + FR-032)
# ---------------------------------------------------------------------------


UserVisibilityLevel = Literal[
    "full",  # visible to any authorized role
    "masked",  # visible but redacted (e.g. email prefix only)
    "hidden",  # field is omitted or replaced with "—" for non-eligible roles
]


# Field name allowlist for UserPrivacySafe. ANY field name NOT in this
# set is REJECTED at the schema boundary. This is the FR-032 / FR-015
# privacy guard — the schema is the canonical allow-list.
_USER_SAFE_FIELD_NAMES = frozenset(
    {
        "email",
        "role",
        "journey_summary",
        "incidents_count",
        "quality_score",
        "created_at",
        "last_active_at",
    }
)


class UserPrivacySafeField(BaseModel):
    """A single privacy-safe field row with visibility level (AC-15.3)."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    name: Literal[
        "email",
        "role",
        "journey_summary",
        "incidents_count",
        "quality_score",
        "created_at",
        "last_active_at",
    ]
    visibility: UserVisibilityLevel
    value: Optional[str] = Field(default=None, max_length=2048)


class UserPrivacySafe(BaseModel):
    """Privacy-safe user profile (FR-015 + FR-032).

    The schema deliberately ONLY carries the 7 allow-listed field names.
    raw_resume / raw_interview_answer / raw_prompt / raw_model_output
    are NOT exposed; the Frontend AC-15.4 grep must return 0 hits when
    applied to ``UsersAccounts.tsx``.
    """

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    user_id: str = Field(..., min_length=1, max_length=64)
    fields: list[UserPrivacySafeField] = Field(default_factory=list)
    cohort_population: int = Field(default=0, ge=0)
    last_computed_at: str = Field(default="unknown", max_length=64)
    freshness_at: str = Field(default="unknown", max_length=64)


__all__ = [
    "CohortListResponse",
    "CohortSegment",
    "FeatureAdoptionMetric",
    "FeatureAdoptionResponse",
    "FeatureAdoptionRow",
    "FunnelComparisonDelta",
    "FunnelResponse",
    "FunnelStep",
    "QuestionTab",
    "QuestionTemplate",
    "QuestionTemplateListResponse",
    "TimeToConvertBand",
    "UserPrivacySafe",
    "UserPrivacySafeField",
    "UserVisibilityLevel",
]