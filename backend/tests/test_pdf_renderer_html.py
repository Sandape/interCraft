"""T025 — PDF renderer HTML contract tests.

Tests the refactored POST /api/v1/export/render endpoint that accepts
front-end generated HTML (instead of markdown + style_id) and returns
PDF/PNG/JPEG binary rendered via Playwright.

Contract: specs/027-resume-center-muji-alignment/contracts/pdf-export.md
"""
from __future__ import annotations

import pytest

from app.api.deps import get_current_user
from app.main import app

pytestmark = pytest.mark.contract


@pytest.fixture(autouse=True)
def auth_override():
    """Bypass real auth for contract tests."""
    app.dependency_overrides[get_current_user] = lambda: object()
    yield
    app.dependency_overrides.pop(get_current_user, None)


async def test_render_export_returns_binary_pdf(client, monkeypatch) -> None:
    """POST /export/render with {html, format:pdf} returns 200 + PDF binary."""

    captured_html: list[str] = []

    async def fake_render_resume(html: str, format_type: str) -> bytes:
        captured_html.append(html)
        assert format_type == "pdf"
        # Verify sanitizer ran before reaching renderer
        assert "<script" not in html.lower()
        return b"%PDF-1.4\nexport"

    from app.api.v1 import export as export_api

    monkeypatch.setattr(export_api, "render_resume", fake_render_resume)

    response = await client.post(
        "/api/v1/export/render",
        json={
            "html": "<div class='resume-style-classic'><h1>Candidate</h1></div>",
            "format": "pdf",
        },
    )

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.headers["content-disposition"].startswith("attachment; filename=")
    assert response.headers["x-request-id"]
    assert response.content == b"%PDF-1.4\nexport"
    assert len(captured_html) == 1


async def test_render_export_empty_html_returns_400_empty_content(client) -> None:
    """Empty html body → 400 EMPTY_CONTENT."""
    response = await client.post(
        "/api/v1/export/render",
        json={"html": "   ", "format": "pdf"},
    )
    assert response.status_code == 400
    body = response.json()
    assert body["error"] == "EMPTY_CONTENT"
    assert body["message"]
    assert body["request_id"]


async def test_render_export_missing_html_returns_400_empty_content(client) -> None:
    """Missing html field → 400 EMPTY_CONTENT (treats None as empty)."""
    response = await client.post(
        "/api/v1/export/render",
        json={"format": "pdf"},
    )
    assert response.status_code == 400
    body = response.json()
    assert body["error"] == "EMPTY_CONTENT"


async def test_render_export_html_too_large_returns_413(client) -> None:
    """html > 1MB → 413 CONTENT_TOO_LARGE."""
    big_html = "x" * (1_000_001)
    response = await client.post(
        "/api/v1/export/render",
        json={"html": big_html, "format": "pdf"},
    )
    assert response.status_code == 413
    body = response.json()
    assert body["error"] == "CONTENT_TOO_LARGE"


async def test_render_export_invalid_format_returns_400(client) -> None:
    """format not in {pdf, png, jpeg} → 400 INVALID_FORMAT."""
    response = await client.post(
        "/api/v1/export/render",
        json={"html": "<p>ok</p>", "format": "docx"},
    )
    assert response.status_code == 400
    body = response.json()
    assert body["error"] == "INVALID_FORMAT"


async def test_render_export_strips_script_tags(client, monkeypatch) -> None:
    """HTML containing <script> is sanitized before reaching render_resume."""
    captured_html: list[str] = []

    async def fake_render_resume(html: str, format_type: str) -> bytes:
        captured_html.append(html)
        return b"%PDF-1.4\nexport"

    from app.api.v1 import export as export_api

    monkeypatch.setattr(export_api, "render_resume", fake_render_resume)

    response = await client.post(
        "/api/v1/export/render",
        json={
            "html": "<p>safe</p><script>alert(1)</script><p>after</p>",
            "format": "pdf",
        },
    )

    assert response.status_code == 200
    assert len(captured_html) == 1
    # The script tag must be stripped before reaching render_resume
    assert "<script" not in captured_html[0].lower()
    assert "alert(1)" not in captured_html[0]
    # Safe content is preserved
    assert "<p>safe</p>" in captured_html[0]
    assert "<p>after</p>" in captured_html[0]


async def test_render_export_strips_iframe_and_onclick(client, monkeypatch) -> None:
    """HTML containing <iframe> and on* attributes is sanitized."""
    captured_html: list[str] = []

    async def fake_render_resume(html: str, format_type: str) -> bytes:
        captured_html.append(html)
        return b"%PDF-1.4\nexport"

    from app.api.v1 import export as export_api

    monkeypatch.setattr(export_api, "render_resume", fake_render_resume)

    response = await client.post(
        "/api/v1/export/render",
        json={
            "html": (
                '<p onclick="alert(1)">x</p>'
                '<iframe src="evil.com"></iframe>'
                '<a href="javascript:alert(1)">click</a>'
            ),
            "format": "pdf",
        },
    )

    assert response.status_code == 200
    cleaned = captured_html[0].lower()
    assert "<iframe" not in cleaned
    assert "onclick" not in cleaned
    assert "javascript:" not in cleaned


async def test_render_export_returns_structured_renderer_failure(client, monkeypatch) -> None:
    """render_resume raising → 500 RENDERING_FAILED with structured body."""

    async def fake_render_resume(html: str, format_type: str) -> bytes:
        raise RuntimeError("browser unavailable")

    from app.api.v1 import export as export_api

    monkeypatch.setattr(export_api, "render_resume", fake_render_resume)

    response = await client.post(
        "/api/v1/export/render",
        json={"html": "<p>x</p>", "format": "png"},
    )

    assert response.status_code == 500
    body = response.json()
    assert body["error"] == "RENDERING_FAILED"
    assert "browser unavailable" in body["message"]
    assert body["request_id"]


async def test_render_export_accepts_locale_optional(client, monkeypatch) -> None:
    """locale field is optional and does not break the request."""

    async def fake_render_resume(html: str, format_type: str) -> bytes:
        return b"%PDF-1.4\nexport"

    from app.api.v1 import export as export_api

    monkeypatch.setattr(export_api, "render_resume", fake_render_resume)

    response = await client.post(
        "/api/v1/export/render",
        json={"html": "<p>ok</p>", "format": "pdf", "locale": "en"},
    )

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
