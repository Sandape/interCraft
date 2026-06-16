"""ARQ WorkerSettings entry point.

Run: `uv run arq app.workers.main.WorkerSettings`
"""
from __future__ import annotations

import os
from typing import ClassVar

from arq.connections import RedisSettings
from arq.cron import cron

from app.modules.versions.auto_snapshot import auto_snapshot_branch
from app.workers.tasks.monthly_quota_reset import monthly_quota_reset
from app.workers.tasks.daily_reconcile import daily_reconcile
from app.workers.tasks.ability_diagnose import ability_diagnose
from app.modules.locks.service import LockService
from app.workers.tasks.purge_expired_accounts import purge_expired_accounts
from app.workers.tasks.physical_cleanup import physical_cleanup
from app.workers.tasks.cleanup_expired_exports import cleanup_expired_exports
from app.workers.tasks.pdf_export import pdf_export
from app.workers.tasks.create_next_audit_partition import create_next_audit_partition
from app.workers.tasks.reset_monthly_quota_cron import reset_monthly_quota_cron

REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")

_auto_release = LockService()


async def auto_release_stale(ctx: dict) -> list:
    """ARQ cron: scan and release stale locks every 30s (Phase 3 T062)."""
    return await _auto_release.auto_release_stale()


class WorkerSettings:
    functions: ClassVar = [
        auto_snapshot_branch,
        monthly_quota_reset,
        auto_release_stale,
        daily_reconcile,
        ability_diagnose,
        purge_expired_accounts,
        physical_cleanup,
        cleanup_expired_exports,
        create_next_audit_partition,
        reset_monthly_quota_cron,
        pdf_export,
    ]
    redis_settings: ClassVar = RedisSettings.from_dsn(REDIS_URL)
    cron_jobs: ClassVar = [
        cron(monthly_quota_reset, name="monthly_quota_reset", month=1, day=1, hour=0, minute=0),
        cron(auto_release_stale, name="auto_release_stale", second={0, 30}),
        cron(daily_reconcile, name="daily_reconcile", hour=3, minute=0),
        cron(purge_expired_accounts, name="purge_expired_accounts", hour=2, minute=0),
        cron(physical_cleanup, name="physical_cleanup", weekday="sun", hour=3, minute=0),
        cron(cleanup_expired_exports, name="cleanup_expired_exports", minute=0),
        cron(create_next_audit_partition, name="create_next_audit_partition", month=1, day=1, hour=0, minute=0),
        cron(reset_monthly_quota_cron, name="reset_monthly_quota_cron", month=1, day=1, hour=0, minute=0),
    ]
    keep_result: ClassVar = 60
    max_tries: ClassVar = 3


__all__ = ["REDIS_URL", "WorkerSettings"]
