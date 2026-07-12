"""Bounded model/Tool loop with durable interruption and evidence gating."""

from __future__ import annotations

import hashlib
import json
import re
import time
from dataclasses import dataclass, replace
from typing import Any, Protocol
from uuid import UUID

from app.core.ids import new_uuid_v7
from app.core.logging import get_logger
from app.modules.agent.runtime.context import ToolContext
from app.modules.agent.runtime.telemetry import agent_span, emit_event, record_metric
from app.modules.agent.tools.registry import (
    ConfirmationPolicy,
    SideEffect,
    ToolRegistry,
    UnknownToolError,
)
from app.modules.agent.tools.result import (
    ToolResult,
    ToolResultStatus,
    assert_success_evidence,
)

log = get_logger("agent.runtime")

# REQ-061 T083 — optional shared runtime hooks (receipt / fence / lineage).
# Imported lazily inside helpers so REQ-060 paths stay import-light.


@dataclass(frozen=True, slots=True)
class ModelToolCall:
    id: str
    name: str
    arguments: dict[str, Any]


@dataclass(frozen=True, slots=True)
class ModelResponse:
    content: str
    tool_calls: tuple[ModelToolCall, ...] = ()
    expected_tool: str | None = None


class ModelGateway(Protocol):
    async def complete(
        self, messages: list[dict[str, Any]], *, tools: list[dict[str, Any]]
    ) -> ModelResponse: ...


@dataclass(frozen=True, slots=True)
class ExecutionRecord:
    id: UUID
    user_id: UUID
    task_id: UUID
    tool_call_id: str
    tool_name: str
    tool_version: str
    args_hash: str
    arguments: dict[str, Any]
    idempotency_key: str
    side_effect: str
    atomicity: str
    binding_id: UUID
    binding_epoch: int
    claim_generation: int
    requires_confirmation: bool
    correlation_id: str | None = None
    trace_id: str | None = None


class ExecutionStore(Protocol):
    async def propose(self, record: ExecutionRecord) -> bool: ...
    async def complete(self, record: ExecutionRecord, result: ToolResult) -> None: ...


class ConfirmationIssuer(Protocol):
    async def issue(self, record: ExecutionRecord) -> str: ...


@dataclass(frozen=True, slots=True)
class RunOutcome:
    status: str
    message: str
    turns: int
    terminal_reason: str | None = None


_SUCCESS_WITH_EFFECT = re.compile(
    r"(?:已|已经).{0,12}(?:创建|登记|更新|生成|保存|完成|提交|删除).{0,8}(?:成功|完成)?"
)

_WRITE_ACTION = re.compile(
    r"(?:请|帮我|立即|现在|马上|直接|确认)?[\s\S]{0,24}"
    r"(?:创建|新增|登记|添加|更新|修改|保存|删除|发起|生成|派生|开始|暂停|结束|取消|恢复|提交)"
)
_WRITE_RESOURCE = re.compile(r"(?:岗位|职位|简历|面试|任务|投递|求职目标|错题|报告|能力画像)")
_EXPLANATION_ONLY = re.compile(r"(?:如何|怎么|怎样|是什么|介绍一下|说明一下|给.*建议)")


def _is_explicit_write_request(message: str) -> bool:
    normalized = " ".join(str(message or "").split())
    if not normalized or _EXPLANATION_ONLY.search(normalized):
        return False
    return bool(_WRITE_ACTION.search(normalized) and _WRITE_RESOURCE.search(normalized))


def build_shared_execution_hints(context: ToolContext) -> dict[str, Any]:
    """Light ExecutionContext-shaped hints for telemetry / adapter linkage (T083).

    Does not open DB transactions or mutate AgentTask rows — preserves REQ-060
    fencing ownership while exposing claim/binding identity for receipts.
    """
    return {
        "task_id": str(context.task_id),
        "user_id": str(context.user_id),
        "binding_id": str(context.binding_id),
        "binding_epoch": int(context.binding_epoch),
        "claim_generation": int(context.claim_generation),
        "capability_code": "wechat_agent",
        "action_code": "run",
        "correlation_id": context.correlation_id,
        "trace_id": context.trace_id,
    }


