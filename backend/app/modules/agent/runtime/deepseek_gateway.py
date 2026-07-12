"""Real DeepSeek function-calling gateway backed by the shared LLM client."""

from __future__ import annotations

import json
import re
import time
from typing import Any

from app.agents.llm_client import LLMClient, LLMInvokeError, get_llm_client
from app.core.config import get_settings
from app.core.logging import get_logger
from app.modules.agent.runtime.orchestrator import ModelResponse, ModelToolCall
from app.modules.agent.runtime.telemetry import agent_span, emit_event, record_metric

log = get_logger("agent.deepseek_gateway")

_UUID_PATTERN = re.compile(
    r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-8][0-9a-fA-F]{3}-"
    r"[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}\b"
)


def _forced_tool_choice(text: str, tools: list[dict[str, Any]]) -> str | dict[str, Any]:
    """Select one Tool only for a complete, high-confidence task command."""
    names = {
        str(item.get("function", {}).get("name"))
        for item in tools
        if item.get("type") == "function"
    }
    normalized = text.strip()
    if re.search(r"(?:不要|别|无需|不需要).{0,8}(?:登记|创建|生成|发起|开始)", normalized):
        return "auto"

    identifiers = _UUID_PATTERN.findall(normalized)
    rules: list[tuple[bool, str]] = [
        (
            bool(re.search(r"(?:派生|定制).{0,6}简历|简历.{0,6}(?:派生|定制)", normalized))
            and bool(identifiers),
            "resume_derive_start",
        ),
        (
            bool(re.search(r"(?:登记|创建|添加).{0,12}(?:目标)?岗位", normalized))
            and "公司" in normalized,
            "job_create",
        ),
        (bool(re.search(r"(?:创建|建立).{0,6}根简历", normalized)), "resume_root_create"),
        (
            bool(re.search(r"(?:开始|发起).{0,8}(?:模拟)?面试", normalized)) and bool(identifiers),
            "interview_start",
        ),
        (bool(re.search(r"(?:查询|查看|列出).{0,8}(?:目标岗位|岗位列表)", normalized)), "job_list"),
        ("错题本" in normalized, "error_book_summary"),
        ("能力画像" in normalized, "ability_profile_get"),
        (bool(re.search(r"(?:求职进度|进度看板)", normalized)), "job_progress_get"),
        ("面试报告" in normalized, "interview_report_list"),
        (bool(re.search(r"(?:查询|查看).{0,6}根简历", normalized)), "resume_root_get"),
    ]
    for matched, name in rules:
        if matched and name in names:
            return {"type": "function", "function": {"name": name}}
    return "auto"


def _has_tool_results(messages: list[dict[str, Any]]) -> bool:
    return any(item.get("role") == "tool" for item in messages)


def _inject_before_last_user(
    messages: list[dict[str, Any]],
    system_message: dict[str, Any],
) -> list[dict[str, Any]]:
    last_user_idx = max(
        (index for index, item in enumerate(messages) if item.get("role") == "user"),
        default=len(messages) - 1,
    )
    return [*messages[:last_user_idx], system_message, *messages[last_user_idx:]]


class DeepSeekToolGateway:
    def __init__(
        self,
        *,
        user_id: str,
        thread_id: str,
        client: LLMClient | None = None,
        correlation_id: str | None = None,
        trace_id: str | None = None,
        task_id: str | None = None,
    ) -> None:
        self.user_id = user_id
        self.thread_id = thread_id
        self.client = client or get_llm_client()
        self.correlation_id = correlation_id
        self.trace_id = trace_id
        self.task_id = task_id

    async def complete(
        self,
        messages: list[dict[str, Any]],
        *,
        tools: list[dict[str, Any]],
    ) -> ModelResponse:
        settings = get_settings()
        started = time.perf_counter()
        last_user_text = next(
            (
                str(item.get("content") or "")
                for item in reversed(messages)
                if item.get("role") == "user"
            ),
            "",
        )
        in_tool_followup = _has_tool_results(messages)
        forced_choice = (
            "auto" if in_tool_followup else _forced_tool_choice(last_user_text, tools)
        )
        expected_tool = (
            str(forced_choice.get("function", {}).get("name"))
            if isinstance(forced_choice, dict)
            else None
        )
        effective_tools = tools
        effective_messages = messages
        if expected_tool and not in_tool_followup:
            effective_tools = [
                item for item in tools if item.get("function", {}).get("name") == expected_tool
            ]
            effective_messages = _inject_before_last_user(
                messages,
                {
                    "role": "system",
                    "content": (
                        f"代码已确定当前参数完整且只能由 {expected_tool} 处理。"
                        "调用工具在本轮只创建可审计提案，运行时会另行向用户展示确认，"
                        "所以现在绝对不要询问用户确认参数或意图。必须立即调用唯一工具；"
                        "纯文本回复会被判定为失败。"
                    ),
                },
            )
        try:
            with agent_span(
                "agent.llm",
                correlation_id=self.correlation_id,
                trace_id=self.trace_id,
                task_id=self.task_id,
            ):
                response = await self.client.invoke_with_tools(
                    messages=effective_messages,
                    tools=effective_tools,
                    user_id=self.user_id,
                    thread_id=self.thread_id,
                    timeout_ms=settings.agent_llm_timeout_seconds * 1000,
                    # DeepSeek's current OpenAI-compatible endpoint rejects
                    # `required` and named tool_choice with HTTP 400. The
                    # candidate list is already narrowed to one Tool.
                    # DeepSeek currently rejects `required`/named choices.
                    tool_choice="auto",
                )
        except Exception as exc:
            retry_count = exc.retry_count if isinstance(exc, LLMInvokeError) else 0
            log.warning(
                "agent.llm.failed",
                error_type=type(exc).__name__,
                provider_error_type=(
                    type(exc.__cause__).__name__ if exc.__cause__ is not None else None
                ),
                retry_count=retry_count,
            )
            emit_event(
                log,
                "agent.llm.completed",
                model=settings.agent_tool_model,
                prompt_version="wechat-agent.v2",
                latency_ms=int((time.perf_counter() - started) * 1000),
                tokens=0,
                status="failed",
                retry_count=retry_count,
                correlation_id=self.correlation_id,
                trace_id=self.trace_id,
                task_id=self.task_id,
            )
            if retry_count:
                record_metric(
                    "agent_retry_total",
                    value=retry_count,
                    layer="llm",
                    category="transient_dependency",
                )
            raise
        usage = response.usage
        emit_event(
            log,
            "agent.llm.completed",
            model=settings.agent_tool_model,
            prompt_version="wechat-agent.v2",
            latency_ms=int((time.perf_counter() - started) * 1000),
            tokens=(usage.prompt_tokens or 0) + (usage.completion_tokens or 0) if usage else 0,
            status="succeeded",
            retry_count=0,
            correlation_id=self.correlation_id,
            trace_id=self.trace_id,
            task_id=self.task_id,
        )
        message = response.choices[0].message
        calls: list[ModelToolCall] = []
        for call in message.tool_calls or []:
            arguments = json.loads(call.function.arguments or "{}")
            if not isinstance(arguments, dict):
                raise ValueError("Tool arguments must be a JSON object")
            calls.append(
                ModelToolCall(
                    id=call.id,
                    name=call.function.name,
                    arguments=arguments,
                )
            )
        return ModelResponse(
            content=message.content or "",
            tool_calls=tuple(calls),
            expected_tool=expected_tool,
        )


__all__ = ["DeepSeekToolGateway"]
