"""REQ-056: ResumeV2Out / ListItemOut accept derive fields."""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from app.modules.resumes_v2.schemas import ResumeV2ListItemOut, ResumeV2Out


def test_list_item_defaults_resume_kind_standard():
    item = ResumeV2ListItemOut.model_validate(
        {
            "id": uuid4(),
            "name": "Std",
            "slug": "std",
            "tags": [],
            "is_public": False,
            "is_locked": False,
            "version": 1,
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
        }
    )
    assert item.resume_kind == "standard"


def test_detail_out_with_all_derive_fields():
    now = datetime.now(timezone.utc)
    out = ResumeV2Out(
        id=uuid4(),
        user_id=uuid4(),
        name="X",
        slug="x",
        tags=[],
        is_public=False,
        is_locked=False,
        password_set=False,
        data={},
        version=0,
        resume_kind="root",
        created_at=now,
        updated_at=now,
    )
    assert out.resume_kind == "root"
