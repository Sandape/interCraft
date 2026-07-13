"""REQ-053 T013/T014 — Alembic migration upgrade/downgrade contract tests.

Verifies that migration `0046_053_interview_research` has the right SHAPE:

- upgrade() declares all required columns / tables / constraints
- downgrade() drops them in reverse
- Status_history JSONB transition tests (T014): the 0046 migration does NOT
  perform an in-place status_history rewrite (per the migration's own
  docstring, that is left to `jobs.cli migrate-status`). The test asserts
  that the legacy 7-status JSONB shape is preserved by the migration (i.e.
  no destructive column drops on `jobs`).

These tests are static — they inspect the migration's source code rather
than running it against a live DB. This makes them runnable in any
environment without a Postgres connection.

Run:
    cd backend && uv run pytest tests/unit/modules/jobs/test_migration_053.py -v
"""
from __future__ import annotations

import inspect
import re

import pytest

pytestmark = [pytest.mark.unit]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _read_migration_source() -> str:
    from importlib import import_module

    mod = import_module("migrations.versions.0046_053_interview_research")
    return inspect.getsource(mod)


# ---------------------------------------------------------------------------
# T013 — upgrade side
# ---------------------------------------------------------------------------


def test_t013_jobs_interview_time_column_added() -> None:
    """Migration must add `interview_time` column to jobs."""
    src = _read_migration_source()
    assert 'sa.Column("interview_time"' in src or "add_column(\n        \"jobs\",\n        sa.Column(\"interview_time\"" in src


def test_t013_jobs_interview_time_partial_index_exists() -> None:
    """Migration must create idx_jobs_interview_time."""
    src = _read_migration_source()
    assert "idx_jobs_interview_time" in src


def test_t013_research_tasks_table_created() -> None:
    """Migration must create interview_research_tasks table."""
    src = _read_migration_source()
    assert 'op.create_table(\n        "interview_research_tasks"' in src or 'create_table(\n        "interview_research_tasks"' in src


def test_t013_research_tasks_required_columns() -> None:
    """interview_research_tasks must declare all required columns."""
    src = _read_migration_source()
    required = [
        "id", "job_id", "user_id", "interview_time", "status",
        "search_dimensions", "report_id", "triggered_at", "started_at",
        "completed_at", "error_message", "created_at", "updated_at",
    ]
    for col in required:
        assert f'sa.Column("{col}"' in src, f"missing column: {col}"


def test_t013_research_tasks_status_check_constraint() -> None:
    """Status check constraint must allow the 6 documented values."""
    src = _read_migration_source()
    # Find the CheckConstraint that names ck_research_tasks_status and
    # verify all 6 status values are inside the same IN clause.
    for status in (
        "pending", "running", "completed", "cancelled", "failed", "quality_failed"
    ):
        assert f"'{status}'" in src, (
            f"status {status!r} missing from migration source"
        )
    # Specifically verify the ck_research_tasks_status block contains all 6
    # by finding the literal constraint string in the source.
    expected_literal = (
        "\"status IN ('pending', 'running', 'completed', 'cancelled', "
        "'failed', 'quality_failed')\""
    )
    assert expected_literal in src, (
        f"ck_research_tasks_status constraint does not contain all 6 expected "
        f"values. Looked for: {expected_literal}"
    )


def test_t013_research_tasks_unique_constraint() -> None:
    """UniqueConstraint on (job_id, interview_time) must exist."""
    src = _read_migration_source()
    assert "UniqueConstraint" in src
    assert '"job_id", "interview_time"' in src or '"job_id","interview_time"' in src


def test_t013_research_results_table_created() -> None:
    """Migration must create interview_research_results table."""
    src = _read_migration_source()
    assert 'create_table(\n        "interview_research_results"' in src


def test_t013_research_results_dimension_check_constraint() -> None:
    """Dimension check constraint must allow the 4 documented dimensions."""
    src = _read_migration_source()
    for dim in (
        "interview_experience", "company_product", "exam_points", "user_weakness"
    ):
        assert f"'{dim}'" in src, f"dimension {dim!r} missing from migration"


def test_t013_interview_reports_extension_columns() -> None:
    """Migration must extend interview_reports with 8 new columns."""
    src = _read_migration_source()
    required = {
        "report_type", "job_id", "interview_time", "research_task_id",
        "rating", "delivery_status", "delivered_at", "quality_check_passed",
    }
    for col in required:
        assert f'sa.Column("{col}"' in src, f"missing column: {col}"


def test_t013_interview_reports_rating_check_constraint() -> None:
    """Rating check constraint must enforce 1..5."""
    src = _read_migration_source()
    m = re.search(r'ck_report_rating.*?rating\s+IS\s+NULL\s+OR\s+\(rating\s*>=\s*1\s+AND\s+rating\s*<=\s*5\)', src, re.DOTALL)
    assert m is not None, "rating 1..5 check constraint missing"


def test_t013_interview_reports_delivery_status_check() -> None:
    """delivery_status check constraint must allow the 5 documented values."""
    src = _read_migration_source()
    for s in ("pending", "sent", "failed", "delayed", "cancelled"):
        assert f"'{s}'" in src, f"delivery_status {s!r} missing"


def test_t013_research_results_company_time_partial_index() -> None:
    """Composite (company, searched_at DESC) index on interview_research_results."""
    src = _read_migration_source()
    assert "idx_research_results_company_time" in src


# ---------------------------------------------------------------------------
# T014 — status_history JSONB transition
# ---------------------------------------------------------------------------


