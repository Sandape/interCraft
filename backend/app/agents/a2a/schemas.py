"""A2A framework schemas (REQ-031 US1, T004).

Pure Pydantic v2 types — no DB, no FastAPI, no LangGraph imports.
The DB-coupled surface lives in :mod:`app.agents.a2a.repository`; the
LangGraph-coupled surface lives in :mod:`app.agents.a2a.supervisor`.

Design notes:

- ``A2AMessage`` mirrors the entity in spec.md "Key Entities" and is
  the wire format for inter-agent communication. It is the schema
  that gets persisted to ``a2a_messages`` table.
- ``AgentDefinition`` is what developers register with the framework.
  ``input_schema`` / ``output_schema`` are Pydantic classes (not
  instances) so the framework can validate context payloads.
- ``RoutingDecision`` is the output of the user's routing function.
  ``next_agent=None`` means "end the graph" — LangGraph routes to END.
- ``SupervisorConfig`` bundles the agents + routing fn + global knobs
  (timeout / depth / cycle).
"""
from __future__ import annotations

from enum import Enum
from typing import Any, Callable
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator
from typing_extensions import TypedDict


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class A2AMessageStatus(str, Enum):
    """Terminal status of an ``A2AMessage``.

    ``pending`` is set when the delegation starts; ``success`` /
    ``failed`` / ``timeout`` are set when the agent returns or the
    runner gives up. The CHECK constraint on the ``a2a_messages``
    table mirrors this enum.
    """

    PENDING = "pending"
    SUCCESS = "success"
    FAILED = "failed"
    TIMEOUT = "timeout"


# ---------------------------------------------------------------------------
# AgentDefinition
# ---------------------------------------------------------------------------

