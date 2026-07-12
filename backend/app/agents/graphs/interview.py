"""REQ-061 interview graph boundary helpers (T073).

Thin integration layer over ``app.agents.interview.graph`` — attaches
ExecutionContext, cancellation checks, strict checkpoint decode/upcast, and
per-stage attempt recording without rewriting the LangGraph topology.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping
from uuid import UUID, uuid4

from app.agents.interview.graph import InterviewGraph, get_interview_graph
from app.modules.ai_runtime.adapters import interview as interview_adapter
from app.modules.ai_runtime.compatibility import CompatibilityDecision
from app.modules.ai_runtime.execution_context import ExecutionContext

__all__ = [
    "InterviewGraph",
    "InterviewRuntimeBridge",
    "StageAttemptRecord",
    "attach_execution_context",
    "check_cancellation",
    "decode_pause_checkpoint",
    "get_interview_graph",
    "record_stage_attempt",
]


@dataclass(slots=True)
class StageAttemptRecord:
    stage_code: str
    attempt_id: UUID
    execution_id: UUID
    claim_generation: int
    status: str = "started"
    metadata: dict[str, Any] = field(default_factory=dict)


def attach_execution_context(
    state: dict[str, Any],
    ctx: ExecutionContext,
) -> dict[str, Any]:
    """Stamp canonical execution identity onto graph state (non-destructive)."""
    out = dict(state)
    out["ai_runtime"] = {
        **(out.get("ai_runtime") or {}),
        "root_task_id": str(ctx.root_task_id),
        "task_id": str(ctx.task_id),
        "execution_id": str(ctx.execution_id),
        "user_id": str(ctx.user_id),
        "tenant_id": str(ctx.tenant_id),
        "claim_generation": int(ctx.claim_generation),
        "capability_code": ctx.capability_code,
        "action_code": ctx.action_code,
        "stage_attempt_id": str(ctx.stage_attempt_id) if ctx.stage_attempt_id else None,
        "correlation_id": ctx.correlation_id,
        "behavior_version": ctx.behavior_version,
    }
    return out


def check_cancellation(
    state: Mapping[str, Any],
    *,
    cancel_requested: bool = False,
) -> bool:
    """Return True when the run must stop before next provider/domain write."""
    if cancel_requested:
        return True
    runtime = state.get("ai_runtime") if isinstance(state.get("ai_runtime"), dict) else {}
    if runtime.get("cancel_requested"):
        return True
    if state.get("cancel_requested"):
        return True
    status = str(state.get("domain_status") or state.get("status") or "").lower()
    if status in {"cancelling", "canceling", "cancelled", "canceled"}:
        return True
    return False


def decode_pause_checkpoint(
    *,
    version: str,
    payload: Mapping[str, Any],
) -> CompatibilityDecision:
    """Decode current/prior live pause checkpoint (N-1 via shared matrix)."""
    return interview_adapter.decode_live_artifact(
        kind="checkpoint",
        version=version,
        payload=payload,
    )


def record_stage_attempt(
    ctx: ExecutionContext,
    *,
    stage_code: str,
    status: str = "started",
    metadata: Mapping[str, Any] | None = None,
) -> StageAttemptRecord:
    attempt_id = ctx.stage_attempt_id or uuid4()
    return StageAttemptRecord(
        stage_code=stage_code,
        attempt_id=attempt_id,
        execution_id=ctx.execution_id,
        claim_generation=ctx.claim_generation,
        status=status,
        metadata=dict(metadata or {}),
    )


class InterviewRuntimeBridge:
    """Service-facing helper that binds ExecutionContext to InterviewGraph ops."""

    def __init__(self, graph: InterviewGraph | None = None) -> None:
        self.graph = graph or get_interview_graph()

    def seed_state(
        self,
        base: dict[str, Any],
        ctx: ExecutionContext,
    ) -> dict[str, Any]:
        return attach_execution_context(base, ctx)

    def should_abort(self, state: Mapping[str, Any], *, cancel_requested: bool = False) -> bool:
        return check_cancellation(state, cancel_requested=cancel_requested)

    def pause_checkpoint(
        self,
        *,
        session_id: str,
        round_no: int,
        scores: list[Mapping[str, Any]],
        schema_version: str = "2",
    ) -> dict[str, Any]:
        return interview_adapter.build_pause_checkpoint(
            session_id=session_id,
            round_no=round_no,
            scores=scores,
            schema_version=schema_version,
        )

    def decode_checkpoint(
        self,
        *,
        version: str,
        payload: Mapping[str, Any],
    ) -> CompatibilityDecision:
        return decode_pause_checkpoint(version=version, payload=payload)
