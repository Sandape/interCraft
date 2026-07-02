"""REQ-039 B1 — admin_console FastAPI router.

Mounted at ``/api/v1/admin-console/observability`` by ``app.main``.

Endpoints (7):

- ``GET    /tasks/{task_id}/tags`` — list the caller's tags on a task.
- ``POST   /tasks/{task_id}/tags`` — add a tag (hard-delete semantics).
- ``DELETE /tasks/{task_id}/tags`` — hard-delete a tag.
- ``POST   /traces/{trace_id}/replay`` — replay a trace (≤5/min, FR-032).
- ``POST   /traces/diff`` — diff two traces (≤20/min, FR-033).
- ``GET    /traces/{trace_id}/nodes/{node_id}/payload`` — byte-range slice.
- ``GET    /health`` — module liveness (placeholder).

Auth (B1): capability check via :func:`app.modules.admin_console.auth.require_capability`.
Tests inject a fake user_id via FastAPI ``dependency_overrides``.

Error mapping:

- 404 ``trace_not_found``
- 410 ``trace_retired`` / ``model_retired``
- 400 ``cross_task_type`` / invalid range
- 409 ``duplicate_tag``
- 413 ``payload_too_large``
- 422 Pydantic validation (tag charset / length)
- 429 ``rate_limited`` with ``retry_after_seconds`` (FR-032 / FR-033)
- 403 ``missing_capability``
"""
from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Annotated, Any
from uuid import UUID

from datetime import datetime

import structlog
from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request, Response, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user_id_optional as _resolve_user_id_from_jwt
from app.core.db import get_db_session_no_rls, set_rls_user_id
from app.modules.admin_console import rate_limit, service
from app.modules.admin_console.auth import REPLAY_TRIGGER, TASK_TAG, require_capability
from app.modules.admin_console.repository import DuplicateTagError
from app.modules.admin_console.schemas import (
    DiffRequest,
    DiffResponse,
    ErrorResponse,
    RateLimitedError,
    ReplayRequest,
    ReplayResponse,
    TaskTagCreateRequest,
    TaskTagListResponse,
    TaskTagOut,
)
from app.modules.admin_console.service import (
    DEFAULT_PAYLOAD_LIMIT,
    CrossTaskTypeDiffError,
    ModelRetiredError,
    PayloadTooLargeError,
    ServiceError,
    TraceNotFoundError,
    TraceRetiredError,
)

router = APIRouter()

logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Auth dependency (B1 stub — resolve user_id from header for E2E)
# ---------------------------------------------------------------------------


async def get_caller_user_id(
    request: Request,
    jwt_user_id: UUID | None = Depends(_resolve_user_id_from_jwt),
) -> UUID:
    """Resolve the caller user_id.

    Resolution order:

    1. ``request.state.user_id`` — set by an upstream middleware (e.g.
       the production auth pipeline).
    2. JWT bearer token — decoded by :func:`app.api.deps.get_current_user_id_optional`.
    3. ``X-Admin-User-Id`` header — dev / E2E shortcut for tests that
       don't want to round-trip through the auth flow.

    Raises HTTP 401 when none of the above yields a valid UUID.
    """
    state_uid = getattr(request.state, "user_id", None)
    if isinstance(state_uid, UUID):
        return state_uid
    if jwt_user_id is not None:
        return jwt_user_id
    header_uid = request.headers.get("X-Admin-User-Id")
    if header_uid:
        try:
            return UUID(header_uid)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"error": "INVALID_USER_ID", "message": str(exc)},
            ) from exc
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail={"error": "AUTH_REQUIRED", "message": "caller user_id not resolved"},
    )


# ---------------------------------------------------------------------------
# DB session with RLS pre-set
# ---------------------------------------------------------------------------


async def _db_session_with_rls(
    resolved_user_id: Annotated[UUID, Depends(get_caller_user_id)],
) -> AsyncIterator[AsyncSession]:
    async for session in get_db_session_no_rls():
        await set_rls_user_id(session, resolved_user_id)
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        return


# ---------------------------------------------------------------------------
# Helpers — error body shape
# ---------------------------------------------------------------------------


