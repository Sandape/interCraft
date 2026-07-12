"""Metadata-only run progress events and polling truth helpers."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

EVENT_NAME = "resume_intelligence.run.updated"
TERMINAL_STATUSES = {"succeeded", "partial_success", "failed", "cancelled", "canceled"}


@dataclass(frozen=True)
class ProgressEvent:
    event_id: str
    event: str
    occurred_at: str
    request_id: str | None
    trace_id: str | None
    run_id: str
    resume_id: str | None
    sequence: int
    status: str
    phase: str
    progress_percent: int
    components: dict[str, str]
    terminal: bool
    error: dict[str, Any] | None = None

    def to_payload(self) -> dict[str, Any]:
        return self.__dict__.copy()


def next_sequence(previous: int | None) -> int:
    return max(0, int(previous or 0)) + 1


def build_progress_event(
    *,
    run_id: str,
    status: str,
    phase: str,
    sequence: int,
    progress_percent: int = 0,
    components: dict[str, str] | None = None,
    request_id: str | None = None,
    trace_id: str | None = None,
    resume_id: str | None = None,
    error: dict[str, Any] | None = None,
) -> ProgressEvent:
    safe_error = None
    if error:
        safe_error = {
            "code": error.get("code"),
            "message": error.get("message"),
            "retryable": bool(error.get("retryable")),
        }
    return ProgressEvent(
        event_id=f"{run_id}:{sequence}",
        event=EVENT_NAME,
        occurred_at=datetime.now(UTC).isoformat(),
        request_id=request_id,
        trace_id=trace_id,
        run_id=run_id,
        resume_id=resume_id,
        sequence=sequence,
        status=status,
        phase=phase,
        progress_percent=max(0, min(100, int(progress_percent))),
        components=dict(components or {}),
        terminal=status in TERMINAL_STATUSES,
        error=safe_error,
    )


def should_poll_after_event(
    *,
    last_seen_sequence: int | None,
    event_sequence: int,
    terminal: bool,
) -> bool:
    if last_seen_sequence is not None and event_sequence <= int(last_seen_sequence):
        return False
    if last_seen_sequence is not None and event_sequence > int(last_seen_sequence) + 1:
        return True
    return terminal


def canonical_polling_truth(row: Any) -> dict[str, Any]:
    status = str(getattr(row, "status", "unknown"))
    return {
        "run_id": str(getattr(row, "id")),
        "status": status,
        "phase": str(getattr(row, "phase", "")),
        "progress_percent": int(getattr(row, "progress_pct", 100 if status in TERMINAL_STATUSES else 0) or 0),
        "components": dict(getattr(row, "component_status", None) or {"analysis": status}),
        "terminal": status in TERMINAL_STATUSES,
        "error": (
            {
                "code": getattr(row, "error_code"),
                "message": getattr(row, "error_message", None) or getattr(row, "error_code"),
                "retryable": False,
            }
            if getattr(row, "error_code", None)
            else None
        ),
    }


__all__ = [
    "EVENT_NAME",
    "ProgressEvent",
    "build_progress_event",
    "canonical_polling_truth",
    "next_sequence",
    "should_poll_after_event",
]
