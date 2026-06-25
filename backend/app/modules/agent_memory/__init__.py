"""agent_memory — Cross-session long-term memory layer for agents (REQ-028 US1).

Self-contained module (Constitution I — Library-First) providing:
  - SemanticMemory ORM model + repository (latest-wins conflict resolution)
  - Rule-based extractor (target_position / target_company / identified_weakness)
  - Token-budget-aware retriever (graceful degrade on DB error)
  - PII redactor (email/phone regex)
  - MemoryRetrievalLog observability table

US1 scope: interview graph only (planner_context retrieves, ARQ task extracts
post-interview). US2/US3/US4 (episodic / procedural / user-control API) are
deferred — see specs/028-long-term-memory/tasks.md.

See README.md for API and examples.
"""
from __future__ import annotations

from app.modules.agent_memory.models import MemoryRetrievalLog, SemanticMemory
from app.modules.agent_memory.schemas import (
    MemoryExtractIn,
    MemoryRetrieveIn,
    MemoryRetrieveOut,
    SemanticMemoryOut,
)

__all__ = [
    "MemoryExtractIn",
    "MemoryRetrieveIn",
    "MemoryRetrieveOut",
    "MemoryRetrievalLog",
    "SemanticMemory",
    "SemanticMemoryOut",
]