def _error_response(
    *,
    code: str,
    message: str,
    status_code: int,
    details: dict[str, Any] | None = None,
) -> JSONResponse:
    body = ErrorResponse(error=code, message=message, details=details).model_dump()
    return JSONResponse(status_code=status_code, content=body)


def _service_error_to_response(exc: ServiceError) -> JSONResponse:
    return _error_response(
        code=exc.code,
        message=exc.message,
        status_code=exc.status_code,
        details=exc.details or None,
    )


def _rate_limited_response(exc: rate_limit.RateLimitedError) -> JSONResponse:
    """Build the 429 body + Retry-After header (FR-032 / FR-033)."""
    return JSONResponse(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        content=RateLimitedError(
            retry_after_seconds=exc.retry_after_seconds
        ).model_dump(),
        headers={"Retry-After": str(exc.retry_after_seconds)},
    )


# ---------------------------------------------------------------------------
# T022 placeholder — module liveness
# ---------------------------------------------------------------------------


@router.get("/health", status_code=200)
async def health() -> dict[str, str]:
    """Module liveness (placeholder, retained for parity with pm_dashboard)."""
    return {"status": "ok", "module": "admin_console", "stage": "b1"}


# ---------------------------------------------------------------------------
# Trace listing + node tree (FR-001 + detail panel support)
#
# B1 shipped the replay / diff / payload-slicing endpoints but did not
# expose a list endpoint or a per-trace node tree endpoint. The
# frontend LogCenter cannot operate without these two, so they land in
# B2 as a minimal completion. The shape mirrors admin_console service
# conventions — JSON envelopes, no streaming, RLS inherited via the
# admin caller resolution.
# ---------------------------------------------------------------------------


@router.get(
    "/traces",
    status_code=200,
    responses={
        200: {"description": "Latest traces (manual-refresh surface)"},
        401: {"description": "Auth required"},
    },
)
async def list_traces(
    user_id: Annotated[UUID, Depends(get_caller_user_id)],
    session: AsyncSession = Depends(_db_session_with_rls),
    limit: int = Query(100, ge=1, le=500),
    task_type: str | None = Query(None, description="Filter by task_type"),
    status_filter: str | None = Query(
        None,
        alias="status",
        description="Filter by status (success/failed/pending/running)",
    ),
    since: datetime | None = Query(
        None,
        description=(
            "Delta-query timestamp (FR-001): only return traces with "
            "created_at >= since. Used by the frontend manual-refresh "
            "path to fetch only what changed since the last fetch."
        ),
    ),
) -> dict[str, Any]:
    """Return the most-recent traces as a JSON envelope.

    B2 addition: supports ``GET /traces?limit=100`` (FR-001) plus the
    filter dimensions needed by the LogCenter filter bar (US1 / SC-001).
    The ``since`` param enables delta-query for manual refresh (FR-001).
    """
    rows = await service.list_traces(
        session,
        limit=limit,
        task_type=task_type,
        status_filter=status_filter,
        since=since,
    )
    return {
        "traces": [
            {
                "id": str(r["id"]),
                "task_id": str(r["task_id"]) if r["task_id"] else None,
                "task_type": r["task_type"],
                "prompt_version": r["prompt_version"],
                "model": r["model"],
                "status": r["status"],
                "error_message": r["error_message"],
                "replay_of": str(r["replay_of"]) if r["replay_of"] else None,
                "started_at": r["created_at"].isoformat() if r["created_at"] else None,
                "ended_at": r["updated_at"].isoformat() if r["updated_at"] else None,
                "duration_ms": None,
            }
            for r in rows
        ],
        "total": len(rows),
    }


