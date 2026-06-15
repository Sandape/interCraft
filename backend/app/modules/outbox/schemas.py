"""M13 — Outbox Pydantic v2 schemas (T026)."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

EntityType = Literal["error_question", "activity", "user_profile", "job", "task"]
OperationType = Literal["create", "update", "delete"]
ReplayStatus = Literal["ok", "conflict", "failed"]


class ReplayEntry(BaseModel):
    client_entry_id: int = Field(ge=0, description="IndexedDB auto-increment id")
    entity_type: EntityType
    operation: OperationType
    entity_id: str = Field(min_length=1, description="UUID of the target entity")
    payload: dict[str, Any] = Field(default_factory=dict)
    entity_updated_at: datetime | None = Field(
        default=None, description="Client's last-known updated_at for conflict detection"
    )
    client_timestamp: int = Field(ge=0, description="Unix ms timestamp of client operation")


class ReplayInput(BaseModel):
    entries: list[ReplayEntry] = Field(max_length=30, description="Max 30 entries per batch")

    @field_validator("entries")
    @classmethod
    def check_max_entries(cls, v: list[ReplayEntry]) -> list[ReplayEntry]:
        if len(v) > 30:
            raise ValueError(f"Too many entries: {len(v)} (max 30)")
        return v


class ReplayResult(BaseModel):
    client_entry_id: int
    status: ReplayStatus
    server_entity: dict[str, Any] | None = None
    conflict_fields: list[str] | None = None
    error: str | None = None


class ReplaySummary(BaseModel):
    total: int
    ok: int
    conflict: int
    failed: int


class ReplayResponse(BaseModel):
    results: list[ReplayResult]
    summary: ReplaySummary


class OutboxStatusResponse(BaseModel):
    status: str = "healthy"
    recent_replays: dict[str, Any] = Field(default_factory=dict)
