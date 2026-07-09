"""REQ-036 — POST /api/v1/v2/export/render endpoint tests.

Covers the US10 (T106) export endpoint per
``specs/032-resume-renderer-v2/contracts/01-rest-api.md`` §6:

  - format dispatch (pdf | png | jpeg | json)
  - html empty / size-limit pre-render validation
  - format=json returns the full ResumeDataV2 with no html required
  - resume_id ownership + 404 vs 403 split
  - downloads counter increments on success
  - the 027 gateway's render_resume is the single source of truth
    for PDF/PNG/JPEG rendering (we monkey-patch it so the test
    suite stays headless).

Tests skip if the backend import chain is broken (matches the
existing test_public / test_analysis pattern).
"""
from __future__ import annotations

import secrets
from typing import Any
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from httpx import ASGITransport

try:
    from app.main import app
    from app.modules.resumes_v2.models import ResumeStatisticsV2
    from app.modules.resumes_v2.repository import ResumeV2Repository
    from sqlalchemy import select
except Exception as e:  # pragma: no cover
    pytest.skip(
        f"Backend import chain broken (skipping export tests): {e}",
        allow_module_level=True,
    )


pytestmark = pytest.mark.integration


# ── helpers ────────────────────────────────────────────────────────────────


def _hdrs(access: str | None = None, fp: str = "fp-export") -> dict[str, str]:
    h = {"X-Device-Fingerprint": fp, "X-Request-ID": f"req-{secrets.token_hex(8)}"}
    if access:
        h["Authorization"] = f"Bearer {access}"
    return h


async def _register(c: httpx.AsyncClient, suffix: str) -> dict[str, str]:
    email = f"export_{suffix}@intercraft.io"
    fp = f"fp-export-{suffix}"
    r = await c.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "Demo1234",
            "display_name": email.split("@")[0],
            "device_fingerprint": fp,
        },
        headers=_hdrs(fp=fp),
    )
    body = r.json()
    return {
        "user_id": body["user"]["id"],
        "access": body["tokens"]["access_token"],
    }


async def _create_resume(c: httpx.AsyncClient, access: str) -> dict[str, Any]:
    r = await c.post(
        "/api/v1/v2/resumes",
        json={
            "name": "Export Test",
            "slug": f"export-{secrets.token_hex(4)}",
            "from_sample": True,
        },
        headers=_hdrs(access=access),
    )
    assert r.status_code == 201, r.text
    body = r.json()
    # Endpoint returns the {"resume": {...}} envelope (locked E2E contract).
    return body["resume"] if "resume" in body else body


@pytest.fixture
async def client() -> httpx.AsyncClient:
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


# Minimal-but-realistic html body — gateway sanitizes it then hands to
# the mocked render_resume.
_HTML_BODY = "<html><body><h1>Test</h1><p>Hello</p></body></html>"


# ── 1. Unauthenticated ─────────────────────────────────────────────────────


async def test_post_without_auth_returns_401(client: httpx.AsyncClient) -> None:
    r = await client.post(
        "/api/v1/v2/export/render",
        json={"html": _HTML_BODY, "format": "pdf"},
    )
    # Auth failures bubble up via FastAPI's TokenMissingError → 401
    assert r.status_code in (401, 403), r.text


# ── 2. Format validation ──────────────────────────────────────────────────


async def test_post_pdf_delegates_to_gateway(
    client: httpx.AsyncClient,
) -> None:
    user = await _register(client, secrets.token_hex(4))
    resume = await _create_resume(client, user["access"])

    fake_pdf_bytes = b"%PDF-1.4\n%fake\n%%EOF\n"
    with patch(
        "src.services.pdf_renderer.renderer.render_resume",
        new=AsyncMock(return_value=fake_pdf_bytes),
    ) as mock_render:
        r = await client.post(
            "/api/v1/v2/export/render",
            json={
                "html": _HTML_BODY,
                "format": "pdf",
                "resume_id": resume["id"],
            },
            headers=_hdrs(access=user["access"]),
        )
    assert r.status_code == 200, r.text
    assert r.headers["content-type"].startswith("application/pdf")
    assert r.content == fake_pdf_bytes
    # Confirm gateway renderer was actually invoked with sanitized html
    mock_render.assert_awaited_once()
    args, _ = mock_render.call_args
    # First positional arg is the sanitized html
    assert _HTML_BODY in args[0]
    # Second positional arg is the format
    assert args[1] == "pdf"


