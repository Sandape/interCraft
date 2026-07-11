"""Agent lifecycle, WeChat binding and master-key-derived envelope encryption."""

from __future__ import annotations

import base64
import hashlib
import logging
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Literal
from uuid import UUID, uuid4

from cryptography.fernet import Fernet
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.modules.agent.models import (
    Agent,
)
from app.modules.agent.repository import (
    AgentMessageRepository,
    AgentPreferenceRepository,
    AgentRepository,
    AgentStatusHistoryRepository,
    WeChatBindingRepository,
    WeChatCredentialRepository,
)
from app.modules.agent.runtime.telemetry import agent_span, emit_event, record_metric

logger = logging.getLogger(__name__)

DevChannel = Literal["wechat", "cli"]

_settings = get_settings()


@dataclass(frozen=True, slots=True)
class DevChatResult:
    reply: str
    inbound_message_id: UUID
    outbound_message_id: UUID | None
    task_id: UUID | None
    correlation_id: str
    status: str
    pending_confirmation: bool = False
    idempotent_replay: bool = False


class DevInboundError(Exception):
    """Raised when CLI/HTTP dev ingress cannot accept a message."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)
_TOKEN_ENCRYPTION_KEY = base64.urlsafe_b64encode(
    hashlib.sha256(f"wechat-agent:{_settings.master_key}".encode()).digest()
)


class AgentService:
    """Personal Agent lifecycle + WeChat binding management."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.agent_repo = AgentRepository(session)
        self.cred_repo = WeChatCredentialRepository(session)
        self.bind_repo = WeChatBindingRepository(session)
        self.msg_repo = AgentMessageRepository(session)
        self.pref_repo = AgentPreferenceRepository(session)
        self.hist_repo = AgentStatusHistoryRepository(session)

    # ── Agent lifecycle ────────────────────────────────────────────

    async def ensure_agent_exists(self, user_id: UUID) -> Agent:
        """Auto-create agent on user registration (idempotent)."""
        agent = await self.agent_repo.get_by_user(user_id)
        if agent is None:
            agent = Agent(user_id=user_id, status="dormant")
            agent = await self.agent_repo.create(agent)
            await self.hist_repo.record(user_id, "none", "dormant", "agent_auto_created")
            await self._ensure_preferences(user_id)
            logger.info("agent_created", extra={"user_id": str(user_id)})
        return agent

    async def _ensure_preferences(self, user_id: UUID) -> None:
        pref = await self.pref_repo.get_by_user(user_id)
        if pref is None:
            await self.pref_repo.upsert(user_id)

    # ── WeChat binding ─────────────────────────────────────────────

    async def bind_wechat(self, user_id: UUID, wechat_uin: str, bot_token: str) -> Agent:
        """Complete WeChat binding after QR code confirmed."""
        # Check if wechat_uin already bound to another user
        existing = await self.bind_repo.get_by_wechat_uin(wechat_uin)
        if existing is not None and str(existing.user_id) != str(user_id):
            raise WeChatAlreadyBoundError(
                wechat_uin=wechat_uin,
                bound_user_id=str(existing.user_id),
            )

        # Create/update binding
        binding = await self.bind_repo.get_by_user(user_id)
        if binding is None:
            binding = await self.bind_repo.create(user_id, wechat_uin)
        else:
            # Re-bind: update wechat_uin if changed, clear unbound_at
            binding.wechat_uin = wechat_uin
            binding.unbound_at = None
            binding.binding_epoch += 1
            binding.last_qrcode_login_at = datetime.now(timezone.utc)
            await self.session.flush()

        # Encrypt and persist credentials
        encrypted_token = _encrypt_token(bot_token)
        await self.cred_repo.upsert(user_id, encrypted_token)

        # Activate agent
        agent = await self.agent_repo.get_by_user(user_id)
        if agent is None:
            agent = await self.ensure_agent_exists(user_id)
        old_status = agent.status
        agent.status = "active"
        agent.wechat_uin = wechat_uin
        agent.status_changed_at = datetime.now(timezone.utc)
        agent.updated_at = datetime.now(timezone.utc)
        await self.session.flush()
        await self.session.refresh(agent)
        await self.hist_repo.record(user_id, old_status, "active", "binding_completed")
        return agent

    async def unbind_wechat(self, user_id: UUID) -> Agent:
        """Unbind WeChat — revoke credentials, deactivate agent."""
        await self.bind_repo.unbind(user_id)
        await self.cred_repo.revoke(user_id)
        agent = await self.agent_repo.get_by_user(user_id)
        if agent is not None:
            old_status = agent.status
            agent.status = "dormant"
            agent.wechat_uin = None
            agent.status_changed_at = datetime.now(timezone.utc)
            agent.updated_at = datetime.now(timezone.utc)
            await self.session.flush()
            await self.hist_repo.record(user_id, old_status, "dormant", "binding_removed")
        return agent

    # ── Inbound dispatch (REQ-052 US3.5) ──────────────────────────

    async def process_inbound_reply(
        self,
        parsed: Any,
        *,
        send_interim: Any | None = None,
    ) -> str:
        """Dispatch an inbound WeChat message to the conversational Agent.

        REQ-054: primary path is ``ConversationOrchestrator`` (intent →
        tools). Falls back to ``PersonalAgentReply`` only if the
        orchestrator import/init fails unexpectedly.

        Args:
            parsed: ``ParsedMessage`` (app.channels.message_handler). The
                field shape is what ``parse_inbound_message`` returns. We
                use ``parsed.from_user_id`` as the user identity (each
                WeChat user has their own InterCraft user_id via the
                binding).
            send_interim: Optional async callback ``(text: str) -> None``
                used by the interview adapter to push interim WeChat
                notices (e.g. 「评分中，请稍候…」) before the final reply.

        Returns:
            Reply text (str). The caller is responsible for enqueueing
            the outbound message via ``enqueue_outbound_message``.
        """
        from uuid import UUID

        # The ``parsed`` carries the originating WeChat user. We resolve
        # back to the InterCraft user_id via the binding table.
        if parsed.from_user_id:
            binding = await self.bind_repo.get_by_wechat_uin(parsed.from_user_id)
            user_id = binding.user_id if binding else None
        else:
            user_id = None

        if user_id is None:
            logger.warning(
                "personal_agent_no_user_for_from_user_id",
                extra={"sender_present": bool(parsed.from_user_id)},
            )
            return "抱歉，未识别到您的账号。"

        uid = UUID(str(user_id))
        if (
            getattr(parsed, "persisted_message_id", None) is not None
            and getattr(parsed, "binding_epoch", None) is not None
        ):
            channel = getattr(parsed, "channel", "wechat")
            return await self._process_production_reply(
                uid=uid,
                binding=binding,
                parsed=parsed,
                channel=channel,
            )
        try:
            from app.modules.agent.conversation import ConversationOrchestrator

            orchestrator = ConversationOrchestrator(self.session, uid, send_interim=send_interim)
            return await orchestrator.handle(parsed)
        except Exception as exc:
            logger.error(
                "conversation_orchestrator_failed_closed",
                extra={"error_type": type(exc).__name__},
            )
            return "任务处理失败，尚未执行或确认任何写操作。请稍后重试。"

    async def process_dev_inbound(
        self,
        user_id: UUID,
        text: str,
        *,
        idempotency_key: str | None = None,
    ) -> DevChatResult:
        """Accept one trusted CLI/HTTP message through the production runtime.

        Persists ``agent_messages`` with ``channel=cli`` and never enqueues
        WeChat outbound delivery. Requires an active WeChat binding so durable
        task fencing can reuse ``binding_id``/``binding_epoch``.
        """
        from types import SimpleNamespace

        from sqlalchemy import select

        from app.modules.agent.models import AgentMessage, AgentTask

        normalized = text.strip()
        if not normalized:
            raise DevInboundError("empty_text", "消息内容不能为空。")

        await self.ensure_agent_exists(user_id)
        binding = await self.bind_repo.get_by_user(user_id)
        if binding is None or binding.unbound_at is not None:
            raise DevInboundError(
                "no_binding",
                "当前账号未绑定微信，无法使用开发入站。请先在 /agent 完成一次扫码绑定。",
            )

        dedupe_key = self._cli_dedupe_key(idempotency_key) if idempotency_key else None
        if dedupe_key is not None:
            replay = await self._find_idempotent_dev_result(user_id, dedupe_key)
            if replay is not None:
                return replay

        inbound = await self._persist_cli_inbound(
            user_id=user_id,
            text=normalized,
            binding_epoch=binding.binding_epoch,
            dedupe_key=dedupe_key,
        )
        parsed = SimpleNamespace(
            text=normalized,
            persisted_message_id=inbound.id,
            binding_epoch=binding.binding_epoch,
            trace_id=inbound.trace_id,
            channel="cli",
            task_id=None,
        )
        reply = await self._process_production_reply(
            uid=user_id,
            binding=binding,
            parsed=parsed,
            channel="cli",
        )
        if parsed.task_id is not None:
            inbound.task_id = parsed.task_id
        outbound = await self._persist_cli_outbound(
            user_id=user_id,
            reply=reply,
            inbound_message_id=inbound.id,
            task_id=getattr(parsed, "task_id", None),
            trace_id=inbound.trace_id or "unavailable",
        )
        inbound.processing_status = "completed"
        await self.session.flush()

        task_status = "succeeded"
        pending_confirmation = False
        if parsed.task_id is not None:
            task = await self.session.get(AgentTask, parsed.task_id)
            if task is not None and str(task.user_id) == str(user_id):
                task_status = task.status
                pending_confirmation = task.status == "awaiting_confirmation"

        return DevChatResult(
            reply=reply,
            inbound_message_id=inbound.id,
            outbound_message_id=outbound.id if outbound is not None else None,
            task_id=parsed.task_id,
            correlation_id=str(inbound.id),
            status=task_status,
            pending_confirmation=pending_confirmation,
        )

    def _cli_dedupe_key(self, idempotency_key: str) -> str:
        normalized = idempotency_key.strip()
        if not normalized:
            raise DevInboundError("invalid_idempotency_key", "idempotency_key 不能为空。")
        return hashlib.sha256(f"cli:{normalized}".encode()).hexdigest()

    async def _find_idempotent_dev_result(
        self,
        user_id: UUID,
        dedupe_key: str,
    ) -> DevChatResult | None:
        from sqlalchemy import select

        from app.modules.agent.models import AgentMessage, AgentTask

        inbound = await self.session.scalar(
            select(AgentMessage)
            .where(
                AgentMessage.user_id == user_id,
                AgentMessage.direction == "inbound",
                AgentMessage.channel == "cli",
                AgentMessage.dedupe_key == dedupe_key,
            )
            .order_by(AgentMessage.created_at.desc())
            .limit(1)
        )
        if inbound is None:
            return None

        outbound = await self.session.scalar(
            select(AgentMessage)
            .where(
                AgentMessage.user_id == user_id,
                AgentMessage.direction == "outbound",
                AgentMessage.channel == "cli",
                AgentMessage.task_id == inbound.task_id,
                AgentMessage.created_at >= inbound.created_at,
            )
            .order_by(AgentMessage.created_at.asc())
            .limit(1)
        )
        if outbound is None and inbound.task_id is None:
            outbound = await self.session.scalar(
                select(AgentMessage)
                .where(
                    AgentMessage.user_id == user_id,
                    AgentMessage.direction == "outbound",
                    AgentMessage.channel == "cli",
                    AgentMessage.created_at >= inbound.created_at,
                )
                .order_by(AgentMessage.created_at.asc())
                .limit(1)
            )
        if outbound is None:
            return None

        task_status = "succeeded"
        pending_confirmation = False
        task_id = inbound.task_id or outbound.task_id
        if task_id is not None:
            task = await self.session.get(AgentTask, task_id)
            if task is not None and str(task.user_id) == str(user_id):
                task_status = task.status
                pending_confirmation = task.status == "awaiting_confirmation"

        return DevChatResult(
            reply=outbound.content,
            inbound_message_id=inbound.id,
            outbound_message_id=outbound.id,
            task_id=task_id,
            correlation_id=str(inbound.id),
            status=task_status,
            pending_confirmation=pending_confirmation,
            idempotent_replay=True,
        )

    async def _persist_cli_inbound(
        self,
        *,
        user_id: UUID,
        text: str,
        binding_epoch: int,
        dedupe_key: str | None,
    ) -> Any:
        from app.modules.agent.models import AgentMessage
        from app.modules.agent.runtime.telemetry import emit_event

        trace_id = uuid4().hex
        inbound = AgentMessage(
            id=uuid4(),
            user_id=user_id,
            direction="inbound",
            content=text,
            message_type="text",
            status="received",
            received_at=datetime.now(timezone.utc),
            channel="cli",
            dedupe_key=dedupe_key,
            processing_status="processing",
            binding_epoch=binding_epoch,
            trace_id=trace_id,
        )
        await self.msg_repo.create(inbound)
        emit_event(
            logger,
            "agent.dev.message.received",
            correlation_id=str(inbound.id),
            trace_id=trace_id,
            message_id=str(inbound.id),
            channel="cli",
        )
        return inbound

    async def _persist_cli_outbound(
        self,
        *,
        user_id: UUID,
        reply: str,
        inbound_message_id: UUID,
        task_id: UUID | None,
        trace_id: str,
    ) -> Any | None:
        from app.modules.agent.models import AgentMessage
        from app.modules.agent.runtime.telemetry import emit_event

        if not reply:
            return None
        outbound = AgentMessage(
            id=uuid4(),
            user_id=user_id,
            direction="outbound",
            content=reply,
            message_type="text",
            status="delivered",
            delivery_status="sent",
            delivered_at=datetime.now(timezone.utc),
            channel="cli",
            task_id=task_id,
            trace_id=trace_id,
            processing_status="completed",
        )
        await self.msg_repo.create(outbound)
        emit_event(
            logger,
            "agent.dev.message.completed",
            correlation_id=str(inbound_message_id),
            trace_id=trace_id,
            message_id=str(outbound.id),
            task_id=str(task_id) if task_id else None,
            channel="cli",
        )
        return outbound

    async def _process_production_reply(
        self,
        *,
        uid: UUID,
        binding: Any,
        parsed: Any,
        channel: DevChannel = "wechat",
    ) -> str:
        """Run the durable registry/function-calling path for persisted inbox work."""
        from pathlib import Path
        from uuid import uuid4

        from sqlalchemy import select

        from app.core.config import get_settings
        from app.modules.agent.models import AgentMessage, AgentTask
        from app.modules.agent.repository import AgentTaskRepository
        from app.modules.agent.runtime.context import ToolContext
        from app.modules.agent.runtime.deepseek_gateway import DeepSeekToolGateway
        from app.modules.agent.runtime.orchestrator import AgentRuntimeOrchestrator
        from app.modules.agent.runtime.stores import SqlConfirmationIssuer, SqlExecutionStore
        from app.modules.agent.runtime.task_worker import AgentTaskWorker
        from app.modules.agent.tools.factory import build_production_registry

        if (
            binding is None
            or binding.unbound_at is not None
            or binding.binding_epoch != int(parsed.binding_epoch)
        ):
            return "微信绑定已变化，本次任务未执行。请重新绑定后再试。"

        confirmation_reply = await self._try_process_confirmation(
            uid=uid,
            binding=binding,
            text=str(parsed.text or ""),
            channel=channel,
        )
        if confirmation_reply is not None:
            return confirmation_reply

        settings = get_settings()
        task_repo = AgentTaskRepository(self.session)
        thread_prefix = "cli" if channel == "cli" else "wechat"
        task_kind = "cli_agent" if channel == "cli" else "wechat_agent"
        task = await task_repo.create_task(
            user_id=uid,
            source_message_id=parsed.persisted_message_id,
            thread_id=f"{thread_prefix}:{binding.id}",
            kind=task_kind,
            summary="CLI 求职任务" if channel == "cli" else "微信求职任务",
            binding_id=binding.id,
            binding_epoch=binding.binding_epoch,
            prompt_version="wechat-agent.v2",
            tool_registry_version="intercraft-agent-tools.v1",
            status="queued",
        )
        parsed.task_id = task.id
        worker = AgentTaskWorker(
            self.session,
            user_id=uid,
            owner_id=uuid4(),
            claim_seconds=settings.wechat_agent_message_claim_seconds,
        )
        claimed = await worker.claim(task.id)
        if claimed is None:
            return "任务已由其他实例接收，正在处理中，不会重复执行。"
        await task_repo.append_event(claimed, stage="understanding", message="正在理解任务")
        prompt = (Path(__file__).parent / "prompts" / "system-v2.md").read_text(encoding="utf-8")

        async def cancel_check() -> bool:
            value = await self.session.scalar(
                select(AgentTask.cancel_requested_at).where(
                    AgentTask.id == claimed.id,
                    AgentTask.user_id == uid,
                )
            )
            return value is not None

        context = ToolContext(
            user_id=uid,
            task_id=claimed.id,
            tool_call_id="model",
            idempotency_key=f"task:{claimed.id}",
            correlation_id=str(parsed.persisted_message_id),
            trace_id=str(getattr(parsed, "trace_id", "unavailable")),
            channel=channel,
            binding_id=binding.id,
            binding_epoch=binding.binding_epoch,
            claim_generation=claimed.claim_generation,
            session=self.session,
            cancel_check=cancel_check,
        )
        orchestrator = AgentRuntimeOrchestrator(
            registry=build_production_registry(),
            gateway=DeepSeekToolGateway(
                user_id=str(uid),
                thread_id=claimed.thread_id,
                correlation_id=str(parsed.persisted_message_id),
                trace_id=str(getattr(parsed, "trace_id", "unavailable")),
                task_id=str(claimed.id),
            ),
            execution_store=SqlExecutionStore(self.session),
            confirmation_issuer=SqlConfirmationIssuer(self.session),
            system_prompt=prompt,
            max_turns=settings.agent_max_tool_turns,
        )
        run_started = time.perf_counter()
        try:
            history_filter = (
                AgentMessage.channel.in_(["cli", "wechat"])
                if channel == "cli"
                else AgentMessage.channel == "wechat"
            )
            history_rows = list(
                reversed(
                    (
                        await self.session.execute(
                            select(AgentMessage)
                            .where(
                                AgentMessage.user_id == uid,
                                history_filter,
                                AgentMessage.id != parsed.persisted_message_id,
                            )
                            .order_by(AgentMessage.created_at.desc())
                            .limit(10)
                        )
                    )
                    .scalars()
                    .all()
                )
            )
            conversation_history = [
                {
                    "role": "user" if row.direction == "inbound" else "assistant",
                    "content": (row.content or "")[:2000],
                }
                for row in history_rows
                if row.content and row.content != "💭 thinking…"
            ][-8:]
            with agent_span(
                "agent.run",
                correlation_id=context.correlation_id,
                trace_id=context.trace_id,
                task_id=str(context.task_id),
                binding_epoch=context.binding_epoch,
                claim_generation=context.claim_generation,
            ):
                outcome = await orchestrator.run(
                    context=context,
                    user_message=parsed.text,
                    conversation_history=conversation_history,
                )
            target_status = {
                "succeeded": "succeeded",
                "clarify": "awaiting_input",
                "awaiting_confirmation": "awaiting_confirmation",
                "running": "waiting_external",
            }.get(outcome.status, "failed")
            updated = await worker.transition(
                claimed,
                to_status=target_status,
                stage=target_status,
            )
            if updated is None:
                return "任务权限或执行租约已变化，结果未提交。"
            await task_repo.append_event(
                updated,
                stage=target_status,
                message=outcome.message[:500],
            )
            emit_event(
                logger,
                "agent.run.completed",
                correlation_id=str(parsed.persisted_message_id),
                trace_id=str(getattr(parsed, "trace_id", "unavailable")),
                task_id=str(claimed.id),
                status=outcome.status,
                terminal_reason=outcome.terminal_reason,
            )
            record_metric("agent_task_total", kind=claimed.kind, outcome=outcome.status)
            record_metric(
                "agent_task_duration_seconds",
                value=time.perf_counter() - run_started,
                kind=claimed.kind,
                outcome=outcome.status,
            )
            return outcome.message
        except Exception as exc:
            logger.error(
                "agent.production_run_failed",
                extra={"task_id": str(task.id), "error_type": type(exc).__name__},
            )
            await worker.transition(claimed, to_status="failed", stage="failed")
            record_metric("agent_task_total", kind=claimed.kind, outcome="failed")
            record_metric(
                "agent_task_duration_seconds",
                value=time.perf_counter() - run_started,
                kind=claimed.kind,
                outcome="failed",
            )
            return "任务处理失败，尚未确认成功。请稍后重试或查询任务状态。"

    async def _try_process_confirmation(
        self,
        *,
        uid: UUID,
        binding: Any,
        text: str,
        channel: DevChannel = "wechat",
    ) -> str | None:
        """Consume an exact durable confirmation and execute its persisted Tool call."""
        import json
        import re
        from datetime import UTC, datetime
        from uuid import uuid4

        from sqlalchemy import select, update

        from app.core.config import get_settings
        from app.modules.agent.models import AgentTask, AgentToolExecution
        from app.modules.agent.repository import AgentTaskRepository
        from app.modules.agent.runtime.confirmations import ConfirmationService
        from app.modules.agent.runtime.context import ToolContext
        from app.modules.agent.runtime.orchestrator import ExecutionRecord
        from app.modules.agent.runtime.stores import SqlExecutionStore
        from app.modules.agent.runtime.task_worker import AgentTaskWorker
        from app.modules.agent.tools.factory import build_production_registry
        from app.modules.agent.tools.result import ToolResultStatus

        confirmations = ConfirmationService(self.session, user_id=uid)
        cancel_match = re.fullmatch(r"\s*(取消|拒绝)\s+([^\s]+)\s*", text)
        if cancel_match is not None:
            token = cancel_match.group(2)
            pending = await confirmations.resolve_pending(token=token)
            if pending is None:
                return "确认标识无效、已使用或已过期，未执行任何操作。"
            decision = "cancel" if cancel_match.group(1) == "取消" else "reject"
            decided = await confirmations.decide(
                token=token,
                task_id=pending.task_id,
                decision=decision,
                expected_args_hash=pending.args_hash,
                expected_version=pending.version,
            )
            if decided is None:
                return "确认已失效或任务权限发生变化，未执行任何操作。"
            await self.session.execute(
                update(AgentToolExecution)
                .where(
                    AgentToolExecution.id == pending.tool_execution_id,
                    AgentToolExecution.user_id == uid,
                    AgentToolExecution.status == "awaiting_confirmation",
                )
                .values(status="cancelled", finished_at=datetime.now(UTC))
            )
            await AgentTaskRepository(self.session).request_cancel(uid, pending.task_id)
            return "已取消待确认操作，未产生业务变更。"

        edit_match = re.fullmatch(r"\s*修改\s+([^\s]+)\s+(.+)\s*", text)
        if edit_match is not None:
            token = edit_match.group(1)
            pending = await confirmations.resolve_pending(token=token)
            if pending is None:
                return "确认标识无效、已使用或已过期，未执行任何操作。"
            try:
                edited_args = json.loads(edit_match.group(2))
            except json.JSONDecodeError:
                return "修改内容格式无效，未变更原确认；请提供 JSON 对象。"
            if not isinstance(edited_args, dict):
                return "修改内容必须是 JSON 对象，未变更原确认。"
            try:
                replacement = await confirmations.edit_and_reissue(
                    token=token,
                    task_id=pending.task_id,
                    expected_args_hash=pending.args_hash,
                    expected_version=pending.version,
                    edited_args=edited_args,
                )
            except Exception as exc:
                from pydantic import ValidationError

                if isinstance(exc, ValidationError):
                    return "修改字段未通过工具校验，原确认仍有效。"
                raise
            if replacement is None:
                return "确认已失效或任务权限发生变化，未修改任何操作。"
            return (
                f"修改已校验。新确认标识：{replacement.token}。"
                "请核对后回复“确认 <标识>”；确认前不会执行。"
            )

        matched = re.fullmatch(r"\s*确认\s+([^\s]+)\s*", text)
        if matched is None:
            return None
        token = matched.group(1)
        pending = await confirmations.resolve_pending(token=token)
        if pending is None:
            return "确认标识无效、已使用或已过期，未执行任何操作。"
        consumed = await confirmations.decide(
            token=token,
            task_id=pending.task_id,
            decision="approve",
            expected_args_hash=pending.args_hash,
            expected_version=pending.version,
        )
        if consumed is None:
            return "确认已失效或任务权限发生变化，未执行任何操作。"

        execution = await self.session.scalar(
            select(AgentToolExecution).where(
                AgentToolExecution.id == pending.tool_execution_id,
                AgentToolExecution.user_id == uid,
            )
        )
        if execution is None:
            return "未找到对应工具执行记录，未执行任何操作。"
        tasks = AgentTaskRepository(self.session)
        queued = await tasks.queue_after_confirmation(
            uid, pending.task_id, binding_epoch=binding.binding_epoch
        )
        if queued is None:
            return "任务状态已变化，确认未触发重复执行。"
        settings = get_settings()
        worker = AgentTaskWorker(
            self.session,
            user_id=uid,
            owner_id=uuid4(),
            claim_seconds=settings.wechat_agent_message_claim_seconds,
        )
        claimed = await worker.claim(queued.id)
        if claimed is None:
            return "任务已由其他实例接管，正在处理中。"
        changed = await self.session.execute(
            update(AgentToolExecution)
            .where(
                AgentToolExecution.id == execution.id,
                AgentToolExecution.user_id == uid,
                AgentToolExecution.status == "awaiting_confirmation",
                AgentToolExecution.binding_epoch == binding.binding_epoch,
            )
            .values(
                status="running",
                claim_generation=claimed.claim_generation,
                started_at=datetime.now(UTC),
            )
        )
        if changed.rowcount != 1:
            return "工具调用已被处理或权限已变化，不会重复执行。"

        registry = build_production_registry()
        definition = registry.get(execution.tool_name)

        async def cancel_check() -> bool:
            value = await self.session.scalar(
                select(AgentTask.cancel_requested_at).where(
                    AgentTask.id == claimed.id, AgentTask.user_id == uid
                )
            )
            return value is not None

        context = ToolContext(
            user_id=uid,
            task_id=claimed.id,
            tool_call_id=execution.tool_call_id,
            idempotency_key=execution.idempotency_key,
            correlation_id=str(claimed.source_message_id or claimed.id),
            trace_id="unavailable",
            channel=channel,
            binding_id=binding.id,
            binding_epoch=binding.binding_epoch,
            claim_generation=claimed.claim_generation,
            session=self.session,
            cancel_check=cancel_check,
        )
        record = ExecutionRecord(
            id=execution.id,
            user_id=uid,
            task_id=claimed.id,
            tool_call_id=execution.tool_call_id,
            tool_name=execution.tool_name,
            tool_version=execution.tool_version,
            args_hash=execution.args_hash,
            arguments=execution.args_json,
            idempotency_key=execution.idempotency_key,
            side_effect=execution.side_effect,
            atomicity=execution.atomicity,
            binding_id=binding.id,
            binding_epoch=binding.binding_epoch,
            claim_generation=claimed.claim_generation,
            requires_confirmation=True,
        )
        effect_unit = await self.session.begin_nested()
        tool_started = time.perf_counter()
        try:
            with agent_span(
                "agent.tool.confirmed",
                correlation_id=context.correlation_id,
                trace_id=context.trace_id,
                task_id=str(context.task_id),
                tool_call_id=context.tool_call_id,
                binding_epoch=context.binding_epoch,
                claim_generation=context.claim_generation,
            ):
                result = await registry.execute(definition.name, execution.args_json, context)
                await SqlExecutionStore(self.session).complete(record, result)
                await effect_unit.commit()
        except Exception:
            if effect_unit.is_active:
                await effect_unit.rollback()
            record_metric("agent_tool_calls_total", tool=definition.name, outcome="failed")
            record_metric(
                "agent_tool_duration_seconds",
                value=time.perf_counter() - tool_started,
                tool=definition.name,
            )
            await worker.transition(claimed, to_status="failed", stage="failed")
            return "工具执行未能形成可验证的原子提交，本次未确认成功。"
        emit_event(
            logger,
            "agent.tool.completed",
            correlation_id=context.correlation_id,
            trace_id=context.trace_id,
            task_id=str(context.task_id),
            tool_call_id=context.tool_call_id,
            tool=definition.name,
            status=result.status.value,
            committed=result.committed,
            resource_type=result.resource_refs[0].type if result.resource_refs else None,
            latency_ms=int((time.perf_counter() - tool_started) * 1000),
            error_category=result.error.category if result.error else None,
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
                logger,
                "agent.db.committed",
                correlation_id=context.correlation_id,
                trace_id=context.trace_id,
                task_id=str(context.task_id),
                tool_call_id=context.tool_call_id,
                operation=definition.name,
                resource_type=result.resource_refs[0].type if result.resource_refs else None,
                resource_id=result.resource_refs[0].id if result.resource_refs else None,
            )
        target = "succeeded" if result.status == ToolResultStatus.SUCCEEDED else "failed"
        updated = await worker.transition(claimed, to_status=target, stage=target)
        if updated is None:
            return "执行租约已变化，无法确认提交结果。"
        return result.user_message

    # ── Status ─────────────────────────────────────────────────────

    async def get_agent_status(self, user_id: UUID) -> dict:
        agent = await self.agent_repo.get_by_user(user_id)
        if agent is None:
            agent = await self.ensure_agent_exists(user_id)
        binding = await self.bind_repo.get_by_user(user_id)
        counts = await self.msg_repo.count_by_user(user_id)
        pref = await self.pref_repo.get_by_user(user_id)
        return {
            "user_id": user_id,
            "status": agent.status,
            "display_name": pref.display_name if pref else "我的求职助手",
            "wechat_bound": binding is not None and binding.unbound_at is None,
            "last_heartbeat_at": agent.last_heartbeat_at,
            "messages_sent_total": counts["sent"],
            "messages_received_total": counts["received"],
        }

    async def get_binding_status(self, user_id: UUID) -> dict:
        binding = await self.bind_repo.get_by_user(user_id)
        agent = await self.agent_repo.get_by_user(user_id)
        return {
            "bound": binding is not None and binding.unbound_at is None,
            "wechat_nickname": None,  # iLink doesn't expose nickname via API directly
            "wechat_avatar_url": None,
            "bound_at": binding.bound_at
            if binding is not None and binding.unbound_at is None
            else None,
            "agent_status": agent.status if agent else "dormant",
        }

    async def is_wechat_uin_bound(self, wechat_uin: str) -> bool:
        binding = await self.bind_repo.get_by_wechat_uin(wechat_uin)
        return binding is not None

    # ── Heartbeat ──────────────────────────────────────────────────

    async def heartbeat(self, user_id: UUID) -> None:
        await self.agent_repo.update_heartbeat(user_id)


# ── Token encryption helpers ────────────────────────────────────────


def _get_fernet() -> Fernet:
    return Fernet(_TOKEN_ENCRYPTION_KEY)


def _encrypt_token(token: str) -> bytes:
    return _get_fernet().encrypt(token.encode("utf-8"))


def encrypt_sensitive_text(value: str) -> bytes:
    """Encrypt durable channel payload text with the existing Agent key."""
    return _encrypt_token(value)


def decrypt_token(encrypted: bytes) -> str:
    return _get_fernet().decrypt(encrypted).decode("utf-8")


# ── Errors ─────────────────────────────────────────────────────────


class WeChatAlreadyBoundError(Exception):
    def __init__(self, wechat_uin: str, bound_user_id: str) -> None:
        self.wechat_uin = wechat_uin
        self.bound_user_id = bound_user_id
        super().__init__(f"WeChat account {wechat_uin} already bound to user {bound_user_id}")


__all__ = [
    "AgentService",
    "DevChatResult",
    "DevInboundError",
    "WeChatAlreadyBoundError",
    "decrypt_token",
    "encrypt_sensitive_text",
]
