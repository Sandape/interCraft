"""Unit tests for suggestion preview/apply (REQ-055)."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.modules.resume_derive.service import DeriveError, ResumeDeriveService


def test_apply_patch_merges_sections_and_metadata():
    data = {
        "basics": {"name": "Ada"},
        "sections": {"skills": {"items": [{"id": "s1", "name": "Python"}]}},
        "metadata": {"derive": {"jd_keywords": ["python"]}},
    }
    patch = {
        "sections": {"skills": {"items": [{"id": "s1", "name": "Python", "level": "expert"}]}},
        "metadata": {"derive": {"last_patch": "kw-order"}},
    }
    out = ResumeDeriveService._apply_patch(data, patch)
    assert out["sections"]["skills"]["items"][0]["level"] == "expert"
    # metadata merge is shallow — patch derive dict replaces prior keys
    assert out["metadata"]["derive"]["last_patch"] == "kw-order"


@pytest.mark.asyncio
async def test_apply_suggestion_raises_version_conflict():
    user_id = uuid4()
    resume_id = uuid4()
    row = MagicMock()
    row.resume_kind = "derived"
    row.version = 3
    row.data = {"sections": {}, "metadata": {"derive": {}}}
    row.derive_meta = {
        "suggestions": [
            {
                "id": "kw-order",
                "apply_mode": "direct",
                "patch": {"summary": {"content": "Updated"}},
            }
        ]
    }
    row.job_id = None
    row.root_resume_id = None

    session = AsyncMock()
    svc = ResumeDeriveService(session)
    svc.resumes = AsyncMock()
    svc.resumes.get = AsyncMock(return_value=row)

    with pytest.raises(DeriveError) as exc:
        await svc.apply_suggestion(
            resume_id,
            user_id=user_id,
            suggestion_id="kw-order",
            client_version=2,
        )
    assert exc.value.code == "VERSION_CONFLICT"
    assert exc.value.status == 409
