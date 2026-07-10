"""Unit tests for page calibrate strategies (REQ-055 US3)."""
from __future__ import annotations

from app.agents.nodes.resume_derive.calibrate_pages import MAX_ROUNDS, calibrate_pages


def _state(*, target: int, md: str, round_no: int = 0, unused: list | None = None) -> dict:
    return {
        "target_page_count": target,
        "calibrate_round": round_no,
        "unused_materials": unused or [],
        "derived_data": {
            "metadata": {
                "markdown": {"sourceMarkdown": md},
            }
        },
    }


def test_compress_strategy_when_too_long():
    long_md = "\n".join(f"## Section {i}\n" + ("content " * 120) for i in range(80))
    out = calibrate_pages(_state(target=1, md=long_md))  # type: ignore[arg-type]
    strategies = out["page_report"]["strategies"]
    assert "compress_weak_content" in strategies
    assert "tighten_line_height" in strategies
    assert strategies.index("compress_weak_content") < strategies.index("tighten_line_height")


def test_expand_strategy_when_too_short():
    short_md = "# Ada\n\n## Summary\nBackend engineer."
    unused = [{"ref": "root:projects:p9", "reason": "low_relevance"}]
    out = calibrate_pages(_state(target=3, md=short_md, unused=unused))  # type: ignore[arg-type]
    strategies = out["page_report"]["strategies"]
    assert "expand_from_included" in strategies
    assert "relax_spacing" in strategies
    md_out = out["derived_data"]["metadata"]["markdown"]["sourceMarkdown"]
    assert "补充素材" in md_out


def test_max_rounds_caps_calibration():
    # Start at MAX_ROUNDS so inner loop never runs; still returns guidance if mismatch.
    huge_md = "x" * 20000
    out = calibrate_pages(_state(target=1, md=huge_md, round_no=MAX_ROUNDS))  # type: ignore[arg-type]
    assert out["page_report"]["rounds"] == MAX_ROUNDS
    assert out["status"] == "needs_guidance"
    assert out["error_code"] == "DERIVE_INFEASIBLE"
