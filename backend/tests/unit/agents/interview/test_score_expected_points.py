"""Score expected_points wiring (REQ-058 T045)."""
from __future__ import annotations

from pathlib import Path


def test_score_prompt_includes_expected_points_placeholder() -> None:
    text = (
        Path(__file__).resolve().parents[4]
        / "app"
        / "agents"
        / "interview"
        / "prompts"
        / "score.md"
    ).read_text(encoding="utf-8")
    assert "{expected_points}" in text
    assert "off_topic" in text
