"""ErrorService — business logic + state machine for error questions.

DEC-P2-5: fresh(practicing)→practicing(f=1-2)→mastered(f=0)
"""
from __future__ import annotations

from uuid import UUID

from fastapi import HTTPException

from app.modules.errors.models import ErrorQuestion
from app.modules.errors.repository import ErrorQuestionRepository

# Valid status transitions (current → allowed next)
VALID_TRANSITIONS: dict[str, set[str]] = {
    "fresh": {"practicing", "archived"},
    "practicing": {"mastered", "fresh", "archived"},
    "mastered": {"fresh", "archived"},  # fresh = via reset only
    "archived": set(),  # terminal
}

# frequency constraints per status
STATUS_FREQUENCY: dict[str, int | tuple[int, int] | None] = {
    "fresh": 3,
    "practicing": (1, 2),
    "mastered": 0,
    "archived": None,
}


def reduce_status(
    current_status: str,
    target_status: str,
    current_frequency: int,
    target_frequency: int | None,
) -> tuple[str, int]:
    """Validate and compute the next (status, frequency) pair."""
    if current_status not in VALID_TRANSITIONS:
        raise HTTPException(status_code=409, detail=f"Unknown current status: {current_status}")

    allowed = VALID_TRANSITIONS.get(current_status, set())
    if target_status not in allowed:
        raise HTTPException(
            status_code=409,
            detail={
                "error": {
                    "code": "invalid_state_transition",
                    "message": f"Cannot transition from '{current_status}' to '{target_status}'.",
                    "details": {"from": current_status, "to": target_status},
                }
            },
        )

    # Determine frequency based on target status
    freq_range = STATUS_FREQUENCY.get(target_status)
    if freq_range is None:
        new_freq = current_frequency
    elif target_frequency is not None:
        if isinstance(freq_range, tuple):
            if target_frequency < freq_range[0] or target_frequency > freq_range[1]:
                raise HTTPException(
                    status_code=422,
                    detail=f"Frequency for '{target_status}' must be in {freq_range}",
                )
        elif target_frequency != freq_range:
            raise HTTPException(
                status_code=422,
                detail=f"Frequency for '{target_status}' must be {freq_range}",
            )
        new_freq = target_frequency
    elif isinstance(freq_range, tuple):
        new_freq = freq_range[0]
    else:
        new_freq = freq_range

    return target_status, new_freq


class ErrorService:
    def __init__(self, repo: ErrorQuestionRepository) -> None:
        self.repo = repo

    async def list(
        self,
        user_id: UUID,
        *,
        dimension: str | None = None,
        status: str | None = None,
        frequency_min: int = 0,
        limit: int = 20,
    ) -> list:
        return await self.repo.list(
            user_id,
            dimension=dimension,
            status=status,
            frequency_min=frequency_min,
            limit=limit,
        )

    async def get(self, id: UUID, user_id: UUID) -> ErrorQuestion:
        instance = await self.repo.get(id, user_id)
        if instance is None:
            raise HTTPException(status_code=404, detail="Error question not found")
        return instance

    async def create(self, user_id: UUID, data: dict) -> ErrorQuestion:
        from datetime import datetime, timezone

        instance = ErrorQuestion(
            user_id=user_id,
            question_text=data["question_text"],
            dimension=data.get("dimension"),
            answer_text=data.get("answer_text"),
            reference_answer_md=data.get("reference_answer_md"),
            score=data.get("score"),
            tags=data.get("tags"),
        )
        return await self.repo.create(instance)

    async def patch(self, id: UUID, user_id: UUID, patch_data: dict) -> ErrorQuestion:
        current = await self.get(id, user_id)

        new_status = patch_data.get("status", current.status)
        new_frequency = patch_data.get("frequency", current.frequency)

        if "status" in patch_data and new_status != current.status:
            resolved_status, resolved_freq = reduce_status(
                current.status, new_status, current.frequency,
                patch_data.get("frequency"),
            )
            patch_data["status"] = resolved_status
            patch_data["frequency"] = resolved_freq

        # Validate frequency/status invariants
        if "frequency" in patch_data and "status" not in patch_data:
            _validate_frequency_status(new_status, patch_data["frequency"])

        instance = await self.repo.patch(id, user_id, patch_data)
        if instance is None:
            raise HTTPException(status_code=404, detail="Error question not found")
        return instance

    async def delete(self, id: UUID, user_id: UUID) -> None:
        ok = await self.repo.soft_delete(id, user_id)
        if not ok:
            raise HTTPException(status_code=404, detail="Error question not found")

    async def reset(self, id: UUID, user_id: UUID) -> ErrorQuestion:
        current = await self.get(id, user_id)
        if current.status != "mastered":
            raise HTTPException(
                status_code=409,
                detail="Only 'mastered' questions can be reset to 'fresh'",
            )
        return await self.repo.reset(id, user_id)

    async def recall(self, id: UUID, user_id: UUID) -> ErrorQuestion:
        current = await self.get(id, user_id)
        if current.frequency <= 0 or current.status == "mastered":
            raise HTTPException(
                status_code=409,
                detail={
                    "error": {
                        "code": "already_mastered",
                        "message": "This error question is already mastered.",
                        "details": {"id": str(id), "status": current.status},
                    }
                },
            )

        instance = await self.repo.recall(id, user_id)
        if instance is None:
            raise HTTPException(status_code=404, detail="Error question not found")
        return instance


def _validate_frequency_status(status: str, frequency: int) -> None:
    freq_range = STATUS_FREQUENCY.get(status)
    if freq_range is None:
        return
    if isinstance(freq_range, tuple):
        if frequency < freq_range[0] or frequency > freq_range[1]:
            raise HTTPException(status_code=422, detail=f"Frequency {frequency} invalid for {status}")
    elif frequency != freq_range:
        raise HTTPException(status_code=422, detail=f"Frequency must be {freq_range} for {status}")


__all__ = ["ErrorService", "reduce_status"]
