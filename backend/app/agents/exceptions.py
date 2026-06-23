"""023 — Checkpointer/LLM agent exceptions."""
from __future__ import annotations


class CheckpointerUnavailableError(Exception):
    """Raised when the PostgreSQL checkpointer connection is unavailable.

    The caller should retry after ``retry_after`` seconds.
    """

    def __init__(self, message: str = "", *, retry_after: int = 30) -> None:
        self.retry_after = retry_after
        super().__init__(message or "Checkpointer unavailable, please retry later")


__all__ = ["CheckpointerUnavailableError"]
