"""Phase 6 — Account schemas: lifecycle, export, import, notification."""
from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


# ---- Lifecycle ----

class DeleteAccountInput(BaseModel):
    confirmation: bool


class DeleteAccountResponse(BaseModel):
    status: str
    scheduled_purge_at: datetime | None = None
    cancellation_deadline: datetime | None = None
    message: str


class CancelDeletionResponse(BaseModel):
    status: str
    message: str


class DeletionStatusResponse(BaseModel):
    status: str
    is_deleting: bool
    scheduled_purge_at: datetime | None = None
    cancellation_deadline: datetime | None = None
    can_cancel: bool | None = None
    days_until_purge: int | None = None
    days_until_cancellation_deadline: int | None = None
    message: str | None = None


# ---- Export ----

class ExportInput(BaseModel):
    include: list[str] | None = None


class ExportCreateResponse(BaseModel):
    task_id: UUID
    status: str
    estimated_minutes: int = 3


class ExportStatusResponse(BaseModel):
    task_id: UUID
    status: str
    progress_pct: int = 0
    created_at: datetime
    completed_at: datetime | None = None
    download_url: str | None = None
    expires_at: datetime | None = None
    file_size_bytes: int | None = None


# ---- Import ----

class ImportResponse(BaseModel):
    branch_id: UUID
    branch_name: str
    blocks_count: int
    message: str


# ---- Notification ----

class NotificationOut(BaseModel):
    id: UUID
    type: str
    title: str
    message: str
    related_task_id: UUID | None = None
    is_read: bool
    created_at: datetime


class NotificationCenterResponse(BaseModel):
    notifications: list[NotificationOut]
    unread_count: int


# ---- Devices ----

class DeviceOut(BaseModel):
    id: UUID
    device_name: str | None = None
    browser: str | None = None
    ip: str | None = None
    last_seen_at: datetime | None = None
    created_at: datetime
    is_current: bool = False


class DevicesResponse(BaseModel):
    devices: list[DeviceOut]


class LogoutOtherDevicesResponse(BaseModel):
    message: str
    sessions_terminated: int


# ---- Security ----

class ChangePasswordInput(BaseModel):
    current_password: str
    new_password: str = Field(min_length=6)


class ChangePasswordResponse(BaseModel):
    message: str


class LoginHistoryItem(BaseModel):
    id: UUID
    ip: str | None = None
    user_agent: str | None = None
    device_name: str | None = None
    created_at: datetime


class LoginHistoryResponse(BaseModel):
    items: list[LoginHistoryItem]
