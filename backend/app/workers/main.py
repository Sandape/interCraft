"""ARQ WorkerSettings entry point.

Run: `uv run arq app.workers.main.WorkerSettings`
"""
from __future__ import annotations

import os
from typing import ClassVar

from arq.connections import RedisSettings

from app.modules.versions.auto_snapshot import auto_snapshot_branch
from app.workers.tasks.monthly_quota_reset import monthly_quota_reset
from app.workers.tasks.daily_reconcile import daily_reconcile
from app.workers.tasks.ability_diagnose import ability_diagnose
from app.modules.locks.service import LockService
from app.workers.tasks.purge_expired_accounts import purge_expired_accounts
from app.workers.tasks.physical_cleanup import physical_cleanup
from app.workers.tasks.cleanup_expired_exports import cleanup_expired_exports
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
    ]
    redis_settings: ClassVar = RedisSettings.from_dsn(REDIS_URL)
    cron_jobs: ClassVar = [
        {
            "name": "monthly_quota_reset",
            "cron": "0 0 1 * *",
            "coroutine": monthly_quota_reset,
        },
        {
            "name": "auto_release_stale",
            "cron": "*/30 * * * *",
            "coroutine": auto_release_stale,
        },
        {
            "name": "daily_reconcile",
            "cron": "0 3 * * *",
            "coroutine": daily_reconcile,
        },
        {
            "name": "purge_expired_accounts",
            "cron": "0 2 * * *",
            "coroutine": purge_expired_accounts,
        },
        {
            "name": "physical_cleanup",
            "cron": "0 3 * * 0",
            "coroutine": physical_cleanup,
        },
        {
            "name": "cleanup_expired_exports",
            "cron": "0 * * * *",
            "coroutine": cleanup_expired_exports,
        },
        {
            "name": "create_next_audit_partition",
            "cron": "0 0 1 * *",
            "coroutine": create_next_audit_partition,
        },
        {
            "name": "reset_monthly_quota_cron",
            "cron": "0 0 1 * *",
            "coroutine": reset_monthly_quota_cron,
        },
    ]
    keep_result: ClassVar = 60
    max_tries: ClassVar = 3


__all__ = ["REDIS_URL", "WorkerSettings"]