@router.get(
    "/traces/{trace_id}/nodes",
    status_code=200,
    responses={
        200: {"description": "Node tree for the trace (master-detail span panel)"},
        404: {"description": "Trace not found"},
    },
)
async def list_trace_nodes(
    trace_id: UUID,
    user_id: Annotated[UUID, Depends(get_caller_user_id)],
    session: AsyncSession = Depends(_db_session_with_rls),
) -> dict[str, Any]:
    """Return the hierarchical node tree of one trace.

    The frontend detail panel renders this as a tree; INPUT/OUTPUT
    payloads are still served via ``/traces/{id}/nodes/{nid}/payload``
    with byte-range paging.
    """
    nodes = await service.list_trace_nodes(session, trace_id=trace_id)
    return {"trace_id": str(trace_id), "nodes": nodes}


# ---------------------------------------------------------------------------
# Tag endpoints (FR-017, FR-018, FR-020, FR-031)
# ---------------------------------------------------------------------------


@router.get(
    "/tasks/{task_id}/tags",
    response_model=TaskTagListResponse,
    status_code=200,
    responses={
        200: {"description": "List of tags owned by the caller"},
        401: {"description": "Auth required"},
    },
)
async def list_task_tags(
    task_id: UUID,
    user_id: Annotated[UUID, Depends(get_caller_user_id)],
    session: AsyncSession = Depends(_db_session_with_rls),
) -> TaskTagListResponse:
    rows = await service.list_tags(session, task_id)
    return TaskTagListResponse(
        tags=[
            TaskTagOut(tag=r.tag, created_at=r.created_at) for r in rows
        ]
    )


@router.post(
    "/tasks/{task_id}/tags",
    response_model=None,
    status_code=201,
    responses={
        201: {"description": "Tag created", "model": TaskTagOut},
        409: {"description": "Duplicate tag"},
        422: {"description": "Tag charset / length invalid"},
        403: {"description": "Missing TASK_TAG capability"},
    },
)
async def add_task_tag(
    task_id: UUID,
    body: Annotated[TaskTagCreateRequest, Body()],
    user_id: UUID = Depends(get_caller_user_id),
    _cap: bool = Depends(require_capability(TASK_TAG)),
    session: AsyncSession = Depends(_db_session_with_rls),
) -> TaskTagOut | JSONResponse:
    try:
        row = await service.add_tag(
            session, task_id=task_id, user_id=user_id, tag=body.tag
        )
    except DuplicateTagError as exc:
        return _error_response(
            code="DUPLICATE_TAG",
            message=str(exc),
            status_code=status.HTTP_409_CONFLICT,
        )
    return TaskTagOut(tag=row.tag, created_at=row.created_at)


@router.delete(
    "/tasks/{task_id}/tags",
    status_code=200,
    responses={
        200: {"description": "Tag removed (or was already absent)"},
        403: {"description": "Missing TASK_TAG capability"},
    },
)
async def delete_task_tag(
    task_id: UUID,
    tag: Annotated[str, Query(min_length=1, max_length=50)],
    user_id: Annotated[UUID, Depends(get_caller_user_id)],
    _cap: Annotated[bool, Depends(require_capability(TASK_TAG))],
    session: AsyncSession = Depends(_db_session_with_rls),
) -> dict[str, Any]:
    deleted = await service.remove_tag(
        session, task_id=task_id, user_id=user_id, tag=tag
    )
    return {"deleted": deleted, "tag": tag}


# ---------------------------------------------------------------------------
# Replay (FR-006, FR-007, FR-008, FR-010, FR-032)
# ---------------------------------------------------------------------------


@router.post(
    "/traces/{trace_id}/replay",
    response_model=None,
    status_code=201,
    responses={
        201: {"description": "Replay trace created", "model": ReplayResponse},
        403: {"description": "Missing REPLAY_TRIGGER capability"},
        404: {"description": "Trace not found"},
        410: {"description": "Model retired"},
        429: {"description": "Replay rate limit exceeded"},
    },
)
async def replay_trace(
    trace_id: UUID,
    user_id: Annotated[UUID, Depends(get_caller_user_id)],
    _cap: Annotated[bool, Depends(require_capability(REPLAY_TRIGGER))],
    session: AsyncSession = Depends(_db_session_with_rls),
    body: Annotated[ReplayRequest | None, Body()] = None,
) -> ReplayResponse | JSONResponse:
    try:
        rate_limit.replay_limiter(str(user_id))
    except rate_limit.RateLimitedError as exc:
        return _rate_limited_response(exc)
    try:
        result = await service.trigger_replay(
            session, orig_trace_id=trace_id, user_id=user_id
        )
    except TraceNotFoundError as exc:
        return _service_error_to_response(exc)
    except ModelRetiredError as exc:
        return _service_error_to_response(exc)
    return ReplayResponse(
        new_trace_id=result.new_trace_id,
        replay_of=result.replay_of,
        prompt_version=result.prompt_version,
        model=result.model,
        status=result.status,
        created_at=result.created_at,
    )