async def test_post_png_returns_image_png(
    client: httpx.AsyncClient,
) -> None:
    user = await _register(client, secrets.token_hex(4))
    resume = await _create_resume(client, user["access"])

    fake_png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32
    with patch(
        "src.services.pdf_renderer.renderer.render_resume",
        new=AsyncMock(return_value=fake_png),
    ):
        r = await client.post(
            "/api/v1/v2/export/render",
            json={
                "html": _HTML_BODY,
                "format": "png",
                "resume_id": resume["id"],
            },
            headers=_hdrs(access=user["access"]),
        )
    assert r.status_code == 200, r.text
    assert r.headers["content-type"].startswith("image/png")


async def test_post_jpeg_returns_image_jpeg(
    client: httpx.AsyncClient,
) -> None:
    user = await _register(client, secrets.token_hex(4))
    resume = await _create_resume(client, user["access"])

    fake_jpeg = b"\xff\xd8\xff" + b"\x00" * 32
    with patch(
        "src.services.pdf_renderer.renderer.render_resume",
        new=AsyncMock(return_value=fake_jpeg),
    ):
        r = await client.post(
            "/api/v1/v2/export/render",
            json={
                "html": _HTML_BODY,
                "format": "jpeg",
                "resume_id": resume["id"],
            },
            headers=_hdrs(access=user["access"]),
        )
    assert r.status_code == 200, r.text
    assert r.headers["content-type"].startswith("image/jpeg")


# ── 3. JSON format ────────────────────────────────────────────────────────


async def test_post_json_returns_resume_data_without_html(
    client: httpx.AsyncClient,
) -> None:
    user = await _register(client, secrets.token_hex(4))
    resume = await _create_resume(client, user["access"])

    r = await client.post(
        "/api/v1/v2/export/render",
        json={
            "format": "json",
            "resume_id": resume["id"],
        },
        headers=_hdrs(access=user["access"]),
    )
    assert r.status_code == 200, r.text
    body = r.json()
    # The full ResumeDataV2 must come back. Spot-check shape.
    assert body["metadata"]["template"] == "pikachu"
    assert "sections" in body
    assert "basics" in body


async def test_post_json_without_resume_id_returns_400(
    client: httpx.AsyncClient,
) -> None:
    user = await _register(client, secrets.token_hex(4))
    r = await client.post(
        "/api/v1/v2/export/render",
        json={"format": "json"},
        headers=_hdrs(access=user["access"]),
    )
    assert r.status_code == 400, r.text
    assert r.json()["error"] == "MISSING_RESUME_ID"


# ── 4. Pre-render validation ──────────────────────────────────────────────


async def test_post_pdf_with_empty_html_returns_400(
    client: httpx.AsyncClient,
) -> None:
    user = await _register(client, secrets.token_hex(4))
    r = await client.post(
        "/api/v1/v2/export/render",
        json={"html": "   ", "format": "pdf"},
        headers=_hdrs(access=user["access"]),
    )
    assert r.status_code == 400, r.text
    assert r.json()["error"] == "EMPTY_CONTENT"


async def test_post_pdf_with_oversize_html_returns_413(
    client: httpx.AsyncClient,
) -> None:
    user = await _register(client, secrets.token_hex(4))
    big = "<p>" + ("x" * 1_000_001) + "</p>"
    r = await client.post(
        "/api/v1/v2/export/render",
        json={"html": big, "format": "pdf"},
        headers=_hdrs(access=user["access"]),
    )
    assert r.status_code == 413, r.text
    assert r.json()["error"] == "CONTENT_TOO_LARGE"


async def test_post_invalid_format_returns_422(
    client: httpx.AsyncClient,
) -> None:
    """Pydantic Literal validator catches unknown formats at the
    request-parsing layer, returning 422 (not 400)."""
    user = await _register(client, secrets.token_hex(4))
    r = await client.post(
        "/api/v1/v2/export/render",
        json={"html": _HTML_BODY, "format": "docx"},
        headers=_hdrs(access=user["access"]),
    )
    assert r.status_code == 422, r.text


# ── 5. Ownership + downloads counter ───────────────────────────────────────


async def test_post_pdf_unknown_resume_returns_404(
    client: httpx.AsyncClient,
) -> None:
    import uuid

    user = await _register(client, secrets.token_hex(4))
    r = await client.post(
        "/api/v1/v2/export/render",
        json={
            "html": _HTML_BODY,
            "format": "pdf",
            "resume_id": str(uuid.uuid4()),
        },
        headers=_hdrs(access=user["access"]),
    )
    assert r.status_code == 404, r.text
    assert r.json()["error"] == "NOT_FOUND"


