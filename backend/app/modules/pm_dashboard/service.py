"""REQ-033 US1 — PM Dashboard service layer (T072).

Pure orchestration: takes a ``DashboardFilter`` + DB session, calls the
repository helpers, and assembles ``PanelResponse`` envelopes for the
overview + funnel endpoints.

Functions:

- ``get_overview(session, filters) -> list[PanelResponse[OverviewPanelData]]``
  — assembles the 6 built-in PM metrics into a single bundled panel.
- ``get_funnel(session, filters) -> list[PanelResponse[FunnelPanelData]]``
  — assembles the 4-step core funnel.
- ``validate_filters(filters) -> DashboardFilter`` — runs Pydantic
  validation; raises ``ValueError`` on bad input. Mapped to HTTP 400 by
  the FastAPI layer.

Quality flags:

- ``partial_data=True`` when the overview / funnel has zero rows for
  the period (empty state).
- ``missing_version_fields`` populated when any of the canonical version
  dimensions (app_version, prompt_fingerprint, model, ...) is missing
  or ``"unknown"``. Surfaces SC-010 normalization.

Cost labeling:

- The estimated cost panel carries ``is_estimate=True`` per FR-008.
- ``freshness_at`` is set to ``"unknown"`` when no data is available,
  otherwise the current UTC time as an ISO 8601 string.

Caching:

- For MVP we always aggregate live (no ``metric_snapshots`` cache
  invalidation logic). The catalog is consulted to read metric
  definitions but does NOT route through the snapshot table yet.
"""
from __future__ import annotations

from datetime import UTC, datetime, timezone
from typing import Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.pm_dashboard import repository
from app.modules.pm_dashboard.schemas import (
    DashboardFilter,
    FunnelPanelData,
    FunnelStep,
    OverviewPanelData,
    PanelResponse,
    QualityFlags,
)


# ---------------------------------------------------------------------------
# Tunables
# ---------------------------------------------------------------------------


#: Canonical funnel step definitions (FR-006). Order matters.
FUNNEL_STEPS: tuple[dict[str, str], ...] = (
    {"event_name": "auth.registered", "step_name": "registered"},
    {"event_name": "product.visit", "step_name": "active_users"},
    {"event_name": "ai.call_completed", "step_name": "completed_ai_tasks"},
    {"event_name": "ai.call_completed", "step_name": "ai_success_rate"},
)


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _missing_version_fields_for(filters: DashboardFilter) -> list[str]:
    """Return canonical version dimensions whose value is unknown / absent."""
    fields = (
        "app_version",
        "prompt_fingerprint",
        "rubric_version",
        "model",
        "graph",
        "node",
    )
    return [f for f in fields if not getattr(filters, f)]


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def validate_filters(filters: DashboardFilter) -> DashboardFilter:
    """Validate ``filters`` (Pydantic has already run).

    Service-level checks live here so the API layer can map
    ``ValueError`` → HTTP 400.
    """
    if filters.date_range_end <= filters.date_range_start:
        raise ValueError(
            "date_range_end must be strictly after date_range_start"
        )
    return filters


# ---------------------------------------------------------------------------
# Overview panel assembly
# ---------------------------------------------------------------------------


