"""T116 — Resume v2 SSE endpoint (US12).

GET /api/v1/v2/resumes/events?resume_id={id}

Streams Server-Sent Events for the v2 resume channel. Internally
opens a dedicated asyncpg LISTEN connection per SSE client and
forwards Postgres NOTIFY payloads to the wire.

Heartbeat: comment line (`: heartbeat\\n\\n`) every 25s. EventSource
ignores comment lines; the heartbeat keeps proxies / load balancers
from idling out the connection.

Per-user connection cap: 5 (configurable in core.config).
"""
from __future__ import annotations

import asyncio
import json
import secrets
import time
from collections import defaultdict
from typing import Any

import asyncpg
from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import StreamingResponse

from app.api.deps import get_current_user_id
from app.core.config import get_settings

router = APIRouter(prefix="/v2", tags=["resumes-v2-sse"])

# Primary channel for resume content updates (PUT). MUST match the
# SQL in `ResumeV2Repository.update_with_version`.
CHANNEL = "resume_update_v2"
# Public-state channel for the `resume.public-changed` event (US11).
# MUST match the SQL in `ResumeV2Service.emit_public_changed`.
PUBLIC_CHANNEL = "resume_v2_public"
HEARTBEAT_INTERVAL = 25.0
IDLE_TIMEOUT = 300.0
MAX_CONNECTIONS_PER_USER = 5

# In-process registry of active connections. The production deployment
# uses uvicorn workers; counts are per-process (acceptable since the
# cap is a soft guard against runaway clients, not a hard limit).
_active_per_user: dict[str, int] = defaultdict(int)
_active_lock = asyncio.Lock()


def _sse_format(event_id: int, event: str, data: dict[str, Any]) -> bytes:
    """Format one SSE event per contracts/03-sse-events.md §3."""
    payload = json.dumps(data, ensure_ascii=False, default=str)
    return (
        f"id: {event_id}\n"
        f"event: {event}\n"
        f"data: {payload}\n\n"
    ).encode("utf-8")


def _heartbeat() -> bytes:
    return b": heartbeat\n\n"


def _user_key(user_id: Any) -> str:
    return str(user_id)


async def _stream_for_user(
    user_id: Any,
    resume_id: str | None,
    request: Request,
) -> Any:
    """Async generator that yields SSE bytes for a single client."""
    settings = get_settings()
    # asyncpg uses libpq-style DSN, but settings.database_url is the
    # SQLAlchemy form (postgresql+asyncpg://). Strip the driver suffix
    # so asyncpg.connect() can read it directly.
    dsn = settings.database_url.replace("postgresql+asyncpg://", "postgresql://", 1)
    if not dsn:
        # No DB → emit a single synthetic event and close.
        yield _sse_format(1, "stream.unavailable", {
            "type": "stream.unavailable",
            "message": "SSE disabled (no DB DSN).",
        })
        return

    conn: asyncpg.Connection | None = None
    queue: asyncio.Queue[asyncpg.pgproto.pgproto | bytes | None] = asyncio.Queue()
    counter = {"id": 0}

    async def _on_notify(_conn, _pid, _channel, payload: str) -> None:
        # Parse the JSON payload and enqueue it. If the payload targets
        # a different resume (or user) than this client, we still forward
        # it; the client filters via `resume_id`.
        try:
            data = json.loads(payload)
        except Exception:
            data = {"raw": payload}
        await queue.put(data)

    async def _listen_loop() -> None:
        nonlocal conn
        try:
            conn = await asyncpg.connect(dsn=dsn)
            await conn.add_listener(CHANNEL, _on_notify)
            await conn.add_listener(PUBLIC_CHANNEL, _on_notify)
            # Keep the connection alive until cancelled.
            while True:
                await asyncio.sleep(IDLE_TIMEOUT / 10)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            await queue.put({"type": "_error", "message": str(e)})
        finally:
            try:
                if conn is not None:
                    await conn.remove_listener(CHANNEL, _on_notify)
                    await conn.remove_listener(PUBLIC_CHANNEL, _on_notify)
                    await conn.close()
            except Exception:
                pass

    listener_task = asyncio.create_task(_listen_loop())

    try:
        # Send an initial "connected" event so the client knows the
        # stream is alive.
        counter["id"] += 1
        yield _sse_format(counter["id"], "connected", {
            "type": "connected",
            "user_id": str(user_id),
            "resume_id": resume_id,
        })

        last_beat = time.monotonic()
        while True:
            # Bail out if the client disconnected.
            if await request.is_disconnected():
                break
            try:
                item = await asyncio.wait_for(queue.get(), timeout=1.0)
            except asyncio.TimeoutError:
                item = None

            if item is None:
                if time.monotonic() - last_beat >= HEARTBEAT_INTERVAL:
                    yield _heartbeat()
                    last_beat = time.monotonic()
                continue

            if isinstance(item, bytes):
                yield item
                continue

            # Filter: only forward events for this user/resume.
            payload_user = item.get("user_id") if isinstance(item, dict) else None
            payload_resume = item.get("resume_id") if isinstance(item, dict) else None
            if payload_user and str(payload_user) != str(user_id):
                continue
            if resume_id and payload_resume and str(payload_resume) != str(resume_id):
                continue

            counter["id"] += 1
            event_name = (item.get("type") if isinstance(item, dict) else None) or "message"
            yield _sse_format(counter["id"], event_name, item)
    finally:
        listener_task.cancel()
        try:
            await listener_task
        except Exception:
            pass
        async with _active_lock:
            _active_per_user[_user_key(user_id)] = max(
                0, _active_per_user[_user_key(user_id)] - 1
            )


@router.get("/resumes/events")
async def stream_resume_events(
    request: Request,
    resume_id: str | None = Query(default=None, max_length=64),
    user_id: Any = Depends(get_current_user_id),
):
    """GET /api/v1/v2/resumes/events — Server-Sent Events stream.

    Optional ``resume_id`` filters events to a single resume; when
    omitted the client receives events for all of the user's resumes.
    """
    key = _user_key(user_id)
    async with _active_lock:
        if _active_per_user[key] >= MAX_CONNECTIONS_PER_USER:
            from fastapi import HTTPException
            raise HTTPException(
                status_code=429,
                detail="Too many SSE connections for this user.",
            )
        _active_per_user[key] += 1

    gen = _stream_for_user(user_id, resume_id, request)
    return StreamingResponse(
        gen,
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
