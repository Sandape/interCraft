"""Shared runtime link + acceptance payload helpers for capability start/status."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any
from uuid import UUID

from app.modules.ai_runtime.adapters.contracts import AcceptanceEnvelope
from app.modules.ai_runtime.acceptance import AcceptanceResult, AcceptanceService
from app.modules.ai_runtime.schemas import TaskAccepted


def runtime_links_for_task(task_id: UUID | str) -> dict[str, str]:
    tid = str(task_id)
    return {
        "task_id": tid,
        "status_url": f"/api/v1/ai-tasks/{tid}",
        "events_url": f"/api/v1/ai-tasks/{tid}/events",
    }


def envelope_payload(envelope: AcceptanceEnvelope) -> dict[str, Any]:
    return {
        "capability_code": envelope.capability_code,
        "action_code": envelope.action_code,
        "service_tier": envelope.service_tier,
        "input_snapshot_ref": envelope.input_snapshot_ref,
        "input_canonical_hash": envelope.input_canonical_hash,
        "allow_degrade": envelope.allow_degrade,
        "max_points": envelope.max_points,
        "milestones": [
            {
                "code": m.code,
                "label": m.label,
                "weight_basis_points": m.weight_basis_points,
                "max_points": m.max_points,
            }
            for m in envelope.milestones
        ],
        "metadata": dict(envelope.metadata or {}),
    }


def task_accepted_payload(accepted: TaskAccepted) -> dict[str, Any]:
    data = accepted.model_dump(mode="json")
    links = runtime_links_for_task(accepted.task_id)
    data.setdefault("status_url", links["status_url"])
    data.setdefault("events_url", links["events_url"])
    return data


def acceptance_result_payload(
    svc: AcceptanceService, result: AcceptanceResult
) -> dict[str, Any]:
    return task_accepted_payload(svc.to_accepted_response(result))


def milestone_projection(
    *,
    codes: tuple[str, ...],
    delivered: tuple[str, ...] = (),
    failed: tuple[str, ...] = (),
    running: str | None = None,
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for code in codes:
        if code in delivered:
            status = "delivered"
        elif code in failed:
            status = "failed"
        elif code == running:
            status = "running"
        else:
            status = "pending"
        out.append(
            {
                "code": code,
                "status": status,
                "settle_eligible": code in delivered,
            }
        )
    return out


__all__ = [
    "acceptance_result_payload",
    "asdict",
    "envelope_payload",
    "milestone_projection",
    "runtime_links_for_task",
    "task_accepted_payload",
]
