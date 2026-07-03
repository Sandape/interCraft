"""[AC-040-US1] FR-007 — PlannerContext Pydantic model.

Replaces the dict-of-dict representation of planner context (long-term
memories + web research bundle) with a Pydantic BaseModel for runtime
validation and clearer field contracts.

Per spec Key Entities:
- ``PlannerContext`` — long-term memory + web research context container
- ``MemoryItem`` — single long-term memory record
- ``WebResearchBundle`` — Tavily / web search results

Field constraints (per AC-7.3a / AC-7.3b):
- ``memories: list[MemoryItem] = Field(...)`` — REQUIRED, non-Optional
  Constructing ``PlannerContext(web_research=...)`` without ``memories``
  raises ``pydantic.ValidationError`` with the field name in the error.
- The graph layer must guard against ``planner_context=None``; accessing
  ``state.planner_context.memories`` raises ``AttributeError`` rather
  than silently returning None.
"""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class MemoryItem(BaseModel):
    """A single long-term memory record surfaced into planner context."""

    content: str
    source: str
    created_at: datetime
    relevance_score: float


class WebResearchBundle(BaseModel):
    """Bundle of web-research results consumed by the planner node."""

    query: str
    results: list[dict] = Field(default_factory=list)


class PlannerContext(BaseModel):
    """Pydantic model replacing the dict-of-dict planner context.

    Per AC-7.3a, ``memories`` is a required (non-Optional) field. Constructing
    this model without ``memories`` raises ``pydantic.ValidationError``.

    Per AC-7.3b, callers must guard against ``state.planner_context is None``
    before accessing ``.memories`` (e.g. via an explicit None check) to
    surface ``AttributeError`` rather than silently proceeding.
    """

    memories: list[MemoryItem] = Field(...)
    web_research: WebResearchBundle


__all__ = ["MemoryItem", "PlannerContext", "WebResearchBundle"]
