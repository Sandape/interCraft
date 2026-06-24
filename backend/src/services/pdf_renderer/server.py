"""PDF Rendering Service — standalone FastAPI microservice for resume export.

Refactored in 027 US1: accepts front-end generated HTML (not Markdown)
and renders via Playwright. Kept in sync with the main app's
``app.api.v1.export`` contract so the microservice can be swapped in
without API drift.
"""

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import Response
import logging
import uuid

from .renderer import render_resume
from .sanitize import sanitize_html

app = FastAPI(title="Resume PDF Renderer")

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("pdf-renderer")


@app.get("/health")
async def health():
    return {"status": "ok", "service": "pdf-renderer"}


@app.post("/api/export/render")
async def render_export(request: Request):
    """Render front-end generated HTML to PDF/PNG/JPEG."""
    request_id = str(uuid.uuid4())
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    html = body.get("html", "")
    format_type = body.get("format", "pdf")
    locale = body.get("locale", "zh")  # accepted for forward compat, unused server-side

    if not html or not html.strip():
        raise HTTPException(status_code=400, detail="EMPTY_CONTENT: html is empty")

    if format_type not in ("pdf", "png", "jpeg"):
        raise HTTPException(status_code=400, detail="INVALID_FORMAT: must be pdf, png, or jpeg")

    if len(html.encode("utf-8")) > 1_000_000:
        raise HTTPException(status_code=413, detail="CONTENT_TOO_LARGE")

    sanitized = sanitize_html(html)

    logger.info(
        "render request",
        extra={
            "request_id": request_id,
            "format": format_type,
            "content_size_bytes": len(html.encode("utf-8")),
        },
    )

    try:
        result = await render_resume(sanitized, format_type)
    except Exception as e:
        logger.error("rendering failed", extra={"request_id": request_id, "error": str(e)})
        raise HTTPException(status_code=500, detail=f"RENDERING_FAILED: {e}")

    content_types = {
        "pdf": "application/pdf",
        "png": "image/png",
        "jpeg": "image/jpeg",
    }

    return Response(
        content=result,
        media_type=content_types[format_type],
        headers={"X-Request-ID": request_id},
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=9000)
