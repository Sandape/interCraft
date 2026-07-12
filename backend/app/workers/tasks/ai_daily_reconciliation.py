"""REQ-061 US9 daily preliminary reconciliation worker (T119 / FR-161).

Runs Asia/Shanghai previous-day point conservation, attempt coverage, rate
coverage, and provider usage checks. Completes before next-day 12:00 CST when
scheduled appropriately by ARQ cron.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo

from app.core.db import get_session_factory
from app.core.logging import get_logger
from app.modules.ai_metering.points.configuration import shanghai_business_date
from app.modules.ai_metering.reconciliation.service import (
    DAILY_DIFF_THRESHOLD,
    ConservationSnapshot,
    ReconciliationService,
    run_daily_reconciliation,
)

log = get_logger("workers.ai_daily_reconciliation")
SHANGHAI = ZoneInfo("Asia/Shanghai")


def previous_shanghai_business_date(at: datetime | None = None):
    moment = at or datetime.now(timezone.utc)
    today = shanghai_business_date(moment)
    return today - timedelta(days=1)


async def run_ai_daily_reconciliation(ctx: dict[str, Any] | None = None) -> dict[str, Any]:
    """Cron entry: preliminary reconciliation for the previous Shanghai day."""
    _ = ctx
    now = datetime.now(timezone.utc)
    business_date = previous_shanghai_business_date(now)
    log.info(
        "ai_daily_reconciliation.start",
        business_date=business_date.isoformat(),
        ts=now.isoformat(),
    )

    # Without live ledger aggregates yet, persist a structured empty/passed run
    # so operators can observe the worker. Callers may inject facts via ctx.
    facts = (ctx or {}).get("facts") or {}
    conservation = facts.get("conservation")
    if isinstance(conservation, dict):
        conservation = ConservationSnapshot(**conservation)

    result = run_daily_reconciliation(
        business_date=business_date,
        conservation=conservation,
        attempt_ids=set(facts.get("attempt_ids") or []),
        cost_event_attempt_ids=set(facts.get("cost_event_attempt_ids") or []),
        unknown_rate_task_count=int(facts.get("unknown_rate_task_count") or 0),
        internal_cost_total=(
            Decimal(str(facts["internal_cost_total"]))
            if facts.get("internal_cost_total") is not None
            else None
        ),
        provider_usage_total=(
            Decimal(str(facts["provider_usage_total"]))
            if facts.get("provider_usage_total") is not None
            else None
        ),
        cost_events=list(facts.get("cost_events") or []),
    )

    run_id = None
    try:
        factory = get_session_factory()
        async with factory() as session:
            svc = ReconciliationService(session)
            _, run = await svc.run_and_persist_daily(
                business_date=business_date,
                conservation=conservation,
                attempt_ids=set(facts.get("attempt_ids") or []) or None,
                cost_event_attempt_ids=set(facts.get("cost_event_attempt_ids") or [])
                or None,
                unknown_rate_task_count=int(facts.get("unknown_rate_task_count") or 0),
                internal_cost_total=(
                    Decimal(str(facts["internal_cost_total"]))
                    if facts.get("internal_cost_total") is not None
                    else None
                ),
                provider_usage_total=(
                    Decimal(str(facts["provider_usage_total"]))
                    if facts.get("provider_usage_total") is not None
                    else None
                ),
                cost_events=list(facts.get("cost_events") or []) or None,
            )
            await session.commit()
            run_id = str(run.id)
    except Exception as exc:  # noqa: BLE001 — worker must still return summary
        log.warning("ai_daily_reconciliation.persist_failed", error=str(exc))
        # Fall back to pure result without persistence.
        result = run_daily_reconciliation(
            business_date=business_date,
            conservation=conservation,
            attempt_ids=set(facts.get("attempt_ids") or []),
            cost_event_attempt_ids=set(facts.get("cost_event_attempt_ids") or []),
            unknown_rate_task_count=int(facts.get("unknown_rate_task_count") or 0),
            internal_cost_total=(
                Decimal(str(facts["internal_cost_total"]))
                if facts.get("internal_cost_total") is not None
                else None
            ),
            provider_usage_total=(
                Decimal(str(facts["provider_usage_total"]))
                if facts.get("provider_usage_total") is not None
                else None
            ),
            cost_events=list(facts.get("cost_events") or []),
        )

    summary = {
        "business_date": business_date.isoformat(),
        "status": result.status,
        "issue_count": len(result.issues),
        "difference_pct": str(result.difference_pct) if result.difference_pct is not None else None,
        "threshold": str(DAILY_DIFF_THRESHOLD),
        "run_id": run_id,
        "ts": now.isoformat(),
    }
    if result.status != "passed":
        log.warning("ai_daily_reconciliation.failed", **summary)
    else:
        log.info("ai_daily_reconciliation.done", **summary)
    return summary


async def ai_daily_reconciliation(ctx: dict[str, Any]) -> dict[str, Any]:
    return await run_ai_daily_reconciliation(ctx)


__all__ = [
    "ai_daily_reconciliation",
    "previous_shanghai_business_date",
    "run_ai_daily_reconciliation",
]
