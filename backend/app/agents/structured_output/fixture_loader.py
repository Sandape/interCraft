"""REQ-038 US3 — Structured output fixture loader.

``load_structured_output_fixture(name)`` loads a fixture JSON file from
``backend/tests/fixtures/structured_output/`` and extracts the ``_raw``
field as a bare string, ready to feed into ``parse_structured_output``.

This ensures tests never pass the full metadata JSON into the parser;
only the raw LLM content reaches the validation path.

[ac-completed: AC-008]
"""
from __future__ import annotations

import json
from pathlib import Path

_FIXTURE_DIR = Path(__file__).resolve().parents[3] / "tests" / "fixtures" / "structured_output"

_FIXTURE_NAMES: dict[str, str] = {
    "missing": "mock_llm_missing.json",
    "enum_violation": "mock_llm_enum_violation.json",
    "oob": "mock_llm_oob.json",
    "malformed": "mock_llm_malformed.json",
    "quota": "mock_llm_quota.json",
    "timeout": "mock_llm_timeout.json",
}


def load_structured_output_fixture(name: str) -> str:
    """Load a structured output fixture by short name and return bare content.

    The fixture JSON is a metadata envelope; this function extracts the
    ``_raw`` field so callers pass only the raw LLM content to the parser.

    Raises:
        KeyError: If ``name`` is not a known fixture.
        FileNotFoundError: If the fixture file does not exist.
        ValueError: If the fixture JSON is missing the ``_raw`` field.
    """
    if name not in _FIXTURE_NAMES:
        raise KeyError(
            f"Unknown fixture '{name}'. "
            f"Available: {', '.join(sorted(_FIXTURE_NAMES))}"
        )

    path = _FIXTURE_DIR / _FIXTURE_NAMES[name]
    if not path.exists():
        raise FileNotFoundError(f"Fixture file not found: {path}")

    data = json.loads(path.read_text(encoding="utf-8"))
    raw = data.get("_raw")
    if raw is None:
        raise ValueError(
            f"Fixture '{name}' ({path}) is missing the '_raw' field. "
            "Ensure the fixture JSON has a '_raw' key with the bare LLM content."
        )
    return str(raw)


__all__ = ["load_structured_output_fixture"]
