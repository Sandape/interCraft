"""REQ-044 US7 — Review Snapshots + Metric Trust Pydantic v2 schemas.

Schema surface (FR-027~FR-030 + SC-012 + Edge Cases):

- :class:`NOT_PROVIDED` — Literal sentinel for missing metric-definition
  fields (AC-27.4 — explicitly render ``"(not provided)"`` so the
  frontend never silently omits).
- :class:`MetricDefinition10Field` — full FR-027 10-field contract
  (definition / owner / source / numerator / denominator / unit /
  period / freshness / completeness / quality_flags). Locks the
  trust-but-verify union shared by US1 decision signal + US2 funnel +
  US3 KPI tooltips (AC-27.3).
- :class:`FrozenValue` — single frozen metric row (FR-029 SC-012).
- :class:`CurrentValue` — single live metric row (FR-030 + AC-30.1).
- :class:`ComparisonDelta` — single baseline-vs-snapshot delta row
  (FR-029 SC-012 + AC-30.3).
- :class:`EvidenceLink` — privacy-safe evidence reference
  (FR-029 + FR-032 — ``label`` is human-readable, never raw payload).
- :class:`ReviewSnapshotRequest` — POST body (FR-029 AC-29.1).
- :class:`ReviewSnapshotResponse` — POST/GET response with the
  8-field SC-012 envelope + FR-030 delta/cluster + EC-1/EC-2 warnings.
- :class:`ReviewSnapshotListResponse` — GET list envelope.

All reuses of US6 governance types are import-only (DataStatus,
WorkspaceId, AuditAction) — DO NOT redeclare.
"""
from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

# Reuse US6 governance types — DO NOT redeclare.
from app.modules.admin_console.governance.schemas import (
    DataStatus,
    VisibilityMode,
    WorkspaceId,
)


# ---------------------------------------------------------------------------
# FR-027 (AC-27.4) — "(not provided)" sentinel
# ---------------------------------------------------------------------------

NOT_PROVIDED: str = "(not provided)"

# Field names that, when missing, must render as NOT_PROVIDED.
_METRIC_DEF_10_FIELDS: tuple[str, ...] = (
    "definition",
    "owner",
    "source",
    "numerator",
    "denominator",
    "unit",
    "period",
    "freshness",
    "completeness",
)


class MetricDefinition10Field(BaseModel):
    """Full 10-field metric trust definition (FR-027).

    The 10 fields are: definition / owner / source / numerator /
    denominator / unit / period / freshness / completeness /
    quality_flags. All string fields default to NOT_PROVIDED so the
    frontend can render the literal ``"(not provided)"`` instead of
    silently dropping a column (AC-27.4).
    """

    model_config = ConfigDict(frozen=False)

    metric_id: str
    name: str
    # FR-027 #1
    definition: str = NOT_PROVIDED
    # FR-027 #2
    owner: str = NOT_PROVIDED
    # FR-027 #3
    source: str = NOT_PROVIDED
    # FR-027 #4
    numerator: str = NOT_PROVIDED
    # FR-027 #5
    denominator: str = NOT_PROVIDED
    # FR-027 #6
    unit: str = NOT_PROVIDED
    # FR-027 #7
    period: str = NOT_PROVIDED
    # FR-027 #8
    freshness: str = NOT_PROVIDED
    # FR-027 #9
    completeness: str = NOT_PROVIDED
    # FR-027 #10 — reuse US6 5-state Literal
    quality_flags: DataStatus = "valid_zero"


def _assert_metric_def_no_missing() -> None:
    """Schema-level lock — every FR-027 field declared with NOT_PROVIDED fallback.

    AC-27.2 contract test asserts these 10 fields are present.
    """
    fields = set(MetricDefinition10Field.model_fields.keys())
    expected = {
        "metric_id",
        "name",
        "definition",
        "owner",
        "source",
        "numerator",
        "denominator",
        "unit",
        "period",
        "freshness",
        "completeness",
        "quality_flags",
    }
    missing = expected - fields
    assert not missing, f"MetricDefinition10Field missing FR-027 fields: {missing}"


_assert_metric_def_no_missing()


# ---------------------------------------------------------------------------
# FR-029 / FR-030 — frozen / current / delta / evidence / list envelope
# ---------------------------------------------------------------------------


