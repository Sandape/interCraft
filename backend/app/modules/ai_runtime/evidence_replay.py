"""REQ-061 read-only evidence replay (T041).

Reconstructs task timelines from events only. Creates zero provider/tool/
domain-write/execution/point/cost records.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.ai_runtime.models import AITask, AITaskEvent


@dataclass(frozen=True, slots=True)
class ReplayChoice:
    input_mode: str  # original_snapshot | latest_snapshot
    behavior_mode: str  # original_locked | current_stable


@dataclass(slots=True)
class ReplayReport:
    task_id: UUID
    complete: bool
    missing_sequences: list[int] = field(default_factory=list)
    events: list[dict[str, Any]] = field(default_factory=list)
    choice: ReplayChoice | None = None
    notes: list[str] = field(default_factory=list)


class EvidenceReplayService:
    """Event-only reconstruction — never mutates business facts."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def replay(
        self,
        *,
        task_id: UUID,
        user_id: UUID,
        choice: ReplayChoice | None = None,
    ) -> ReplayReport:
        task = await self.session.get(AITask, task_id)
        if task is None or task.user_id != user_id:
            raise LookupError("task not found")

        result = await self.session.execute(
            select(AITaskEvent)
            .where(AITaskEvent.task_id == task_id)
            .order_by(AITaskEvent.sequence.asc())
        )
        events = list(result.scalars().all())
        sequences = [e.sequence for e in events]
        missing: list[int] = []
        if sequences:
            expected = list(range(1, max(sequences) + 1))
            missing = [n for n in expected if n not in sequences]

        report = ReplayReport(
            task_id=task_id,
            complete=not missing,
            missing_sequences=missing,
            events=[
                {
                    "event_id": str(e.id),
                    "sequence": e.sequence,
                    "event_type": e.event_type,
                    "occurred_at": e.occurred_at.isoformat(),
                    "from_status": e.from_status,
                    "to_status": e.to_status,
                    "safe_message": e.safe_message,
                    "payload_summary": e.payload_summary,
                }
                for e in events
            ],
            choice=choice
            or ReplayChoice(
                input_mode="original_snapshot",
                behavior_mode="original_locked",
            ),
            notes=[
                "read_only_replay",
                "no_provider_calls",
                "no_point_or_cost_mutations",
            ],
        )
        return report


__all__ = ["EvidenceReplayService", "ReplayChoice", "ReplayReport"]
