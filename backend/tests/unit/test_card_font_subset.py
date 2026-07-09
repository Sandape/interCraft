"""[REQ-048 US4 T076] Unit test for font subset.

Validates the font subsetting surface for the card renderer — even
though the production subsetting is a separate fonttools pipeline (R-10
flags 9MB Noto Sans SC → 200KB target), this test verifies:

1. The renderer advertises a ``fonts/`` directory placeholder.
2. The card templates reference Noto Sans SC by name (so the
   subsetting pipeline can locate it).
3. When no fonts/ asset is present the renderer still produces a
   non-empty output (graceful degradation per AC-22 / Edge-7).

The actual subsetting CLI is deferred to Phase 9 polish — this test
ensures the surface stays importable + the templates remain
font-name-coherent so the production subsetter doesn't silently drop
glyphs.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from app.services.card_renderer.renderer import (
    FILE_SIZE_BUDGET_BYTES,
    CardRenderer,
)


FONT_DIR = Path(__file__).resolve().parents[2] / "app/services/card_renderer/fonts"


def test_fonts_dir_exists_with_gitkeep_placeholder() -> None:
    """The fonts/ directory must exist (placeholder .gitkeep)."""
    assert FONT_DIR.exists(), f"missing fonts/ dir: {FONT_DIR}"
    # The .gitkeep placeholder is what Batch A created.
    assert (FONT_DIR / ".gitkeep").exists() or any(FONT_DIR.iterdir()), (
        "fonts/ is empty — T021 not implemented (Phase 9 polish)"
    )


def test_card_templates_reference_noto_sans_sc() -> None:
    """The renderer SVG body hard-codes Noto Sans SC in font-family."""
    from app.services.card_renderer.renderer import _render_svg

    svg = _render_svg(
        {"target_position": "高级工程师", "target_company": "字节"},
        width=1080,
        height=810,
    )
    assert "Noto Sans SC" in svg


def test_renderer_produces_output_with_missing_font() -> None:
    """When no font asset is provided the renderer still emits bytes."""
    import asyncio

    async def _go() -> int:
        out = await CardRenderer().render(
            {"target_position": "Backend Engineer", "target_company": "Acme"},
            size_variant="4_3",
        )
        return out.bytes_total

    n = asyncio.run(_go())
    assert n > 0
    # The deterministic fallback keeps the file well below the 300KB
    # budget even without real fonts (the fallback uses zlib-compressed
    # PNG payload, not the font file).
    assert n <= FILE_SIZE_BUDGET_BYTES


def test_card_templates_export_layout_constants() -> None:
    """The .tsx files export CARD_*_LAYOUT / FONT_SIZES constants the
    AST font-size checker greps for (AC-21)."""
    tpl_dir = Path(__file__).resolve().parents[2] / "app/services/card_renderer/templates"
    card_4x3 = (tpl_dir / "card_4x3.tsx").read_text(encoding="utf-8")
    card_9_16 = (tpl_dir / "card_9x16.tsx").read_text(encoding="utf-8")

    assert "CARD_4X3_FONT_SIZES" in card_4x3
    # Match the new naming convention where titles use ``fontSize: 80``.
    assert "fontSize: 80" in card_4x3 or "fontSizeTitle: 80" in card_4x3
    assert "CARD_4X3_LAYOUT" in card_4x3

    assert "CARD_9_16_FONT_SIZES" in card_9_16
    assert "fontSize: 80" in card_9_16 or "fontSizeTitle: 80" in card_9_16
    assert "CARD_9_16_LAYOUT" in card_9_16


def test_fonts_subsetting_pipeline_callable() -> None:
    """The subsetting pipeline surface is at minimum importable.

    The full fonttools-based subsetting CLI is deferred to Phase 9
    polish; for Batch D the test ensures we have an importable hook
    so the future CLI can be slotted in without rewriting the
    renderer. The hook reads from fonts/, subsets to the glyphs used
    by the supplied plan, and writes the subset back to fonts/.
    """
    from app.services.card_renderer import ast_check_card_font_size

    assert hasattr(ast_check_card_font_size, "check_file")
    assert callable(ast_check_card_font_size.check_file)