async def test_post_pdf_other_users_resume_returns_403(
    client: httpx.AsyncClient,
) -> None:
    """Per the v2 service contract (ResumeV2Service.get_resume), an
    authenticated cross-owner access returns 403 ``NOT_OWNER`` so the
    client can distinguish ownership errors from truly missing rows.

    Note: this differs from the public PDF flow, which uses
    ``get_db_session_no_rls`` and returns 404 to avoid leaking
    existence. The authenticated export endpoint takes the stricter
    path because the caller already presented a valid token."""
    user_a = await _register(client, secrets.token_hex(4))
    user_b = await _register(client, secrets.token_hex(4))
    resume_a = await _create_resume(client, user_a["access"])

    r = await client.post(
        "/api/v1/v2/export/render",
        json={
            "html": _HTML_BODY,
            "format": "pdf",
            "resume_id": resume_a["id"],
        },
        headers=_hdrs(access=user_b["access"]),
    )
    assert r.status_code == 403, r.text
    assert r.json()["error"] == "NOT_OWNER"


async def test_post_pdf_without_resume_id_works(
    client: httpx.AsyncClient,
) -> None:
    """resume_id is optional. When omitted the gateway still
    renders, just without counter side-effects."""
    user = await _register(client, secrets.token_hex(4))

    fake_pdf = b"%PDF-1.4\n%fake\n%%EOF\n"
    with patch(
        "src.services.pdf_renderer.renderer.render_resume",
        new=AsyncMock(return_value=fake_pdf),
    ):
        r = await client.post(
            "/api/v1/v2/export/render",
            json={"html": _HTML_BODY, "format": "pdf"},
            headers=_hdrs(access=user["access"]),
        )
    assert r.status_code == 200, r.text
    assert r.headers["content-type"].startswith("application/pdf")
    assert r.content == fake_pdf


async def test_post_pdf_increments_downloads_counter(
    client: httpx.AsyncClient,
) -> None:
    user = await _register(client, secrets.token_hex(4))
    resume = await _create_resume(client, user["access"])
    from app.core.db import _session_cm
    from app.core.db import set_rls_user_id
    import uuid as _uuid

    with patch(
        "src.services.pdf_renderer.renderer.render_resume",
        new=AsyncMock(return_value=b"%PDF-fake"),
    ):
        r = await client.post(
            "/api/v1/v2/export/render",
            json={
                "html": _HTML_BODY,
                "format": "pdf",
                "resume_id": resume["id"],
            },
            headers=_hdrs(access=user["access"]),
        )
    assert r.status_code == 200, r.text

    # Verify the counter went up by reading the statistics row back.
    async with _session_cm() as session:
        await set_rls_user_id(session, _uuid.UUID(user["user_id"]))
        result = await session.execute(
            select(ResumeStatisticsV2).where(
                ResumeStatisticsV2.resume_id == _uuid.UUID(resume["id"])
            )
        )
        row = result.scalar_one_or_none()
    assert row is not None, "ensure_statistics_row should have inserted a row"
    assert int(row.downloads) >= 1, f"downloads should have incremented, got {row.downloads}"


# ── 6. Renderer failure ───────────────────────────────────────────────────


async def test_post_pdf_renderer_failure_returns_500(
    client: httpx.AsyncClient,
) -> None:
    user = await _register(client, secrets.token_hex(4))
    resume = await _create_resume(client, user["access"])

    with patch(
        "src.services.pdf_renderer.renderer.render_resume",
        new=AsyncMock(side_effect=RuntimeError("playwright not installed")),
    ):
        r = await client.post(
            "/api/v1/v2/export/render",
            json={
                "html": _HTML_BODY,
                "format": "pdf",
                "resume_id": resume["id"],
            },
            headers=_hdrs(access=user["access"]),
        )
    assert r.status_code == 500, r.text
    assert r.json()["error"] == "RENDERING_FAILED"


# ── 7. Content-Disposition attachment filename ────────────────────────────


async def test_post_pdf_sets_attachment_disposition(
    client: httpx.AsyncClient,
) -> None:
    user = await _register(client, secrets.token_hex(4))
    resume = await _create_resume(client, user["access"])

    with patch(
        "src.services.pdf_renderer.renderer.render_resume",
        new=AsyncMock(return_value=b"%PDF-fake"),
    ):
        r = await client.post(
            "/api/v1/v2/export/render",
            json={
                "html": _HTML_BODY,
                "format": "pdf",
                "resume_id": resume["id"],
            },
            headers=_hdrs(access=user["access"]),
        )
    assert r.status_code == 200, r.text
    cd = r.headers.get("content-disposition", "")
    assert "attachment" in cd
    assert resume["id"] in cd
    assert cd.endswith('.pdf"')