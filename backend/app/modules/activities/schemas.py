"""Activity Pydantic schemas."""
from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel


class ActivityOut(BaseModel):
    id: UUID
    type: str
    actor_type: str
    payload_json: dict[str, Any]
    request_id: str | None
    occurred_at: datetime

    model_config = {"from_attributes": True}


class ActivityListOut(BaseModel):
    items: list[ActivityOut]
    next_cursor: str | None
    has_more: bool


class LogActivityInput(BaseModel):
    user_id: UUID
    type: str
    actor_type: str = "system"
    payload_json: dict[str, Any] = {}
    request_id: str | None = None


__all__ = ["ActivityListOut", "ActivityOut", "LogActivityInput"]
