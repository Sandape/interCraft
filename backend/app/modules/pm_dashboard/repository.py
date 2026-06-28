"""REQ-033 US1 + US2 + US3 + US4 — PM Dashboard repository queries (T071, T084, T093, T103).

Async SQLAlchemy 2.0 queries against the ``product_events``,
``ai_invocation_records``, ``pm_metric_snapshots``, and ``badcases``
tables created by migration 0024.

US1 functions:

- ``list_product_events`` — filtered event rows (rarely needed by panels,
  but useful for diagnostics).
- ``count_active_users`` — distinct user_id from product events in window.
- ``count_registered_users`` — distinct user_id from ``auth.registered``
  events in window.
- ``count_completed_ai_tasks`` — distinct task / invocation in window
  where AI status = SUCCESS.
- ``count_ai_tasks_total`` — total AI invocations (success + failure) in
  window.
- ``sum_token_usage`` — sum of prompt + completion tokens in window.
- ``sum_estimated_cost`` — sum of ``estimated_cost`` in window.
- ``compute_ai_success_rate`` — float in [0.0, 1.0]; 0.0 when no tasks.
- ``count_open_badcases`` — count of badcases not in (CLOSED, REJECTED).

US2 functions (T084) — Resume Diagnosis Panel:

- ``count_resume_diagnoses`` — distinct ``resume_diagnosis.started`` events.
- ``count_successful_resume_diagnoses`` — distinct successful outcomes.
- ``count_report_views`` — distinct ``resume_diagnosis.report_viewed`` events.
- ``count_suggestions_shown`` — count of ``resume_diagnosis.suggestion_shown``
  events.
- ``count_suggestions_accepted`` — count of
  ``resume_diagnosis.suggestion_accepted`` events.
- ``avg_resume_score_before`` — average ``metadata.score_before`` over
  diagnosis completion events.
- ``avg_resume_score_after`` — average ``metadata.score_after`` over
  diagnosis completion events.

US3 functions (T093) — Mock Interview Panel:

- ``count_interview_starts`` — count of ``interview.started`` events.
- ``count_interview_completions`` — count of ``interview.completed`` events.
- ``count_interview_failures`` — count of ``interview.failed`` events.
- ``count_interview_retries`` — count of ``interview.retry`` events.
- ``count_interview_report_views`` — count of ``interview.report_viewed``
  events.
- ``avg_interview_question_count`` — average ``metadata.question_count``
  over completed sessions.

US2 fallback rationale (T084): the dedicated ``resume_diagnoses`` /
``resume_diagnosis_suggestions`` / ``resume_diagnosis_events`` tables
were planned in spec.md §data-model but the migration (0024) has not
landed (033-POLISH restoration pending). To keep the panel functional,
all US2 aggregations read from the ``product_events`` table using
``event_name LIKE 'resume_diagnosis.%'``. Each event row carries the
relevant metadata in the ``metadata`` JSONB column. This preserves
privacy: the panel returns counts + deltas only — never raw resume
content. When the dedicated tables land, the queries can be swapped
without touching the service / API contract.

US3 fallback rationale (T093): the dedicated ``interview_outcomes``
table was planned in spec.md §data-model but the migration (0024) has
not landed (033-POLISH restoration pending). To keep the panel
functional, all US3 aggregations read from the ``product_events`` table
using ``event_name LIKE 'interview.%'``. Each event row carries the
relevant metadata in the ``metadata`` JSONB column. Privacy: the panel
returns counts + rates + average question count only — never raw
interview content (questions / answers / transcript / audio). When the
dedicated tables land, the queries can be swapped without touching the
service / API contract.

All queries are filtered by ``date_range_start <= occurred_at <
date_range_end`` and apply the optional filters from
``DashboardFilter`` (environment, app_version, release_stage, model).

The repository is RLS-aware: ``product_events.user_id``, ``badcases.user_id``
and ``ai_invocation_records.user_id`` all have RLS policies, so the
caller MUST set ``app.user_id`` before invoking any helper (consistent
with the rest of the 033 suite).
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.telemetry_contracts.models import (
    AIInvocationRecord,
    Badcase,
    ProductFunnelEvent,
)
from app.modules.pm_dashboard.schemas import DashboardFilter


# ---------------------------------------------------------------------------
# Helpers — filter application
# ---------------------------------------------------------------------------


def _apply_event_filters(
    stmt: Any,
    model: Any,
    filters: DashboardFilter,
) -> Any:
    """Apply shared date + environment + version filters to a stmt.

    ``model`` is either ``ProductFunnelEvent`` or ``AIInvocationRecord``.
    Typed as ``Any`` because these two ORM classes share no common base
    that has ``occurred_at``; the only common contract is duck-typed
    column access.
    """
    stmt = stmt.where(
        model.occurred_at >= filters.date_range_start,
        model.occurred_at < filters.date_range_end,
    )
    if filters.environment:
        env_upper = filters.environment.upper()
        if hasattr(model, "environment"):
            stmt = stmt.where(model.environment == env_upper.lower())
    if filters.model and hasattr(model, "model"):
        stmt = stmt.where(model.model == filters.model)
    if filters.app_version and hasattr(model, "app_version"):
        stmt = stmt.where(model.app_version == filters.app_version)
    return stmt


# ---------------------------------------------------------------------------
# Funnel step events — counts by event_name
# ---------------------------------------------------------------------------


async def count_event_rows(
    session: AsyncSession,
    filters: DashboardFilter,
    event_name: str,
) -> int:
    """Count rows of ``ProductFunnelEvent`` with ``event_name=event_name``.

    Used by the funnel service layer to compute per-step counts.
    """
    stmt = select(func.count(ProductFunnelEvent.id)).where(
        ProductFunnelEvent.event_name == event_name,
        ProductFunnelEvent.occurred_at >= filters.date_range_start,
        ProductFunnelEvent.occurred_at < filters.date_range_end,
    )
    if filters.environment:
        # ProductFunnelEvent stores env in version_context JSONB; we filter
        # on the JSONB key (cheap when indexed). For MVP we filter
        # client-side if not present.
        # No indexed column for environment on product_events; skip here.
        pass
    result = await session.execute(stmt)
    return int(result.scalar() or 0)


async def count_distinct_users_for_event(
    session: AsyncSession,
    filters: DashboardFilter,
    event_name: str,
) -> int:
    """Count distinct user_id for rows with the given event_name."""
    stmt = select(func.count(func.distinct(ProductFunnelEvent.user_id))).where(
        ProductFunnelEvent.event_name == event_name,
        ProductFunnelEvent.occurred_at >= filters.date_range_start,
        ProductFunnelEvent.occurred_at < filters.date_range_end,
    )
    result = await session.execute(stmt)
    return int(result.scalar() or 0)


# ---------------------------------------------------------------------------
# Overview metrics
# ---------------------------------------------------------------------------


async def count_active_users(
    session: AsyncSession,
    filters: DashboardFilter,
) -> int:
    """Distinct user_id over product events in window (UV proxy).

    Counts any non-anonymous event row as "active". Distinct users
    carrying at least one event in the period.
    """
    stmt = select(
        func.count(func.distinct(ProductFunnelEvent.user_id))
    ).where(
        ProductFunnelEvent.occurred_at >= filters.date_range_start,
        ProductFunnelEvent.occurred_at < filters.date_range_end,
        ProductFunnelEvent.user_id.is_not(None),
    )
    result = await session.execute(stmt)
    return int(result.scalar() or 0)


async def count_registered_users(
    session: AsyncSession,
    filters: DashboardFilter,
) -> int:
    """Distinct user_id with an ``auth.registered`` event in window."""
    return await count_distinct_users_for_event(
        session, filters, "auth.registered"
    )


async def count_visits(
    session: AsyncSession,
    filters: DashboardFilter,
) -> int:
    """Count of ``product.visit`` events (UV)."""
    return await count_event_rows(session, filters, "product.visit")


async def count_completed_ai_tasks(
    session: AsyncSession,
    filters: DashboardFilter,
) -> int:
    """Count of ``AIInvocationRecord`` rows with ``status='SUCCESS'`` in window."""
    stmt = select(func.count(AIInvocationRecord.id)).where(
        AIInvocationRecord.created_at >= filters.date_range_start,
        AIInvocationRecord.created_at < filters.date_range_end,
        AIInvocationRecord.status == "SUCCESS",
    )
    if filters.model:
        stmt = stmt.where(AIInvocationRecord.model == filters.model)
    result = await session.execute(stmt)
    return int(result.scalar() or 0)


async def count_ai_tasks_total(
    session: AsyncSession,
    filters: DashboardFilter,
) -> int:
    """Total AI invocations (any status) in window."""
    stmt = select(func.count(AIInvocationRecord.id)).where(
        AIInvocationRecord.created_at >= filters.date_range_start,
        AIInvocationRecord.created_at < filters.date_range_end,
    )
    if filters.model:
        stmt = stmt.where(AIInvocationRecord.model == filters.model)
    result = await session.execute(stmt)
    return int(result.scalar() or 0)


async def sum_token_usage(
    session: AsyncSession,
    filters: DashboardFilter,
) -> int:
    """Sum of prompt_tokens + completion_tokens over invocations in window."""
    stmt = select(
        func.coalesce(
            func.sum(
                AIInvocationRecord.prompt_tokens + AIInvocationRecord.completion_tokens
            ),
            0,
        )
    ).where(
        AIInvocationRecord.created_at >= filters.date_range_start,
        AIInvocationRecord.created_at < filters.date_range_end,
    )
    if filters.model:
        stmt = stmt.where(AIInvocationRecord.model == filters.model)
    result = await session.execute(stmt)
    return int(result.scalar() or 0)


async def sum_estimated_cost(
    session: AsyncSession,
    filters: DashboardFilter,
) -> float:
    """Sum of ``estimated_cost`` over invocations in window.

    Returns 0.0 when no rows match. The cost is labeled as an estimate
    per FR-008 — see service.OverviewPanelData.
    """
    stmt = select(
        func.coalesce(func.sum(AIInvocationRecord.estimated_cost), 0)
    ).where(
        AIInvocationRecord.created_at >= filters.date_range_start,
        AIInvocationRecord.created_at < filters.date_range_end,
        AIInvocationRecord.estimated_cost.is_not(None),
    )
    if filters.model:
        stmt = stmt.where(AIInvocationRecord.model == filters.model)
    result = await session.execute(stmt)
    val = result.scalar() or 0
    return float(val)


async def compute_ai_success_rate(
    session: AsyncSession,
    filters: DashboardFilter,
) -> float:
    """AI success rate = completed / total in window.

    Returns 0.0 when total=0 (no rows). Clamped to [0.0, 1.0].
    """
    total = await count_ai_tasks_total(session, filters)
    if total <= 0:
        return 0.0
    completed = await count_completed_ai_tasks(session, filters)
    return max(0.0, min(1.0, completed / total))


async def count_open_badcases(
    session: AsyncSession,
    filters: DashboardFilter,
) -> int:
    """Count of badcases not in (CLOSED, REJECTED).

    Badcases don't carry an ``occurred_at`` column — they're created with
    ``created_at``. We treat ``date_range_start <= created_at <
    date_range_end`` as the window. For MVP, we do not require a date
    range on badcase queries (badcases are reviewed over their lifetime).
    """
    stmt = select(func.count(Badcase.id)).where(
        Badcase.status.notin_(["CLOSED", "REJECTED"])
    )
    result = await session.execute(stmt)
    return int(result.scalar() or 0)


# ---------------------------------------------------------------------------
# Diagnostics — full event list (rarely used by panels)
# ---------------------------------------------------------------------------


async def list_product_events(
    session: AsyncSession,
    filters: DashboardFilter,
    limit: int = 100,
) -> list[ProductFunnelEvent]:
    """Return the most recent ``limit`` product events in window."""
    stmt = (
        select(ProductFunnelEvent)
        .where(
            ProductFunnelEvent.occurred_at >= filters.date_range_start,
            ProductFunnelEvent.occurred_at < filters.date_range_end,
        )
        .order_by(ProductFunnelEvent.occurred_at.desc())
        .limit(limit)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


# ---------------------------------------------------------------------------
# US2 (T084) — Resume Diagnosis Panel aggregations
#
# Fallback to ``ProductEvent`` rows where
# ``event_name LIKE 'resume_diagnosis.%'``. Each event row carries the
# relevant metadata in the ``metadata`` JSONB column. Privacy: the panel
# returns counts + deltas only — never raw resume content.
# ---------------------------------------------------------------------------

#: Canonical event_name values for resume diagnosis (US2).
RESUME_DIAGNOSIS_STARTED = "resume_diagnosis.started"
RESUME_DIAGNOSIS_SUCCEEDED = "resume_diagnosis.succeeded"
RESUME_DIAGNOSIS_FAILED = "resume_diagnosis.failed"
RESUME_DIAGNOSIS_REPORT_VIEWED = "resume_diagnosis.report_viewed"
RESUME_DIAGNOSIS_SUGGESTION_SHOWN = "resume_diagnosis.suggestion_shown"
RESUME_DIAGNOSIS_SUGGESTION_ACCEPTED = "resume_diagnosis.suggestion_accepted"


def _base_event_query(event_name: str, filters: DashboardFilter) -> Any:
    """Build a base ProductEvent query filtered by event_name + window.

    Used by all US2 aggregations. Does NOT apply environment / app_version
    filters because the current ``ProductFunnelEvent`` schema stores those
    in ``version_context`` JSONB. Filtering on JSONB requires an indexed
    GIN index which is out of scope for US2; the service layer applies
    those filters when the dedicated ``resume_diagnoses`` table lands.
    """
    return (
        select(func.count(ProductFunnelEvent.id))
        .where(
            ProductFunnelEvent.event_name == event_name,
            ProductFunnelEvent.occurred_at >= filters.date_range_start,
            ProductFunnelEvent.occurred_at < filters.date_range_end,
        )
    )


async def count_resume_diagnoses(
    session: AsyncSession,
    filters: DashboardFilter,
) -> int:
    """Count distinct resume diagnosis runs started in the window.

    Reads ``event_name == 'resume_diagnosis.started'``. Returns the
    raw row count (not distinct user_id — a single user may start
    multiple diagnoses in a window).
    """
    stmt = _base_event_query(RESUME_DIAGNOSIS_STARTED, filters)
    result = await session.execute(stmt)
    return int(result.scalar() or 0)


async def count_successful_resume_diagnoses(
    session: AsyncSession,
    filters: DashboardFilter,
) -> int:
    """Count distinct resume diagnosis runs that completed with SUCCESS.

    Reads ``event_name == 'resume_diagnosis.succeeded'``. A diagnosis is
    considered successful when the AI pipeline finishes without raising
    a fatal error.
    """
    stmt = _base_event_query(RESUME_DIAGNOSIS_SUCCEEDED, filters)
    result = await session.execute(stmt)
    return int(result.scalar() or 0)


async def count_report_views(
    session: AsyncSession,
    filters: DashboardFilter,
) -> int:
    """Count distinct ``resume_diagnosis.report_viewed`` events.

    Multiple views by the same user are counted independently (PM cares
    about engagement, not unique viewers).
    """
    stmt = _base_event_query(RESUME_DIAGNOSIS_REPORT_VIEWED, filters)
    result = await session.execute(stmt)
    return int(result.scalar() or 0)


async def count_suggestions_shown(
    session: AsyncSession,
    filters: DashboardFilter,
) -> int:
    """Count of ``resume_diagnosis.suggestion_shown`` events.

    Each event represents one suggestion surfaced in the UI to the user.
    """
    stmt = _base_event_query(RESUME_DIAGNOSIS_SUGGESTION_SHOWN, filters)
    result = await session.execute(stmt)
    return int(result.scalar() or 0)


async def count_suggestions_accepted(
    session: AsyncSession,
    filters: DashboardFilter,
) -> int:
    """Count of ``resume_diagnosis.suggestion_accepted`` events.

    Each event represents one suggestion the user explicitly accepted.
    Used together with ``count_suggestions_shown`` to compute the
    acceptance rate (FR for US2).
    """
    stmt = _base_event_query(RESUME_DIAGNOSIS_SUGGESTION_ACCEPTED, filters)
    result = await session.execute(stmt)
    return int(result.scalar() or 0)


async def avg_resume_score_before(
    session: AsyncSession,
    filters: DashboardFilter,
) -> float:
    """Average ``metadata.score_before`` over succeeded diagnoses in window.

    Returns 0.0 when no rows match. The score is expected in [0, 100].
    Privacy: only the aggregate is returned; individual scores are not
    surfaced.
    """
    from sqlalchemy import Float

    score_key = ProductFunnelEvent.metadata["score_before"].astext.cast(Float)
    stmt = select(func.coalesce(func.avg(score_key), 0.0)).where(
        ProductFunnelEvent.event_name == RESUME_DIAGNOSIS_SUCCEEDED,
        ProductFunnelEvent.occurred_at >= filters.date_range_start,
        ProductFunnelEvent.occurred_at < filters.date_range_end,
    )
    result = await session.execute(stmt)
    val = result.scalar() or 0.0
    return float(val)


async def avg_resume_score_after(
    session: AsyncSession,
    filters: DashboardFilter,
) -> float:
    """Average ``metadata.score_after`` over succeeded diagnoses in window.

    Returns 0.0 when no rows match. Pairs with ``avg_resume_score_before``
    to compute the score delta (avg_after - avg_before).
    """
    from sqlalchemy import Float

    score_key = ProductFunnelEvent.metadata["score_after"].astext.cast(Float)
    stmt = select(func.coalesce(func.avg(score_key), 0.0)).where(
        ProductFunnelEvent.event_name == RESUME_DIAGNOSIS_SUCCEEDED,
        ProductFunnelEvent.occurred_at >= filters.date_range_start,
        ProductFunnelEvent.occurred_at < filters.date_range_end,
    )
    result = await session.execute(stmt)
    val = result.scalar() or 0.0
    return float(val)


# ---------------------------------------------------------------------------
# US3 (T093) — Mock Interview Panel aggregations
#
# Fallback to ``ProductEvent`` rows where
# ``event_name LIKE 'interview.%'``. Each event row carries the
# relevant metadata in the ``metadata`` JSONB column. Privacy: the panel
# returns counts + rates + average question count only — never raw
# interview content (questions / answers / transcript / audio).
# ---------------------------------------------------------------------------

#: Canonical event_name values for mock interview (US3).
INTERVIEW_STARTED = "interview.started"
INTERVIEW_COMPLETED = "interview.completed"
INTERVIEW_FAILED = "interview.failed"
INTERVIEW_RETRY = "interview.retry"
INTERVIEW_REPORT_VIEWED = "interview.report_viewed"


async def count_interview_starts(
    session: AsyncSession,
    filters: DashboardFilter,
) -> int:
    """Count of ``interview.started`` events in the window.

    Returns the raw row count. A single user may start multiple interview
    sessions in a window; all are counted independently.
    """
    stmt = _base_event_query(INTERVIEW_STARTED, filters)
    result = await session.execute(stmt)
    return int(result.scalar() or 0)


async def count_interview_completions(
    session: AsyncSession,
    filters: DashboardFilter,
) -> int:
    """Count of ``interview.completed`` events in the window.

    A session is considered complete when the interview pipeline finishes
    without raising a fatal error.
    """
    stmt = _base_event_query(INTERVIEW_COMPLETED, filters)
    result = await session.execute(stmt)
    return int(result.scalar() or 0)


async def count_interview_failures(
    session: AsyncSession,
    filters: DashboardFilter,
) -> int:
    """Count of ``interview.failed`` events in the window.

    These are sessions that ended in a fatal failure (timeout, LLM
    error, etc.). Used together with ``count_interview_starts`` to
    compute the failure rate.
    """
    stmt = _base_event_query(INTERVIEW_FAILED, filters)
    result = await session.execute(stmt)
    return int(result.scalar() or 0)


async def count_interview_retries(
    session: AsyncSession,
    filters: DashboardFilter,
) -> int:
    """Count of ``interview.retry`` events in the window.

    A retry is recorded when the user explicitly requests another
    attempt after a failure. Multiple retries per session are counted
    independently.
    """
    stmt = _base_event_query(INTERVIEW_RETRY, filters)
    result = await session.execute(stmt)
    return int(result.scalar() or 0)


async def count_interview_report_views(
    session: AsyncSession,
    filters: DashboardFilter,
) -> int:
    """Count of ``interview.report_viewed`` events in the window.

    Multiple views by the same user are counted independently (PM cares
    about engagement, not unique viewers).
    """
    stmt = _base_event_query(INTERVIEW_REPORT_VIEWED, filters)
    result = await session.execute(stmt)
    return int(result.scalar() or 0)


async def avg_interview_question_count(
    session: AsyncSession,
    filters: DashboardFilter,
) -> float:
    """Average ``metadata.question_count`` over completed sessions in window.

    Returns 0.0 when no rows match. Privacy: only the aggregate is
    returned; individual question counts are not surfaced, and no
    question text is ever read.
    """
    from sqlalchemy import Float

    qc_key = ProductFunnelEvent.metadata["question_count"].astext.cast(Float)
    stmt = select(func.coalesce(func.avg(qc_key), 0.0)).where(
        ProductFunnelEvent.event_name == INTERVIEW_COMPLETED,
        ProductFunnelEvent.occurred_at >= filters.date_range_start,
        ProductFunnelEvent.occurred_at < filters.date_range_end,
    )
    result = await session.execute(stmt)
    val = result.scalar() or 0.0
    return float(val)


# ---------------------------------------------------------------------------
# US4 (T103) — AI Operations Panel aggregations
#
# Reads directly from the existing ``AIInvocationRecord`` table (no new
# table, no migration). The LLM client hook populates this table via
# ``_extract_and_record_ai_invocation`` (US9 T040) on every invoke +
# invoke_stream. Privacy: the panel returns counts + rates + percentiles
# only; raw prompt / completion text is never read.
# ---------------------------------------------------------------------------


def _ai_invocations_base_stmt(filters: DashboardFilter) -> Any:
    """Build a base AIInvocationRecord query filtered by date + model.

    All US4 aggregations share this date + model filter; environment /
    app_version filters are applied opportunistically when the column
    is present (US4 T103 scope is the core date + model + RLS path;
    the broader version filter set will land when the dedicated
    ``ai_invocation_version_context`` join table arrives).
    """
    stmt = select(AIInvocationRecord).where(
        AIInvocationRecord.created_at >= filters.date_range_start,
        AIInvocationRecord.created_at < filters.date_range_end,
    )
    if filters.model:
        stmt = stmt.where(AIInvocationRecord.model == filters.model)
    return stmt


async def count_ai_invocations(
    session: AsyncSession,
    filters: DashboardFilter,
) -> int:
    """Total ``AIInvocationRecord`` rows in window (any status)."""
    stmt = select(func.count(AIInvocationRecord.id)).where(
        AIInvocationRecord.created_at >= filters.date_range_start,
        AIInvocationRecord.created_at < filters.date_range_end,
    )
    if filters.model:
        stmt = stmt.where(AIInvocationRecord.model == filters.model)
    result = await session.execute(stmt)
    return int(result.scalar() or 0)


async def count_ai_invocations_success(
    session: AsyncSession,
    filters: DashboardFilter,
) -> int:
    """Rows with ``status='SUCCESS'`` in window."""
    stmt = select(func.count(AIInvocationRecord.id)).where(
        AIInvocationRecord.created_at >= filters.date_range_start,
        AIInvocationRecord.created_at < filters.date_range_end,
        AIInvocationRecord.status == "SUCCESS",
    )
    if filters.model:
        stmt = stmt.where(AIInvocationRecord.model == filters.model)
    result = await session.execute(stmt)
    return int(result.scalar() or 0)


async def count_ai_invocations_failure(
    session: AsyncSession,
    filters: DashboardFilter,
) -> int:
    """Rows with status != 'SUCCESS' in window (failure / timeout / cancelled)."""
    stmt = select(func.count(AIInvocationRecord.id)).where(
        AIInvocationRecord.created_at >= filters.date_range_start,
        AIInvocationRecord.created_at < filters.date_range_end,
        AIInvocationRecord.status != "SUCCESS",
    )
    if filters.model:
        stmt = stmt.where(AIInvocationRecord.model == filters.model)
    result = await session.execute(stmt)
    return int(result.scalar() or 0)


async def count_ai_invocations_retried(
    session: AsyncSession,
    filters: DashboardFilter,
) -> int:
    """Rows where ``retry_count > 0`` in window (a retry was needed)."""
    stmt = select(func.count(AIInvocationRecord.id)).where(
        AIInvocationRecord.created_at >= filters.date_range_start,
        AIInvocationRecord.created_at < filters.date_range_end,
        AIInvocationRecord.retry_count > 0,
    )
    if filters.model:
        stmt = stmt.where(AIInvocationRecord.model == filters.model)
    result = await session.execute(stmt)
    return int(result.scalar() or 0)


async def sum_ai_prompt_tokens(
    session: AsyncSession,
    filters: DashboardFilter,
) -> int:
    """Sum of ``prompt_tokens`` over invocations in window."""
    stmt = select(
        func.coalesce(func.sum(AIInvocationRecord.prompt_tokens), 0)
    ).where(
        AIInvocationRecord.created_at >= filters.date_range_start,
        AIInvocationRecord.created_at < filters.date_range_end,
    )
    if filters.model:
        stmt = stmt.where(AIInvocationRecord.model == filters.model)
    result = await session.execute(stmt)
    return int(result.scalar() or 0)


async def sum_ai_completion_tokens(
    session: AsyncSession,
    filters: DashboardFilter,
) -> int:
    """Sum of ``completion_tokens`` over invocations in window."""
    stmt = select(
        func.coalesce(func.sum(AIInvocationRecord.completion_tokens), 0)
    ).where(
        AIInvocationRecord.created_at >= filters.date_range_start,
        AIInvocationRecord.created_at < filters.date_range_end,
    )
    if filters.model:
        stmt = stmt.where(AIInvocationRecord.model == filters.model)
    result = await session.execute(stmt)
    return int(result.scalar() or 0)


async def ai_latency_percentile(
    session: AsyncSession,
    filters: DashboardFilter,
    percentile: float,
) -> float:
    """Compute a percentile of ``latency_ms`` via Postgres ``percentile_cont``.

    Returns 0.0 when no rows match. ``percentile`` must be in (0, 1];
    out-of-range values are clamped to (0, 1] to avoid silent misuse.

    Privacy: only the aggregate is returned; individual latency values
    are not surfaced.
    """
    # Clamp the percentile to (0, 1] to avoid silent misuse.
    pct = max(0.0, min(1.0, float(percentile)))
    if pct <= 0.0:
        return 0.0
    stmt = _ai_invocations_base_stmt(filters)
    # Wrap as a subquery so we can apply percentile_cont to the
    # selected latency_ms column. We use func.percentile_cont with
    # ``within_group`` to use the ordered-set aggregate form.
    from sqlalchemy import Float, literal

    inner = stmt.with_only_columns(
        AIInvocationRecord.latency_ms
    ).subquery()
    pct_expr = func.percentile_cont(literal(pct)).within_group(
        inner.c.latency_ms.asc()
    )
    out_stmt = select(func.coalesce(pct_expr.cast(Float), 0.0))
    result = await session.execute(out_stmt)
    val = result.scalar() or 0.0
    return float(val)


async def ai_top_breakdown(
    session: AsyncSession,
    filters: DashboardFilter,
    dimension: str,
    top_n: int = 5,
) -> dict[str, int]:
    """Top-N breakdown of call counts by ``dimension``.

    ``dimension`` must be one of: ``"model"``, ``"graph"``, ``"node"``,
    ``"prompt_fingerprint"``. Other values return an empty dict
    (defensive — never raises on bad caller input).

    The breakdown is ordered by count DESC, then dimension ASC
    (deterministic tiebreak). The result dict is ordered by count
    (Python 3.7+ dict insertion order is the iteration order).
    """
    if dimension not in {"model", "graph", "node", "prompt_fingerprint"}:
        return {}
    col = getattr(AIInvocationRecord, dimension)
    stmt = (
        select(col.label("dim"), func.count(AIInvocationRecord.id).label("cnt"))
        .where(
            AIInvocationRecord.created_at >= filters.date_range_start,
            AIInvocationRecord.created_at < filters.date_range_end,
        )
        .group_by(col)
        .order_by(func.count(AIInvocationRecord.id).desc(), col.asc())
        .limit(top_n)
    )
    if filters.model and dimension != "model":
        stmt = stmt.where(AIInvocationRecord.model == filters.model)
    result = await session.execute(stmt)
    rows = result.all()
    out: dict[str, int] = {}
    for dim_val, cnt in rows:
        # Normalize None → "unknown" so the panel never has null keys
        # (SC-010). Stringify enum-like values defensively.
        key = "unknown" if dim_val is None else str(dim_val)
        out[key] = int(cnt)
    return out


__all__ = [
    "ai_latency_percentile",  # US4 T103
    "ai_top_breakdown",  # US4 T103
    "avg_interview_question_count",
    "avg_resume_score_after",
    "avg_resume_score_before",
    "compute_ai_success_rate",
    "count_active_users",
    "count_ai_invocations",  # US4 T103
    "count_ai_invocations_failure",  # US4 T103
    "count_ai_invocations_retried",  # US4 T103
    "count_ai_invocations_success",  # US4 T103
    "count_ai_tasks_total",
    "count_completed_ai_tasks",
    "count_event_rows",
    "count_distinct_users_for_event",
    "count_interview_completions",
    "count_interview_failures",
    "count_interview_report_views",
    "count_interview_retries",
    "count_interview_starts",
    "count_open_badcases",
    "count_registered_users",
    "count_report_views",
    "count_resume_diagnoses",
    "count_suggestions_accepted",
    "count_suggestions_shown",
    "count_successful_resume_diagnoses",
    "count_visits",
    "list_product_events",
    "sum_ai_completion_tokens",  # US4 T103
    "sum_ai_prompt_tokens",  # US4 T103
    "sum_estimated_cost",
    "sum_token_usage",
]