def maybe_issue_write_authorization_receipt(
    *,
    context: ToolContext,
    tool_name: str,
    args_hash: str,
    tool_version: str,
    side_effect: str,
) -> str | None:
    """Issue an immutable authorization receipt for WRITE/EXTERNAL tools (T083).

    Returns receipt id for telemetry; CAS consumption happens at adopt time via
    ``ai_runtime.authorization`` helpers when adapters fence effects.
    """
    if side_effect not in {"write", "external"}:
        return None
    from app.modules.ai_runtime.adapters import wechat_agent as wx

    receipt = wx.issue_tool_authorization(
        actor_id=str(context.user_id),
        tenant_id=str(context.user_id),
        action=f"tool.{tool_name}",
        target_id=str(context.task_id),
        target_version=int(context.claim_generation),
        argument_hash=f"sha256:{args_hash}",
        tool_policy_version=tool_version,
        budget_points=0,
        expires_at="2099-01-01T00:00:00Z",
        idempotency_key=context.idempotency_key or f"{context.task_id}:{tool_name}",
        approval_id=context.correlation_id or "dev",
        claim_generation=int(context.claim_generation),
    )
    return receipt.id


_MAX_TOOL_MODEL_CHARS = 8000


def _canonical_args(arguments: dict[str, Any]) -> str:
    return json.dumps(
        arguments, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str
    )


def _tool_content_for_model(result: ToolResult) -> str:
    content = result.model_dump_json(exclude_none=True)
    if len(content) <= _MAX_TOOL_MODEL_CHARS:
        return content
    compact = {
        "status": result.status.value,
        "user_message": result.user_message[:500],
        "data": {
            "truncated": True,
            "next_action": "使用带 limit 的只读工具继续分页查看",
        },
        "resource_refs": [
            item.model_dump(mode="json", exclude_none=True) for item in result.resource_refs[:10]
        ],
        "committed": result.committed,
        "error": result.error.model_dump(mode="json", exclude_none=True) if result.error else None,
    }
    return json.dumps(
        compact,
        ensure_ascii=False,
        separators=(",", ":"),
        default=str,
    )


async def _active_interview_hint(context: ToolContext) -> dict[str, str] | None:
    from app.modules.agent.conversation.interview.mutex import has_active_session

    active = await has_active_session(context.session, context.user_id)
    if active is None:
        return None
    company = getattr(active, "company", "") or ""
    position = getattr(active, "position", "") or ""
    status = getattr(active, "status", "") or ""
    return {
        "role": "system",
        "content": (
            f"当前存在进行中的模拟面试：session_id={active.id}，"
            f"目标={company} · {position}，状态={status}。"
            "用户若回复面试答案，或说「开始」「开始面试」「准备好了」「继续面试」，"
            "必须调用 interview_continue，arguments.session_id 必须是该 session_id，"
            "arguments.answer 必须与用户原文完全一致。"
            "用户若明确说「暂停面试」调用 interview_pause；「结束面试」调用 interview_end。"
            "此状态下禁止调用 interview_start 创建新面试。"
        ),
    }


def _looks_like_new_agent_task(text: str) -> bool:
    normalized = text.strip()
    if re.search(r"(?:不要|别|无需|不需要).{0,8}(?:登记|创建|生成|发起|开始)", normalized):
        return False
    patterns = (
        r"(?:派生|定制).{0,6}简历",
        r"(?:登记|创建|添加).{0,12}(?:目标)?岗位",
        r"(?:创建|建立).{0,6}根简历",
        r"(?:开始|发起).{0,8}(?:模拟)?面试",
        r"(?:查询|查看|列出).{0,8}(?:目标岗位|岗位列表)",
        r"错题本",
        r"能力画像",
        r"(?:求职进度|进度看板)",
        r"面试报告",
        r"(?:查询|查看).{0,6}根简历",
        r"^确认\s+\S+",
        r"^取消\s+\S+",
    )
    return any(re.search(pattern, normalized) for pattern in patterns)


def _forced_interview_tool(user_message: str) -> str | None:
    text = user_message.strip()
    if text in {"暂停", "暂停面试", "先暂停"}:
        return "interview_pause"
    if text in {"结束面试", "结束模拟面试", "退出面试"}:
        return "interview_end"
    if text in {"降级继续面试", "使用通用题继续面试"}:
        return "interview_plan_degrade"
    if text in {"开始", "开始面试", "准备好了", "继续面试"}:
        return "interview_continue"
    if _looks_like_new_agent_task(text):
        return None
    if len(text) >= 8:
        return "interview_continue"
    return None


def _inject_before_last_user(
    messages: list[dict[str, Any]],
    system_message: dict[str, Any],
) -> list[dict[str, Any]]:
    last_user_idx = max(
        (index for index, item in enumerate(messages) if item.get("role") == "user"),
        default=len(messages) - 1,
    )
    return [*messages[:last_user_idx], system_message, *messages[last_user_idx:]]


