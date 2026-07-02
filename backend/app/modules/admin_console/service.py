"""REQ-039 B1 — admin_console service layer.

Pure orchestration over :mod:`app.modules.admin_console.repository` +
the FastAPI-facing exceptions raised by the API layer. Public API:

Tag CRUD (FR-016, FR-017, FR-018, FR-020, FR-031):
- :func:`list_tags`
- :func:`add_tag`
- :func:`remove_tag`

Replay (FR-006, FR-007, FR-008, FR-010, FR-032):
- :func:`trigger_replay`

Diff (FR-011, FR-012, FR-013, FR-014, FR-015, FR-033):
- :func:`compute_diff`

Payload pagination (FR-025, FR-026, FR-027, FR-028, FR-029):
- :func:`fetch_payload_chunk`

All write paths append to ``admin_audit_log`` per FR-008 / FR-014 /
FR-030 / IC-7.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.admin_console import audit, repository
from app.modules.admin_console.models import TaskTag
from app.modules.admin_console.repository import DuplicateTagError

# ---------------------------------------------------------------------------
# Domain exceptions (mapped to HTTP status by the API layer)
# ---------------------------------------------------------------------------


class ServiceError(Exception):
    """Base for service-layer domain errors."""

    status_code: int = 500
    code: str = "INTERNAL_ERROR"

    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}


class TraceNotFoundError(ServiceError):
    status_code = 404
    code = "TRACE_NOT_FOUND"


class TraceRetiredError(ServiceError):
    """410 Gone — trace is past its retention window (FR-004)."""

    status_code = 410
    code = "TRACE_RETIRED"


class ModelRetiredError(ServiceError):
    """410 Gone — replay-target model is retired (FR-010)."""

    status_code = 410
    code = "MODEL_RETIRED"


class CrossTaskTypeDiffError(ServiceError):
    """400 Bad Request — diff across different task_type (FR-012)."""

    status_code = 400
    code = "CROSS_TASK_TYPE"


class PayloadTooLargeError(ServiceError):
    """413 Payload Too Large — payload exceeds 50MB (FR-029)."""

    status_code = 413
    code = "PAYLOAD_TOO_LARGE"

    def __init__(self, size: int, limit: int) -> None:
        super().__init__(
            f"payload size {size} exceeds limit {limit}",
            details={"size": size, "limit": limit},
        )
        self.size = size
        self.limit = limit


# ---------------------------------------------------------------------------
# Tags
# ---------------------------------------------------------------------------


_TAG_PATTERN = re.compile(r"^[A-Za-z0-9_\-一-龥 ]+$")


def validate_tag_text(tag: str) -> str:
    """Re-validate tag text in the service layer (defense in depth).

    Returns the canonical tag. Raises :class:`ValueError` (mapped to
    422 by the API layer) on length / charset violations.
    """
    if not isinstance(tag, str):
        raise ValueError("tag must be a string")
    stripped = tag.strip()
    if not (1 <= len(stripped) <= 50):
        raise ValueError(
            f"tag length must be 1-50 chars (got {len(stripped)})"
        )
    if not _TAG_PATTERN.match(stripped):
        raise ValueError(
            "tag must match ^[A-Za-z0-9_\\-\\u4e00-\\u9fa5 ]+$"
        )
    return stripped


async def list_tags(
    session: AsyncSession, task_id: UUID
) -> list[TaskTag]:
    """List all tags the calling user has on ``task_id`` (RLS scoped)."""
    return list(await repository.list_tags(session, task_id))


# ---------------------------------------------------------------------------
# Trace listing + node tree (B2 addition)
#
# These functions back the LogCenter frontend's master/detail view.
# They are intentionally minimal: SELECT-most-recent N, then derive
# the hierarchical node view from the trace's `node_payloads` JSON.
# ---------------------------------------------------------------------------


async def list_traces(
    session: AsyncSession,
    *,
    limit: int = 100,
    task_type: str | None = None,
    status_filter: str | None = None,
    since: datetime | None = None,
) -> list[dict[str, Any]]:
    """Return up to ``limit`` traces ordered by most-recent-first.

    Filters apply at SQL level. ``status_filter`` accepts the same
    vocabulary the frontend uses (``success`` / ``failed`` /
    ``pending`` / ``running``). Unknown filters are ignored (empty
    result) rather than rejected so the frontend can safely pass user
    input without sanitizing.

    ``since`` enables delta-query (FR-001): when provided, only rows
    with ``created_at >= since`` are returned. This is the manual-refresh
    path the frontend uses to avoid re-fetching the full 100 most-recent
    rows on every refresh.

    Implementation note: raw ``text()`` SQL is used here instead of
    ``select(Trace)`` because the auth module's ``User.avatar`` mapper
    relationship forward-references ``UserAvatar`` which is not in the
    registry when this service runs from a non-app process. Raw SQL
    keeps the response deterministic and mapper-free.
    """
    from sqlalchemy import text

    where_clauses: list[str] = []
    params: dict[str, Any] = {"lim": limit}
    if task_type:
        where_clauses.append("task_type = :task_type")
        params["task_type"] = task_type
    if status_filter:
        where_clauses.append("status = :status_filter")
        params["status_filter"] = status_filter
    if since is not None:
        where_clauses.append("created_at >= :since")
        params["since"] = since

    where_sql = (" WHERE " + " AND ".join(where_clauses)) if where_clauses else ""
    sql = text(
        "SELECT id, task_id, task_type, prompt_version, model, status, "
        "error_message, replay_of, created_at, updated_at "
        "FROM traces"
        f"{where_sql} "
        "ORDER BY created_at DESC LIMIT :lim"
    ).bindparams(**params)

    result = await session.execute(sql)
    return [dict(row._mapping) for row in result.fetchall()]


async def list_trace_nodes(
    session: AsyncSession,
    *,
    trace_id: UUID,
) -> list[dict[str, Any]]:
    """Return the node tree for a trace as a flat list.

    The frontend renders a hierarchical view; the JSON layout here
    keeps each node self-describing with name + status + timing so
    the panel can build the tree in one pass. ``payloads`` is the
    node_id set the frontend will lazy-load via the byte-range
    endpoint (FR-025..FR-027).
    """
    from sqlalchemy import text

    result = await session.execute(
        text(
            """
            WITH t AS (
                SELECT status, node_payloads
                FROM traces
                WHERE id = :trace_id
            ),
            object_nodes AS (
                SELECT
                    key AS node_id,
                    value AS payload,
                    t.status AS trace_status
                FROM t, jsonb_each(t.node_payloads)
                WHERE jsonb_typeof(t.node_payloads) = 'object'
                  AND jsonb_typeof(value) = 'object'
            ),
            array_nodes AS (
                SELECT
                    COALESCE(
                        value ->> 'name',
                        value ->> 'node_id',
                        'node_' || (ord - 1)::text
                    ) AS node_id,
                    value AS payload,
                    t.status AS trace_status
                FROM t, jsonb_array_elements(t.node_payloads) WITH ORDINALITY AS arr(value, ord)
                WHERE jsonb_typeof(t.node_payloads) = 'array'
                  AND jsonb_typeof(value) = 'object'
            )
            SELECT
                node_id,
                COALESCE(payload ->> 'name', node_id) AS name,
                COALESCE(payload ->> 'status', trace_status, 'unknown') AS status,
                payload ->> 'parent' AS parent,
                payload ->> 'started_at' AS started_at,
                payload ->> 'ended_at' AS ended_at,
                payload ? 'input' AS has_input,
                payload ? 'output' AS has_output
            FROM (
                SELECT * FROM object_nodes
                UNION ALL
                SELECT * FROM array_nodes
            ) nodes
            ORDER BY name ASC
            """
        ),
        {"trace_id": trace_id},
    )
    return [dict(row) for row in result.mappings().all()]


async def add_tag(
    session: AsyncSession,
    *,
    task_id: UUID,
    user_id: UUID,
    tag: str,
) -> TaskTag:
    """Insert a tag (hard-delete semantics: re-add = new row)."""
    canonical = validate_tag_text(tag)
    try:
        row = await repository.add_tag(
            session, task_id=task_id, user_id=user_id, tag=canonical
        )
    except DuplicateTagError:
        raise
    await audit.log_tag_added(session, user_id, task_id=task_id, tag=canonical)
    return row


async def remove_tag(
    session: AsyncSession,
    *,
    task_id: UUID,
    user_id: UUID,
    tag: str,
) -> bool:
    """Hard-delete a tag. Returns False when the tag didn't exist."""
    deleted = await repository.delete_tag(
        session, task_id=task_id, user_id=user_id, tag=tag
    )
    if deleted:
        await audit.log_tag_removed(session, user_id, task_id=task_id, tag=tag)
    return deleted


