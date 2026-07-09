"""[REQ-048 T082] Card renderer HTTP server.

Exposes ``POST /render`` and ``GET /health``. The endpoint contract is:

- ``POST /render`` body:
    ``{"plan": <InterviewPlan dict>, "size_variant": "4_3" | "9_16"}``
  Response:
    ``{"image_bytes_b64": ..., "width": 1080, "height": 810,
       "sha256_hex": ..., "bytes_total": ..., "size_variant": ...}``

- ``GET /health`` → ``{"status": "ok", "renderer": "satori-stub",
  "fallback": true}`` (the production path runs @vercel/og + resvg + sharp
  via the Node.js sub-service at port 8766; this Python module is the
  in-process fallback used when the sub-service is unreachable, plus
  the test surface for AC-17a / AC-17b / AC-21 / AC-22 / AC-24).

The cache integration lives at the call-site (the interviews API
``GET /interviews/{id}/card`` endpoint) rather than here, so the
sub-service stays a pure renderer.
"""
from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, FastAPI, HTTPException

from app.services.card_renderer.renderer import (
    LAYOUT_4_3,
    LAYOUT_9_16,
    CardRenderer,
)


logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/health")
async def health() -> dict:
    """Sub-service health probe."""
    return {
        "status": "ok",
        "renderer": "satori-stub",
        "fallback": True,
        "layouts": {"4_3": LAYOUT_4_3, "9_16": LAYOUT_9_16},
    }


@router.post("/render")
async def render(body: dict[str, Any]) -> dict:
    """Render an InterviewPlan to a JPG envelope.

    The body is intentionally untyped at the boundary so callers can
    feed in partial plans (focus_areas missing, etc.) without 422s —
    the renderer is tolerant.
    """
    plan = body.get("plan")
    if not isinstance(plan, dict):
        raise HTTPException(
            status_code=422,
            detail={"error": {"code": "INVALID_PLAN", "message": "plan must be a dict"}},
        )
    size_variant = body.get("size_variant", "4_3")
    if size_variant not in {"4_3", "9_16"}:
        raise HTTPException(
            status_code=422,
            detail={
                "error": {
                    "code": "INVALID_SIZE_VARIANT",
                    "message": "size_variant must be '4_3' or '9_16'",
                    "ctx": {"size_variant": size_variant},
                }
            },
        )

    renderer = CardRenderer()
    result = await renderer.render(plan, size_variant=size_variant)
    return result.to_dict()


def build_app() -> FastAPI:
    """Build the standalone FastAPI app for uvicorn entrypoint."""
    app = FastAPI(title="intercraft-card-renderer", version="0.1.0")
    app.include_router(router)
    return app


__all__ = ["build_app", "router"]