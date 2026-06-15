"""Phase 6 — Content schemas: resources, help FAQ."""
from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


# ---- Resources ----

class ResourceOut(BaseModel):
    id: UUID
    title: str
    summary: str
    category: str
    tags: list[str] = []
    content_type: str = "article"
    read_time_minutes: int | None = None
    sort_order: int = 0
    created_at: datetime


class ResourceDetailOut(ResourceOut):
    content: str
    video_url: str | None = None
    related_resources: list[dict] = []


class ResourceListResponse(BaseModel):
    items: list[ResourceOut]
    total: int
    limit: int
    offset: int


# ---- FAQ ----

class FaqItem(BaseModel):
    id: UUID
    question: str
    category: str
    sort_order: int = 0


class FaqCategory(BaseModel):
    category: str
    label: str
    items: list[FaqItem]


class FaqListResponse(BaseModel):
    categories: list[FaqCategory]


class FaqDetailOut(BaseModel):
    id: UUID
    question: str
    answer: str
    category: str
    sort_order: int = 0
    created_at: datetime


# ---- Search ----

class SearchResultItem(BaseModel):
    id: UUID
    title: str | None = None
    question: str | None = None
    category: str
    score: float = 0.0


class SearchResponse(BaseModel):
    faq: list[SearchResultItem] = []
    resources: list[SearchResultItem] = []
