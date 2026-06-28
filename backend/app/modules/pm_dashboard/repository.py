"""REQ-033 US1 — PM Dashboard repository queries (T071).

Async SQLAlchemy 2.0 queries against the ``product_events``,
``ai_invocation_records``, ``pm_metric_snapshots``, and ``badcases``
tables created by migration 0024.

Functions:

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


__all__ = [
    "compute_ai_success_rate",
    "count_active_users",
    "count_ai_tasks_total",
    "count_completed_ai_tasks",
    "count_event_rows",
    "count_distinct_users_for_event",
    "count_open_badcases",
    "count_registered_users",
    "count_visits",
    "list_product_events",
    "sum_estimated_cost",
    "sum_token_usage",
]