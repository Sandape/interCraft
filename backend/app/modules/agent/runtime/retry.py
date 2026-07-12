"""Bounded retry decisions shared by model, Tool, DB and channel layers."""

from __future__ import annotations

import random
from dataclasses import dataclass
from enum import StrEnum


class ErrorCategory(StrEnum):
    VALIDATION = "validation"
    AUTHZ = "authz"
    NOT_FOUND = "not_found"
    CONFLICT = "conflict"
    RATE_LIMIT = "rate_limit"
    TIMEOUT = "timeout"
    DEPENDENCY = "dependency"
    INTERNAL = "internal"
    UNKNOWN_RESULT = "unknown_result"
    CANCELLED = "cancelled"


class RetryAction(StrEnum):
    RETRY = "retry"
    RECONCILE = "reconcile"
    TERMINAL = "terminal"
    DEAD_LETTER = "dead_letter"


@dataclass(frozen=True, slots=True)
class RetryDecision:
    action: RetryAction
    delay_seconds: float | None = None
    reason: str = ""


_TERMINAL = frozenset(
    {
        ErrorCategory.VALIDATION,
        ErrorCategory.AUTHZ,
        ErrorCategory.NOT_FOUND,
        ErrorCategory.CONFLICT,
        ErrorCategory.CANCELLED,
    }
)
_TRANSIENT = frozenset(
    {ErrorCategory.RATE_LIMIT, ErrorCategory.TIMEOUT, ErrorCategory.DEPENDENCY}
)


def decide_retry(
    category: ErrorCategory,
    *,
    attempt: int,
    max_attempts: int,
    idempotent: bool,
    effect_started: bool = False,
    retry_after_seconds: float | None = None,
    base_delay_seconds: float = 1,
    max_delay_seconds: float = 60,
    jitter_ratio: float = 0.2,
) -> RetryDecision:
    """Classify one failed attempt without ever replaying an uncertain effect."""
    if category in _TERMINAL:
        return RetryDecision(RetryAction.TERMINAL, reason=category.value)

    if category is ErrorCategory.UNKNOWN_RESULT:
        return RetryDecision(RetryAction.RECONCILE, reason="unknown_result")

    if effect_started and category in _TRANSIENT:
        return RetryDecision(RetryAction.RECONCILE, reason="effect_may_have_started")

    if not idempotent and category in _TRANSIENT:
        return RetryDecision(RetryAction.RECONCILE, reason="non_idempotent")

    if attempt >= max_attempts:
        return RetryDecision(RetryAction.DEAD_LETTER, reason="attempts_exhausted")

    if category is ErrorCategory.INTERNAL:
        if attempt > 1 or effect_started or not idempotent:
            return RetryDecision(RetryAction.TERMINAL, reason="internal_not_safe")
    elif category not in _TRANSIENT:
        return RetryDecision(RetryAction.TERMINAL, reason="unclassified")

    delay = (
        retry_after_seconds
        if category is ErrorCategory.RATE_LIMIT and retry_after_seconds is not None
        else base_delay_seconds * (2 ** max(attempt - 1, 0))
    )
    delay = min(max(delay, 0), max_delay_seconds)
    if jitter_ratio:
        delay *= random.uniform(max(0, 1 - jitter_ratio), 1 + jitter_ratio)
    return RetryDecision(RetryAction.RETRY, delay_seconds=delay, reason=category.value)


__all__ = ["ErrorCategory", "RetryAction", "RetryDecision", "decide_retry"]