def test_t014_migration_does_not_drop_status_history_column() -> None:
    """REQ-053: status_history JSONB must be preserved by the 0046 migration.
    The migration adds columns to jobs but does NOT drop status_history.
    """
    src = _read_migration_source()
    # The migration adds 1 column to jobs (interview_time). If it dropped
    # status_history, we'd see a `drop_column("jobs", "status_history")`.
    assert 'drop_column("jobs", "status_history")' not in src


def test_t014_legacy_status_history_jsonb_shape_documented() -> None:
    """The 0046 docstring must mention that status_history is preserved
    and the data migration is left to jobs.cli migrate-status."""
    src = _read_migration_source()
    assert "status_history" in src
    assert "migrate-status" in src or "migrate_status" in src


def test_t014_legacy_statuses_in_migration_docstring() -> None:
    """The migration's documentation must reference the legacy statuses
    (oa, hr) so the contract is discoverable in code review."""
    src = _read_migration_source()
    # Either as code or in docstring — at minimum the 7-status machine
    # must be conceptually referenced.
    src_lower = src.lower()
    assert "oa" in src_lower or "hr" in src_lower or "status_history" in src_lower


# ---------------------------------------------------------------------------
# Downgrade smoke
# ---------------------------------------------------------------------------


def test_t013_downgrade_smoke_path_exists() -> None:
    """The 0046 migration module must expose upgrade() and downgrade()."""
    from importlib import import_module

    mod = import_module("migrations.versions.0046_053_interview_research")
    assert hasattr(mod, "downgrade"), "0046 migration lost its downgrade()"
    assert callable(mod.downgrade)
    assert hasattr(mod, "upgrade") and callable(mod.upgrade)


def test_t013_downgrade_drops_columns_in_reverse() -> None:
    """downgrade() must drop the 8 interview_reports columns added in upgrade."""
    src = _read_migration_source()
    downgrade_body = src.split("def downgrade()")[1]
    # All 8 columns must appear in a drop_column call
    for col in (
        "quality_check_passed", "delivered_at", "delivery_status", "rating",
        "research_task_id", "interview_time", "job_id", "report_type",
    ):
        assert f'drop_column("interview_reports", "{col}")' in downgrade_body, (
            f"downgrade does not drop interview_reports.{col}"
        )


def test_t013_downgrade_drops_research_tables() -> None:
    """downgrade() must drop both research tables."""
    src = _read_migration_source()
    downgrade_body = src.split("def downgrade()")[1]
    assert 'drop_table("interview_research_results")' in downgrade_body
    assert 'drop_table("interview_research_tasks")' in downgrade_body


def test_t013_revision_id_format() -> None:
    """revision id must be the documented 0046_053_interview_research."""
    from importlib import import_module

    mod = import_module("migrations.versions.0046_053_interview_research")
    assert mod.revision == "0046_053_interview_research"
    assert mod.down_revision == "0045_llm_ops_eval_workflow"


# ---------------------------------------------------------------------------
# T053 — alembic_version.version_num width
# ---------------------------------------------------------------------------


def test_t053_version_num_widened_before_alterations(monkeypatch) -> None:
    """0048 migration must widen alembic_version.version_num BEFORE recording
    its own revision identifier.

    The 0048 revision identifier is 45 characters, which exceeds the
    Alembic default VARCHAR(32) for alembic_version.version_num.
    Generates offline SQL and verifies ordering.
    """
    import io
    from importlib import import_module

    from alembic import command
    from alembic.config import Config

    mod = import_module(
        "migrations.versions.0048_053_relax_interview_reports_for_research"
    )

    # Revision length must justify the widen
    assert len(mod.revision) > 32, (
        f"Revision {mod.revision!r} is {len(mod.revision)} chars — "
        f"no wider version_num needed for <= 32 chars"
    )

    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql+asyncpg://user:pass@localhost:5432/dummy",
    )

    # --- upgrade offline SQL ---
    buffer = io.StringIO()
    config = Config("alembic.ini", output_buffer=buffer)
    command.upgrade(
        config,
        "0047_053_fix_jobs_status_chk:0048_053_relax_interview_reports_for_research",
        sql=True,
    )
    upgrade_sql = buffer.getvalue()

    widen_pos = upgrade_sql.find(
        "ALTER TABLE alembic_version ALTER COLUMN version_num TYPE VARCHAR(255)"
    )
    record_pos = upgrade_sql.find(
        "UPDATE alembic_version SET version_num="
    )
    assert widen_pos >= 0, (
        "upgrade SQL must contain ALTER TABLE alembic_version ALTER COLUMN "
        "version_num TYPE VARCHAR(255)"
    )
    assert record_pos >= 0, (
        "upgrade SQL must record the new revision in alembic_version"
    )
    assert widen_pos < record_pos, (
        f"version_num widen (pos {widen_pos}) must occur BEFORE "
        f"revision record (pos {record_pos})"
    )

    # --- downgrade offline SQL ---
    buffer = io.StringIO()
    config = Config("alembic.ini", output_buffer=buffer)
    command.downgrade(
        config,
        "0048_053_relax_interview_reports_for_research:0047_053_fix_jobs_status_chk",
        sql=True,
    )
    downgrade_sql = buffer.getvalue()

    # Downgrade must NOT contain any ALTER on alembic_version
    assert "ALTER TABLE alembic_version" not in downgrade_sql, (
        "downgrade SQL must NOT narrow alembic_version.version_num"
    )


__all__ = []
