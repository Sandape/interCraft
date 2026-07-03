"""036 cleanup resume data (dev only).

Revision ID: 0026_036_cleanup_resume_data
Revises: 0025_035_admin_observability
Create Date: 2026-06-30

REQ-036 US3 / FR-009~FR-012 — empty the v1/v2 resume tables in dev so that
Phase A.2 (Playwright) starts from a clean baseline.

Tables affected:
  * resume_branches               (v1; TRUNCATE)
  * resumes_v2                    (v2; TRUNCATE)
  * resume_statistics_v2          (CASCADE; explicit TRUNCATE for row counts)
  * resume_analysis_v2            (CASCADE; explicit TRUNCATE for row counts)
  * outbox (resume / resume_v2)   (DELETE orphan rows only)

Idempotency: TRUNCATE on an empty table is a no-op success; DELETE on a
non-existent aggregate_id is a no-op. Running this migration twice yields
the same end state and the same successful return. Re-run safety relies
on:
  1. ``app.environment`` GUC == dev/development/test, OR
  2. ``APP_ENV`` env var == dev/development/test, OR
  3. current_database() starting with ``intercraft_dev`` / ``intercraft_test``
The migration aborts with ``RuntimeError`` on any other environment.

Downgrade: not supported — restoration must use the
``docs/evidence/036-data-cleanup-*/db-backup.sql`` artifact captured by
``backend/app/scripts/cleanup_resume_data.py`` before this migration ran.
"""
from __future__ import annotations

import os

import sqlalchemy as sa
from alembic import op

revision = "0026_036_cleanup_resume_data"
down_revision = "0025_035_admin_observability"
branch_labels = None
depends_on = None

OUTBOX_AGGREGATE_TYPES = ("resume", "resume_v2")
DEV_ENVS = frozenset({"dev", "development", "test", "testing"})


def _resolve_environment(bind: sa.engine.Connection | None) -> str:
    """Mirror the script's detection order: APP_ENV > GUC > db_name.

    In ``alembic upgrade --sql`` offline mode, ``bind`` is a
    :class:`sqlalchemy.engine.mock.MockConnection` whose ``execute()``
    returns self (or another MockConnection) and cannot produce scalar
    results. We detect that path via ``isinstance`` and short-circuit
    so offline SQL generation never crashes; the produced SQL is
    inspected only, never executed.
    """
    from sqlalchemy.engine.mock import MockConnection

    env = os.environ.get("APP_ENV")
    if env:
        return env.strip().lower()
    if bind is None or isinstance(bind, MockConnection):
        return ""
    guc = bind.execute(sa.text("SELECT current_setting('app.environment', true)")).scalar()
    if guc:
        return str(guc).strip().lower()
    db = bind.execute(sa.text("SELECT current_database()")).scalar()
    db_name = str(db or "").lower()
    if db_name.startswith("intercraft_test") or "_test" in db_name:
        return "test"
    if db_name.startswith("intercraft_dev") or db_name == "intercraft":
        return "dev"
    return ""


def _has_table(bind: sa.engine.Connection, name: str) -> bool:
    r = bind.execute(
        sa.text("SELECT 1 FROM pg_tables WHERE tablename = :n LIMIT 1"),
        {"n": name},
    ).scalar()
    return r is not None


def upgrade() -> None:
    bind = op.get_bind()
    env = _resolve_environment(bind)
    # Offline SQL generation mode (no live DB) yields env="". Skip
    # rather than raising — emitted SQL is only inspected.
    if env == "":
        return
    if env not in DEV_ENVS:
        raise RuntimeError(
            f"0026_036_cleanup_resume_data refuses to run in env={env!r}. "
            "Use backend/app/scripts/cleanup_resume_data.py for dev cleanup; "
            "for prod roll-out, run as a planned migration with DBA review."
        )

    # 1) Outbox orphan cleanup (skip silently if table is absent)
    if _has_table(bind, "outbox"):
        op.execute(
            sa.text(
                "DELETE FROM outbox "
                "WHERE aggregate_type = ANY(:agg) "
                "AND aggregate_id NOT IN (SELECT id FROM resumes_v2) "
                "AND aggregate_id NOT IN (SELECT id FROM resume_branches)"
            ).bindparams(agg=list(OUTBOX_AGGREGATE_TYPES))
        )

    # 2) resume_branches (v1) — TRUNCATE CASCADE
    op.execute("TRUNCATE TABLE resume_branches RESTART IDENTITY CASCADE")

    # 3) resumes_v2 — TRUNCATE CASCADE (auto-clears resume_statistics_v2 /
    #    resume_analysis_v2 via ON DELETE CASCADE; explicit below for
    #    deterministic row counts in the migration log)
    op.execute("TRUNCATE TABLE resumes_v2 RESTART IDENTITY CASCADE")

    # 4) Child tables — explicit TRUNCATE so future schema changes that
    #    drop the CASCADE link don't silently orphan rows.
    if _has_table(bind, "resume_statistics_v2"):
        op.execute("TRUNCATE TABLE resume_statistics_v2 RESTART IDENTITY CASCADE")
    if _has_table(bind, "resume_analysis_v2"):
        op.execute("TRUNCATE TABLE resume_analysis_v2 RESTART IDENTITY CASCADE")


def downgrade() -> None:
    raise NotImplementedError(
        "0026_036_cleanup_resume_data is irreversible. "
        "Restore from docs/evidence/036-data-cleanup-*/db-backup.sql "
        "(produced by backend/app/scripts/cleanup_resume_data.py --backup --execute) "
        "if rollback is required."
    )
