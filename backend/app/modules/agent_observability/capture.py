from __future__ import annotations

import contextlib
from collections.abc import Callable
from typing import Any, TypeVar

import structlog

logger = structlog.get_logger("agent_observability.capture")

T = TypeVar("T")

CENTRALIZED_AGENT_LLM_FLOWS: tuple[str, ...] = (
    "interview_supervisor",
    "error_coach",
    "resume_optimize",
    "general_coach",
)


def capture_fail_open(event_name: str, payload: dict[str, Any]) -> None:
    """Best-effort capture hook.

    The REQ-035 capture contract is fail-open: observability write failures must
    never block user-facing agent flows. This MVP hook logs metadata only and is
    ready to be replaced by repository persistence.
    """

    with contextlib.suppress(Exception):
        logger.info("agent_observability.capture", event_name=event_name, **payload)


def fail_open_wrapper(name: str, fn: Callable[..., T]) -> Callable[..., T]:
    def wrapped(*args: Any, **kwargs: Any) -> T:
        try:
            capture_fail_open(f"{name}.start", {"name": name})
        except Exception:
            pass
        return fn(*args, **kwargs)

    return wrapped


__all__ = [
    "CENTRALIZED_AGENT_LLM_FLOWS",
    "capture_fail_open",
    "fail_open_wrapper",
]