# ---------------------------------------------------------------------------
# Diff (FR-011, FR-012, FR-013, FR-014, FR-015, FR-033)
# ---------------------------------------------------------------------------


@router.post(
    "/traces/diff",
    response_model=None,
    status_code=200,
    responses={
        200: {"description": "Diff computed", "model": DiffResponse},
        400: {"description": "Cross task_type diff rejected"},
        403: {"description": "Missing admin capability"},
        404: {"description": "Trace not found"},
        429: {"description": "Diff rate limit exceeded"},
    },
)
async def diff_traces(
    body: Annotated[DiffRequest, Body()],
    user_id: Annotated[UUID, Depends(get_caller_user_id)],
    session: AsyncSession = Depends(_db_session_with_rls),
) -> DiffResponse | JSONResponse:
    try:
        rate_limit.diff_limiter(str(user_id))
    except rate_limit.RateLimitedError as exc:
        return _rate_limited_response(exc)
    try:
        result = await service.compute_diff(
            session,
            left_trace_id=body.left_trace_id,
            right_trace_id=body.right_trace_id,
            user_id=user_id,
        )
    except CrossTaskTypeDiffError as exc:
        return _service_error_to_response(exc)
    except TraceNotFoundError as exc:
        return _service_error_to_response(exc)
    return DiffResponse(
        left_trace_id=result.left_trace_id,
        right_trace_id=result.right_trace_id,
        task_type=result.task_type,
        nodes=[
            {
                "node_name": n["node_name"],
                "side": n["side"],
                "status_left": n.get("status_left"),
                "status_right": n.get("status_right"),
                "fields": n["fields"],
            }
            for n in result.nodes
        ],
        node_count=result.node_count,
    )


# ---------------------------------------------------------------------------
# Payload pagination (FR-025, FR-026, FR-027, FR-028, FR-029)
# ---------------------------------------------------------------------------


@router.get(
    "/traces/{trace_id}/nodes/{node_id}/payload",
    status_code=200,
    responses={
        200: {"description": "Byte-range chunk (text/plain)"},
        404: {"description": "Trace or node not found"},
        413: {"description": "Payload exceeds 50MB"},
    },
)
async def get_node_payload(
    trace_id: UUID,
    node_id: str,
    user_id: Annotated[UUID, Depends(get_caller_user_id)],
    session: AsyncSession = Depends(_db_session_with_rls),
    offset: int = Query(0, ge=0),
    limit: int = Query(DEFAULT_PAYLOAD_LIMIT, gt=0, le=DEFAULT_PAYLOAD_LIMIT),
) -> Response:
    try:
        chunk = await service.fetch_payload_chunk(
            session,
            trace_id=trace_id,
            node_id=node_id,
            offset=offset,
            limit=limit,
        )
    except PayloadTooLargeError as exc:
        return _service_error_to_response(exc)
    except TraceNotFoundError as exc:
        return _service_error_to_response(exc)
    # Build Content-Range header per FR-026.
    start = chunk.offset
    end = chunk.offset + chunk.limit
    total = chunk.total_size
    content_range = f"bytes {start}-{max(end - 1, 0)}/{total}"
    return Response(
        content=chunk.chunk,
        media_type="text/plain; charset=utf-8",
        headers={
            "Content-Range": content_range,
            "X-Total-Size": str(total),
            "X-Offset": str(start),
            "X-Limit": str(chunk.limit),
            "X-Remaining": str(chunk.remaining),
        },
    )


__all__ = ["get_caller_user_id", "router"]