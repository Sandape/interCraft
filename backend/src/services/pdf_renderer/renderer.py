"""Playwright-based resume renderer — receives complete HTML and renders
to PDF/PNG/JPEG.

Refactored in 027 US1: the backend no longer parses Markdown or loads
style CSS. The frontend generates a complete HTML string (via the
unified ``renderMarkdown()`` engine) and POSTs it to ``/export/render``.
The backend's only job is to wrap that HTML in a document shell and
render it through headless Chromium — guaranteeing preview↔PDF parity.

Deleted in this refactor:
- ``_markdown_to_html`` (frontend now owns Markdown parsing)
- ``_load_css`` / ``_load_template`` (CSS now inlined in frontend HTML)
- ``_escape`` (no Markdown text to escape)
- ``styles/`` and ``templates/`` directories (T033)

Contract: specs/027-resume-center-muji-alignment/contracts/pdf-export.md
"""
from __future__ import annotations

import logging

logger = logging.getLogger("pdf-renderer")

# A4 portrait at 96 DPI ≈ 794×1123 px. Playwright PDF uses CSS pixels.
_A4_VIEWPORT = {"width": 794, "height": 1123}

_HTML_DOC_TEMPLATE = """<!DOCTYPE html>
<html lang=\"zh-CN\">
<head>
<meta charset=\"utf-8\" />
<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
<style>
/* Renderer-side resets: zero margin so the frontend CSS controls all spacing.
   Print background colors/images are forced on for PDF (Playwright strips
   them by default). */
html, body {{
  margin: 0;
  padding: 0;
  background: #ffffff;
}}
@page {{
  size: A4;
  margin: 0;
}}
</style>
</head>
<body>
{body}
</body>
</html>
"""


def wrap_html_document(html_body: str) -> str:
    """Wrap a body HTML fragment in a full HTML document shell.

    The frontend sends a fragment (style + content). We add the
    ``<!DOCTYPE html>``, ``<html>``, ``<head>``, and ``<body>`` wrapper
    so Playwright has a well-formed document to render.
    """
    return _HTML_DOC_TEMPLATE.format(body=html_body)


async def render_with_playwright(html: str, format_type: str) -> bytes:
    """Render a complete HTML document to PDF/PNG/JPEG via Playwright.

    Caller is responsible for sanitization (see ``sanitize_html``).
    This function wraps the HTML in a document shell, launches a headless
    Chromium page at A4 dimensions, and renders.

    Args:
        html: sanitized HTML body fragment (or full document — wrapper is idempotent)
        format_type: one of ``{"pdf", "png", "jpeg"}``

    Returns:
        Binary image/PDF bytes.

    Raises:
        RuntimeError: if Playwright is not installed or browser launch fails.
    """
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        logger.error("Playwright not installed. Run: playwright install chromium")
        raise RuntimeError("Playwright not available")

    document = wrap_html_document(html)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(viewport=_A4_VIEWPORT)
        await page.set_content(document, wait_until="networkidle")

        if format_type == "pdf":
            result = await page.pdf(
                format="A4",
                print_background=True,
                margin={"top": "0", "bottom": "0", "left": "0", "right": "0"},
            )
        else:
            result = await page.screenshot(
                full_page=True,
                type=format_type,
                scale="device",
            )

        await browser.close()
        return result


# Backwards-compat alias — export.py imports `render_resume` and the
# contract test patches `export_api.render_resume`. The new signature is
# ``(html, format_type)`` (no ``style_id``).
async def render_resume(html: str, format_type: str) -> bytes:
    """Alias for ``render_with_playwright`` — kept for import-name stability."""
    return await render_with_playwright(html, format_type)
