"""Pydantic schemas for sessions."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class DeviceSession(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    device_id: str
    device_name: str | None
    device_fingerprint: str
    last_seen_at: datetime
    last_seen_ip: str | None
    last_seen_ua: str | None
    trusted_at: datetime | None
    created_at: datetime
    is_current: bool = False


class SessionsListResponse(BaseModel):
    sessions: list[DeviceSession]


__all__ = ["DeviceSession", "SessionsListResponse"]
