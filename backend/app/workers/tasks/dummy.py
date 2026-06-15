"""Dummy ARQ task — verifies worker boot end-to-end."""
from __future__ import annotations

from typing import Any


async def ping(ctx: dict[str, Any]) -> dict[str, Any]:
    """No-op task used in `arq app.workers.main.WorkerSettings` smoke test."""
    return {"pong": True, "ts": ctx.get("job_try")}


__all__ = ["ping"]