# ---------------------------------------------------------------------------
# Replay
# ---------------------------------------------------------------------------


@dataclass
class ReplayResult:
    new_trace_id: UUID
    replay_of: UUID
    prompt_version: str
    model: str
    status: str
    created_at: datetime


# Set of model strings that the demo backend treats as "retired" (FR-010).
# In production this is a DB-backed lookup against a model registry;
# for B1 we keep it process-local so tests can override via
# :func:`set_retired_models`.
_retired_models: set[str] = set()


def set_retired_models(models: set[str]) -> None:
    """Test / seed helper to mark models as retired (FR-010)."""
    global _retired_models
    _retired_models = set(models)


def reset_retired_models() -> None:
    """Test helper — clear the retired model set."""
    set_retired_models(set())


async def trigger_replay(
    session: AsyncSession,
    *,
    orig_trace_id: UUID,
    user_id: UUID,
) -> ReplayResult:
    """Create a new trace with ``replay_of=orig_trace_id``.

    Behaviour (FR-006 / FR-007 / FR-008 / FR-010):

    - Read the original trace (raise :class:`TraceNotFoundError` if missing).
    - If the original model is in the retired set, raise
      :class:`ModelRetiredError` (HTTP 410).
    - Copy ``prompt_version`` + ``model`` + ``input_payload`` (snapshot).
    - Insert a new trace with ``replay_of=orig_trace_id`` and
      ``status='pending'`` (the worker will pick it up; B1 only stores).
    - Audit-log the replay (FR-008 / IC-5).
    """
    orig = await repository.get_trace(session, orig_trace_id)
    if orig is None:
        raise TraceNotFoundError(f"trace {orig_trace_id} not found")
    if orig.model in _retired_models:
        raise ModelRetiredError(
            f"model {orig.model!r} has been retired; cannot replay"
        )
    new_row = await repository.insert_trace(
        session,
        task_id=orig.task_id,
        user_id=orig.user_id,
        task_type=orig.task_type,
        prompt_version=orig.prompt_version,
        model=orig.model,
        input_payload=dict(orig.input_payload or {}),
        status="pending",
        replay_of=orig.id,
        node_payloads=dict(orig.node_payloads or {}),
        error_message=None,
        trace_id=uuid4(),
    )
    await audit.log_replay(
        session,
        user_id,
        orig_trace_id=orig.id,
        new_trace_id=new_row.id,
    )
    return ReplayResult(
        new_trace_id=new_row.id,
        replay_of=orig.id,
        prompt_version=new_row.prompt_version,
        model=new_row.model,
        status=new_row.status,
        created_at=new_row.created_at,
    )


