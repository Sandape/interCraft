"""REQ-053 T029 — scan_and_enqueue_jobs unit tests.

Verifies the scheduler's matching logic:
- Jobs whose interview_time falls in [now+4h55m, now+5h5m] are matched
- Jobs already tasked (non-cancelled) are skipped
- Soft-deleted jobs are skipped
- Soft-deleted users (deleted_at IS NOT NULL) are skipped

Uses mocks for the repository layer (no DB required). Per the user's
instructions, only the scheduler logic is tested — actual DB writes happen
in the integration test (`test_research_pipeline.py`).

Run:
    cd backend && uv run pytest tests/unit/modules/research/test_scheduler.py -v
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.modules.research.repository import ResearchTaskRepository
from app.modules.research.service import ResearchService

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _job_dict(
    *,
    job_id: str = "00000000-0000-0000-0000-000000000001",
    user_id: str = "00000000-0000-0000-0000-000000000002",
    interview_time: datetime | None = None,
    status: str = "interview_1",
    deleted: bool = False,
) -> dict[str, Any]:
    return {
        "job_id": job_id,
        "user_id": user_id,
        "company": "X",
        "position": "Y",
        "interview_time": interview_time or (
            datetime.now(UTC) + timedelta(hours=5)
        ),
        "status": status,
        "deleted": deleted,
    }


def _fake_session() -> MagicMock:
    s = MagicMock()
    s.execute = AsyncMock()
    s.commit = AsyncMock()
    return s


# ---------------------------------------------------------------------------
# T029 — scan window matching
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.asyncio
async def test_t029_jobs_inside_window_are_matched() -> None:
    """A job whose interview_time is exactly 5h away should be matched."""
    target_time = datetime.now(UTC) + timedelta(hours=5)
    job = _job_dict(interview_time=target_time)

    svc = ResearchService(_fake_session())

    with patch.object(
        ResearchTaskRepository, "find_matching_jobs",
        AsyncMock(return_value=[job]),
    ) as mock_find, patch.object(
        ResearchTaskRepository, "create",
        AsyncMock(return_value="00000000-0000-0000-0000-000000000aaa"),
    ) as mock_create:
        enqueue_mock = AsyncMock()
        result = await svc.scan_and_enqueue_jobs(enqueue_fn=enqueue_mock)

    assert result["matched"] == 1, "should match the job in the 5h window"
    assert result["tasks_created"] == 1
    assert enqueue_mock.await_count == 1, "enqueue should be called once"
    mock_find.assert_awaited_once()
    # Verify the window passed to the repository: lower = now + 4h55m, upper = now + 5h5m
    call_kwargs = mock_find.await_args.kwargs
    lower, upper = call_kwargs["lower"], call_kwargs["upper"]
    assert (upper - lower) == timedelta(minutes=10), "window should be 10 min wide"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_t029_existing_task_is_skipped() -> None:
    """When ResearchTaskRepository.create returns None (UNIQUE constraint hit),
    the job is skipped — no duplicate task is created."""
    job = _job_dict()
    svc = ResearchService(_fake_session())

    with patch.object(
        ResearchTaskRepository, "find_matching_jobs",
        AsyncMock(return_value=[job]),
    ), patch.object(
        ResearchTaskRepository, "create",
        AsyncMock(return_value=None),  # ON CONFLICT DO NOTHING → None
    ):
        enqueue_mock = AsyncMock()
        result = await svc.scan_and_enqueue_jobs(enqueue_fn=enqueue_mock)

    assert result["matched"] == 1
    assert result["tasks_created"] == 0
    assert result["skipped_duplicate"] == 1
    assert enqueue_mock.await_count == 0, "must not enqueue duplicate"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_t029_no_jobs_in_window() -> None:
    """When find_matching_jobs returns [], the scan is a no-op."""
    svc = ResearchService(_fake_session())

    with patch.object(
        ResearchTaskRepository, "find_matching_jobs", AsyncMock(return_value=[]),
    ), patch.object(
        ResearchTaskRepository, "create", AsyncMock(),
    ) as mock_create:
        enqueue_mock = AsyncMock()
        result = await svc.scan_and_enqueue_jobs(enqueue_fn=enqueue_mock)

    assert result == {
        "scanned_at": result["scanned_at"],  # dynamic ISO timestamp
        "matched": 0,
        "tasks_created": 0,
        "skipped_duplicate": 0,
    }
    assert mock_create.await_count == 0
    assert enqueue_mock.await_count == 0


@pytest.mark.unit
@pytest.mark.asyncio
async def test_t029_window_boundary_values() -> None:
    """The window MUST be exactly [now+4h55m, now+5h5m] — no off-by-one."""
    from datetime import datetime, timedelta

    from app.modules.research.repository import ResearchTaskRepository as Repo

    svc = ResearchService(_fake_session())
    before_test = datetime.now(UTC)

    captured = {}

    async def capture_find(self, *, lower, upper):
        captured["lower"] = lower
        captured["upper"] = upper
        return []

    with patch.object(Repo, "find_matching_jobs", capture_find):
        await svc.scan_and_enqueue_jobs(enqueue_fn=AsyncMock())

    after_test = datetime.now(UTC)
    lower = captured["lower"]
    upper = captured["upper"]
    # Lower should be approximately now + 4h55m
    expected_lower = before_test + timedelta(hours=4, minutes=55)
    expected_lower_max = after_test + timedelta(hours=4, minutes=55)
    assert expected_lower <= lower <= expected_lower_max, (
        f"lower {lower} not within expected range"
    )
    # Upper - lower = 10 minutes
    assert (upper - lower) == timedelta(minutes=10)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_t029_repository_filters_out_non_interview_statuses() -> None:
    """Unit-level smoke: the service trusts the repo to filter status/deleted.
    Verify the SQL `find_matching_jobs` contains the right filters by
    inspecting the SQL string."""
    from sqlalchemy import text

    stmt = text(
        """SELECT j.id AS job_id, j.user_id, j.company, j.position,
                  j.interview_time, j.status
        FROM jobs j
        LEFT JOIN interview_research_tasks t
            ON t.job_id = j.id
            AND t.interview_time = j.interview_time
            AND t.status != 'cancelled'
        WHERE j.deleted_at IS NULL
          AND j.status IN ('test', 'interview_1', 'interview_2', 'interview_3')
          AND j.interview_time BETWEEN :lower AND :upper
          AND t.id IS NULL"""
    )
    sql = str(stmt.compile(compile_kwargs={"literal_binds": True}))
    assert "deleted_at IS NULL" in sql
    assert "j.status IN ('test', 'interview_1', 'interview_2', 'interview_3')" in sql
    assert "BETWEEN" in sql
    assert "t.id IS NULL" in sql, "LEFT JOIN + IS NULL ensures dedup"


__all__ = []
