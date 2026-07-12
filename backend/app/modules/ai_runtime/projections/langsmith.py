"""LangSmith projection destination helpers (REQ-061 T160).

Policy-authorized, idempotent catch-up of metadata/redacted/restricted
representations. Never calls engines/providers/tools/metering.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Literal
from uuid import UUID

Representation = Literal["metadata", "redacted", "restricted"]
ALLOWED_REPRESENTATIONS: frozenset[str] = frozenset(
    {"metadata", "redacted", "restricted"}
)


@dataclass(frozen=True)
class LangSmithDestinationStatus:
    destination: str = "langsmith"
    backlog_count: int = 0
    blocked_by_policy_count: int = 0
    last_success_at: datetime | None = None
    last_confirmed_sequence: str | None = None
    available: bool = True


@dataclass(frozen=True)
class LangSmithDeepLinks:
    task_url: str
    execution_url: str | None
    attempt_url: str | None


def build_deep_links(
    *,
    task_id: UUID | str,
    execution_id: UUID | str | None = None,
    attempt_id: UUID | str | None = None,
    base: str = "/api/v1/admin-console/ai",
) -> LangSmithDeepLinks:
    tid = str(task_id)
    return LangSmithDeepLinks(
        task_url=f"{base}/tasks/{tid}",
        execution_url=f"{base}/tasks/{tid}?execution_id={execution_id}"
        if execution_id
        else None,
        attempt_url=f"{base}/tasks/{tid}/attempts?attempt_id={attempt_id}"
        if attempt_id
        else None,
    )


def authorize_representation(
    representation: str,
    *,
    policy_allows_restricted: bool = False,
) -> tuple[bool, str | None]:
    if representation not in ALLOWED_REPRESENTATIONS:
        return False, "representation_not_approved"
    if representation == "restricted" and not policy_allows_restricted:
        return False, "restricted_blocked_by_policy"
    return True, None


def project_blocked_representation(
    *,
    source_event_id: str,
    root_task_id: str,
    reason: str,
) -> dict[str, Any]:
    return {
        "destination": "langsmith",
        "status": "blocked",
        "source_event_id": source_event_id,
        "root_task_id": root_task_id,
        "reason": reason,
        "provider_calls_created": 0,
        "projected_at": datetime.now(UTC).isoformat(),
    }


def project_event_representation(
    *,
    source_event_id: str,
    root_task_id: str,
    sequence: int,
    representation: Representation = "metadata",
    links: LangSmithDeepLinks | None = None,
    policy_allows_restricted: bool = False,
) -> dict[str, Any]:
    ok, reason = authorize_representation(
        representation, policy_allows_restricted=policy_allows_restricted
    )
    if not ok:
        return project_blocked_representation(
            source_event_id=source_event_id,
            root_task_id=root_task_id,
            reason=reason or "blocked",
        )
    return {
        "destination": "langsmith",
        "status": "pending",
        "source_event_id": source_event_id,
        "root_task_id": root_task_id,
        "sequence": sequence,
        "representation": representation,
        "links": {
            "task": links.task_url if links else None,
            "execution": links.execution_url if links else None,
            "attempt": links.attempt_url if links else None,
        },
        "provider_calls_created": 0,
        "tool_calls_created": 0,
        "projected_at": datetime.now(UTC).isoformat(),
    }


def catch_up_is_idempotent(delivery_id: str, already_confirmed: set[str]) -> bool:
    """True when a delivery was already confirmed (safe to skip)."""
    return delivery_id in already_confirmed


__all__ = [
    "ALLOWED_REPRESENTATIONS",
    "LangSmithDeepLinks",
    "LangSmithDestinationStatus",
    "authorize_representation",
    "build_deep_links",
    "catch_up_is_idempotent",
    "project_blocked_representation",
    "project_event_representation",
]
