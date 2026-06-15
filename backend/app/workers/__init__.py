"""ARQ worker settings + dummy task for boot verification (M03)."""
from __future__ import annotations

import os
from typing import ClassVar

import arq

from app.modules.versions.auto_snapshot import auto_snapshot_branch

# ARQ reads WorkerSettings attributes at boot.
REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")


class WorkerSettings:
    functions: ClassVar = [auto_snapshot_branch]
    redis_settings: ClassVar = arq.connections.RedisSettings.from_dsn(REDIS_URL)
    on_startup: ClassVar = None
    on_shutdown: ClassVar = None
    cron_jobs: ClassVar = []  # Phase 1: empty. Phase 2: register 30-min auto-snapshot.
    keep_result: ClassVar = 60
    max_tries: ClassVar = 3
