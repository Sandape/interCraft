"""REQ-056: list/detail schema must accept derive fields (contracts/list-schema.md)."""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from app.modules.resumes_v2.schemas import ResumeV2ListItemOut, ResumeV2ListOut, ResumeV2Out


def test_list_item_accepts_resume_kind_root():
    item = ResumeV2ListItemOut.model_validate(
        {
            "id": uuid4(),
            "name": "Root",
            "slug": "root",
            "tags": [],
            "is_public": False,
            "is_locked": False,
            "version": 0,
            "resume_kind": "root",
            "job_id": None,
            "target_page_count": None,
            "actual_page_count": None,
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
        }
    )
    assert item.resume_kind == "root"


def test_list_item_accepts_derived_page_fields():
    jid = uuid4()
    item = ResumeV2ListItemOut.model_validate(
        {
            "id": uuid4(),
            "name": "Derived",
            "slug": "derived-1",
            "tags": ["derived"],
            "is_public": False,
            "is_locked": False,
            "version": 0,
            "resume_kind": "derived",
            "job_id": jid,
            "target_page_count": 2,
            "actual_page_count": 2,
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
        }
    )
    assert item.resume_kind == "derived"
    assert item.job_id == jid
    assert item.target_page_count == 2


def test_list_out_envelope_with_derive_fields():
    now = datetime.now(timezone.utc)
    out = ResumeV2ListOut.model_validate(
        {
            "data": [
                {
                    "id": uuid4(),
                    "name": "Root",
                    "slug": "root",
                    "tags": [],
                    "is_public": False,
                    "is_locked": False,
                    "version": 0,
                    "resume_kind": "root",
                    "job_id": None,
                    "target_page_count": None,
                    "actual_page_count": None,
                    "created_at": now,
                    "updated_at": now,
                }
            ]
        }
    )
    assert out.data[0].resume_kind == "root"


def test_detail_out_accepts_derive_meta():
    now = datetime.now(timezone.utc)
    row = ResumeV2Out.model_validate(
        {
            "id": uuid4(),
            "user_id": uuid4(),
            "name": "D",
            "slug": "d",
            "tags": [],
            "is_public": False,
            "is_locked": False,
            "password_set": False,
            "data": {},
            "version": 0,
            "resume_kind": "derived",
            "root_resume_id": uuid4(),
            "job_id": uuid4(),
            "root_version_at_derive": 0,
            "target_page_count": 1,
            "actual_page_count": 1,
            "derive_meta": {"page_report": {}},
            "created_at": now,
            "updated_at": now,
        }
    )
    assert row.resume_kind == "derived"
    assert row.derive_meta is not None