# ---------------------------------------------------------------------------
# Diff
# ---------------------------------------------------------------------------


def _align_nodes(
    left_payloads: dict[str, Any],
    right_payloads: dict[str, Any],
) -> list[dict[str, Any]]:
    """Align nodes by ``node_name`` (FR-013).

    Returns a list of dicts with keys ``node_name`` / ``side`` /
    ``status_left`` / ``status_right`` / ``fields`` (list of
    field-level changes). Nodes present in only one trace land in
    side='left' or side='right' with empty ``fields`` list.

    Field-level diff is computed via a shallow key-by-key comparison
    over the JSON-serialized input / output dicts. A real production
    diff would use a structured json-patch; for B1 we keep the output
    human-readable and stable.
    """
    keys = sorted(set(left_payloads) | set(right_payloads))
    out: list[dict[str, Any]] = []
    for name in keys:
        left = left_payloads.get(name)
        right = right_payloads.get(name)
        if left is not None and right is not None:
            fields = _diff_fields(left, right, prefix=name)
            out.append(
                {
                    "node_name": name,
                    "side": "both",
                    "status_left": (left.get("status") if isinstance(left, dict) else None),
                    "status_right": (right.get("status") if isinstance(right, dict) else None),
                    "fields": fields,
                }
            )
        elif left is not None:
            out.append(
                {
                    "node_name": name,
                    "side": "left",
                    "status_left": (left.get("status") if isinstance(left, dict) else None),
                    "status_right": None,
                    "fields": [],
                }
            )
        else:
            out.append(
                {
                    "node_name": name,
                    "side": "right",
                    "status_left": None,
                    "status_right": (right.get("status") if isinstance(right, dict) else None),
                    "fields": [],
                }
            )
    return out


def _diff_fields(
    left: dict[str, Any], right: dict[str, Any], *, prefix: str
) -> list[dict[str, Any]]:
    """Shallow field-level diff between two node payload dicts.

    Emits entries with ``path`` / ``op`` (``add`` | ``del`` | ``mod``)
    / ``left`` / ``right``. Path uses dotted notation for nested keys
    but only 1-level deep for B1; deeper traversal is a future FR.

    TODO(039-polish): spec FR-015 example path ``input.messages[2].content``
    implies nested traversal. When the polish batch lands, replace this
    with a recursive walker that emits ``input.messages[2].content``
    style paths and array-index segments. Until then the API contract
    documents the 1-level limit via :class:`DiffFieldEntry`'s schema
    description.
    """
    keys = sorted(set(left) | set(right))
    fields: list[dict[str, Any]] = []
    for key in keys:
        lv = left.get(key)
        rv = right.get(key)
        if lv is None and rv is None:
            continue
        if lv is None:
            fields.append({"path": f"{prefix}.{key}", "op": "add", "left": None, "right": rv})
        elif rv is None:
            fields.append({"path": f"{prefix}.{key}", "op": "del", "left": lv, "right": None})
        elif lv != rv:
            fields.append({"path": f"{prefix}.{key}", "op": "mod", "left": lv, "right": rv})
    return fields


