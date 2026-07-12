"""REQ-061 US11 — scheduled online evaluation + calibration reminders (T149)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from app.core.logging import get_logger
from app.eval.calibration import (
    CalibrationExample,
    CalibrationStore,
    run_monthly_calibration,
)
from app.eval.judge import default_req061_rubric, evaluate_case
from app.eval.online_sampler import OnlineSampler

log = get_logger("workers.ai_evaluation")

_STORE = CalibrationStore()
_SAMPLER = OnlineSampler(seed=61)


async def run_online_evaluation(ctx: dict[str, Any] | None = None) -> dict[str, Any]:
    """Sample queued tasks and attach durable evaluation links."""
    payload = ctx or {}
    tasks = list(payload.get("tasks") or [])
    links: list[dict[str, Any]] = []
    for row in tasks:
        link = _SAMPLER.sample_task(
            task_id=str(row.get("task_id") or row.get("id") or ""),
            capability_code=str(row.get("capability_code") or "general_coach"),
            action_code=str(row.get("action_code") or ""),
            execution_id=row.get("execution_id"),
            severity=row.get("severity"),
            negative_feedback=bool(row.get("negative_feedback")),
            anomalous_points=bool(row.get("anomalous_points")),
            rubric_version=str(row.get("rubric_version") or "rubric.req061.v1"),
            evidence_ref=row.get("evidence_ref"),
        )
        if link.sampled:
            verdict = evaluate_case(
                {
                    "case_id": link.evaluation_link_id,
                    "passed": row.get("passed", True),
                    "deterministicMetrics": {"score": float(row.get("score", 0.9))},
                },
                rubric=default_req061_rubric(),
            )
            links.append({**link.to_dict(), "verdict": verdict.to_dict()})

    summary = {
        "evaluated_at": datetime.now(UTC).isoformat(),
        "input_count": len(tasks),
        "sampled_count": len(links),
        "links": links,
    }
    log.info("ai_evaluation.online", sampled=len(links), total=len(tasks))
    return summary


async def run_calibration_reminder(ctx: dict[str, Any] | None = None) -> dict[str, Any]:
    """Monthly calibration reminder / dry-run against provided labels."""
    payload = ctx or {}
    month = str(payload.get("month") or datetime.now(UTC).strftime("%Y-%m"))
    raw_examples = list(payload.get("examples") or [])
    examples = [
        CalibrationExample(
            example_id=str(ex.get("example_id") or f"ex-{i}"),
            capability_code=str(ex.get("capability_code") or "interview"),
            stratum=str(ex.get("stratum") or "normal"),
            severity=ex.get("severity"),
            human_passed=bool(ex.get("human_passed")),
            judge_passed=bool(ex.get("judge_passed")),
            month=str(ex.get("month") or month),
        )
        for i, ex in enumerate(raw_examples)
    ]
    if not examples:
        reminder = {
            "month": month,
            "status": "reminder",
            "message": "monthly calibration sample target is 100 stratified human labels",
            "min_labels": 100,
        }
        log.info("ai_evaluation.calibration_reminder", **reminder)
        return reminder

    report = run_monthly_calibration(examples, month=month, store=_STORE)
    log.info(
        "ai_evaluation.calibration",
        month=month,
        eligibility=report.eligibility.value,
        labels=report.label_count,
    )
    return report.to_dict()


async def ai_evaluation(ctx: dict[str, Any]) -> dict[str, Any]:
    mode = str((ctx or {}).get("mode") or "online")
    if mode == "calibration":
        return await run_calibration_reminder(ctx)
    return await run_online_evaluation(ctx)


__all__ = [
    "ai_evaluation",
    "run_calibration_reminder",
    "run_online_evaluation",
]