class FrozenValue(BaseModel):
    """Single frozen metric value (FR-029 SC-012 AC-29.1)."""

    model_config = ConfigDict(frozen=False)

    metric_id: str
    value: float
    unit: str
    captured_at: str
    data_status: DataStatus = "valid_zero"


class CurrentValue(BaseModel):
    """Single live current metric value (FR-030 AC-30.1)."""

    model_config = ConfigDict(frozen=False)

    metric_id: str
    value: float
    unit: str
    captured_at: str
    data_status: DataStatus = "valid_zero"


class ComparisonDelta(BaseModel):
    """Single baseline-vs-snapshot delta row (FR-029 + AC-30.3)."""

    model_config = ConfigDict(frozen=False)

    metric_id: str
    delta_pct: float
    period: str


class EvidenceLink(BaseModel):
    """Privacy-safe evidence reference (FR-029 + FR-032 SC-010).

    ``label`` is a human-readable summary; the link is an opaque id
    reference (no raw payload ever embedded).
    """

    model_config = ConfigDict(frozen=False)

    label: str
    kind: Literal["incident", "trace", "ai_task", "badcase", "export"]
    target_id: str


ReviewSnapshotFormat = Literal["json", "markdown"]


class ReviewSnapshotRequest(BaseModel):
    """POST /review-snapshots body (FR-029 AC-29.1)."""

    model_config = ConfigDict(frozen=False)

    workspace: WorkspaceId
    filters: dict[str, Any] = Field(default_factory=dict)
    comparison_period: str = Field(
        min_length=1, max_length=200,
        description="Human-readable comparison baseline label, e.g. 'vs prior week'",
    )
    annotations: str = Field(
        default="",
        max_length=4000,
        description="PM commentary that gets baked into the snapshot (FR-029 SC-012)",
    )
    format: ReviewSnapshotFormat = "json"


class ReviewSnapshotResponse(BaseModel):
    """POST + GET /review-snapshots/{id} response (FR-029/030 + SC-012).

    The 8 SC-012 fields (frozen_values / comparison_deltas /
    metric_definitions / freshness_warnings / quality_flags /
    evidence_links / filters / annotations) are all required
    non-empty by AC-SC-12.1.
    """

    model_config = ConfigDict(frozen=False)

    snapshot_id: str
    workspace: WorkspaceId
    generated_at: str
    generated_by: str
    # SC-012 #1 — visible filters at snapshot time
    filters: dict[str, Any]
    # SC-012 #2 — frozen metric values
    frozen_values: list[FrozenValue]
    # SC-012 #3 — comparison deltas (baseline vs snapshot period)
    comparison_deltas: list[ComparisonDelta]
    # SC-012 #4 — metric definitions (10-field)
    metric_definitions: list[MetricDefinition10Field]
    # SC-012 #5 — freshness warnings
    freshness_warnings: list[str]
    # SC-012 #6 — quality flags map (metric_id -> DataStatus)
    quality_flags: dict[str, DataStatus]
    # SC-012 #7 — annotations (PM commentary baked in)
    annotations: str
    # SC-012 #8 — privacy-safe evidence links
    evidence_links: list[EvidenceLink]
    # FR-030 + AC-30.1 — current (live) values mirror
    current_values: list[CurrentValue]
    # EC-2 — cohort definition changed since snapshot
    cohort_definition_changed: bool = False
    cohort_change_warning: Optional[str] = None
    # EC-1 — late-arriving data warnings (delta cluster)
    late_arriving_warnings: list[str] = Field(default_factory=list)
    # AC-29.4 — download URL points at US6 export route
    download_url: str
    expires_at: str
    # Top-level data status (FR-028)
    data_status: DataStatus = "valid_zero"
    visibility_mode: VisibilityMode = "full"
    # Comparison period label echo
    comparison_period: str


class ReviewSnapshotListResponse(BaseModel):
    """GET /review-snapshots list envelope (FR-029)."""

    model_config = ConfigDict(frozen=False)

    snapshots: list[ReviewSnapshotResponse]
    total: int
    data_status: DataStatus = "valid_zero"


__all__ = [
    "NOT_PROVIDED",
    "ComparisonDelta",
    "CurrentValue",
    "EvidenceLink",
    "FrozenValue",
    "MetricDefinition10Field",
    "ReviewSnapshotFormat",
    "ReviewSnapshotListResponse",
    "ReviewSnapshotRequest",
    "ReviewSnapshotResponse",
]