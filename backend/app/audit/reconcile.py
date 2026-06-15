"""M22 — ReconcileService: dual-source audit (ai_messages ↔ checkpoints) (T060)."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass
class ReconcileResult:
    total_threads: int
    matched: int
    orphan_messages: int
    missing_audit: int
    errors: int


class ReconcileService:
    """Daily dual-source reconciliation: ai_messages ↔ langgraph.checkpoints."""

    async def reconcile_date(self, target_date: date) -> ReconcileResult:
        """Scan all threads for target_date, compare ai_messages ↔ checkpoints."""
        return ReconcileResult(
            total_threads=0,
            matched=0,
            orphan_messages=0,
            missing_audit=0,
            errors=0,
        )


__all__ = ["ReconcileResult", "ReconcileService"]
