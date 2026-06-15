"""M12 — Lock Pydantic v2 schemas (T016)."""
from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

ResourceType = Literal["resume_branch", "error_question"]


class AcquireInput(BaseModel):
    resource_type: ResourceType
    resource_id: UUID


class LockStatus(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    locked: bool
    lock_id: str | None = None
    resource_type: str | None = None
    resource_id: str | None = None
    user_id: str | None = None
    user_name: str | None = None
    device_id: str | None = None
    acquired_at: datetime | None = None
    expires_at: datetime | None = None


class ReleaseResponse(BaseModel):
    lock_id: str
    resource_type: str
    resource_id: str
    released_at: datetime


class LockEvent(BaseModel):
    type: str
    resource_type: str
    resource_id: str
    user_id: str | None = None
    user_name: str | None = None
    device_id: str | None = None
    acquired_at: datetime | None = None
    released_at: datetime | None = None
    reason: str | None = None
    message: str | None = None


class HeartbeatMessage(BaseModel):
    type: Literal["lock.heartbeat"] = "lock.heartbeat"
    lock_id: str
    resource_type: str
    resource_id: str
