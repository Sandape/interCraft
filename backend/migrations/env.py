"""Alembic env — async engine + autogenerate off (Phase 1)."""

from __future__ import annotations

import asyncio
import os
import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

# Ensure `app.*` imports resolve when alembic is invoked from `backend/`.
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.core.config import get_settings  # noqa: E402
from app.core.db import Base  # noqa: E402
from app.modules.ability_profile.models import ExportLog, ProfileShareLink  # noqa: E402,F401
from app.modules.account.models import ExportTask  # noqa: E402,F401
from app.modules.account.notification import Notification  # noqa: E402,F401
from app.modules.admin_console.models import AdminAuditLog, TaskTag, Trace  # noqa: E402,F401
from app.modules.ai_metering import models as ai_metering_models  # noqa: E402,F401
from app.modules.ai_metering.usage_cost import models as ai_usage_cost_models  # noqa: E402,F401
from app.modules.ai_runtime import models as ai_runtime_models  # noqa: E402,F401
from app.modules.audit.models import AuditLog  # noqa: E402,F401

# Import model modules so their tables register on Base.metadata.
from app.modules.auth.models import AuthSession, User, UserCredential  # noqa: E402,F401
from app.modules.avatars.models import UserAvatar  # noqa: E402,F401
from app.modules.content.models import HelpFAQ, Resource, SubscriptionPlan  # noqa: E402,F401
from app.modules.resumes.models import ResumeBlock, ResumeBranch  # noqa: E402,F401
from app.modules.telemetry_contracts import models as telemetry_contract_models  # noqa: E402,F401
from app.modules.versions.models import ResumeVersion  # noqa: E402,F401

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _get_url() -> str:
    """Use env var DATABASE_URL when set, else fall back to alembic.ini."""
    env = os.environ.get("DATABASE_URL")
    if env:
        return env
    return get_settings().database_url


def run_migrations_offline() -> None:
    context.configure(
        url=_get_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        render_as_batch=False,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    cfg = config.get_section(config.config_ini_section) or {}
    cfg["sqlalchemy.url"] = _get_url()
    connectable = async_engine_from_config(
        cfg,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
