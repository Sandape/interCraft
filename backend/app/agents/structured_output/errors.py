"""REQ-038 US1 P1 — Structured-output error taxonomy.

5 categories, locked at ac-matrix AC-006a / AC-008:
    schema_invalid, parse_fail, quota, timeout, oob

[ac-completed: AC-006a, AC-008]
"""
from __future__ import annotations

from typing import Literal

CategoryType = Literal["schema_invalid", "parse_fail", "quota", "timeout", "oob"]


class StructuredOutputError(Exception):
    """Base class for all structured-output failures.

    Each subclass pins its `category` class attribute so callers can
    rely on `exc.category` without string sniffing.
    """

    category: CategoryType = "schema_invalid"

    def __init__(
        self,
        message: str,
        *,
        category: CategoryType | None = None,
        node_name: str | None = None,
        cause: BaseException | None = None,
    ) -> None:
        if category is not None:
            # type: ignore[assignment]
            self.category = category
        self.node_name = node_name
        self.cause = cause
        super().__init__(message)


class SchemaInvalid(StructuredOutputError):
    """LLM output parsed as JSON but failed Pydantic validation."""

    category = "schema_invalid"


class ParseFail(StructuredOutputError):
    """LLM output was not valid JSON at all."""

    category = "parse_fail"


class Timeout(StructuredOutputError):
    """LLM call timed out (HTTP 504 / connect timeout)."""

    category = "timeout"


class Quota(StructuredOutputError):
    """LLM call rejected due to rate limit / quota exhaustion (HTTP 429)."""

    category = "quota"

    def __init__(
        self,
        message: str = "quota exceeded",
        *,
        used: int | None = None,
        quota: int | None = None,
        estimated: int | None = None,
        node_name: str | None = None,
        cause: BaseException | None = None,
    ) -> None:
        self.used = used
        self.quota = quota
        self.estimated = estimated
        super().__init__(message, node_name=node_name, cause=cause)


class OutOfBounds(StructuredOutputError):
    """LLM output contained numeric values outside Pydantic Field bounds."""

    category = "oob"


__all__ = [
    "StructuredOutputError",
    "SchemaInvalid",
    "ParseFail",
    "Timeout",
    "Quota",
    "OutOfBounds",
    "CategoryType",
]