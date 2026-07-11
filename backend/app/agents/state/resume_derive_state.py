"""LangGraph state for resume_derive."""
from __future__ import annotations

from typing import Any, TypedDict


class ResumeDeriveState(TypedDict, total=False):
    run_id: str
    user_id: str
    job_id: str
    root_resume_id: str
    root_version: int
    root_data: dict[str, Any]
    jd_text: str
    job_company: str
    job_position: str
    target_page_count: int
    template_id: str
    jd_parse: dict[str, Any]
    source_inventory: list[dict[str, str]]
    evidence_map: dict[str, Any]
    selection_plan: dict[str, Any]
    derived_data: dict[str, Any]
    unused_materials: list[dict[str, Any]]
    takeaway_notes: list[str]
    suggestions: list[dict[str, Any]]
    supplement_questions: list[dict[str, Any]]
    page_report: dict[str, Any]
    status: str  # succeeded | partial_success | needs_guidance | failed
    error_code: str
    error_message: str
    calibrate_round: int
    allowed_refs: list[str]
    input_fingerprint: str
