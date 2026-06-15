"""PDF Rendering Service — FastAPI server for resume export."""

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import Response
import logging
import uuid

app = FastAPI(title="Resume PDF Renderer")

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("pdf-renderer")


@app.get("/health")
async def health():
    return {"status": "ok", "service": "pdf-renderer"}


@app.post("/api/export/render")
async def render_export(request: Request):
    """Render resume to PDF/PNG/JPEG."""
    request_id = str(uuid.uuid4())
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    markdown = body.get("markdown", "")
    style_id = body.get("style_id", "compact-one-page")
    format_type = body.get("format", "pdf")
    locale = body.get("locale", "zh")

    # Validation
    if not markdown or not markdown.strip():
        raise HTTPException(status_code=400, detail="EMPTY_CONTENT: markdown is empty")

    valid_styles = ("classic-one-page", "compact-one-page", "modern-two-column", "editorial")
    if style_id not in valid_styles:
        raise HTTPException(status_code=400, detail=f"INVALID_STYLE: must be one of {valid_styles}")

    if format_type not in ("pdf", "png", "jpeg"):
        raise HTTPException(status_code=400, detail="INVALID_FORMAT: must be pdf, png, or jpeg")

    if len(markdown) > 500_000:
        raise HTTPException(status_code=413, detail="CONTENT_TOO_LARGE")

    logger.info(
        "render request",
        extra={
            "request_id": request_id,
            "style_id": style_id,
            "format": format_type,
            "content_size_bytes": len(markdown),
        },
    )

    try:
        from .renderer import render_resume
        result = await render_resume(markdown, style_id, format_type)
    except ImportError:
        raise HTTPException(status_code=501, detail="Rendering engine not initialized")
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
