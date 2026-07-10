"""Contract tests for suggestion API schemas (REQ-055)."""
from __future__ import annotations

from app.modules.resume_derive.schemas import SuggestionApplyIn, SuggestionPreviewIn


def test_suggestion_preview_in_fields():
    fields = set(SuggestionPreviewIn.model_fields)
    assert {"suggestion_id", "client_version"}.issubset(fields)


def test_suggestion_apply_in_fields():
    fields = set(SuggestionApplyIn.model_fields)
    assert {"suggestion_id", "client_version", "preview_token"}.issubset(fields)
