from __future__ import annotations

from app.observability.tracing import ensure_generic_otlp_representation


def test_generic_otlp_full_content_is_not_exported_raw() -> None:
    assert ensure_generic_otlp_representation("FULL_CONTENT") == "REDACTED"


def test_generic_otlp_allows_metadata_only_and_redacted() -> None:
    assert ensure_generic_otlp_representation("METADATA_ONLY") == "METADATA_ONLY"
    assert ensure_generic_otlp_representation("REDACTED") == "REDACTED"
