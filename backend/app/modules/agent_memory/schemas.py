"""Pydantic schemas for agent_memory module.

US1 scope: only the schemas needed for storage / retrieval / extraction.
User-facing API schemas (list / search / delete / forget-me) are deferred
to US4.
"""
from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class SemanticMemoryOut(BaseModel):
    """Public representation of a semantic memory row."""

    id: UUID
    user_id: UUID
    fact_key: str
    fact_value: str
    confidence: float
    source: str
    version: int
    status: str
    schema_version: int
    meta: dict = Field(default_factory=dict)
    superseded_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class MemoryRetrieveIn(BaseModel):
    """Input shape for retrieve_active_memories().

    `query` is optional — US1 uses exact-key match, so query is informational
    only (logged to MemoryRetrievalLog). Future US2/US3 will use it for
    embedding similarity.
    """

    user_id: UUID
    graph: str
    node: str
    query: str | None = None
    token_budget: int = Field(default=500, ge=0, le=2000)


class MemoryRetrieveOut(BaseModel):
    """Result of a retrieval call."""

    memories: list[SemanticMemoryOut]
    token_budget_used: int
    retrieval_latency_ms: int
    degraded: bool = False  # True if retrieval hit an error and returned []


class MemoryExtractIn(BaseModel):
    """Input for extract_and_store().

    Captures the post-interview snapshot needed to extract facts. The
    caller (ARQ task) is responsible for assembling this from graph state.
    """

    user_id: UUID
    session_id: UUID
    position: str | None = None
    company: str | None = None
    interview_plan: dict | None = None
    interview_report: dict | None = None
    overall_score: float | None = None


__all__ = [
    "MemoryExtractIn",
    "MemoryRetrieveIn",
    "MemoryRetrieveOut",
    "SemanticMemoryOut",
]
