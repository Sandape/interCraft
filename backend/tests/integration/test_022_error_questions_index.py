"""022 US3 — Integration test: error_questions compound partial index.

Verifies that `idx_error_questions_user_status_freq_created` is used
for the ErrorBook listing query pattern (SC-003).
"""
from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = pytest.mark.integration


async def test_error_questions_index_exists(db_session: AsyncSession) -> None:
    """Index is present in pg_indexes."""
    res = await db_session.execute(
        text(
            "SELECT indexname FROM pg_indexes "
            "WHERE tablename='error_questions' "
            "AND indexname='idx_error_questions_user_status_freq_created'"
        )
    )
    assert res.first() is not None, (
        "idx_error_questions_user_status_freq_created not found in pg_indexes"
    )


async def test_error_questions_index_used_for_list_query(
    db_session: AsyncSession,
) -> None:
    """EXPLAIN shows Index Scan for the typical ErrorBook listing pattern."""
    explain = await db_session.execute(
        text(
            "EXPLAIN (FORMAT TEXT) "
            "SELECT user_id, status, frequency, created_at "
            "FROM error_questions "
            "WHERE user_id = '00000000-0000-0000-0000-000000000001' "
            "AND deleted_at IS NULL "
            "ORDER BY status, frequency, created_at "
            "LIMIT 500"
        )
    )
    plan = "\n".join(row[0] for row in explain.all())
    assert "Seq Scan" not in plan, (
        f"Query plan uses Seq Scan instead of Index Scan:\n{plan}"
    )
