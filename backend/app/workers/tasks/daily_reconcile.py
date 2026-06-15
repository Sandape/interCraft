"""ARQ cron: daily reconcile (M22 — T007/T061).

Runs at 03:00 UTC daily. Scans yesterday's threads,
compares ai_messages ↔ langgraph.checkpoints,
writes mismatches to audit_logs.
"""
from __future__ import annotations

from datetime import date, timedelta

import structlog

from app.audit.reconcile import ReconcileService

logger = structlog.get_logger("workers.daily_reconcile")


async def daily_reconcile(ctx: dict) -> dict:
    """Daily dual-source reconciliation cron handler."""
    yesterday = date.today() - timedelta(days=1)
    svc = ReconcileService()
    result = await svc.reconcile_date(yesterday)

    logger.info(
        "reconcile.done",
        date=str(yesterday),
        total_threads=result.total_threads,
        matched=result.matched,
        orphan_messages=result.orphan_messages,
        missing_audit=result.missing_audit,
        errors=result.errors,
    )

    mismatch_rate = 0.0
    if result.total_threads > 0:
        mismatch_rate = (result.orphan_messages + result.missing_audit) / result.total_threads
    if mismatch_rate > 0.001:
        logger.critical(
            "reconcile.mismatch_alert",
            date=str(yesterday),
            mismatch_rate=mismatch_rate,
            orphan_messages=result.orphan_messages,
            missing_audit=result.missing_audit,
        )

    return {
        "date": str(yesterday),
        "total_threads": result.total_threads,
        "matched": result.matched,
        "orphan_messages": result.orphan_messages,
        "missing_audit": result.missing_audit,
        "errors": result.errors,
    }


__all__ = ["daily_reconcile"]
