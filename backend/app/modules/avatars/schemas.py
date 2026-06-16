"""Pydantic schemas for the avatar module (Feature 013)."""
from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class AvatarOut(BaseModel):
    """Response shape returned by upload and fetch (mirror) routes."""

    model_config = ConfigDict(from_attributes=True)

    avatar_id: UUID
    url: str
    content_type: str
    byte_size: int
    width: int | None = None
    height: int | None = None
    created_at: datetime


class AvatarRemoveResponse(BaseModel):
    status: str = Field(default="removed")
    message: str = Field(default="已移除头像")


__all__ = ["AvatarOut", "AvatarRemoveResponse"]