async def _explicit_command_authorized(
    *,
    tool_name: str,
    user_message: str,
    arguments: dict[str, Any],
    context: ToolContext,
) -> bool:
    """Bind explicit interview effects to the unique owner-scoped active session."""
    from app.modules.agent.conversation.interview.mutex import has_active_session

    active = await has_active_session(context.session, context.user_id)
    if active is None:
        return False
    session_id = arguments.get("session_id")
    if session_id is None or str(session_id) != str(active.id):
        return False
    text = user_message.strip()
    exact_commands = {
        "interview_pause": {"暂停", "暂停面试", "先暂停"},
        "interview_end": {"结束面试", "结束模拟面试", "退出面试"},
        "interview_plan_degrade": {"降级继续面试", "使用通用题继续面试"},
    }
    if tool_name in exact_commands:
        return text in exact_commands[tool_name]
    if tool_name != "interview_continue":
        return False
    answer = str(arguments.get("answer") or "").strip()
    blocked_controls = {
        "取消",
        "取消任务",
        "暂停",
        "暂停面试",
        "结束面试",
        "退出面试",
    }
    begin_phrases = {"开始", "开始面试", "准备好了", "继续面试"}
    if bool(answer) and answer == text and text in begin_phrases:
        return True
    return bool(answer) and answer == text and text not in blocked_controls


