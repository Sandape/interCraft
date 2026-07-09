"""Card renderer service (REQ-048 US4 / T081).

Renders 4:3 + 9:16 doubao card images via the
:class:`CardRenderer` Python pipeline (with a Node.js + @vercel/og +
sharp mozjpeg production path) plus a Redis-backed 7d cache.

Public surface:

- :class:`CardRenderer` — main renderer (T081)
- :func:`render_card` — module-level shortcut used by AC-17a/17b scripts
- :class:`RenderedCard` — render output envelope
- :mod:`app.services.card_renderer.cache` — Redis cache (T084)
- :mod:`app.services.card_renderer.server` — FastAPI sub-service (T082)
- :mod:`app.services.card_renderer.cli` — typer CLI (T083)
- :mod:`app.services.card_renderer.ast_check_card_font_size` — AC-21 static checker
"""
from __future__ import annotations

from app.services.card_renderer.renderer import (
    CardRenderer,
    FILE_SIZE_BUDGET_BYTES,
    JPEG_QUALITY,
    LAYOUT_4_3,
    LAYOUT_9_16,
    RenderedCard,
    render_card,
    size_is_9_16,
)


__all__ = [
    "CardRenderer",
    "FILE_SIZE_BUDGET_BYTES",
    "JPEG_QUALITY",
    "LAYOUT_4_3",
    "LAYOUT_9_16",
    "RenderedCard",
    "render_card",
    "size_is_9_16",
]