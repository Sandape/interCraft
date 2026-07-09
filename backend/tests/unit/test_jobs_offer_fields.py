"""024 — Unit tests: Job offer field validation (US1).

Tests the service-layer validation rules for offer_* fields:
  1. Offer fields accepted when status == "offer"
  2. Offer fields rejected when status != "offer"
  3. offer_deadline_at must be in the future
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.modules.jobs.models import Job
from app.modules.jobs.service import JobService


def _fake_job(status: str = "applied", **kw) -> Job:
    uid = uuid4()
    j = Job(
        id=uid,
        user_id=uid,
        company="TestCo",
        position="Engineer",
        status=status,
        status_history=[{"from": None, "to": status, "at": datetime.now(timezone.utc).isoformat(), "note": ""}],
        last_status_changed_at=datetime.now(timezone.utc),
        base_location="",
        employment_type="unspecified",
    )
    for k, v in kw.items():
        setattr(j, k, v)
    return j


@pytest.fixture
def svc():
    s = AsyncMock(spec=JobService)
    # Real session not needed — we directly test the static _validate logic
    session = AsyncMock()
    svc = JobService(session)
    svc.repo = AsyncMock()
    return svc


class TestOfferFieldsValidation:
    async def test_accepts_offer_fields_when_status_is_offer(self, svc):
        """PATCH with offer_* fields succeeds when job.status == 'offer'."""
        job = _fake_job(status="offer")
        svc.repo.get = AsyncMock(return_value=job)

        data = {
            "offer_salary_text": "100K",
            "offer_contact_name": "HR Name",
            "offer_contact_info": "hr@example.com",
            "offer_deadline_at": (datetime.now(timezone.utc) + timedelta(days=7)).isoformat(),
        }
        result = await svc.patch(job.id, job.user_id, data)
        assert result is not None

    async def test_rejects_offer_fields_when_status_is_applied(self, svc):
        """PATCH with offer_* fields fails when job.status is 'applied'."""
        job = _fake_job(status="applied")
        svc.repo.get = AsyncMock(return_value=job)

        data = {"offer_salary_text": "100K"}
        with pytest.raises(HTTPException) as exc:
            await svc.patch(job.id, job.user_id, data)
        assert exc.value.status_code == 409

    async def test_rejects_offer_fields_when_status_is_test(self, svc):
        """PATCH with offer_* fields fails when job.status is 'test'."""
        job = _fake_job(status="test")
        svc.repo.get = AsyncMock(return_value=job)

        data = {"offer_contact_name": "Name"}
        with pytest.raises(HTTPException) as exc:
            await svc.patch(job.id, job.user_id, data)
        assert exc.value.status_code == 409

    async def test_allows_non_offer_fields_when_status_is_not_offer(self, svc):
        """PATCH with only non-offer fields still works regardless of status."""
        job = _fake_job(status="applied")
        svc.repo.get = AsyncMock(return_value=job)
        svc.repo.patch = AsyncMock(return_value=job)

        result = await svc.patch(job.id, job.user_id, {"company": "NewCo"})
        assert result is not None

    async def test_rejects_offer_past_deadline(self, svc):
        """offer_deadline_at must be in the future."""
        job = _fake_job(status="offer")
        svc.repo.get = AsyncMock(return_value=job)

        data = {"offer_deadline_at": (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()}
        with pytest.raises(HTTPException) as exc:
            await svc.patch(job.id, job.user_id, data)
        assert exc.value.status_code == 422

    async def test_accepts_null_offer_deadline(self, svc):
        """Setting offer_deadline_at to None is allowed."""
        job = _fake_job(status="offer")
        svc.repo.get = AsyncMock(return_value=job)
        svc.repo.patch = AsyncMock(return_value=job)

        result = await svc.patch(job.id, job.user_id, {"offer_deadline_at": None})
        assert result is not None

    async def test_accepts_future_deadline(self, svc):
        """offer_deadline_at set to a future date is accepted."""
        job = _fake_job(status="offer")
        svc.repo.get = AsyncMock(return_value=job)
        svc.repo.patch = AsyncMock(return_value=job)

        data = {"offer_deadline_at": (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()}
        result = await svc.patch(job.id, job.user_id, data)
        assert result is not None
