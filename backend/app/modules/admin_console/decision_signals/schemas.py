"""REQ-044 US1 — Decision Signal Pydantic v2 schemas (FR-007~FR-010).

Schema surface:

- :class:`DecisionSignalCategory` — Literal of the 6 FR-007 categories.
- :class:`ConfidenceTier` — Literal of the 4 FR-009 confidence levels
  (confirmed / sampled / inferred / candidate).
- :class:`SignalSeverity` — Literal of severity bands (critical / high /
  medium / low / info).
- :class:`EvidenceLink` — link + label + privacy class.
- :class:`SignalQualityFlags` — copy of pm_dashboard QualityFlags
  semantics adapted for the decision-queue (stale / partial_baseline /
  no_data).
- :class:`DecisionSignal` — single signal row (FR-008 fields).
- :class:`DecisionSignalListResponse` — list envelope + freshness_at +
  quiet_steady_state flag (FR-010).
- :class:`CommandCenterOverview` — top-level 4 KPI tiles for the
  workspace header (Product Health / AI Quality / AI Cost / System
  Health).

Validation invariants locked by AC matrix:

- ``confidence`` MUST be one of the 4 FR-009 tiers.
- ``severity`` MUST be one of the 5 bands.
- ``category`` MUST be one of the 6 FR-007 categories.
- ``evidence_links`` MUST be a list (possibly empty for the moment,
  populated by Phase 2 batch 3).
- ``freshness_at`` MUST be an ISO 8601 string OR the literal
  ``"unknown"`` per FR-028 (valid zero / stale / missing).
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

# ---------------------------------------------------------------------------
# Category / Confidence / Severity enums (FR-007 / FR-009)
# ---------------------------------------------------------------------------


DecisionSignalCategory = Literal[
    "product",  # product health / funnel movement / feature adoption
    "ai-quality",  # success rate / latency / eval results / badcase link
    "ai-cost",  # token cost / cost-quality tradeoff (FR-019)
    "system-health",  # system reliability / incidents
    "incident",  # operational / product-impacting incidents
    "data-quality",  # freshness / completeness / partial data
]

ConfidenceTier = Literal[
    "confirmed",  # direct observation, full population, no unknowns
    "sampled",  # observed but sampled (subset of users/period)
    "inferred",  # derived from indirect signals (no direct measurement)
    "candidate",  # low confidence — must be visually distinct
]

SignalSeverity = Literal[
    "critical",
    "high",
    "medium",
    "low",
    "info",
]


# ---------------------------------------------------------------------------
# Supporting types
# ---------------------------------------------------------------------------


class EvidenceLink(BaseModel):
    """A single evidence link attached to a signal.

    FR-008 says each signal MUST include ``next_review_link``; we also
    surface an ``evidence_links`` array per FR-018 so AI-quality signals
    can attach eval/badcase/log references.

    Fields:

    - ``label`` — human-readable label rendered in the drawer.
    - ``href`` — deep-link route (e.g. ``/admin-console/ai-operations?from=signal-001``).
    - ``kind`` — semantic class for icon selection
      (review / eval / badcase / log / trace / metric / report).
    - ``privacy_class`` — visibility tier; ``public`` is shown to PM,
      ``internal`` to operations, ``restricted`` to maintainer only.
    """

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    label: str = Field(..., min_length=1, max_length=120)
    href: str = Field(..., min_length=1, max_length=512)
    kind: Literal["review", "eval", "badcase", "log", "trace", "metric", "report"] = "review"
    privacy_class: Literal["public", "internal", "restricted"] = "public"


class SignalQualityFlags(BaseModel):
    """Quality flags for a single decision signal (FR-009 / FR-028).

    Mirrors pm_dashboard.QualityFlags semantics adapted for the
    decision-queue scope. All flags default to False / empty so the
    backend can return a signal even when telemetry is missing.
    """

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    stale: bool = Field(
        default=False,
        description="True if freshness_at exceeds the metric definition target.",
    )
    partial_baseline: bool = Field(
        default=False,
        description="True if the comparison period is incomplete (Edge Case line 322).",
    )
    delayed_ingestion: bool = Field(
        default=False,
        description="True if the underlying data ingestion lags behind real time.",
    )
    missing_version_fields: list[str] = Field(default_factory=list)
    sampled_data: bool = Field(default=False)
    partial_data: bool = Field(default=False)
    no_data: bool = Field(
        default=False,
        description="True if the signal exists but the underlying metric has zero rows.",
    )


# ---------------------------------------------------------------------------
# DecisionSignal — FR-008
# ---------------------------------------------------------------------------


class DecisionSignal(BaseModel):
    """A single prioritized item in the command-center decision queue.

    FR-008 mandated fields (10):

    - ``id`` — stable signal identifier.
    - ``category`` — one of the 6 FR-007 categories.
    - ``what_changed`` — plain-language description of the change.
    - ``affected_segment`` — segment / cohort the change applies to.
    - ``comparison_baseline`` — comparison period label + summary.
    - ``severity`` — critical / high / medium / low / info.
    - ``confidence`` — confirmed / sampled / inferred / candidate.
    - ``owner`` — current owner or suggested owner.
    - ``freshness_at`` — ISO 8601 timestamp OR the literal ``"unknown"``.
    - ``next_review_link`` — link to the next review surface.

    Plus:

    - ``quality_flags`` — :class:`SignalQualityFlags` for FR-028.
    - ``evidence_links`` — :class:`list[EvidenceLink]` for FR-018.
    - ``priority`` — numeric sort key (higher = more urgent).
    - ``detected_at`` — when the signal was first raised.
    - ``headline_metric_id`` — optional pointer to the underlying
      metric_id (e.g. ``"overview.ai_success_rate"``) for downstream
      drilldown (Phase 2 batch 3).
    """

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    id: str = Field(..., min_length=1, max_length=64)
    category: DecisionSignalCategory
    what_changed: str = Field(..., min_length=1, max_length=512)
    affected_segment: str = Field(..., min_length=1, max_length=256)
    comparison_baseline: str = Field(..., min_length=1, max_length=256)
    severity: SignalSeverity
    confidence: ConfidenceTier
    owner: str = Field(..., min_length=1, max_length=128)
    freshness_at: str = Field(..., min_length=1, max_length=64)
    next_review_link: str = Field(..., min_length=1, max_length=512)
    evidence_links: list[EvidenceLink] = Field(default_factory=list)
    quality_flags: SignalQualityFlags = Field(default_factory=SignalQualityFlags)
    priority: int = Field(default=0, ge=0, le=1000)
    detected_at: str = Field(..., min_length=1, max_length=64)
    headline_metric_id: Optional[str] = Field(default=None, max_length=128)
    title: str = Field(..., min_length=1, max_length=160)

    @field_validator("freshness_at")
    @classmethod
    def _validate_freshness(cls, value: str) -> str:
        # Allow either a real ISO 8601 timestamp or the literal
        # "unknown" sentinel (FR-028).
        if value == "unknown":
            return value
        # Minimal ISO 8601 sanity check (no timezone arithmetic).
        try:
            datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:  # pragma: no cover - defensive
            raise ValueError(
                "freshness_at must be ISO 8601 or the literal 'unknown'"
            ) from exc
        return value


# ---------------------------------------------------------------------------
# List response + workspace overview
# ---------------------------------------------------------------------------


class DecisionSignalListResponse(BaseModel):
    """Top-level envelope for GET /command-center/signals."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    signals: list[DecisionSignal] = Field(default_factory=list)
    total: int = Field(ge=0)
    high_severity_count: int = Field(
        default=0,
        ge=0,
        description="Count of severity in {critical, high}; drives FR-010 quiet-state.",
    )
    quiet_steady_state: bool = Field(
        default=False,
        description="True iff high_severity_count == 0 (FR-010).",
    )
    freshness_at: str = Field(default="unknown")
    last_reviewed_at: str = Field(default="unknown")
    open_reviews: int = Field(default=0, ge=0)


class CommandCenterOverview(BaseModel):
    """Top-level 4 KPI tiles for the workspace header.

    Static values for US1 — Phase 2 batch 2 will wire these to the
    pm_dashboard overview panel.
    """

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    product_health: float = Field(default=0.0)
    product_health_unit: str = Field(default="score")
    ai_quality: float = Field(default=0.0)
    ai_quality_unit: str = Field(default="rate")
    ai_cost: float = Field(default=0.0)
    ai_cost_unit: str = Field(default="usd")
    system_health: float = Field(default=0.0)
    system_health_unit: str = Field(default="score")
    freshness_at: str = Field(default="unknown")


class CommandCenterOverviewResponse(BaseModel):
    """Envelope for the overview KPI tiles."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    overview: CommandCenterOverview
    freshness_at: str = Field(default="unknown")


__all__ = [
    "CommandCenterOverview",
    "CommandCenterOverviewResponse",
    "ConfidenceTier",
    "DecisionSignal",
    "DecisionSignalCategory",
    "DecisionSignalListResponse",
    "EvidenceLink",
    "SignalQualityFlags",
    "SignalSeverity",
]