class AgentDefinition(BaseModel):
    """Declarative registration of one agent.

    Attributes
    ----------
    name:
        Unique agent name within the graph (used as the LangGraph node
        name and as the ``child_agent`` in A2AMessage).
    role:
        Human-readable description of the agent's responsibility —
        logged at delegation start for traceability.
    input_schema:
        Optional Pydantic class used by the framework to validate the
        context slice before calling the agent's function. ``None``
        skips validation (pass raw dict through).
    output_schema:
        Optional Pydantic class used by the framework to validate the
        agent's return value. ``None`` skips validation.
    timeout_seconds:
        Per-agent timeout. ``None`` falls back to the Supervisor's
        ``default_timeout_seconds``.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    name: str = Field(..., min_length=1, max_length=128)
    role: str = Field(..., min_length=1, max_length=512)
    input_schema: type[BaseModel] | None = None
    output_schema: type[BaseModel] | None = None
    timeout_seconds: float | None = Field(default=None, gt=0.0)

    @field_validator("name")
    @classmethod
    def _name_no_double_underscore(cls, v: str) -> str:
        """Disallow names starting with ``__`` — reserved for internal nodes.

        The Supervisor inserts a hidden ``__supervisor_router__`` node;
        user-defined agent names must not collide with it.
        """
        if v.startswith("__"):
            raise ValueError(
                f"Agent name {v!r} starts with '__' which is reserved for "
                "internal framework nodes (e.g. __supervisor_router__)"
            )
        return v


# ---------------------------------------------------------------------------
# A2AMessage
# ---------------------------------------------------------------------------

class A2AMessage(BaseModel):
    """Standardized inter-agent message envelope (spec FR-016).

    Persisted to the ``a2a_messages`` table for debugging (FR-017).
    Linked to OTel trace via ``trace_id`` so per-invocation queries
    return every message in order (FR-018).
    """

    model_config = ConfigDict(use_enum_values=True)

    id: UUID = Field(default_factory=uuid4)
    trace_id: str = Field(..., min_length=1)
    thread_id: str = Field(..., min_length=1)
    parent_agent: str = Field(..., min_length=1)
    child_agent: str = Field(..., min_length=1)
    task: str = Field(..., min_length=1, max_length=512)
    context: dict[str, Any] = Field(default_factory=dict)
    expected_output: dict[str, Any] = Field(default_factory=dict)
    status: A2AMessageStatus = Field(default=A2AMessageStatus.PENDING)
    result: dict[str, Any] | None = None
    error_reason: str | None = None
    retry_count: int = Field(default=0, ge=0, le=5)
    duration_ms: int | None = Field(default=None, ge=0)
    created_at: str | None = None
    updated_at: str | None = None


# ---------------------------------------------------------------------------
# DelegationRecord
# ---------------------------------------------------------------------------

class DelegationRecord(BaseModel):
    """Runtime record of one delegation attempt (in-memory).

    Distinct from ``A2AMessage``: ``A2AMessage`` is the DB-shaped wire
    format with audit timestamps; ``DelegationRecord`` is what
    ``DelegationRunner.run`` returns to its caller (no timestamps,
    no UUID).
    """

    model_config = ConfigDict(use_enum_values=True)

    parent: str
    child: str
    task: str
    result: dict[str, Any] | None = None
    duration_ms: int = 0
    status: A2AMessageStatus = A2AMessageStatus.PENDING
    retry_count: int = 0
    error_reason: str | None = None


# ---------------------------------------------------------------------------
# RoutingDecision
# ---------------------------------------------------------------------------

class RoutingDecision(BaseModel):
    """Output of a routing function.

    Attributes
    ----------
    next_agent:
        Name of the agent to visit next, or ``None`` to end the graph
        (LangGraph routes to END).
    reason:
        Short human-readable reason — emitted as a ``a2a.routing_decision``
        structlog event for debugging.
    depth:
        Current delegation depth (0 for the entry node). The Supervisor
        increments before passing the decision on.
    """

    next_agent: str | None
    reason: str = ""
    depth: int = 0


# ---------------------------------------------------------------------------
# SupervisorConfig
# ---------------------------------------------------------------------------

class SupervisorConfig(BaseModel):
    """Full configuration for a :class:`Supervisor`.

    Attributes
    ----------
    agents:
        List of :class:`AgentDefinition`. Names must be unique.
    routing_fn:
        Callable that maps state → :class:`RoutingDecision`. Invoked
        by the Supervisor's hidden router node after each agent.
    default_timeout_seconds:
        Per-agent timeout fallback when ``AgentDefinition.timeout_seconds``
        is ``None``. Defaults to 30 s (spec FR-006).
    max_delegation_depth:
        Hard cap on delegation depth. Defaults to 3 (spec FR-007).
    enable_cycle_detection:
        When ``True`` (default), visiting an ancestor agent raises
        :class:`CycleDetectedError` (spec FR-007).
    parent_agent:
        Logical "root" agent name — used as ``parent_agent`` for the
        first delegation. Defaults to ``"__supervisor__"``.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    agents: list[AgentDefinition] = Field(..., min_length=1)
    routing_fn: Callable[..., RoutingDecision]  # type: ignore[type-arg]
    default_timeout_seconds: float = Field(default=30.0, gt=0.0)
    max_delegation_depth: int = Field(default=3, ge=1, le=10)
    enable_cycle_detection: bool = True
    parent_agent: str = "__supervisor__"

    @field_validator("agents")
    @classmethod
    def _agent_names_unique(cls, agents: list[AgentDefinition]) -> list[AgentDefinition]:
        names = [a.name for a in agents]
        if len(names) != len(set(names)):
            duplicates = {n for n in names if names.count(n) > 1}
            raise ValueError(f"Duplicate agent names in SupervisorConfig: {sorted(duplicates)}")
        return agents


# ---------------------------------------------------------------------------
# LangGraph state shape for the Supervisor's hidden router node
# ---------------------------------------------------------------------------

class SupervisorRouterState(TypedDict, total=False):
    """State fields that the Supervisor's hidden router node reads / writes.

    LangGraph ``StateGraph`` state is a TypedDict; this is the slice the
    framework reserves for its own routing bookkeeping. User agents
    should treat the outer state as opaque and read their own fields.
    """

    a2a_visited: list[str]
    a2a_depth: int


__all__ = [
    "A2AMessage",
    "A2AMessageStatus",
    "AgentDefinition",
    "DelegationRecord",
    "RoutingDecision",
    "SupervisorConfig",
    "SupervisorRouterState",
]