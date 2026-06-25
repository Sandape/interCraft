"""SemanticMemory + MemoryRetrievalLog SQLAlchemy models.

Per specs/028-long-term-memory/spec.md §Key Entities.

US1 scope: semantic memories only. Episodic / procedural memory tables
are deferred (US2/US3) — see tasks.md.

RLS: both tables FORCE ROW LEVEL SECURITY with `user_id = app.user_id` policy
(mirrors migrations/versions/0001_initial.py::_enable_rls). The retrieval
path always sets `app.user_id` before SELECT so RLS hides other users'
memories automatically.
"""
from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.core.ids import new_uuid_v7


class SemanticMemory(Base):
    """A user fact extracted from prior agent interactions.

    Examples:
      - fact_key="target_position", fact_value="前端开发工程师"
      - fact_key="identified_weakness", fact_value="system_design"
      - fact_key="stated_preference", fact_value="concise_hints"

    Conflict resolution: when a new fact with the same (user_id, fact_key)
    is upserted, the old row's `status` flips to `superseded` and
    `superseded_at` is stamped. The old row is NOT deleted (spec SC-006
    "marked superseded, not deleted in 100% of cases").

    Schema versioning (FR-004): `schema_version` lets extraction logic
    evolve without invalidating stored data. `version` is the per-fact
    revision counter (1, 2, 3, ...).
    """

    __tablename__ = "semantic_memories"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=new_uuid_v7
    )
    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    fact_key: Mapped[str] = mapped_column(Text, nullable=False)
    fact_value: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[float] = mapped_column(
        Numeric(3, 2), nullable=False, server_default=text("0.5")
    )
    # extracted_from_llm_output | user_asserted | system_inferred
    source: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("'extracted_from_llm_output'")
    )
    version: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("1")
    )
    # active | superseded
    status: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("'active'")
    )
    schema_version: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("1")
    )
    # Free-form metadata: extraction source session_id, model name, etc.
    meta: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    superseded_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    superseded_by: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("semantic_memories.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('active', 'superseded')", name="ck_semantic_memories_status"
        ),
        CheckConstraint(
            "source IN ('extracted_from_llm_output', 'user_asserted', 'system_inferred')",
            name="ck_semantic_memories_source",
        ),
        CheckConstraint(
            "confidence >= 0.0 AND confidence <= 1.0",
            name="ck_semantic_memories_confidence",
        ),
        CheckConstraint("version >= 1", name="ck_semantic_memories_version"),
        CheckConstraint("schema_version >= 1", name="ck_semantic_memories_schema_version"),
        # One active fact per (user_id, fact_key) — enforced via partial unique index.
        # Superseded rows keep their old (user_id, fact_key) value; the partial index
        # only constrains rows where status='active'.
        Index(
            "uq_semantic_memories_active_user_key",
            "user_id",
            "fact_key",
            unique=True,
            postgresql_where=text("status = 'active'"),
        ),
        Index(
            "idx_semantic_memories_user_active",
            "user_id",
            "created_at",
            postgresql_where=text("status = 'active'"),
        ),
    )


class MemoryRetrievalLog(Base):
    """Observability row recording what memories were injected into a call.

    Per spec FR-012: "Memory retrieval MUST be observable — which memories
    were injected into which call is logged."

    One row per `retrieve_active_memories()` call. `retrieved_memory_ids`
    is a JSONB array of UUIDs (strings for portability).
    """

    __tablename__ = "memory_retrieval_logs"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=new_uuid_v7
    )
    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    graph: Mapped[str] = mapped_column(Text, nullable=False)
    node: Mapped[str] = mapped_column(Text, nullable=False)
    query: Mapped[str | None] = mapped_column(Text, nullable=True)
    retrieved_memory_ids: Mapped[list] = mapped_column(
        JSONB, nullable=False, server_default=text("'[]'::jsonb")
    )
    token_budget_used: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    retrieval_latency_ms: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        Index(
            "idx_memory_retrieval_logs_user_created",
            "user_id",
            "created_at",
        ),
    )


__all__ = ["MemoryRetrievalLog", "SemanticMemory"]
