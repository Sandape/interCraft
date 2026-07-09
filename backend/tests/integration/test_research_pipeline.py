"""REQ-053 T030 — research pipeline integration test.

Creates a job with interview_time ~5h in the future, invokes
`ResearchService.scan_and_enqueue_jobs`, and verifies that:

1. The job is matched (within the scan window)
2. A task is created in the DB
3. The enqueue_fn is invoked with the new task_id
4. Subsequent scans return matched=0 (deduplication via UNIQUE constraint)

Skipped when DATABASE_URL is the placeholder.

Run:
    cd backend && uv run pytest tests/integration/test_research_pipeline.py -v
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


pytestmark = [pytest.mark.integration]


async def _create_test_job_with_interview(
    db_session: AsyncSession,
    user_id,
    interview_time: datetime,
    *,
    status: str = "interview_1",
    company: str = "PipelineCo",
) -> str:
    """Insert a job + user fixture directly into the DB (bypasses RLS)."""
    import secrets
    job_id = secrets.token_hex(8)
    # Ensure user
    await db_session.execute(
        text(
            """INSERT INTO users (id, email, password_hash, display_name, created_at, updated_at)
            VALUES (:uid, :e, 'x', 'pipe', now(), now())
            ON CONFLICT (id) DO NOTHING"""
        ),
        {"uid": user_id, "e": f"pipe-{user_id.hex[:8]}@test.io"},
    )
    await db_session.execute(
        text(
            """INSERT INTO jobs (id, user_id, company, position, status,
                                 interview_time, created_at, updated_at)
            VALUES (:jid, :uid, :co, 'Backend', :st, :it, now(), now())"""
        ),
        {
            "jid": job_id,
            "uid": user_id,
            "co": company,
            "st": status,
            "it": interview_time,
        },
    )
    await db_session.commit()
    return job_id


@pytest.mark.asyncio
async def test_t030_scan_creates_task_for_5h_window_job(db_session: AsyncSession) -> None:
    """Job at +5h should be matched and tasked on first scan; second scan no-ops."""
    from uuid import uuid4
    from app.modules.research.service import ResearchService

    user_id = uuid4()
    target_time = datetime.now(timezone.utc) + timedelta(hours=5)
    job_id = await _create_test_job_with_interview(
        db_session, user_id, target_time, company="MatchMe"
    )

    svc = ResearchService(db_session)
    enqueued: list[str] = []

    async def fake_enqueue(task_id: str) -> None:
        enqueued.append(task_id)

    result = await svc.scan_and_enqueue_jobs(enqueue_fn=fake_enqueue)

    assert result["matched"] >= 1, f"expected >=1 matched, got {result}"
    assert result["tasks_created"] >= 1
    assert len(enqueued) >= 1, "enqueue_fn should be called for matched jobs"

    # Verify the task row exists in DB
    res = await db_session.execute(
        text(
            """SELECT id, job_id, status FROM interview_research_tasks
            WHERE job_id = :jid"""
        ),
        {"jid": job_id},
    )
    tasks = res.all()
    assert len(tasks) >= 1, "task row should exist"
    assert tasks[0][2] == "pending", f"task should be pending, got {tasks[0][2]}"

    # Second scan — must NOT create duplicates
    enqueued.clear()
    result2 = await svc.scan_and_enqueue_jobs(enqueue_fn=fake_enqueue)
    assert result2["matched"] == 0, (
        f"second scan should match no jobs (UNIQUE constraint), got {result2}"
    )
    assert len(enqueued) == 0


@pytest.mark.asyncio
async def test_t030_jobs_outside_window_not_matched(
    db_session: AsyncSession,
) -> None:
    """A job whose interview_time is far in the future (>5h5m) is not matched."""
    from uuid import uuid4
    from app.modules.research.service import ResearchService

    user_id = uuid4()
    far_future = datetime.now(timezone.utc) + timedelta(hours=10)
    await _create_test_job_with_interview(
        db_session, user_id, far_future, company="TooFarCo"
    )

    svc = ResearchService(db_session)
    enqueued: list[str] = []

    async def fake_enqueue(task_id: str) -> None:
        enqueued.append(task_id)

    result = await svc.scan_and_enqueue_jobs(enqueue_fn=fake_enqueue)
    assert result["matched"] == 0, f"job at +10h should not match, got {result}"
    assert len(enqueued) == 0


@pytest.mark.asyncio
async def test_t030_deleted_job_not_matched(db_session: AsyncSession) -> None:
    """Soft-deleted jobs (deleted_at IS NOT NULL) must be excluded."""
    from uuid import uuid4
    from app.modules.research.service import ResearchService

    user_id = uuid4()
    target_time = datetime.now(timezone.utc) + timedelta(hours=5)
    job_id = await _create_test_job_with_interview(
        db_session, user_id, target_time, company="DeletedCo"
    )

    # Soft-delete
    await db_session.execute(
        text("UPDATE jobs SET deleted_at = now() WHERE id = :jid"),
        {"jid": job_id},
    )
    await db_session.commit()

    svc = ResearchService(db_session)
    enqueued: list[str] = []

    async def fake_enqueue(task_id: str) -> None:
        enqueued.append(task_id)

    result = await svc.scan_and_enqueue_jobs(enqueue_fn=fake_enqueue)
    assert result["matched"] == 0, f"deleted job should not match, got {result}"


__all__ = []