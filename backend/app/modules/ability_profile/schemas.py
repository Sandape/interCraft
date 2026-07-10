"""Pydantic schemas for Personal Ability Profile module.

Per contracts/ — profile, share, export, admin.
PIN removed per Feature 024 US5.
"""
from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


# ─── Dashboard ───────────────────────────────────────────────────────────────

class DimensionHistoryPoint(BaseModel):
    date: str
    actual_score: float
    ideal_score: float


class DashboardDimension(BaseModel):
    key: str
    label_zh: str
    actual_score: float
    ideal_score: float
    self_assessed_score: float | None = None
    source: str
    trend: str = "stable"
    history: list[DimensionHistoryPoint] = []


class DashboardResponse(BaseModel):
    dimensions: list[DashboardDimension]
    generated_at: datetime


class DashboardOut(BaseModel):
    data: DashboardResponse


# ─── Share Link ──────────────────────────────────────────────────────────────

class ShareLinkCreate(BaseModel):
    expires_in_hours: int | None = Field(default=None, ge=1, le=720)


class ShareLinkResponse(BaseModel):
    id: UUID
    token: str
    url: str
    expires_at: datetime | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class ShareLinkListResponse(BaseModel):
    id: UUID
    token: str
    url: str
    expires_at: datetime | None = None
    revoked_at: datetime | None = None
    access_count: int = 0
    last_accessed_at: datetime | None = None
    status: str = "active"
    created_at: datetime

    model_config = {"from_attributes": True}


class ShareLinkListOut(BaseModel):
    data: list[ShareLinkListResponse]


class SharedProfileOwner(BaseModel):
    name: str
    title: str | None = None


class SharedProfileDimension(BaseModel):
    key: str
    label_zh: str
    actual_score: float
    ideal_score: float = 10.0


class SharedProfileResponse(BaseModel):
    owner: SharedProfileOwner
    generated_at: datetime
    dimensions: list[SharedProfileDimension]


class SharedProfileOut(BaseModel):
    data: SharedProfileResponse


# ─── Export ──────────────────────────────────────────────────────────────────

class ExportTriggerResponse(BaseModel):
    export_id: UUID
    status: str = "pending"
    estimated_wait_seconds: int = 10
    requested_at: datetime


class ExportStatusResponse(BaseModel):
    export_id: UUID
    status: str
    file_size_bytes: int | None = None
    download_url: str | None = None
    requested_at: datetime
    completed_at: datetime | None = None


class ExportListItem(BaseModel):
    export_id: UUID
    status: str
    file_size_bytes: int | None = None
    requested_at: datetime
    completed_at: datetime | None = None


class ExportListOut(BaseModel):
    data: list[ExportListItem]


# ─── Admin ───────────────────────────────────────────────────────────────────

class AdminDashboardResponse(DashboardResponse):
    viewed_user_id: UUID
    viewed_user_name: str


# ─── Shared helpers used by api.py ───────────────────────────────────────────

class ShareLinkCreateOut(BaseModel):
    data: ShareLinkResponse


class ExportTriggerOut(BaseModel):
    data: ExportTriggerResponse


class ExportStatusOut(BaseModel):
    data: ExportStatusResponse


class AdminDashboardOut(BaseModel):
    data: AdminDashboardResponse


__all__ = [
    "AdminDashboardOut",
    "AdminDashboardResponse",
    "DashboardDimension",
    "DashboardOut",
    "DashboardResponse",
    "DimensionHistoryPoint",
    "ExportListItem",
    "ExportListOut",
    "ExportStatusOut",
    "ExportStatusResponse",
    "ExportTriggerOut",
    "ExportTriggerResponse",
    "ShareLinkCreate",
    "ShareLinkCreateOut",
    "ShareLinkListOut",
    "ShareLinkListResponse",
    "ShareLinkResponse",
    "SharedProfileDimension",
    "SharedProfileOut",
    "SharedProfileOwner",
    "SharedProfileResponse",
]
