"""Typed Tool result envelope; final responses may only cite this evidence."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ToolResultStatus(StrEnum):
    SUCCEEDED = "succeeded"
    CLARIFY = "clarify"
    AWAITING_CONFIRMATION = "awaiting_confirmation"
    RUNNING = "running"
    RETRYABLE_ERROR = "retryable_error"
    TERMINAL_ERROR = "terminal_error"
    CANCELLED = "cancelled"
    UNKNOWN_RESULT = "unknown_result"


class ToolError(BaseModel):
    model_config = ConfigDict(extra="forbid")
    category: str
    code: str | None = None
    retryable: bool = False


class ResourceRef(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: str
    id: str
    url: str | None = None


class ToolResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: ToolResultStatus
    user_message: str = Field(min_length=1, max_length=1000)
    data: dict[str, Any] | None = None
    resource_refs: list[ResourceRef] = Field(default_factory=list)
    error: ToolError | None = None
    committed: bool = False
    committed_at: datetime | None = None
    retry_after_seconds: int | None = Field(default=None, ge=0, le=3600)

    @model_validator(mode="after")
    def _consistent_status(self) -> "ToolResult":
        if self.status == ToolResultStatus.SUCCEEDED and self.error is not None:
            raise ValueError("successful ToolResult cannot contain an error")
        if self.status in {
            ToolResultStatus.RETRYABLE_ERROR,
            ToolResultStatus.TERMINAL_ERROR,
            ToolResultStatus.UNKNOWN_RESULT,
        } and self.error is None:
            raise ValueError("error ToolResult requires an error envelope")
        if self.committed and self.committed_at is None:
            raise ValueError("committed ToolResult requires committed_at")
        return self

    @classmethod
    def succeeded(
        cls,
        message: str,
        *,
        data: dict[str, Any] | None = None,
        resource_refs: list[ResourceRef] | None = None,
        committed: bool = False,
        committed_at: datetime | None = None,
    ) -> "ToolResult":
        return cls(
            status=ToolResultStatus.SUCCEEDED,
            user_message=message,
            data=data,
            resource_refs=resource_refs or [],
            committed=committed,
            committed_at=committed_at,
        )

    @classmethod
    def cancelled(cls, message: str = "任务已取消") -> "ToolResult":
        return cls(status=ToolResultStatus.CANCELLED, user_message=message)


def assert_success_evidence(result: ToolResult, *, write: bool) -> None:
    if result.status != ToolResultStatus.SUCCEEDED:
        raise ValueError("Tool did not succeed")
    if write and (not result.committed or result.committed_at is None):
        raise ValueError("write success has no commit evidence")


__all__ = [
    "ResourceRef",
    "ToolError",
    "ToolResult",
    "ToolResultStatus",
    "assert_success_evidence",
]