@dataclass
class DiffResult:
    left_trace_id: UUID
    right_trace_id: UUID
    task_type: str
    nodes: list[dict[str, Any]]
    node_count: int


async def compute_diff(
    session: AsyncSession,
    *,
    left_trace_id: UUID,
    right_trace_id: UUID,
    user_id: UUID,
) -> DiffResult:
    """Compute a node-aligned diff between two traces.

    Rejects cross-task-type diffs with :class:`CrossTaskTypeDiffError`
    (FR-012 → HTTP 400).
    """
    if left_trace_id == right_trace_id:
        raise CrossTaskTypeDiffError(
            "left_trace_id and right_trace_id must differ"
        )
    rows = await repository.get_traces_by_ids(
        session, [left_trace_id, right_trace_id]
    )
    by_id = {r.id: r for r in rows}
    left = by_id.get(left_trace_id)
    right = by_id.get(right_trace_id)
    if left is None or right is None:
        missing = left_trace_id if left is None else right_trace_id
        raise TraceNotFoundError(f"trace {missing} not found")
    if left.task_type != right.task_type:
        raise CrossTaskTypeDiffError(
            f"只能 diff 同 task_type 的两条 trace (left={left.task_type}, "
            f"right={right.task_type})"
        )
    left_payloads = dict(left.node_payloads or {})
    right_payloads = dict(right.node_payloads or {})
    nodes = _align_nodes(left_payloads, right_payloads)
    await audit.log_diff(
        session,
        user_id,
        left_trace_id=left.id,
        right_trace_id=right.id,
        node_count=len(nodes),
    )
    return DiffResult(
        left_trace_id=left.id,
        right_trace_id=right.id,
        task_type=left.task_type,
        nodes=nodes,
        node_count=len(nodes),
    )


# ---------------------------------------------------------------------------
# Payload pagination
# ---------------------------------------------------------------------------


DEFAULT_PAYLOAD_LIMIT = 51200
MAX_PAYLOAD_BYTES = 50 * 1024 * 1024  # 50MB per FR-029


@dataclass
class PayloadChunk:
    trace_id: UUID
    node_id: str
    offset: int
    limit: int
    chunk: str
    total_size: int
    remaining: int


def _normalize_chunk_args(offset: int, limit: int) -> tuple[int, int]:
    if offset < 0:
        raise ValueError("offset must be >= 0")
    if limit <= 0:
        raise ValueError("limit must be > 0")
    if limit > DEFAULT_PAYLOAD_LIMIT:
        # Cap at one chunk's worth to keep memory bounded; callers can
        # re-request with offset to walk the payload.
        limit = DEFAULT_PAYLOAD_LIMIT
    return offset, limit


async def fetch_payload_chunk(
    session: AsyncSession,
    *,
    trace_id: UUID,
    node_id: str,
    offset: int = 0,
    limit: int = DEFAULT_PAYLOAD_LIMIT,
) -> PayloadChunk:
    """Return one byte-range slice of a node's payload (FR-025/026/029).

    Raises :class:`PayloadTooLargeError` when the underlying payload
    exceeds 50MB; :class:`TraceNotFoundError` when the trace is
    missing; :class:`ValueError` on bad offset/limit.
    """
    offset, limit = _normalize_chunk_args(offset, limit)
    res = await repository.list_node_payload(session, trace_id, node_id)
    if res is None:
        # Trace missing OR node missing — surface as 404.
        raise TraceNotFoundError(
            f"node {node_id!r} not found in trace {trace_id}"
        )
    raw, total_size = res
    if total_size > MAX_PAYLOAD_BYTES:
        raise PayloadTooLargeError(total_size, MAX_PAYLOAD_BYTES)
    start = min(offset, total_size)
    end = min(start + limit, total_size)
    chunk = raw[start:end]
    return PayloadChunk(
        trace_id=trace_id,
        node_id=node_id,
        offset=start,
        limit=end - start,
        chunk=chunk,
        total_size=total_size,
        remaining=max(0, total_size - end),
    )


__all__ = [
    "CrossTaskTypeDiffError",
    "DEFAULT_PAYLOAD_LIMIT",
    "DiffResult",
    "MAX_PAYLOAD_BYTES",
    "ModelRetiredError",
    "PayloadChunk",
    "PayloadTooLargeError",
    "ReplayResult",
    "ServiceError",
    "TraceNotFoundError",
    "TraceRetiredError",
    "add_tag",
    "compute_diff",
    "fetch_payload_chunk",
    "list_tags",
    "remove_tag",
    "reset_retired_models",
    "set_retired_models",
    "trigger_replay",
    "validate_tag_text",
]