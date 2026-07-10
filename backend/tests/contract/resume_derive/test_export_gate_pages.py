"""REQ-056: export-gate page mismatch contract (extends unit logic)."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.modules.resume_derive.service import ResumeDeriveService


@pytest.mark.asyncio
async def test_export_gate_pages_equal_allows():
    row = MagicMock()
    row.resume_kind = "derived"
    row.target_page_count = 3
    row.actual_page_count = 3
    row.data = {"metadata": {"derive": {"pendingClaims": []}}}
    row.derive_meta = {}

    session = AsyncMock()
    svc = ResumeDeriveService(session)
    svc.resumes = AsyncMock()
    svc.resumes.get = AsyncMock(return_value=row)

    out = await svc.export_gate(uuid4(), user_id=uuid4())
    assert out["exportable"] is True
    assert out["target_page_count"] == 3
    assert out["actual_page_count"] == 3


@pytest.mark.asyncio
async def test_export_gate_pages_2_vs_1_denies():
    row = MagicMock()
    row.resume_kind = "derived"
    row.target_page_count = 2
    row.actual_page_count = 1
    row.data = {"metadata": {"derive": {"pendingClaims": []}}}
    row.derive_meta = {}

    session = AsyncMock()
    svc = ResumeDeriveService(session)
    svc.resumes = AsyncMock()
    svc.resumes.get = AsyncMock(return_value=row)

    out = await svc.export_gate(uuid4(), user_id=uuid4())
    assert out["exportable"] is False
    assert "page_count_mismatch" in out["blockers"]
