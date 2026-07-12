"""REQ-061 framework-neutral ExecutionContext (T021).

Composition roots (FastAPI, ARQ, CLI, graph) assemble this context; domain
code and provider gateway consume it without importing web frameworks.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession


@dataclass(slots=True)
class RetryBudget:
    max_attempts: int = 3
    attempts_used: int = 0

    @property
    def remaining(self) -> int:
        return max(0, self.max_attempts - self.attempts_used)

    def consume(self) -> None:
        if self.remaining <= 0:
            raise RuntimeError("retry budget exhausted")
        self.attempts_used += 1


@dataclass(slots=True)
class CostBudget:
    max_points: int | None = None
    spent_points: int = 0
    max_usd: str | None = None

    def admit_points(self, points: int) -> None:
        if self.max_points is not None and self.spent_points + points > self.max_points:
            raise RuntimeError("point cost budget exceeded")
        self.spent_points += points


@dataclass(frozen=True, slots=True)
class ExecutionContext:
    """Shared execution identity for one AI run across adapters and providers."""

    root_task_id: UUID
    task_id: UUID
    execution_id: UUID
    user_id: UUID
    tenant_id: UUID
    claim_generation: int
    capability_code: str
    action_code: str
    session: AsyncSession | None = None
    stage_attempt_id: UUID | None = None
    authorization_receipt_id: UUID | None = None
    correlation_id: str | None = None
    trace_id: str | None = None
    behavior_version: str | None = None
    retry_budget: RetryBudget = field(default_factory=RetryBudget)
    cost_budget: CostBudget = field(default_factory=CostBudget)
    metadata: dict[str, Any] = field(default_factory=dict)

    def with_stage(self, stage_attempt_id: UUID) -> ExecutionContext:
        return ExecutionContext(
            root_task_id=self.root_task_id,
            task_id=self.task_id,
            execution_id=self.execution_id,
            user_id=self.user_id,
            tenant_id=self.tenant_id,
            claim_generation=self.claim_generation,
            capability_code=self.capability_code,
            action_code=self.action_code,
            session=self.session,
            stage_attempt_id=stage_attempt_id,
            authorization_receipt_id=self.authorization_receipt_id,
            correlation_id=self.correlation_id,
            trace_id=self.trace_id,
            behavior_version=self.behavior_version,
            retry_budget=self.retry_budget,
            cost_budget=self.cost_budget,
            metadata=dict(self.metadata),
        )


def build_execution_context(
    *,
    root_task_id: UUID,
    task_id: UUID,
    execution_id: UUID,
    user_id: UUID,
    tenant_id: UUID,
    claim_generation: int,
    capability_code: str,
    action_code: str,
    session: AsyncSession | None = None,
    **kwargs: Any,
) -> ExecutionContext:
    return ExecutionContext(
        root_task_id=root_task_id,
        task_id=task_id,
        execution_id=execution_id,
        user_id=user_id,
        tenant_id=tenant_id,
        claim_generation=claim_generation,
        capability_code=capability_code,
        action_code=action_code,
        session=session,
        **kwargs,
    )


__all__ = [
    "CostBudget",
    "ExecutionContext",
    "RetryBudget",
    "build_execution_context",
]
