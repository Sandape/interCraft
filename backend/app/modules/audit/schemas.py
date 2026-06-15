"""Phase 6 — Audit schemas."""
from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class AuditLogOut(BaseModel):
    id: UUID
    action: str
    resource_type: str
    resource_id: UUID | None = None
    old_values: dict | None = None
    new_values: dict | None = None
    ip_address: str | None = None
    user_agent: str | None = None
    token_usage: int | None = None
    duration_ms: int | None = None
    node_input_summary: str | None = None
    node_output_summary: str | None = None
    created_at: datetime


class AuditLogListResponse(BaseModel):
    items: list[AuditLogOut]
    total: int
    limit: int
    offset: int


class AdminAuditLogOut(AuditLogOut):
    actor_id: UUID


class AdminAuditLogListResponse(BaseModel):
    items: list[AdminAuditLogOut]
    total: int
    limit: int
    offset: int
