"""019 — Unit tests for the 5 extended fields on jobs (FR-001~FR-006).

Covers: CreateJobInput / PatchJobInput / JobOut default behaviour,
length/enum/ge validation, and field passthrough.
"""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.modules.jobs.schemas import (
    CreateJobInput,
    JobOut,
    PatchJobInput,
)


def test_create_job_minimal_uses_defaults() -> None:
    body = CreateJobInput(company="字节", position="前端")
    assert body.base_location is None
    assert body.requirements_md is None
    assert body.employment_type == "unspecified"
    assert body.salary_range_text is None
    assert body.headcount is None


def test_create_job_with_all_5_fields_succeeds() -> None:
    body = CreateJobInput(
        company="字节",
        position="前端",
        base_location="北京",
        requirements_md="## 要求\n- 3年 React",
        employment_type="experienced",
        salary_range_text="30-50K · 16薪",
        headcount=5,
    )
    assert body.base_location == "北京"
    assert body.requirements_md.startswith("## 要求")
    assert body.employment_type == "experienced"
    assert body.salary_range_text == "30-50K · 16薪"
    assert body.headcount == 5


def test_base_location_over_50_chars_rejected() -> None:
    with pytest.raises(ValidationError):
        CreateJobInput(company="x", position="y", base_location="a" * 51)


def test_requirements_md_over_5000_chars_rejected() -> None:
    with pytest.raises(ValidationError):
        CreateJobInput(company="x", position="y", requirements_md="x" * 5001)


def test_employment_type_invalid_value_rejected() -> None:
    with pytest.raises(ValidationError):
        CreateJobInput(company="x", position="y", employment_type="intern")  # type: ignore[arg-type]


@pytest.mark.parametrize("v", ["internship", "campus", "experienced", "contract", "unspecified"])
def test_employment_type_valid_values_accepted(v: str) -> None:
    body = CreateJobInput(company="x", position="y", employment_type=v)  # type: ignore[arg-type]
    assert body.employment_type == v


def test_salary_range_text_over_100_chars_rejected() -> None:
    with pytest.raises(ValidationError):
        CreateJobInput(company="x", position="y", salary_range_text="x" * 101)


def test_headcount_zero_or_negative_rejected() -> None:
    with pytest.raises(ValidationError):
        CreateJobInput(company="x", position="y", headcount=0)
    with pytest.raises(ValidationError):
        CreateJobInput(company="x", position="y", headcount=-1)


def test_patch_job_partial_updates_5_fields() -> None:
    body = PatchJobInput(base_location="上海", headcount=10)
    dumped = body.model_dump(exclude_none=True)
    assert dumped == {"base_location": "上海", "headcount": 10}


def test_job_out_includes_5_fields() -> None:
    """JobOut exposes the 5 new fields (FR-006)."""
    fields = JobOut.model_fields.keys()
    for f in ("base_location", "requirements_md", "employment_type", "salary_range_text", "headcount"):
        assert f in fields, f"JobOut missing field: {f}"
