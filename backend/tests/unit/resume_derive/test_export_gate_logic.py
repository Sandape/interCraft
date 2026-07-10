"""Unit tests for export_gate blocker rules (REQ-055)."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.modules.resume_derive.service import ResumeDeriveService


@pytest.mark.asyncio
async def test_export_gate_blocks_page_mismatch():
    row = MagicMock()
    row.resume_kind = "derived"
    row.target_page_count = 2
    row.actual_page_count = 3
    row.data = {"metadata": {"derive": {"pendingClaims": []}}}
    row.derive_meta = {}

    session = AsyncMock()
    svc = ResumeDeriveService(session)
    svc.resumes = AsyncMock()
    svc.resumes.get = AsyncMock(return_value=row)

    out = await svc.export_gate(uuid4(), user_id=uuid4())
    assert out["exportable"] is False
    assert "page_count_mismatch" in out["blockers"]


@pytest.mark.asyncio
async def test_export_gate_blocks_pending_claims():
    row = MagicMock()
    row.resume_kind = "derived"
    row.target_page_count = 1
    row.actual_page_count = 1
    row.data = {
        "metadata": {
            "derive": {
                "pendingClaims": [{"question_id": "gap-k8s", "reason": "evidence_missing"}]
            }
        }
    }
    row.derive_meta = {}

    session = AsyncMock()
    svc = ResumeDeriveService(session)
    svc.resumes = AsyncMock()
    svc.resumes.get = AsyncMock(return_value=row)

    out = await svc.export_gate(uuid4(), user_id=uuid4())
    assert out["exportable"] is False
    assert "pending_claims" in out["blockers"]


@pytest.mark.asyncio
async def test_export_gate_passes_when_clean():
    row = MagicMock()
    row.resume_kind = "derived"
    row.target_page_count = 1
    row.actual_page_count = 1
    row.data = {"metadata": {"derive": {"pendingClaims": []}}}
    row.derive_meta = {}

    session = AsyncMock()
    svc = ResumeDeriveService(session)
    svc.resumes = AsyncMock()
    svc.resumes.get = AsyncMock(return_value=row)

    out = await svc.export_gate(uuid4(), user_id=uuid4())
    assert out["exportable"] is True
    assert out["blockers"] == []
