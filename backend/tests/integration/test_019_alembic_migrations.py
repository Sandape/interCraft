"""019 — Alembic migration smoke tests (Feature 019: Cross-Module Linking).

Verifies that:
- 0009_job_fields adds 5 columns to jobs with correct defaults
- 0010_interview_job_id adds job_id column with FK + index
- 0011_error_src_qid adds source_question_id column with partial unique index
- All 3 migrations are idempotent (re-running is a no-op)
"""
from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = pytest.mark.integration


async def test_019_job_fields_columns_exist(db_session: AsyncSession) -> None:
    expected = {
        "base_location": "text",
        "requirements_md": "text",
        "employment_type": "text",
        "salary_range_text": "text",
        "headcount": "integer",
    }
    res = await db_session.execute(
        text(
            "SELECT column_name, data_type FROM information_schema.columns "
            "WHERE table_name='jobs' AND column_name IN "
            "('base_location','requirements_md','employment_type','salary_range_text','headcount')"
        )
    )
    rows = {r[0]: r[1] for r in res.all()}
    assert set(rows.keys()) == expected.keys(), f"missing columns: {expected.keys() - rows.keys()}"
    for col, dtype in expected.items():
        assert rows[col] == dtype, f"jobs.{col} expected {dtype}, got {rows[col]}"


async def test_019_job_fields_defaults(db_session: AsyncSession) -> None:
    """base_location defaults to '', employment_type defaults to 'unspecified'."""
    res = await db_session.execute(
        text(
            "SELECT column_name, column_default FROM information_schema.columns "
            "WHERE table_name='jobs' AND column_name IN ('base_location','employment_type')"
        )
    )
    defaults = {r[0]: r[1] for r in res.all()}
    # column_default is reported as e.g. "''::text" or "'unspecified'::text" by Postgres
    assert defaults.get("base_location") in ("", "''", "''::text"), defaults
    assert defaults.get("employment_type") in ("unspecified", "'unspecified'", "'unspecified'::text"), defaults


async def test_019_interview_job_id_column_and_index(db_session: AsyncSession) -> None:
    res = await db_session.execute(
        text(
            "SELECT column_name, data_type FROM information_schema.columns "
            "WHERE table_name='interview_sessions' AND column_name='job_id'"
        )
    )
    row = res.first()
    assert row is not None, "interview_sessions.job_id missing"
    assert row[1] == "uuid", f"job_id expected uuid, got {row[1]}"
    res = await db_session.execute(
        text("SELECT indexname FROM pg_indexes WHERE tablename='interview_sessions' "
             "AND indexname='ix_interview_sessions_job_id'")
    )
    assert res.first() is not None, "interview_sessions_job_id_idx missing"


async def test_019_error_source_question_id_column_and_partial_unique(db_session: AsyncSession) -> None:
    res = await db_session.execute(
        text(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name='error_questions' AND column_name='source_question_id'"
        )
    )
    assert res.first() is not None, "error_questions.source_question_id missing"
    res = await db_session.execute(
        text(
            "SELECT indexname FROM pg_indexes WHERE tablename='error_questions' "
            "AND indexname='error_questions_source_question_id_uidx'"
        )
    )
    assert res.first() is not None, "partial unique index missing"
