"""REQ-061 US11 — gray-stage evaluation + automatic stop/rollback (T149)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from app.core.logging import get_logger
from app.modules.ai_runtime.provider_gateway.release_service import (
    ReleaseServiceError,
    get_release_service,
)

log = get_logger("workers.ai_release_guard")


async def run_gray_stage_evaluation(ctx: dict[str, Any] | None = None) -> dict[str, Any]:
    """Evaluate stop thresholds / advance eligibility for active gray batches."""
    payload = ctx or {}
    service = get_release_service()
    batch_id = payload.get("release_batch_id")
    results: list[dict[str, Any]] = []

    batches = (
        [service.get_batch(str(batch_id))]
        if batch_id
        else service.list_batches()
    )
    for batch in batches:
        if batch is None:
            continue
        metrics = payload.get("metrics") or {}
        should_stop, reason = service.check_stop_thresholds(
            batch.release_batch_id,
            safety_incident=bool(metrics.get("safety_incident")),
            success_rate_delta_pp=float(metrics.get("success_rate_delta_pp") or 0),
            p95_latency_delta_pct=float(metrics.get("p95_latency_delta_pct") or 0),
            unit_cost_delta_pct=float(metrics.get("unit_cost_delta_pct") or 0),
            negative_feedback_delta_pp=float(
                metrics.get("negative_feedback_delta_pp") or 0
            ),
            erroneous_charge_rate=float(metrics.get("erroneous_charge_rate") or 0),
        )
        action = "observe"
        if should_stop and reason:
            service.stop_and_rollback(batch.release_batch_id, reason=reason)
            action = "rollback"
            log.warning(
                "ai_release_guard.stop",
                release_batch_id=batch.release_batch_id,
                reason=reason,
            )
        elif payload.get("try_advance"):
            try:
                service.advance_stage(
                    batch.release_batch_id,
                    now=datetime.now(UTC),
                    low_traffic=bool(payload.get("low_traffic")),
                    dual_approved_low_traffic=bool(
                        payload.get("dual_approved_low_traffic")
                    ),
                )
                action = "advanced"
            except ReleaseServiceError as exc:
                action = f"advance_blocked:{exc}"

        refreshed = service.get_batch(batch.release_batch_id)
        results.append(
            {
                "release_batch_id": batch.release_batch_id,
                "action": action,
                "status": refreshed.status.value if refreshed else None,
                "stage_percent": refreshed.stage_percent if refreshed else None,
                "stop_reason": refreshed.stop_reason if refreshed else None,
            }
        )

    return {
        "evaluated_at": datetime.now(UTC).isoformat(),
        "results": results,
    }


async def run_rollback_sweep(ctx: dict[str, Any] | None = None) -> dict[str, Any]:
    """Ensure stopped batches expose a rollback target (idempotent)."""
    payload = ctx or {}
    service = get_release_service()
    fixed = 0
    for batch in service.list_batches():
        if batch.status.value in {"stopped", "rolled_back"} and not batch.rollback_target:
            batch.rollback_target = batch.stable_policy_version
            fixed += 1
    log.info("ai_release_guard.rollback_sweep", fixed=fixed, hint=payload.get("hint"))
    return {"fixed": fixed, "batch_count": len(service.list_batches())}


async def ai_release_guard(ctx: dict[str, Any]) -> dict[str, Any]:
    mode = str((ctx or {}).get("mode") or "gray")
    if mode == "rollback_sweep":
        return await run_rollback_sweep(ctx)
    return await run_gray_stage_evaluation(ctx)


__all__ = [
    "ai_release_guard",
    "run_gray_stage_evaluation",
    "run_rollback_sweep",
]
