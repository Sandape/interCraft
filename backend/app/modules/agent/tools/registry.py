"""Versioned registry used for schema export, validation and dispatch."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from pydantic import BaseModel

from app.modules.agent.runtime.context import ToolContext, sanitize_tool_arguments
from app.modules.agent.tools.result import ToolError, ToolResult, ToolResultStatus


class SideEffect(StrEnum):
    NONE = "none"
    READ = "read"
    WRITE = "write"
    EXTERNAL = "external"


class ConfirmationPolicy(StrEnum):
    NEVER = "never"
    ALWAYS = "always"
    POLICY = "policy"
    EXPLICIT_COMMAND = "explicit_command"


class Atomicity(StrEnum):
    LOCAL_TRANSACTION = "local_transaction"
    COMMAND_OUTBOX = "command_outbox"
    PROVIDER_IDEMPOTENT = "provider_idempotent"
    RECONCILE_REQUIRED = "reconcile_required"


ToolExecutor = Callable[[BaseModel, ToolContext], Awaitable[ToolResult]]


@dataclass(frozen=True, slots=True)
class ToolDefinition:
    name: str
    version: str
    description: str
    input_model: type[BaseModel]
    output_model: type[BaseModel]
    side_effect: SideEffect
    confirmation: ConfirmationPolicy
    permission: str
    timeout_seconds: int
    max_attempts: int
    retryable_errors: frozenset[str]
    atomicity: Atomicity
    executor: ToolExecutor
    reconciliation: str | None = None


class DuplicateToolError(ValueError):
    pass


class UnknownToolError(LookupError):
    pass


class ToolRegistry:
    def __init__(self, *, version: str) -> None:
        self.version = version
        self._tools: dict[str, ToolDefinition] = {}

    def register(self, definition: ToolDefinition) -> None:
        if definition.name in self._tools:
            raise DuplicateToolError(definition.name)
        if not definition.name or len(definition.name) > 64:
            raise ValueError("invalid tool name")
        if definition.timeout_seconds < 1 or definition.max_attempts < 1:
            raise ValueError("invalid timeout/retry policy")
        self._tools[definition.name] = definition

    def get(self, name: str) -> ToolDefinition:
        try:
            return self._tools[name]
        except KeyError as exc:
            raise UnknownToolError(name) from exc

    def names(self) -> tuple[str, ...]:
        return tuple(sorted(self._tools))

    def openai_tools(self, *, allowed: set[str] | None = None) -> list[dict[str, Any]]:
        names = sorted(allowed if allowed is not None else self._tools)

        def model_description(definition: ToolDefinition) -> str:
            if definition.confirmation in {
                ConfirmationPolicy.ALWAYS,
                ConfirmationPolicy.POLICY,
            }:
                return (
                    f"{definition.description} "
                    "调用本工具只会创建运行时持久化确认，确认前不会执行。"
                    "参数齐全时必须立即调用，不要先用自然语言索要确认。"
                )
            return definition.description

        return [
            {
                "type": "function",
                "function": {
                    "name": definition.name,
                    "description": model_description(definition),
                    "parameters": definition.input_model.model_json_schema(),
                },
            }
            for name in names
            for definition in [self.get(name)]
        ]

    def describe(self, name: str) -> dict[str, Any]:
        definition = self.get(name)
        return {
            "name": definition.name,
            "version": definition.version,
            "input_schema": definition.input_model.model_json_schema(),
            "output_schema": definition.output_model.model_json_schema(),
            "side_effect": definition.side_effect.value,
            "confirmation": definition.confirmation.value,
            "atomicity": definition.atomicity.value,
            "permission": definition.permission,
            "timeout_seconds": definition.timeout_seconds,
            "max_attempts": definition.max_attempts,
        }

    async def execute(
        self,
        name: str,
        arguments: dict[str, Any],
        context: ToolContext,
    ) -> ToolResult:
        definition = self.get(name)
        clean = sanitize_tool_arguments(arguments)
        validated = definition.input_model.model_validate(clean)
        from app.modules.agent.runtime.retry import (
            ErrorCategory,
            RetryAction,
            decide_retry,
        )

        for attempt in range(1, definition.max_attempts + 1):
            if await context.is_cancel_requested():
                return ToolResult.cancelled()
            savepoint = await context.session.begin_nested()
            try:
                async with asyncio.timeout(definition.timeout_seconds):
                    result = await definition.executor(validated, context)
            except TimeoutError:
                if savepoint.is_active:
                    await savepoint.rollback()
                result = ToolResult(
                    status=ToolResultStatus.RETRYABLE_ERROR,
                    user_message="工具执行超时，请稍后重试",
                    error=ToolError(category="timeout", code="TOOL_TIMEOUT", retryable=True),
                )
            except Exception:
                if savepoint.is_active:
                    await savepoint.rollback()
                raise
            else:
                if (
                    definition.side_effect in {SideEffect.WRITE, SideEffect.EXTERNAL}
                    and result.status != ToolResultStatus.SUCCEEDED
                ):
                    await savepoint.rollback()
                else:
                    await savepoint.commit()

            if result.status != ToolResultStatus.RETRYABLE_ERROR or result.error is None:
                return result
            try:
                category = ErrorCategory(result.error.category)
            except ValueError:
                category = ErrorCategory.INTERNAL
            decision = decide_retry(
                category,
                attempt=attempt,
                max_attempts=definition.max_attempts,
                idempotent=definition.side_effect in {SideEffect.NONE, SideEffect.READ},
                effect_started=definition.side_effect in {SideEffect.WRITE, SideEffect.EXTERNAL},
                jitter_ratio=0,
            )
            if decision.action is not RetryAction.RETRY:
                return result
            from app.modules.agent.runtime.telemetry import record_metric

            record_metric(
                "agent_retry_total",
                layer="tool",
                category=category.value,
            )
            await asyncio.sleep(decision.delay_seconds or 0)

        return result


__all__ = [
    "Atomicity",
    "ConfirmationPolicy",
    "DuplicateToolError",
    "SideEffect",
    "ToolDefinition",
    "ToolRegistry",
    "UnknownToolError",
]
