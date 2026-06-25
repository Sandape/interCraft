"""A2A Multi-Agent Orchestration Library (feature 031 US1).

Self-contained library (Constitution I: Library-First) that extracts the
Supervisor + subgraph orchestration pattern from feature 025 into a
reusable component. New multi-agent graphs declare their agents and
routing rules; the framework compiles a ``StateGraph`` with built-in
timeout, depth cap, cycle detection, and A2A message persistence.

Public surface:

- :class:`AgentDefinition` — declares one agent's name, role, schema, timeout.
- :class:`A2AMessage` — the standardized inter-agent message envelope.
- :class:`DelegationRecord` — the runtime record of one delegation attempt.
- :class:`RoutingDecision` — what the routing function returns.
- :class:`SupervisorConfig` — full configuration for a ``Supervisor``.
- :class:`Supervisor` — compiles a ``StateGraph`` from agent list + routing fn.
- :class:`DelegationRunner` — runs one delegation with timeout + retry + persistence.
- :class:`A2AMessageRepository` — DB persistence helper.
- :class:`CycleDetectedError` — raised when an agent visits itself / ancestor.
- :class:`DepthExceededError` — raised when delegation depth exceeds the cap.
- :class:`AgentTimeoutError` — raised when a delegation times out.

All routing/state types in :mod:`app.agents.a2a.schemas` are pure
Pydantic and have no DB / FastAPI dependency; the DB-coupled surface
(:mod:`app.agents.a2a.repository`) is a small adapter over
``get_session_factory``.
"""
from __future__ import annotations

from app.agents.a2a.delegation import DelegationRunner, AgentTimeoutError
from app.agents.a2a.repository import A2AMessageRepository
from app.agents.a2a.routing import (
    CycleDetectedError,
    DepthExceededError,
    check_cycle,
    decide,
    enforce_depth,
)
from app.agents.a2a.schemas import (
    A2AMessage,
    A2AMessageStatus,
    AgentDefinition,
    DelegationRecord,
    RoutingDecision,
    SupervisorConfig,
)
from app.agents.a2a.supervisor import Supervisor

__all__ = [
    "A2AMessage",
    "A2AMessageRepository",
    "A2AMessageStatus",
    "AgentDefinition",
    "AgentTimeoutError",
    "CycleDetectedError",
    "DelegationRecord",
    "DelegationRunner",
    "DepthExceededError",
    "RoutingDecision",
    "Supervisor",
    "SupervisorConfig",
    "check_cycle",
    "decide",
    "enforce_depth",
]