class AgentRuntimeOrchestrator:
    def __init__(
        self,
        *,
        registry: ToolRegistry,
        gateway: ModelGateway,
        execution_store: ExecutionStore,
        confirmation_issuer: ConfirmationIssuer,
        system_prompt: str,
        max_turns: int = 8,
    ) -> None:
        self.registry = registry
        self.gateway = gateway
        self.execution_store = execution_store
        self.confirmation_issuer = confirmation_issuer
        self.system_prompt = system_prompt
        self.max_turns = max_turns

    async def run(
        self,
        *,
        context: ToolContext,
        user_message: str,
        conversation_history: list[dict[str, str]] | None = None,
    ) -> RunOutcome:
        messages: list[dict[str, Any]] = [{"role": "system", "content": self.system_prompt}]
        from app.modules.agent.conversation.interview.mutex import has_active_session

        active_interview = await has_active_session(context.session, context.user_id)
        interview_hint = await _active_interview_hint(context)
        if interview_hint is not None:
            messages.append(interview_hint)
        if conversation_history:
            messages.extend(conversation_history[-8:])
        messages.append({"role": "user", "content": user_message})
        forced_interview_tool = (
            _forced_interview_tool(user_message) if active_interview is not None else None
        )
        successful_results: list[tuple[ToolResult, SideEffect]] = []

        for turn in range(1, self.max_turns + 1):
            turn_messages = messages
            tools = self.registry.openai_tools()
            local_expected_tool: str | None = None
            if (
                forced_interview_tool
                and not any(item.get("role") == "tool" for item in messages)
            ):
                local_expected_tool = forced_interview_tool
                tools = [
                    item
                    for item in tools
                    if item.get("function", {}).get("name") == forced_interview_tool
                ]
                args_hint = (
                    f'session_id={active_interview.id}，answer="{user_message.strip()}"'
                    if forced_interview_tool == "interview_continue"
                    else f"session_id={active_interview.id}"
                )
                turn_messages = _inject_before_last_user(
                    messages,
                    {
                        "role": "system",
                        "content": (
                            f"代码已确定当前轮次只能调用 {forced_interview_tool}，"
                            f"参数必须为 {args_hint}。必须立即调用该工具，禁止纯文本回复。"
                        ),
                    },
                )
            try:
                response = await self.gateway.complete(turn_messages, tools=tools)
            except Exception:
                return RunOutcome(
                    status="terminal_error",
                    message="模型服务暂时不可用，本次没有执行或确认任何写操作。请稍后重试或查询已有任务状态。",
                    turns=turn,
                    terminal_reason="model_dependency",
                )
            if not response.tool_calls:
                expected_tool = response.expected_tool or local_expected_tool
                if expected_tool and turn < self.max_turns:
                    messages.append(
                        {
                            "role": "system",
                            "content": (
                                f"代码已强制当前轮次只能调用 {expected_tool}。"
                                "禁止纯文本回复；必须立即发起该工具调用。"
                            ),
                        }
                    )
                    continue
                if expected_tool:
                    return RunOutcome(
                        status="terminal_error",
                        message="模型未按已确认的任务意图生成工具调用，本次未执行任何操作。请稍后重试。",
                        turns=turn,
                        terminal_reason="required_tool_omitted",
                    )
                content = response.content.strip() or "我还需要更多信息才能继续。"
                if _SUCCESS_WITH_EFFECT.search(content) and not any(
                    result.status == ToolResultStatus.SUCCEEDED for result, _ in successful_results
                ):
                    return RunOutcome(
                        status="terminal_error",
                        message="我还没有工具执行成功的证据，因此不能确认该操作已完成。",
                        turns=turn,
                        terminal_reason="missing_tool_evidence",
                    )
                write_evidence = any(
                    result.status == ToolResultStatus.SUCCEEDED
                    and side_effect in {SideEffect.WRITE, SideEffect.EXTERNAL}
                    and result.committed
                    for result, side_effect in successful_results
                )
                if _is_explicit_write_request(user_message) and not write_evidence:
                    if turn < self.max_turns:
                        messages.extend(
                            [
                                {"role": "assistant", "content": content},
                                {
                                    "role": "system",
                                    "content": (
                                        "执行证据校验：用户明确要求改变 InterCraft 数据，"
                                        "本轮尚无写 Tool 证据。必须选择匹配的已注册 Tool；"
                                        "若必要参数确实缺失，只能明确追问，不能声称已执行。"
                                    ),
                                },
                            ]
                        )
                        continue
                    return RunOutcome(
                        status="terminal_error",
                        message="本次没有形成可验证的工具执行或确认，因此未执行该操作。请补充必要信息后重试。",
                        turns=turn,
                        terminal_reason="missing_tool_evidence",
                    )
                return RunOutcome(status="succeeded", message=content, turns=turn)

            assistant_calls: list[dict[str, Any]] = []
            for call in response.tool_calls:
                try:
                    definition = self.registry.get(call.name)
                except UnknownToolError:
                    return RunOutcome(
                        status="terminal_error",
                        message="模型请求了未注册工具，任务已安全停止。",
                        turns=turn,
                        terminal_reason="unknown_tool",
                    )

                if (
                    definition.confirmation == ConfirmationPolicy.EXPLICIT_COMMAND
                    and not await _explicit_command_authorized(
                        tool_name=definition.name,
                        user_message=user_message,
                        arguments=call.arguments,
                        context=context,
                    )
                ):
                    return RunOutcome(
                        status="clarify",
                        message=(
                            "面试控制指令不明确或与当前会话不匹配，未执行。"
                            "请明确回复继续、暂停或结束当前面试。"
                        ),
                        turns=turn,
                        terminal_reason="explicit_command_not_authorized",
                    )

                canonical = _canonical_args(call.arguments)
                args_hash = hashlib.sha256(canonical.encode()).hexdigest()
                idempotency_key = hashlib.sha256(
                    f"{context.user_id}:{context.task_id}:{call.id}:{args_hash}".encode()
                ).hexdigest()
                record = ExecutionRecord(
                    id=new_uuid_v7(),
                    user_id=context.user_id,
                    task_id=context.task_id,
                    tool_call_id=call.id,
                    tool_name=definition.name,
                    tool_version=definition.version,
                    args_hash=args_hash,
                    arguments=call.arguments,
                    idempotency_key=idempotency_key,
                    side_effect=definition.side_effect.value,
                    atomicity=definition.atomicity.value,
                    binding_id=context.binding_id,
                    binding_epoch=context.binding_epoch,
                    claim_generation=context.claim_generation,
                    correlation_id=context.correlation_id,
                    trace_id=context.trace_id,
                    requires_confirmation=definition.confirmation
                    in {
                        ConfirmationPolicy.ALWAYS,
                        ConfirmationPolicy.POLICY,
                    },
                )
                proposed = await self.execution_store.propose(record)
                emit_event(
                    log,
                    "agent.tool.proposed",
                    correlation_id=context.correlation_id,
                    trace_id=context.trace_id,
                    task_id=str(context.task_id),
                    tool_call_id=call.id,
                    tool=definition.name,
                    version=definition.version,
                    args_hash=args_hash,
                    confirmation=record.requires_confirmation,
                    binding_epoch=context.binding_epoch,
                    claim_generation=context.claim_generation,
                )
                if proposed is False:
                    return RunOutcome(
                        status="running",
                        message="该工具调用已被接收，正在查询已有执行结果，不会重复执行。",
                        turns=turn,
                        terminal_reason="duplicate_tool_execution",
                    )

                if definition.confirmation in {
                    ConfirmationPolicy.ALWAYS,
                    ConfirmationPolicy.POLICY,
                }:
                    token = await self.confirmation_issuer.issue(record)
                    return RunOutcome(
                        status="awaiting_confirmation",
                        message=(
                            f"准备执行 {definition.name}。确认标识：{token}。"
                            "请回复“确认 <标识>”、修改或取消；确认前不会执行。"
                        ),
                        turns=turn,
                    )

                call_context = replace(
                    context,
                    tool_call_id=call.id,
                    idempotency_key=idempotency_key,
                )
                receipt_id = maybe_issue_write_authorization_receipt(
                    context=call_context,
                    tool_name=definition.name,
                    args_hash=args_hash,
                    tool_version=definition.version,
                    side_effect=definition.side_effect.value,
                )
                if receipt_id:
                    emit_event(
                        log,
                        "agent.tool.authorization_receipt",
                        tool_call_id=call.id,
                        authorization_receipt_id=receipt_id,
                        **build_shared_execution_hints(call_context),
                    )
                effect_unit = await context.session.begin_nested()
                tool_started = time.perf_counter()
                try:
                    with agent_span(
                        "agent.tool",
                        correlation_id=context.correlation_id,
                        trace_id=context.trace_id,
                        task_id=str(context.task_id),
                        tool_call_id=call.id,
                        binding_epoch=context.binding_epoch,
                        claim_generation=context.claim_generation,
                    ):
                        result = await self.registry.execute(
                            definition.name, call.arguments, call_context
                        )
                        if (
                            definition.side_effect in {SideEffect.WRITE, SideEffect.EXTERNAL}
                            and result.status == ToolResultStatus.SUCCEEDED
                        ):
                            assert_success_evidence(result, write=True)
                        await self.execution_store.complete(record, result)
                        await effect_unit.commit()
                except Exception as exc:
                    if effect_unit.is_active:
                        await effect_unit.rollback()
                    # T083: stale lease may have recorded an attempt but must not
                    # adopt the tool result into business truth.
                    from app.modules.agent.runtime.stores import StaleExecutionClaimError

                    if isinstance(exc, StaleExecutionClaimError):
                        emit_event(
                            log,
                            "agent.tool.rejected_stale",
                            correlation_id=context.correlation_id,
                            trace_id=context.trace_id,
                            task_id=str(context.task_id),
                            tool_call_id=call.id,
                            authorization_receipt_id=receipt_id,
                            claim_generation=context.claim_generation,
                        )
                        return RunOutcome(
                            status="unknown_result",
                            message=(
                                "工具执行结果未能在当前执行 fence 下采纳，"
                                "请查询任务状态或等待对账确认，不要假定已成功或未发生。"
                            ),
                            turns=turn,
                            terminal_reason="stale_claim_cannot_adopt",
                        )
                    return RunOutcome(
                        status="terminal_error",
                        message="工具参数或执行结果未通过安全校验，未执行成功。",
                        turns=turn,
                        terminal_reason="tool_validation",
                    )
                emit_event(
                    log,
                    "agent.tool.completed",
                    task_id=str(context.task_id),
                    tool_call_id=call.id,
                    tool=definition.name,
                    status=result.status.value,
                    committed=result.committed,
                    resource_type=result.resource_refs[0].type if result.resource_refs else None,
                    error_category=result.error.category if result.error else None,
                    latency_ms=int((time.perf_counter() - tool_started) * 1000),
                    correlation_id=context.correlation_id,
                    trace_id=context.trace_id,
                )
                record_metric(
                    "agent_tool_calls_total",
                    tool=definition.name,
                    outcome=result.status.value,
                )
                record_metric(
                    "agent_tool_duration_seconds",
                    value=time.perf_counter() - tool_started,
                    tool=definition.name,
                )
                if result.committed:
                    emit_event(
                        log,
                        "agent.db.committed",
                        task_id=str(context.task_id),
                        tool_call_id=call.id,
                        correlation_id=context.correlation_id,
                        trace_id=context.trace_id,
                        operation=definition.name,
                        resource_type=result.resource_refs[0].type
                        if result.resource_refs
                        else None,
                        resource_id=result.resource_refs[0].id if result.resource_refs else None,
                    )
                successful_results.append((result, definition.side_effect))
                assistant_calls.append(
                    {
                        "id": call.id,
                        "type": "function",
                        "function": {"name": call.name, "arguments": canonical},
                    }
                )
                messages.append(
                    {
                        "role": "assistant",
                        "content": "",
                        "tool_calls": assistant_calls[-1:],
                    }
                )
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": call.id,
                        "content": _tool_content_for_model(result),
                    }
                )

        return RunOutcome(
            status="terminal_error",
            message="任务调用工具次数过多，已安全停止。",
            turns=self.max_turns,
            terminal_reason="max_turns",
        )


__all__ = [
    "AgentRuntimeOrchestrator",
    "ExecutionRecord",
    "ModelResponse",
    "ModelToolCall",
    "RunOutcome",
    "build_shared_execution_hints",
    "maybe_issue_write_authorization_receipt",
]
