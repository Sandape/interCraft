"""Runtime DeriveError codes for REQ-055 guard rails."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.modules.jobs.models import Job
from app.modules.resume_derive.service import DeriveError, ResumeDeriveService


@pytest.mark.asyncio
async def test_start_run_no_root():
    session = AsyncMock()
    svc = ResumeDeriveService(session)
    svc.resumes = AsyncMock()
    svc.runs = AsyncMock()
    svc.get_root = AsyncMock(return_value=None)

    with pytest.raises(DeriveError) as exc:
        await svc.start_run(
            user_id=uuid4(),
            job_id=uuid4(),
            target_page_count=1,
        )
    assert exc.value.code == "NO_ROOT"


@pytest.mark.asyncio
async def test_start_run_no_jd():
    session = AsyncMock()
    svc = ResumeDeriveService(session)
    svc.runs = AsyncMock()
    root = MagicMock()
    root.id = uuid4()
    root.version = 1
    root.resume_kind = "root"
    svc.get_root = AsyncMock(return_value=root)

    job = Job(
        id=uuid4(),
        user_id=uuid4(),
        company="Acme",
        position="Engineer",
        status="applied",
        status_history=[],
        last_status_changed_at=None,
        base_location="",
        employment_type="unspecified",
        requirements_md="   ",
    )
    session.get = AsyncMock(return_value=job)

    with pytest.raises(DeriveError) as exc:
        await svc.start_run(
            user_id=job.user_id,
            job_id=job.id,
            target_page_count=2,
        )
    assert exc.value.code == "NO_JD"


@pytest.mark.asyncio
async def test_create_root_root_exists():
    session = AsyncMock()
    svc = ResumeDeriveService(session)
    svc.resumes = AsyncMock()
    existing = MagicMock()
    svc.get_root = AsyncMock(return_value=existing)

    with pytest.raises(DeriveError) as exc:
        await svc.create_root(user_id=uuid4(), name="Root", slug="root")
    assert exc.value.code == "ROOT_EXISTS"
    assert exc.value.status == 409
