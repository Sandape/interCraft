"""Phase 7 — Global search response schemas."""
from __future__ import annotations

from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field

SearchType = Literal["resume", "interview", "ability", "faq", "resource"]


class SearchResultItem(BaseModel):
    id: str
    type: SearchType
    title: str
    subtitle: str | None = None
    destination: str
    score: float
    meta: dict[str, Any] = Field(default_factory=dict)


class SearchGroup(BaseModel):
    type: SearchType
    label: str
    items: list[SearchResultItem]
    total: int


class SearchResponse(BaseModel):
    groups: list[SearchGroup]
    query: str
    took_ms: int


__all__ = ["SearchResultItem", "SearchGroup", "SearchResponse", "SearchType"]
