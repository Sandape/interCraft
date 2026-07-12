"""Trusted execution context kept outside model-controlled Tool arguments."""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from typing import Any, Literal
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

_AUTHORITY_FIELDS = frozenset(
    {
        "user_id",
        "owner_id",
        "binding_id",
        "binding_epoch",
        "claim_generation",
        "task_id",
        "tool_call_id",
        "idempotency_key",
        "authorization",
        "permission",
        "session",
        "trace_id",
        "correlation_id",
    }
)


def sanitize_tool_arguments(arguments: Mapping[str, Any]) -> dict[str, Any]:
    """Copy arguments while discarding fields owned by the runtime boundary."""
    return {
        key: value
        for key, value in arguments.items()
        if key.strip().lower() not in _AUTHORITY_FIELDS
    }


@dataclass(frozen=True, slots=True)
class ToolContext:
    user_id: UUID
    task_id: UUID
    tool_call_id: str
    idempotency_key: str
    correlation_id: str
    trace_id: str
    channel: Literal["wechat", "web", "cli"]
    binding_id: UUID
    binding_epoch: int
    claim_generation: int
    session: AsyncSession
    cancel_check: Callable[[], Awaitable[bool]]

    async def is_cancel_requested(self) -> bool:
        return bool(await self.cancel_check())


__all__ = ["ToolContext", "sanitize_tool_arguments"]
