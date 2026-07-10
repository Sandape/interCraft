"""REQ-056 US6: enqueue failure maps to ENQUEUE_FAILED."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.modules.resume_derive.service import DeriveError, ResumeDeriveService


@pytest.mark.asyncio
async def test_start_run_enqueue_failure_raises_503():
    session = AsyncMock()
    job = MagicMock()
    job.user_id = uuid4()
    job.requirements_md = "Need Python"
    session.get = AsyncMock(return_value=job)

    root = MagicMock()
    root.id = uuid4()
    root.version = 0
    root.resume_kind = "root"

    run = MagicMock()
    run.id = uuid4()
    run.status = "queued"

    svc = ResumeDeriveService(session)
    svc.get_root = AsyncMock(return_value=root)
    svc.runs = AsyncMock()
    svc.runs.create = AsyncMock(return_value=run)

    with patch(
        "app.core.redis.enqueue_job",
        AsyncMock(side_effect=RuntimeError("redis down")),
    ):
        with pytest.raises(DeriveError) as ei:
            await svc.start_run(
                user_id=job.user_id,
                job_id=uuid4(),
                target_page_count=1,
            )
    assert ei.value.status == 503
    assert ei.value.code == "ENQUEUE_FAILED"
    assert run.status == "failed"
    assert run.error_code == "ENQUEUE_FAILED"
