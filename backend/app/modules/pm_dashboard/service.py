"""REQ-033 US1 + US2 + US3 + US4 + US7 — PM Dashboard service layer (T072, T085, T094, T104, T129).

Pure orchestration: takes a ``DashboardFilter`` + DB session, calls the
repository helpers, and assembles ``PanelResponse`` envelopes for the
overview + funnel endpoints.

Functions:

- ``get_overview(session, filters) -> list[PanelResponse[OverviewPanelData]]``
  — assembles the 6 built-in PM metrics into a single bundled panel.
- ``get_funnel(session, filters) -> list[PanelResponse[FunnelPanelData]]``
  — assembles the 4-step core funnel.
- ``get_resume_diagnosis(session, filters) ->
  list[PanelResponse[ResumeDiagnosisPanelData]]`` — assembles the US2
  resume diagnosis panel.
- ``get_mock_interview(session, filters) ->
  list[PanelResponse[MockInterviewPanelData]]`` — assembles the US3
  mock interview panel.
- ``get_ai_operations(session, filters) ->
  list[PanelResponse[AIOperationsPanelData]]`` — assembles the US4
  AI operations panel (7 core metrics + 4 top-N breakdowns).
- ``get_version_experiment(session, filters) ->
  list[PanelResponse[VersionExperimentPanelData]]`` — assembles the
  US7 version/experiment breakdown panel (5 metric cards + 2 tables).
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
    AIOperationsPanelData,
    DashboardFilter,
    ExperimentBreakdownEntry,
    FunnelPanelData,
    FunnelStep,
    MockInterviewPanelData,
    OverviewPanelData,
    PanelResponse,
    QualityFlags,
    ResumeDiagnosisPanelData,
    VersionBreakdownEntry,
    VersionExperimentPanelData,
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


# ---------------------------------------------------------------------------
# US2 (T085) - Resume Diagnosis Panel assembly
# ---------------------------------------------------------------------------


async def get_resume_diagnosis(
    session: AsyncSession,
    filters: DashboardFilter,
) -> list[PanelResponse[Any]]:
    """Assemble the resume diagnosis panel (US2).

    Returns a list of PanelResponse rows whose ``data`` field carries
    the 5 core metrics: success rate, report views, suggestions shown,
    suggestions accepted, acceptance rate, score delta (avg after -
    avg before).

    Empty window: returns 0 values + ``quality_flags.partial_data=True``
    + ``freshness_at="unknown"`` per SC-009.

    Privacy: the panel surfaces counts + deltas only; raw resume content
    is never returned. The repository reads ``ProductEvent`` rows tagged
    with ``event_name LIKE 'resume_diagnosis.%'`` (US2 fallback -- see
    repository.py docstring for the migration-pending rationale).
    """
    validate_filters(filters)

    # Pull aggregates.
    total = await repository.count_resume_diagnoses(session, filters)
    success = await repository.count_successful_resume_diagnoses(session, filters)
    report_views = await repository.count_report_views(session, filters)
    suggestions_shown = await repository.count_suggestions_shown(session, filters)
    suggestions_accepted = await repository.count_suggestions_accepted(
        session, filters
    )
    score_before = await repository.avg_resume_score_before(session, filters)
    score_after = await repository.avg_resume_score_after(session, filters)

    # Derived rates.
    success_rate = (success / total) if total > 0 else 0.0
    acceptance_rate = (
        (suggestions_accepted / suggestions_shown)
        if suggestions_shown > 0
        else 0.0
    )
    score_delta = score_after - score_before

    data_payload = ResumeDiagnosisPanelData(
        success_count=success,
        total_count=total,
        success_rate=success_rate,
        report_views=report_views,
        suggestions_shown=suggestions_shown,
        suggestions_accepted=suggestions_accepted,
        acceptance_rate=acceptance_rate,
        score_delta_before=score_before,
        score_delta_after=score_after,
        score_delta=score_delta,
    )

    has_data = (
        total > 0
        or report_views > 0
        or suggestions_shown > 0
        or suggestions_accepted > 0
    )

    quality_flags = QualityFlags(
        missing_version_fields=_missing_version_fields_for(filters),
        sampled_data=False,
        delayed_ingestion=False,
        partial_data=not has_data,
    )

    freshness = _now_iso() if has_data else "unknown"

    panel = PanelResponse[ResumeDiagnosisPanelData](
        metric_id="pm.resume_diagnosis",
        display_name="Resume Diagnosis",
        value=float(success),
        unit="count",
        period_start=filters.date_range_start,
        period_end=filters.date_range_end,
        dimensions=filters.to_dimensions(),
        source_of_truth="product_events (resume_diagnosis.*)",
        freshness_at=freshness,
        quality_flags=quality_flags,
        data=data_payload,
    )

    return [panel]


# ---------------------------------------------------------------------------
# US3 (T094) - Mock Interview Panel assembly
# ---------------------------------------------------------------------------


async def get_mock_interview(
    session: AsyncSession,
    filters: DashboardFilter,
) -> list[PanelResponse[Any]]:
    """Assemble the mock interview panel (US3).

    Returns a list of PanelResponse rows whose ``data`` field carries
    the 5 core metrics: starts, completions, completion rate, avg
    question count, report views, retries, failure rate, failure
    categories.

    Empty window: returns 0 values + ``quality_flags.partial_data=True``
    + ``freshness_at="unknown"`` per SC-009.

    Privacy: the panel surfaces counts + rates + average question count
    only; raw interview content is never returned. The repository reads
    ``ProductEvent`` rows tagged with ``event_name LIKE 'interview.%'``
    (US3 fallback -- see repository.py docstring for the
    migration-pending rationale).
    """
    validate_filters(filters)

    # Pull aggregates.
    starts = await repository.count_interview_starts(session, filters)
    completions = await repository.count_interview_completions(session, filters)
    failures = await repository.count_interview_failures(session, filters)
    retries = await repository.count_interview_retries(session, filters)
    report_views = await repository.count_interview_report_views(session, filters)
    avg_qc = await repository.avg_interview_question_count(session, filters)

    # Derived rates (clamped to [0, 1]).
    completion_rate = (completions / starts) if starts > 0 else 0.0
    completion_rate = max(0.0, min(1.0, completion_rate))
    failure_rate = (failures / starts) if starts > 0 else 0.0
    failure_rate = max(0.0, min(1.0, failure_rate))

    # Failure categories — MVP placeholder: empty dict. The dedicated
    # ``interview_outcomes.failure_category`` column is not yet landed
    # in a migration (033-POLISH). When it lands, the repository layer
    # will compute the breakdown.
    failure_categories: dict[str, int] = {}

    data_payload = MockInterviewPanelData(
        starts=starts,
        completions=completions,
        completion_rate=completion_rate,
        avg_question_count=avg_qc,
        report_views=report_views,
        retries=retries,
        failure_rate=failure_rate,
        failure_categories=failure_categories,
    )

    has_data = (
        starts > 0
        or completions > 0
        or failures > 0
        or retries > 0
        or report_views > 0
    )

    quality_flags = QualityFlags(
        missing_version_fields=_missing_version_fields_for(filters),
        sampled_data=False,
        delayed_ingestion=False,
        partial_data=not has_data,
    )

    freshness = _now_iso() if has_data else "unknown"

    panel = PanelResponse[MockInterviewPanelData](
        metric_id="pm.mock_interview",
        display_name="Mock Interview",
        value=float(starts),
        unit="count",
        period_start=filters.date_range_start,
        period_end=filters.date_range_end,
        dimensions=filters.to_dimensions(),
        source_of_truth="product_events (interview.*)",
        freshness_at=freshness,
        quality_flags=quality_flags,
        data=data_payload,
    )

    return [panel]


# ---------------------------------------------------------------------------
# US4 (T104) - AI Operations Panel assembly
# ---------------------------------------------------------------------------


#: Number of top entries to surface per breakdown dimension
#: (model / graph / node / prompt_fingerprint). The PM dashboard shows
#: "top 5" by call count to avoid one-offs dominating the view.
AI_OPS_TOP_N: int = 5


async def get_ai_operations(
    session: AsyncSession,
    filters: DashboardFilter,
) -> list[PanelResponse[Any]]:
    """Assemble the AI operations panel (US4).

    Returns a list of PanelResponse rows whose ``data`` field carries
    the 7 core metrics (call_count, success_count, failure_count,
    success_rate, failure_rate, retry_count, p50/p95/p99 latency,
    estimated_cost, total_tokens + prompt + completion tokens) plus
    the 4 top-N breakdowns (model, graph, node, prompt_fingerprint).

    Empty window: returns 0 values + ``quality_flags.partial_data=True``
    + ``freshness_at="unknown"`` per SC-009.

    Privacy: the panel surfaces counts + rates + aggregates + breakdowns
    only. Raw prompt / completion text is never read from
    ``AIInvocationRecord`` (no payload fields surfaced). The cost is
    labeled as an estimate per FR-008.
    """
    validate_filters(filters)

    # Pull aggregates (parallel where possible; sequential keeps it simple).
    call_count = await repository.count_ai_invocations(session, filters)
    success_count = await repository.count_ai_invocations_success(session, filters)
    failure_count = await repository.count_ai_invocations_failure(session, filters)
    retry_count = await repository.count_ai_invocations_retried(session, filters)
    prompt_tokens = await repository.sum_ai_prompt_tokens(session, filters)
    completion_tokens = await repository.sum_ai_completion_tokens(session, filters)
    p50 = await repository.ai_latency_percentile(session, filters, 0.50)
    p95 = await repository.ai_latency_percentile(session, filters, 0.95)
    p99 = await repository.ai_latency_percentile(session, filters, 0.99)
    # Reuse the existing cost helper (US1) for the sum of estimated_cost
    # — the AIInvocationRecord table already carries the cost recorded
    # by the LLM client hook (US9 T040) so the panel just sums it.
    estimated_cost = await repository.sum_estimated_cost(session, filters)
    # Top-5 breakdowns
    model_breakdown = await repository.ai_top_breakdown(
        session, filters, "model", top_n=AI_OPS_TOP_N
    )
    graph_breakdown = await repository.ai_top_breakdown(
        session, filters, "graph", top_n=AI_OPS_TOP_N
    )
    node_breakdown = await repository.ai_top_breakdown(
        session, filters, "node", top_n=AI_OPS_TOP_N
    )
    prompt_fingerprint_breakdown = await repository.ai_top_breakdown(
        session, filters, "prompt_fingerprint", top_n=AI_OPS_TOP_N
    )

    # Derived rates (clamped to [0, 1]).
    success_rate = (success_count / call_count) if call_count > 0 else 0.0
    success_rate = max(0.0, min(1.0, success_rate))
    failure_rate = (failure_count / call_count) if call_count > 0 else 0.0
    failure_rate = max(0.0, min(1.0, failure_rate))
    total_tokens = prompt_tokens + completion_tokens

    data_payload = AIOperationsPanelData(
        call_count=call_count,
        success_count=success_count,
        failure_count=failure_count,
        success_rate=success_rate,
        failure_rate=failure_rate,
        retry_count=retry_count,
        p50_latency_ms=p50,
        p95_latency_ms=p95,
        p99_latency_ms=p99,
        estimated_cost=estimated_cost,
        total_tokens=total_tokens,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        is_estimate=True,  # FR-008 — cost is always labeled as estimate
        model_breakdown=model_breakdown,
        graph_breakdown=graph_breakdown,
        node_breakdown=node_breakdown,
        prompt_fingerprint_breakdown=prompt_fingerprint_breakdown,
    )

    has_data = call_count > 0

    quality_flags = QualityFlags(
        missing_version_fields=_missing_version_fields_for(filters),
        sampled_data=False,
        delayed_ingestion=False,
        partial_data=not has_data,
    )

    freshness = _now_iso() if has_data else "unknown"

    panel = PanelResponse[AIOperationsPanelData](
        metric_id="pm.ai_operations",
        display_name="AI Operations",
        value=float(call_count),
        unit="count",
        period_start=filters.date_range_start,
        period_end=filters.date_range_end,
        dimensions=filters.to_dimensions(),
        source_of_truth="ai_invocation_records",
        freshness_at=freshness,
        quality_flags=quality_flags,
        data=data_payload,
    )

    return [panel]


# ---------------------------------------------------------------------------
# US7 (T129) — Version / Experiment Panel assembly
# ---------------------------------------------------------------------------


#: Number of top entries to surface per breakdown table (version /
#: experiment). The PM dashboard shows "top 5" by event count to avoid
#: one-offs dominating the view.
VERSION_EXPERIMENT_TOP_N: int = 5


async def get_version_experiment(
    session: AsyncSession,
    filters: DashboardFilter,
) -> list[PanelResponse[Any]]:
    """Assemble the version / experiment panel (US7).

    Returns a single ``PanelResponse`` whose ``data`` field carries:

    - 5 metric cards: ``event_count`` + 4 distinct dimension counts
      (``prompt_fingerprint`` / ``model`` / ``app_version`` /
      ``experiment_id``).
    - 2 breakdown tables: ``top_versions`` (rows of
      ``prompt_fingerprint × rubric_version × app_version × model``
      ordered by count desc, top 5) + ``top_experiments`` (rows of
      ``experiment_id`` ordered by count desc, top 5).
    - ``trace_available`` flag — when ``False``, the frontend renders
      the "trace unavailable" badge (US7 T123 contract).

    Empty window: returns 0 values + ``quality_flags.partial_data=True``
    + ``freshness_at="unknown"`` per SC-009.

    Privacy: only counts + breakdowns are surfaced. Raw event content
    (no prompt / completion / message / response text) is never read.
    The repository aggregations only touch the structured version
    columns + ``experiment_id`` / ``trace_id`` / ``created_at``.
    """
    validate_filters(filters)

    event_count = await repository.count_ai_version_breakdown_rows(session, filters)
    distinct = await repository.distinct_version_dimensions(session, filters)
    top_versions = await repository.top_versions_breakdown(
        session, filters, top_n=VERSION_EXPERIMENT_TOP_N
    )
    top_experiments = await repository.top_experiments_breakdown(
        session, filters, top_n=VERSION_EXPERIMENT_TOP_N
    )
    trace_available = await repository.has_any_trace_in_window(session, filters)

    top_versions_payload = [
        VersionBreakdownEntry(
            prompt_fingerprint=r.get("prompt_fingerprint", "unknown"),
            rubric_version=r.get("rubric_version", "unknown"),
            app_version=r.get("app_version", "unknown"),
            model=r.get("model", "unknown"),
            count=int(r.get("count", 0) or 0),
        )
        for r in top_versions
    ]
    top_experiments_payload = [
        ExperimentBreakdownEntry(
            experiment_id=r.get("experiment_id", "unknown"),
            count=int(r.get("count", 0) or 0),
        )
        for r in top_experiments
    ]

    data_payload = VersionExperimentPanelData(
        event_count=event_count,
        distinct_prompt_fingerprints=int(distinct.get("prompt_fingerprint", 0)),
        distinct_models=int(distinct.get("model", 0)),
        distinct_app_versions=int(distinct.get("app_version", 0)),
        distinct_experiments=int(distinct.get("experiment_id", 0)),
        top_versions=top_versions_payload,
        top_experiments=top_experiments_payload,
        trace_available=bool(trace_available),
        top_versions_source="ai_invocation_records (grouped by version_context)",
    )

    has_data = event_count > 0

    quality_flags = QualityFlags(
        missing_version_fields=_missing_version_fields_for(filters),
        sampled_data=False,
        delayed_ingestion=False,
        partial_data=not has_data,
    )

    freshness = _now_iso() if has_data else "unknown"

    panel = PanelResponse[VersionExperimentPanelData](
        metric_id="pm.version_experiment",
        display_name="Version & Experiment",
        value=float(event_count),
        unit="count",
        period_start=filters.date_range_start,
        period_end=filters.date_range_end,
        dimensions=filters.to_dimensions(),
        source_of_truth="product_events (grouped by version_context)",
        freshness_at=freshness,
        quality_flags=quality_flags,
        data=data_payload,
    )

    return [panel]


__all__ = [
    "AI_OPS_TOP_N",
    "FUNNEL_STEPS",
    "VERSION_EXPERIMENT_TOP_N",
    "get_ai_operations",  # US4 T104
    "get_funnel",
    "get_mock_interview",  # US3 T094
    "get_overview",
    "get_resume_diagnosis",  # US2 T085
    "get_version_experiment",  # US7 T129
    "validate_filters",
]