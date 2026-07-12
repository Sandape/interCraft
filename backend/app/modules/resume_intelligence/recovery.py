"""Retry and terminal error policy for resume intelligence runs."""
from __future__ import annotations

from dataclasses import dataclass

RETRYABLE_CODES = {"MODEL_UNAVAILABLE", "PROVIDER_TIMEOUT", "ENQUEUE_FAILED"}
TERMINAL_CODES = {
    "STRUCTURED_OUTPUT_INVALID",
    "SOURCE_VALIDATION_FAILED",
    "RUN_CANCELLED",
    "RUN_TERMINAL",
    "IDEMPOTENCY_MISMATCH",
}
RETRYABLE_COMPONENTS = {"analysis", "suggestions", "page_report"}


@dataclass(frozen=True)
class RetryDecision:
    allowed: bool
    retryable: bool
    next_attempt: int
    terminal_code: str | None = None
    reason: str = ""


def bounded_retry_policy(
    *,
    error_code: str,
    attempt: int,
    max_attempts: int = 3,
) -> RetryDecision:
    if error_code in TERMINAL_CODES:
        return RetryDecision(False, False, attempt, error_code, "terminal error")
    if error_code not in RETRYABLE_CODES:
        return RetryDecision(False, False, attempt, "UNKNOWN_ERROR", "non-retryable error")
    if attempt >= max_attempts:
        return RetryDecision(False, False, attempt, error_code, "retry budget exhausted")
    return RetryDecision(True, True, attempt + 1, None, "retry scheduled")


def safe_partial_component_retry(
    component_status: dict[str, str],
    *,
    component: str,
) -> dict[str, str]:
    if component not in RETRYABLE_COMPONENTS:
        raise ValueError(f"Component is not retryable: {component}")
    current = str(component_status.get(component) or "")
    if current not in {"failed", "skipped"}:
        raise ValueError(f"Component is not in a retryable state: {current}")
    updated = dict(component_status)
    updated[component] = "pending"
    return updated


def classify_terminal_error(exc: BaseException) -> dict[str, object]:
    name = type(exc).__name__
    text = str(exc)
    if "cancel" in text.casefold():
        code = "RUN_CANCELLED"
        retryable = False
    elif name in {"TimeoutError", "ProviderTimeoutError"}:
        code = "MODEL_UNAVAILABLE"
        retryable = True
    elif name in {"StructuredOutputError", "ValidationError"}:
        code = "STRUCTURED_OUTPUT_INVALID"
        retryable = False
    else:
        code = "UNKNOWN_ERROR"
        retryable = False
    return {"code": code, "message": name, "retryable": retryable}


__all__ = [
    "RetryDecision",
    "bounded_retry_policy",
    "classify_terminal_error",
    "safe_partial_component_retry",
]
