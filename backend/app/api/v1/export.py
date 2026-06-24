"""Resume export gateway mounted under /api/v1/export.

Spec 027 US1 — refactored to accept front-end generated HTML instead of
markdown + style_id. The front-end uses the unified `renderMarkdown` engine
to produce the HTML; the backend wraps it in a full document and feeds it
to Playwright. This eliminates preview↔PDF rendering drift.
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel

from app.api.deps import get_current_user
from app.core.logging import get_logger
from src.services.pdf_renderer.renderer import render_resume
from src.services.pdf_renderer.sanitize import sanitize_html

router = APIRouter(prefix="/export")
log = get_logger("resume-export")

VALID_FORMATS = {"pdf", "png", "jpeg"}
MAX_HTML_BYTES = 1_000_000
CONTENT_TYPES = {
    "pdf": "application/pdf",
    "png": "image/png",
    "jpeg": "image/jpeg",
}


class ExportRequest(BaseModel):
    """HTML-based export payload (spec 027 US1).

    `markdown` and `style_id` were removed — the front-end renders markdown
    to HTML via the unified render engine before posting.
    """

    html: str = ""
    format: str = "pdf"
    locale: str = "zh"


def _error(status_code: int, code: str, message: str, request_id: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"error": code, "message": message, "request_id": request_id},
        headers={"X-Request-ID": request_id},
    )


def _request_id(request: Request) -> str:
    return request.headers.get("X-Request-ID") or str(uuid.uuid4())


@router.post("/render", response_model=None)
async def render_export(
    payload: ExportRequest,
    request: Request,
    _user=Depends(get_current_user),
) -> Response:
    """Render pre-generated HTML to a binary PDF, PNG, or JPEG response."""

    request_id = _request_id(request)
    html = payload.html or ""
    content_size = len(html.encode("utf-8"))

    if not html.strip():
        return _error(400, "EMPTY_CONTENT", "Resume content is empty.", request_id)
    if payload.format not in VALID_FORMATS:
        return _error(400, "INVALID_FORMAT", "Export format is not supported.", request_id)
    if content_size > MAX_HTML_BYTES:
        return _error(413, "CONTENT_TOO_LARGE", "Resume content is too large.", request_id)

    # Defense in depth: sanitize dangerous tags/attributes before rendering.
    # The frontend also sanitizes, but we re-sanitize server-side to guard
    # against direct API calls bypassing the frontend pipeline.
    sanitized = sanitize_html(html)

    log.info(
        "resume_export.render.start",
        request_id=request_id,
        format=payload.format,
        content_size_bytes=content_size,
        sanitized_size_bytes=len(sanitized),
    )

    try:
        result = await render_resume(sanitized, payload.format)
    except Exception as exc:  # pragma: no cover - exact renderer failures vary by host
        log.error(
            "resume_export.render.failed",
            request_id=request_id,
            format=payload.format,
            error=str(exc),
        )
        return _error(500, "RENDERING_FAILED", f"Rendering failed: {exc}", request_id)

    headers = {
        "Content-Disposition": f'attachment; filename="resume-{request_id}.{payload.format}"',
        "X-Request-ID": request_id,
    }
    log.info(
        "resume_export.render.success",
        request_id=request_id,
        format=payload.format,
        content_size_bytes=content_size,
        output_size_bytes=len(result),
    )
    return Response(content=result, media_type=CONTENT_TYPES[payload.format], headers=headers)
