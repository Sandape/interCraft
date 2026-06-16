"""Contract tests for the resume export gateway."""
from __future__ import annotations

import pytest

from app.api.deps import get_current_user
from app.main import app

pytestmark = pytest.mark.contract


@pytest.fixture(autouse=True)
def auth_override():
    app.dependency_overrides[get_current_user] = lambda: object()
    yield
    app.dependency_overrides.pop(get_current_user, None)


async def test_render_export_returns_binary_pdf(client, monkeypatch) -> None:
    async def fake_render_resume(markdown: str, style_id: str, format_type: str) -> bytes:
        assert markdown.startswith("# Candidate")
        assert style_id == "compact-one-page"
        assert format_type == "pdf"
        return b"%PDF-1.4\nexport"

    from app.api.v1 import export as export_api

    monkeypatch.setattr(export_api, "render_resume", fake_render_resume)

    response = await client.post(
        "/api/v1/export/render",
        json={
            "markdown": "# Candidate\n\n## Summary\n\nSenior engineer",
            "style_id": "compact-one-page",
            "format": "pdf",
        },
    )

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.headers["content-disposition"].startswith("attachment; filename=")
    assert response.headers["x-request-id"]
    assert response.content == b"%PDF-1.4\nexport"


@pytest.mark.parametrize(
    ("payload", "status_code", "error_code"),
    [
        (
            {"markdown": " ", "style_id": "compact-one-page", "format": "pdf"},
            400,
            "EMPTY_CONTENT",
        ),
        (
            {"markdown": "# Candidate", "style_id": "unknown-style", "format": "pdf"},
            400,
            "INVALID_STYLE",
        ),
        (
            {"markdown": "# Candidate", "style_id": "compact-one-page", "format": "docx"},
            400,
            "INVALID_FORMAT",
        ),
        (
            {
                "markdown": "x" * 500_001,
                "style_id": "compact-one-page",
                "format": "pdf",
            },
            413,
            "CONTENT_TOO_LARGE",
        ),
    ],
)
async def test_render_export_validation_errors(client, payload, status_code, error_code) -> None:
    response = await client.post("/api/v1/export/render", json=payload)

    assert response.status_code == status_code
    body = response.json()
    assert body["error"] == error_code
    assert body["message"]
    assert body["request_id"]


async def test_render_export_returns_structured_renderer_failure(client, monkeypatch) -> None:
    async def fake_render_resume(markdown: str, style_id: str, format_type: str) -> bytes:
        raise RuntimeError("browser unavailable")

    from app.api.v1 import export as export_api

    monkeypatch.setattr(export_api, "render_resume", fake_render_resume)

    response = await client.post(
        "/api/v1/export/render",
        json={
            "markdown": "# Candidate\n\n## Summary\n\nSenior engineer",
            "style_id": "compact-one-page",
            "format": "png",
        },
    )

    assert response.status_code == 500
    body = response.json()
    assert body["error"] == "RENDERING_FAILED"
    assert "browser unavailable" in body["message"]
    assert body["request_id"]