async def get_overview(
    session: AsyncSession,
    filters: DashboardFilter,
) -> list[PanelResponse[Any]]:
    """Assemble the product-overview panels (FR-002 + FR-006 + FR-007).

    Returns a list of PanelResponse rows. The Overview panel is a single
    bundled panel whose ``data`` field carries all 8 FR-002 fields.
    """
    validate_filters(filters)

    # Pull live aggregates.
    uv = await repository.count_visits(session, filters)
    registered = await repository.count_registered_users(session, filters)
    active = await repository.count_active_users(session, filters)
    completed_ai = await repository.count_completed_ai_tasks(session, filters)
    success_rate = await repository.compute_ai_success_rate(session, filters)
    total_tokens = await repository.sum_token_usage(session, filters)
    est_cost = await repository.sum_estimated_cost(session, filters)
    open_badcases = await repository.count_open_badcases(session, filters)

    data = OverviewPanelData(
        uv=uv,
        registered_users=registered,
        active_users=active,
        completed_ai_tasks=completed_ai,
        ai_success_rate=success_rate,
        total_tokens=total_tokens,
        estimated_cost=est_cost,
        open_badcases=open_badcases,
        is_estimate=True,  # FR-008 — cost fields are estimates
    )

    # Quality flags: if all aggregates are zero, surface partial_data.
    total_count = (
        uv
        + registered
        + active
        + completed_ai
        + total_tokens
        + int(est_cost)
        + open_badcases
    )
    quality_flags = QualityFlags(
        missing_version_fields=_missing_version_fields_for(filters),
        sampled_data=False,
        delayed_ingestion=False,
        partial_data=(total_count == 0),
    )

    freshness = _now_iso() if total_count > 0 else "unknown"

    panel = PanelResponse[OverviewPanelData](
        metric_id="pm.overview",
        display_name="Product Overview",
        value=float(uv + registered + active + completed_ai),
        unit="count",
        period_start=filters.date_range_start,
        period_end=filters.date_range_end,
        dimensions=filters.to_dimensions(),
        source_of_truth="product_events + ai_invocation_records + badcases",
        freshness_at=freshness,
        quality_flags=quality_flags,
        data=data,
    )

    return [panel]


# ---------------------------------------------------------------------------
# Funnel panel assembly
# ---------------------------------------------------------------------------


async def get_funnel(
    session: AsyncSession,
    filters: DashboardFilter,
) -> list[PanelResponse[Any]]:
    """Assemble the core funnel panel (FR-006).

    Returns a single PanelResponse whose ``data.steps`` carries the
    4 funnel steps with per-step conversion rates + ``largest_drop_off``
    flag.
    """
    validate_filters(filters)

    # Pull event counts per step.
    step_counts: list[tuple[dict[str, str], int]] = []
    for step in FUNNEL_STEPS:
        cnt = await repository.count_event_rows(session, filters, step["event_name"])
        step_counts.append((step, cnt))

    # Compute conversions.
    total_rows = sum(c for _, c in step_counts)
    has_data = total_rows > 0

    entry_count = step_counts[0][1] if step_counts else 0
    prev_count = entry_count
    steps: list[FunnelStep] = []
    largest_drop = -1.0
    largest_drop_idx = -1
    for i, (step, cnt) in enumerate(step_counts):
        if prev_count > 0:
            conv_prev = cnt / prev_count
        else:
            conv_prev = 0.0
        if entry_count > 0:
            conv_entry = cnt / entry_count
        else:
            conv_entry = 0.0
        steps.append(
            FunnelStep(
                step_name=step["step_name"],
                step_order=i,
                count=cnt,
                conversion_from_previous=conv_prev,
                conversion_from_entry=conv_entry,
                largest_drop_off=False,  # set below
            )
        )
        if i > 0:
            drop = prev_count - cnt
            if drop > largest_drop:
                largest_drop = drop
                largest_drop_idx = i
        prev_count = cnt

    if largest_drop_idx >= 0:
        steps[largest_drop_idx] = steps[largest_drop_idx].model_copy(
            update={"largest_drop_off": True}
        )

    total_completion = steps[-1].count if steps else 0
    data = FunnelPanelData(
        steps=steps,
        total_entry=entry_count,
        total_completion=total_completion,
    )

    quality_flags = QualityFlags(
        missing_version_fields=_missing_version_fields_for(filters),
        sampled_data=False,
        delayed_ingestion=False,
        partial_data=not has_data,
    )

    freshness = _now_iso() if has_data else "unknown"

    panel = PanelResponse[FunnelPanelData](
        metric_id="pm.funnel",
        display_name="Core Funnel",
        value=float(total_completion),
        unit="count",
        period_start=filters.date_range_start,
        period_end=filters.date_range_end,
        dimensions=filters.to_dimensions(),
        source_of_truth="product_events",
        freshness_at=freshness,
        quality_flags=quality_flags,
        data=data,
    )

    return [panel]


__all__ = [
    "FUNNEL_STEPS",
    "get_funnel",
    "get_overview",
    "validate_filters",
]