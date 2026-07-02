"""REQ-039 B1 — admin_console Pydantic v2 schemas.

Schemas for the 7 endpoints (tag CRUD, replay, diff, payload pagination):

- :class:`TaskTagOut` — single tag row.
- :class:`TaskTagListResponse` — list response (FR-017 GET).
- :class:`TaskTagCreateRequest` — POST body (FR-017 + FR-018).
- :class:`ReplayRequest` / :class:`ReplayResponse` — FR-006 / FR-007.
- :class:`DiffRequest` / :class:`DiffResponse` — FR-011 / FR-013.
- :class:`PayloadChunkResponse` — FR-025 / FR-026 byte-range response.
- :class:`AdminAuditEntry` — audit log projection.
- :class:`ErrorResponse` — uniform 4xx/5xx body for HTTPException.
- :class:`RateLimitedError` — 429 body shape (FR-032 / FR-033).

Validation invariants locked by AC matrix:

- Tag length 1-50 chars (FR-018 / E5).
- Tag regex ``^[A-Za-z0-9_\\-\\u4e00-\\u9fa5 ]+$`` (E5).
- ``offset`` >= 0, ``limit`` 1-51200, default 51200 (FR-025).
"""
from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

# ---------------------------------------------------------------------------
# Shared error body
# ---------------------------------------------------------------------------


class ErrorResponse(BaseModel):
    """Uniform 4xx/5xx body shape."""

    error: str
    message: str
    details: dict[str, Any] | None = None


class RateLimitedError(BaseModel):
    """429 body per FR-032 / FR-033."""

    reason: Literal["rate_limited"] = "rate_limited"
    retry_after_seconds: int


# ---------------------------------------------------------------------------
# Task tags (FR-016, FR-017, FR-018, FR-020)
# ---------------------------------------------------------------------------

_TAG_PATTERN = re.compile(r"^[A-Za-z0-9_\-一-龥 ]+$")


class TaskTagCreateRequest(BaseModel):
    """POST body for ``POST .../tasks/{id}/tags``.

    Tag must be 1-50 chars and match the regex in E5.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    tag: str = Field(
        ...,
        min_length=1,
        max_length=50,
        description="Tag text; 1-50 chars; charset = letters / digits / _ / - / CJK / space.",
    )

    @field_validator("tag")
    @classmethod
    def _validate_tag_charset(cls, v: str) -> str:
        if not _TAG_PATTERN.match(v):
            raise ValueError(
                "tag must match ^[A-Za-z0-9_\\-\\u4e00-\\u9fa5 ]+$ (letters, digits, _, -, CJK, space only)"
            )
        return v


class TaskTagOut(BaseModel):
    """GET / POST / DELETE response shape for a single tag."""

    tag: str
    created_at: datetime


class TaskTagListResponse(BaseModel):
    """GET /tasks/{id}/tags response — list of the caller's tags."""

    tags: list[TaskTagOut]


# ---------------------------------------------------------------------------
# Replay (FR-006, FR-007, FR-008, FR-010, FR-032)
# ---------------------------------------------------------------------------


class ReplayRequest(BaseModel):
    """POST body for replay endpoint."""

    model_config = ConfigDict(extra="forbid")

    note: str | None = Field(
        default=None,
        max_length=500,
        description="Optional developer note (e.g. 'verifying fix for #1234').",
    )


class ReplayResponse(BaseModel):
    """Response shape for replay endpoint."""

    new_trace_id: UUID
    replay_of: UUID
    prompt_version: str
    model: str
    status: str
    created_at: datetime


# ---------------------------------------------------------------------------
# Diff (FR-011, FR-012, FR-013, FR-014, FR-015, FR-033)
# ---------------------------------------------------------------------------


class DiffRequest(BaseModel):
    """POST body for diff endpoint."""

    model_config = ConfigDict(extra="forbid")

    left_trace_id: UUID
    right_trace_id: UUID


class DiffFieldEntry(BaseModel):
    """One field-level change in a node diff."""

    path: str = Field(
        ...,
        description="JSON-path-like location, e.g. 'input.messages[2].content'.",
    )
    op: Literal["add", "del", "mod"]
    left: Any | None = None
    right: Any | None = None


class DiffNodeEntry(BaseModel):
    """One node's diff contribution."""

    node_name: str
    side: Literal["left", "right", "both"]
    status_left: str | None = None
    status_right: str | None = None
    fields: list[DiffFieldEntry] = Field(default_factory=list)


class DiffResponse(BaseModel):
    """Response shape for diff endpoint."""

    left_trace_id: UUID
    right_trace_id: UUID
    task_type: str
    nodes: list[DiffNodeEntry]
    node_count: int


# ---------------------------------------------------------------------------
# Node IO payload (FR-025, FR-026, FR-027, FR-028, FR-029)
# ---------------------------------------------------------------------------


class PayloadChunkResponse(BaseModel):
    """Byte-range response for a single node's payload chunk.

    Note: in the FastAPI handler we return ``JSONResponse`` directly to
    set the ``Content-Range`` + ``X-Total-Size`` headers (FR-026); this
    Pydantic model is for OpenAPI documentation + tests.
    """

    trace_id: UUID
    node_id: str
    offset: int
    limit: int
    chunk: str
    total_size: int
    remaining: int


# ---------------------------------------------------------------------------
# Audit log (FR-008 / FR-014 / FR-030)
# ---------------------------------------------------------------------------


class AdminAuditEntry(BaseModel):
    """One row of the audit log (read-only projection)."""

    id: UUID
    user_id: UUID
    action: str
    target_kind: str
    target_id: UUID | None
    details: dict[str, Any]
    created_at: datetime


__all__ = [
    "AdminAuditEntry",
    "DiffFieldEntry",
    "DiffNodeEntry",
    "DiffRequest",
    "DiffResponse",
    "ErrorResponse",
    "PayloadChunkResponse",
    "RateLimitedError",
    "ReplayRequest",
    "ReplayResponse",
    "TaskTagCreateRequest",
    "TaskTagListResponse",
    "TaskTagOut",
]