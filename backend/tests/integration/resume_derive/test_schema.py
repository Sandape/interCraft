"""Smoke: ORM columns for REQ-055 resume derive."""
from __future__ import annotations

from sqlalchemy import inspect

from app.modules.resume_derive.models import ResumeDeriveRun
from app.modules.resumes_v2.models import ResumeV2


def test_resume_derive_run_table_registered():
    assert ResumeDeriveRun.__tablename__ == "resume_derive_runs"


def test_resume_v2_has_resume_kind_column():
    cols = {c.key for c in inspect(ResumeV2).columns}
    assert "resume_kind" in cols
    assert "target_page_count" in cols
    assert "actual_page_count" in cols
    assert "derive_meta" in cols
