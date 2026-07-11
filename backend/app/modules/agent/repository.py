"""Agent repositories — CRUD for 6 agent tables (REQ-052 T012).

Each repository enforces RLS via explicit user_id filtering.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import func, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.agent.models import (
    Agent,
    AgentMessage,
    AgentPreference,
    AgentStatusHistory,
    AgentTask,
    AgentTaskEvent,
    AgentToolExecution,
    WeChatBinding,
    WeChatCredential,
)

# ── AgentRepository ─────────────────────────────────────────────────


class AgentRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_user(self, user_id: UUID) -> Agent | None:
        stmt = select(Agent).where(Agent.user_id == user_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def create(self, agent: Agent) -> Agent:
        self.session.add(agent)
        await self.session.flush()
        await self.session.refresh(agent)
        return agent

    async def update_status(self, user_id: UUID, status: str) -> Agent | None:
        agent = await self.get_by_user(user_id)
        if agent is None:
            return None
        agent.status = status
        agent.status_changed_at = datetime.now(timezone.utc)
        agent.updated_at = datetime.now(timezone.utc)
        await self.session.flush()
        return agent

    async def update_heartbeat(self, user_id: UUID) -> None:
        stmt = (
            update(Agent)
            .where(Agent.user_id == user_id)
            .values(last_heartbeat_at=datetime.now(timezone.utc))
        )
        await self.session.execute(stmt)
        await self.session.flush()

    async def set_wechat_uin(self, user_id: UUID, wechat_uin: str) -> None:
        stmt = (
            update(Agent)
            .where(Agent.user_id == user_id)
            .values(wechat_uin=wechat_uin, updated_at=datetime.now(timezone.utc))
        )
        await self.session.execute(stmt)
        await self.session.flush()

    async def list_by_status(self, status: str, limit: int = 500) -> list[Agent]:
        stmt = (
            select(Agent)
            .where(Agent.status == status)
            .order_by(Agent.last_heartbeat_at.asc().nulls_first())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())


# ── WeChatCredentialRepository ──────────────────────────────────────


class WeChatCredentialRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_user(self, user_id: UUID) -> WeChatCredential | None:
        stmt = select(WeChatCredential).where(WeChatCredential.user_id == user_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def upsert(
        self,
        user_id: UUID,
        bot_token_encrypted: bytes | None = None,
        base_url: str = "https://ilinkai.weixin.qq.com",
    ) -> WeChatCredential:
        cred = await self.get_by_user(user_id)
        if cred is None:
            cred = WeChatCredential(
                user_id=user_id,
                bot_token_encrypted=bot_token_encrypted,
                base_url=base_url,
                status="active",
            )
            self.session.add(cred)
        else:
            cred.bot_token_encrypted = bot_token_encrypted
            cred.base_url = base_url
            cred.status = "active"
            cred.updated_at = datetime.now(timezone.utc)
        await self.session.flush()
        await self.session.refresh(cred)
        await self.session.execute(
            text(
                "INSERT INTO wechat_consumer_registrations "
                "(user_id, credential_id, cursor, active, updated_at) "
                "VALUES (:user_id, :credential_id, :cursor, true, now()) "
                "ON CONFLICT (user_id) DO UPDATE SET "
                "credential_id=EXCLUDED.credential_id, cursor=EXCLUDED.cursor, "
                "active=true, updated_at=now()"
            ),
            {"user_id": user_id, "credential_id": cred.id, "cursor": cred.cursor or ""},
        )
        return cred

    async def update_cursor(self, user_id: UUID, cursor: str) -> None:
        stmt = (
            update(WeChatCredential)
            .where(WeChatCredential.user_id == user_id)
            .values(
                cursor=cursor,
                last_polled_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )
        )
        await self.session.execute(stmt)
        await self.session.execute(
            text(
                "UPDATE wechat_consumer_registrations "
                "SET cursor=:cursor, updated_at=now() WHERE user_id=:user_id"
            ),
            {"cursor": cursor, "user_id": user_id},
        )
        await self.session.flush()

    async def update_context_token(self, user_id: UUID, context_token: str) -> None:
        stmt = (
            update(WeChatCredential)
            .where(WeChatCredential.user_id == user_id)
            .values(context_token=context_token, updated_at=datetime.now(timezone.utc))
        )
        await self.session.execute(stmt)
        await self.session.flush()

    async def revoke(self, user_id: UUID) -> None:
        stmt = (
            update(WeChatCredential)
            .where(WeChatCredential.user_id == user_id)
            .values(status="revoked", updated_at=datetime.now(timezone.utc))
        )
        await self.session.execute(stmt)
        await self.session.execute(
            text(
                "UPDATE wechat_consumer_registrations "
                "SET active=false, updated_at=now() WHERE user_id=:user_id"
            ),
            {"user_id": user_id},
        )
        await self.session.flush()

    async def mark_expired(self, user_id: UUID) -> None:
        stmt = (
            update(WeChatCredential)
            .where(WeChatCredential.user_id == user_id)
            .values(status="expired", updated_at=datetime.now(timezone.utc))
        )
        await self.session.execute(stmt)
        await self.session.execute(
            text(
                "UPDATE wechat_consumer_registrations "
                "SET active=false, updated_at=now() WHERE user_id=:user_id"
            ),
            {"user_id": user_id},
        )
        await self.session.flush()

    async def list_active(self, limit: int = 100) -> list[WeChatCredential]:
        stmt = select(WeChatCredential).where(WeChatCredential.status == "active").limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def list_active_no_rls(self, limit: int = 100) -> list[WeChatCredential]:
        """List active credentials bypassing RLS — for connection pool startup."""
        raise PermissionError(
            "cross-tenant credential reads are disabled; use "
            "get_active_credentials() and tenant-scoped sessions"
        )


# ── WeChatBindingRepository ─────────────────────────────────────────


class WeChatBindingRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_user(self, user_id: UUID) -> WeChatBinding | None:
        # NOTE: do NOT filter on unbound_at IS NULL. ``unbind()`` is a soft
        # delete — the row is preserved so the user can re-bind later. If we
        # filtered, ``bind_wechat()`` would always see "no binding" for a
        # previously-unbound user and try to INSERT, which collides with the
        # ``wechat_bindings_user_id_key`` unique constraint and 500s the poll.
        stmt = select(WeChatBinding).where(
            WeChatBinding.user_id == user_id,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_wechat_uin(self, wechat_uin: str) -> WeChatBinding | None:
        stmt = select(WeChatBinding).where(
            WeChatBinding.wechat_uin == wechat_uin,
            WeChatBinding.unbound_at.is_(None),
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def create(
        self,
        user_id: UUID,
        wechat_uin: str,
    ) -> WeChatBinding:
        binding = WeChatBinding(
            user_id=user_id,
            wechat_uin=wechat_uin,
            last_qrcode_login_at=datetime.now(timezone.utc),
        )
        self.session.add(binding)
        await self.session.flush()
        await self.session.refresh(binding)
        return binding

    async def unbind(self, user_id: UUID) -> bool:
        binding = await self.get_by_user(user_id)
        if binding is None:
            return False
        binding.unbound_at = datetime.now(timezone.utc)
        binding.binding_epoch += 1
        await self.session.flush()
        return True


# ── AgentMessageRepository ──────────────────────────────────────────


class AgentMessageRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, msg: AgentMessage) -> AgentMessage:
        self.session.add(msg)
        await self.session.flush()
        await self.session.refresh(msg)
        return msg

    async def update_status(
        self, msg_id: UUID, status: str, error_message: str | None = None
    ) -> None:
        values: dict = {"status": status}
        if status == "sent":
            values["sent_at"] = datetime.now(timezone.utc)
        if error_message:
            values["error_message"] = error_message
        stmt = update(AgentMessage).where(AgentMessage.id == msg_id).values(**values)
        await self.session.execute(stmt)
        await self.session.flush()

    async def list_by_user(self, user_id: UUID, limit: int = 50) -> list[AgentMessage]:
        stmt = (
            select(AgentMessage)
            .where(AgentMessage.user_id == user_id)
            .order_by(AgentMessage.created_at.desc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def list_pending(self, user_id: UUID) -> list[AgentMessage]:
        """Find pending outbound messages for queue rebuild."""
        stmt = (
            select(AgentMessage)
            .where(
                AgentMessage.user_id == user_id,
                AgentMessage.direction == "outbound",
                AgentMessage.status == "pending",
            )
            .order_by(AgentMessage.created_at.asc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def claim_outbound(
        self,
        user_id: UUID,
        *,
        owner_id: UUID,
        claim_seconds: int,
        limit: int = 20,
    ) -> list[AgentMessage]:
        """Atomically claim deliverable rows; expired claims may be recovered."""
        now = datetime.now(timezone.utc)
        candidate_ids = (
            select(AgentMessage.id)
            .where(
                AgentMessage.user_id == user_id,
                AgentMessage.direction == "outbound",
                AgentMessage.status.in_(["pending", "sending"]),
                AgentMessage.delivery_status.in_(["pending", "retry_wait", "claimed"]),
                (AgentMessage.next_attempt_at.is_(None)) | (AgentMessage.next_attempt_at <= now),
                (AgentMessage.claim_until.is_(None)) | (AgentMessage.claim_until <= now),
            )
            .order_by(AgentMessage.created_at.asc())
            .with_for_update(skip_locked=True)
            .limit(limit)
        )
        stmt = (
            update(AgentMessage)
            .where(AgentMessage.id.in_(candidate_ids))
            .values(
                status="sending",
                delivery_status="claimed",
                claim_owner=owner_id,
                claim_until=now + timedelta(seconds=claim_seconds),
                attempt_count=AgentMessage.attempt_count + 1,
                error_category=None,
                error_detail_redacted=None,
            )
            .returning(AgentMessage)
        )
        result = await self.session.execute(stmt)
        await self.session.flush()
        return list(result.scalars().all())

    async def finish_outbound_claim(
        self,
        message_id: UUID,
        *,
        owner_id: UUID,
        delivery_status: str,
        error_category: str | None = None,
        retry_at: datetime | None = None,
    ) -> bool:
        """CAS-complete a delivery claim so stale workers cannot overwrite it."""
        values: dict[str, object | None] = {
            "delivery_status": delivery_status,
            "claim_owner": None,
            "claim_until": None,
            "next_attempt_at": retry_at,
            "error_category": error_category,
        }
        if delivery_status == "sent":
            values.update(
                status="sent",
                sent_at=datetime.now(timezone.utc),
                delivered_at=datetime.now(timezone.utc),
            )
        elif delivery_status == "failed":
            values["status"] = "failed"
        elif delivery_status == "retry_wait":
            values["status"] = "pending"
        elif delivery_status == "unknown_delivery":
            values["status"] = "unknown_delivery"
        stmt = (
            update(AgentMessage)
            .where(
                AgentMessage.id == message_id,
                AgentMessage.claim_owner == owner_id,
                AgentMessage.delivery_status == "claimed",
            )
            .values(**values)
        )
        result = await self.session.execute(stmt)
        await self.session.flush()
        return bool(result.rowcount)

    async def count_by_user(self, user_id: UUID) -> dict:
        """Return sent/received counts for a user."""
        sent = await self.session.scalar(
            select(func.count(AgentMessage.id)).where(
                AgentMessage.user_id == user_id,
                AgentMessage.direction == "outbound",
                AgentMessage.status == "sent",
            )
        )
        received = await self.session.scalar(
            select(func.count(AgentMessage.id)).where(
                AgentMessage.user_id == user_id,
                AgentMessage.direction == "inbound",
            )
        )
        return {"sent": sent or 0, "received": received or 0}


# ── AgentPreferenceRepository ───────────────────────────────────────


class AgentPreferenceRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_user(self, user_id: UUID) -> AgentPreference | None:
        stmt = select(AgentPreference).where(AgentPreference.user_id == user_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def upsert(
        self,
        user_id: UUID,
        display_name: str | None = None,
        quiet_hours_start: Any = ...,
        quiet_hours_end: Any = ...,
        notification_mode: str | None = None,
    ) -> AgentPreference:
        """Upsert preferences.

        ``quiet_hours_*`` use Ellipsis as "leave unchanged" so callers can
        explicitly clear DND by passing ``None``.
        """
        pref = await self.get_by_user(user_id)
        if pref is None:
            pref = AgentPreference(user_id=user_id)
            self.session.add(pref)
        if display_name is not None:
            pref.display_name = display_name
        if quiet_hours_start is not ...:
            pref.quiet_hours_start = quiet_hours_start
        if quiet_hours_end is not ...:
            pref.quiet_hours_end = quiet_hours_end
        if notification_mode is not None:
            pref.notification_mode = notification_mode
        pref.updated_at = datetime.now(timezone.utc)
        await self.session.flush()
        await self.session.refresh(pref)
        return pref


# ── AgentStatusHistoryRepository ────────────────────────────────────


class AgentStatusHistoryRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def record(
        self,
        user_id: UUID,
        old_status: str,
        new_status: str,
        reason: str,
    ) -> AgentStatusHistory:
        entry = AgentStatusHistory(
            user_id=user_id,
            old_status=old_status,
            new_status=new_status,
            reason=reason,
        )
        self.session.add(entry)
        await self.session.flush()
        await self.session.refresh(entry)
        return entry

    async def list_by_user(self, user_id: UUID, limit: int = 20) -> list[AgentStatusHistory]:
        stmt = (
            select(AgentStatusHistory)
            .where(AgentStatusHistory.user_id == user_id)
            .order_by(AgentStatusHistory.changed_at.desc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())


class AgentTaskRepository:
    """Owner-scoped durable task operations with claim and binding fencing."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, user_id: UUID, task_id: UUID) -> AgentTask | None:
        return await self.session.scalar(
            select(AgentTask).where(
                AgentTask.id == task_id,
                AgentTask.user_id == user_id,
            )
        )

    async def list_recent(
        self,
        user_id: UUID,
        *,
        status: str | None = None,
        limit: int = 50,
    ) -> list[AgentTask]:
        statement = select(AgentTask).where(AgentTask.user_id == user_id)
        if status:
            statement = statement.where(AgentTask.status == status)
        rows = await self.session.execute(
            statement.order_by(AgentTask.created_at.desc()).limit(limit)
        )
        return list(rows.scalars().all())

    async def request_cancel(self, user_id: UUID, task_id: UUID) -> AgentTask | None:
        task = await self.get_by_id(user_id, task_id)
        if task is None or task.status in {"succeeded", "cancelled", "dead_letter"}:
            return None
        now = datetime.now(timezone.utc)
        immediate = task.status in {
            "received",
            "understanding",
            "awaiting_input",
            "awaiting_confirmation",
            "queued",
            "retry_wait",
            "failed",
        }
        task.status = "cancelled" if immediate else "cancel_requested"
        task.stage = task.status
        task.cancel_requested_at = now
        task.completed_at = now if immediate else None
        task.version += 1
        await self.session.flush()
        return task

    async def resume_task(self, user_id: UUID, task_id: UUID) -> AgentTask | None:
        task = await self.session.scalar(
            select(AgentTask)
            .where(AgentTask.id == task_id, AgentTask.user_id == user_id)
            .with_for_update()
        )
        if task is None or task.status not in {"failed", "unknown_result", "cancelled"}:
            return None
        if (
            task.schema_version != "agent-task.v1"
            or task.prompt_version != "wechat-agent.v2"
            or task.tool_registry_version != "intercraft-agent-tools.v1"
        ):
            return None
        binding = await self.session.scalar(
            select(WeChatBinding).where(
                WeChatBinding.id == task.binding_id,
                WeChatBinding.user_id == user_id,
                WeChatBinding.unbound_at.is_(None),
                WeChatBinding.binding_epoch == task.binding_epoch,
            )
        )
        if binding is None:
            return None
        unresolved_execution = await self.session.scalar(
            select(AgentToolExecution.id).where(
                AgentToolExecution.task_id == task.id,
                AgentToolExecution.user_id == user_id,
                AgentToolExecution.status.in_(("claimed", "running", "unknown_result")),
            )
        )
        if unresolved_execution is not None:
            return None
        existing_resume = await self.session.scalar(
            select(AgentTask.id).where(
                AgentTask.user_id == user_id,
                AgentTask.resume_from_task_id == task.id,
            )
        )
        if existing_resume is not None:
            return None
        resumed = AgentTask(
            user_id=user_id,
            source_message_id=None,
            thread_id=task.thread_id,
            kind=task.kind,
            status="queued",
            stage="resume_queued",
            summary=task.summary,
            context_json=dict(task.context_json or {}),
            resume_from_task_id=task.id,
            prompt_version=task.prompt_version,
            tool_registry_version=task.tool_registry_version,
            schema_version=task.schema_version,
            binding_id=task.binding_id,
            binding_epoch=task.binding_epoch,
        )
        self.session.add(resumed)
        await self.session.flush()
        await self.session.refresh(resumed)
        return resumed

    async def replay_message(self, user_id: UUID, source_message_id: UUID) -> AgentTask | None:
        """Create one audited retry lineage from a dead-letter source message."""
        task = await self.session.scalar(
            select(AgentTask)
            .where(
                AgentTask.user_id == user_id,
                AgentTask.source_message_id == source_message_id,
            )
            .with_for_update()
        )
        if task is None or task.status != "dead_letter":
            return None
        if (
            task.schema_version != "agent-task.v1"
            or task.prompt_version != "wechat-agent.v2"
            or task.tool_registry_version != "intercraft-agent-tools.v1"
        ):
            return None
        binding = await self.session.scalar(
            select(WeChatBinding.id).where(
                WeChatBinding.id == task.binding_id,
                WeChatBinding.user_id == user_id,
                WeChatBinding.unbound_at.is_(None),
                WeChatBinding.binding_epoch == task.binding_epoch,
            )
        )
        if binding is None:
            return None
        unresolved = await self.session.scalar(
            select(AgentToolExecution.id).where(
                AgentToolExecution.task_id == task.id,
                AgentToolExecution.user_id == user_id,
                AgentToolExecution.status.in_(("claimed", "running", "unknown_result")),
            )
        )
        if unresolved is not None:
            return None
        already_replayed = await self.session.scalar(
            select(AgentTask.id).where(
                AgentTask.user_id == user_id,
                AgentTask.resume_from_task_id == task.id,
            )
        )
        if already_replayed is not None:
            return None
        replay = AgentTask(
            user_id=user_id,
            source_message_id=None,
            thread_id=task.thread_id,
            kind=task.kind,
            status="queued",
            stage="replay_queued",
            summary=task.summary,
            context_json=dict(task.context_json or {}),
            resume_from_task_id=task.id,
            prompt_version=task.prompt_version,
            tool_registry_version=task.tool_registry_version,
            schema_version=task.schema_version,
            binding_id=task.binding_id,
            binding_epoch=task.binding_epoch,
        )
        self.session.add(replay)
        await self.session.flush()
        await self.session.refresh(replay)
        await self.append_event(
            replay,
            stage="replay_queued",
            message="已创建经审计的安全重放任务",
        )
        return replay

    async def create_task(
        self,
        *,
        user_id: UUID,
        source_message_id: UUID | None,
        thread_id: str,
        kind: str,
        summary: str,
        binding_id: UUID,
        binding_epoch: int,
        prompt_version: str,
        tool_registry_version: str,
        status: str = "received",
    ) -> AgentTask:
        task = AgentTask(
            user_id=user_id,
            source_message_id=source_message_id,
            thread_id=thread_id,
            kind=kind,
            status=status,
            stage=status,
            summary=summary,
            binding_id=binding_id,
            binding_epoch=binding_epoch,
            prompt_version=prompt_version,
            tool_registry_version=tool_registry_version,
        )
        self.session.add(task)
        await self.session.flush()
        await self.session.refresh(task)
        return task

    async def claim_task(
        self,
        user_id: UUID,
        task_id: UUID,
        *,
        owner_id: UUID,
        claim_seconds: int,
    ) -> AgentTask | None:
        now = datetime.now(timezone.utc)
        statement = (
            update(AgentTask)
            .where(
                AgentTask.id == task_id,
                AgentTask.user_id == user_id,
                AgentTask.status.in_(("queued", "retry_wait", "running", "waiting_external")),
                (AgentTask.claim_until.is_(None)) | (AgentTask.claim_until <= now),
                select(WeChatBinding.id)
                .where(
                    WeChatBinding.id == AgentTask.binding_id,
                    WeChatBinding.user_id == user_id,
                    WeChatBinding.unbound_at.is_(None),
                    WeChatBinding.binding_epoch == AgentTask.binding_epoch,
                )
                .exists(),
            )
            .values(
                status="running",
                stage="running",
                claim_owner=owner_id,
                claim_until=now + timedelta(seconds=claim_seconds),
                claim_generation=AgentTask.claim_generation + 1,
                version=AgentTask.version + 1,
                updated_at=now,
            )
            .returning(AgentTask)
        )
        return (await self.session.execute(statement)).scalar_one_or_none()

    async def transition_claimed(
        self,
        user_id: UUID,
        task_id: UUID,
        *,
        owner_id: UUID,
        claim_generation: int,
        binding_epoch: int,
        from_status: str,
        to_status: str,
        stage: str,
    ) -> AgentTask | None:
        from app.modules.agent.runtime.schemas import (
            TaskStatus,
            validate_task_transition,
        )

        validate_task_transition(TaskStatus(from_status), TaskStatus(to_status))
        now = datetime.now(timezone.utc)
        terminal = to_status in {"succeeded", "failed", "cancelled", "dead_letter"}
        statement = (
            update(AgentTask)
            .where(
                AgentTask.id == task_id,
                AgentTask.user_id == user_id,
                AgentTask.status == from_status,
                AgentTask.claim_owner == owner_id,
                AgentTask.claim_generation == claim_generation,
                AgentTask.binding_epoch == binding_epoch,
                AgentTask.claim_until > now,
                select(WeChatBinding.id)
                .where(
                    WeChatBinding.id == AgentTask.binding_id,
                    WeChatBinding.user_id == user_id,
                    WeChatBinding.unbound_at.is_(None),
                    WeChatBinding.binding_epoch == binding_epoch,
                )
                .exists(),
            )
            .values(
                status=to_status,
                stage=stage,
                version=AgentTask.version + 1,
                updated_at=now,
                completed_at=now if terminal else None,
                claim_owner=None if terminal or to_status == "awaiting_confirmation" else owner_id,
                claim_until=None
                if terminal or to_status == "awaiting_confirmation"
                else AgentTask.claim_until,
            )
            .returning(AgentTask)
        )
        return (await self.session.execute(statement)).scalar_one_or_none()

    async def queue_after_confirmation(
        self,
        user_id: UUID,
        task_id: UUID,
        *,
        binding_epoch: int,
    ) -> AgentTask | None:
        statement = (
            update(AgentTask)
            .where(
                AgentTask.id == task_id,
                AgentTask.user_id == user_id,
                AgentTask.status == "awaiting_confirmation",
                AgentTask.binding_epoch == binding_epoch,
                select(WeChatBinding.id)
                .where(
                    WeChatBinding.id == AgentTask.binding_id,
                    WeChatBinding.user_id == user_id,
                    WeChatBinding.unbound_at.is_(None),
                    WeChatBinding.binding_epoch == binding_epoch,
                )
                .exists(),
            )
            .values(
                status="queued",
                stage="confirmed",
                version=AgentTask.version + 1,
                updated_at=datetime.now(timezone.utc),
            )
            .returning(AgentTask)
        )
        return (await self.session.execute(statement)).scalar_one_or_none()

    async def recover_expired_task(
        self,
        user_id: UUID,
        task_id: UUID,
        *,
        max_attempts: int,
    ) -> AgentTask | None:
        """Recover one owner-scoped stale task without replaying unknown effects."""
        if max_attempts < 1:
            raise ValueError("max_attempts must be positive")
        now = datetime.now(timezone.utc)
        task = await self.session.scalar(
            select(AgentTask)
            .where(AgentTask.id == task_id, AgentTask.user_id == user_id)
            .with_for_update()
        )
        if task is None or task.status not in {
            "running",
            "waiting_external",
            "cancel_requested",
        }:
            return None
        if task.status != "cancel_requested" and (
            task.claim_until is None or task.claim_until > now
        ):
            return None

        binding_active = await self.session.scalar(
            select(WeChatBinding.id).where(
                WeChatBinding.id == task.binding_id,
                WeChatBinding.user_id == user_id,
                WeChatBinding.unbound_at.is_(None),
                WeChatBinding.binding_epoch == task.binding_epoch,
            )
        )
        executions = list(
            (
                await self.session.execute(
                    select(AgentToolExecution).where(
                        AgentToolExecution.task_id == task.id,
                        AgentToolExecution.user_id == user_id,
                    )
                )
            )
            .scalars()
            .all()
        )

        error_category: str | None = None
        if task.status == "cancel_requested" or binding_active is None:
            target = "cancelled"
            error_category = "binding_revoked" if binding_active is None else None
        elif any(
            execution.status == "succeeded" and execution.committed_at is not None
            for execution in executions
        ):
            target = "succeeded"
        elif (
            any(
                execution.status in {"claimed", "running", "unknown_result"}
                for execution in executions
            )
            or task.status == "waiting_external"
        ):
            target = "unknown_result"
            error_category = "unknown_result"
        elif task.claim_generation >= max_attempts:
            target = "dead_letter"
            error_category = "retry_exhausted"
        else:
            target = "retry_wait"
            error_category = "stale_claim"

        terminal = target in {"succeeded", "cancelled", "dead_letter"}
        task.status = target
        task.stage = target
        task.error_category = error_category
        task.claim_owner = None
        task.claim_until = None
        task.completed_at = now if terminal else None
        task.version += 1
        task.updated_at = now
        await self.session.flush()
        await self.append_event(
            task,
            stage=target,
            message={
                "retry_wait": "任务执行租约过期, 已进入安全重试队列",
                "unknown_result": "任务执行结果需要先对账, 未自动重放",
                "dead_letter": "任务重试已耗尽, 等待人工处理",
                "cancelled": "任务已在安全检查点取消",
                "succeeded": "已根据持久提交证据恢复任务终态",
            }[target],
        )
        return task

    async def append_event(
        self,
        task: AgentTask,
        *,
        stage: str,
        message: str,
        percent: int | None = None,
    ) -> AgentTaskEvent:
        await self.session.execute(
            select(AgentTask.id)
            .where(AgentTask.id == task.id, AgentTask.user_id == task.user_id)
            .with_for_update()
        )
        last_sequence = await self.session.scalar(
            select(func.max(AgentTaskEvent.sequence)).where(
                AgentTaskEvent.task_id == task.id,
                AgentTaskEvent.user_id == task.user_id,
            )
        )
        event = AgentTaskEvent(
            task_id=task.id,
            user_id=task.user_id,
            sequence=int(last_sequence or 0) + 1,
            status=task.status,
            stage=stage,
            percent=percent,
            message=message,
        )
        self.session.add(event)
        await self.session.flush()
        return event

    async def link_event_delivery(
        self,
        user_id: UUID,
        task_id: UUID,
        sequence: int,
        delivery_message_id: UUID,
    ) -> AgentTaskEvent | None:
        """Idempotently bind one progress event to one owner-scoped outbox row."""
        statement = (
            update(AgentTaskEvent)
            .where(
                AgentTaskEvent.user_id == user_id,
                AgentTaskEvent.task_id == task_id,
                AgentTaskEvent.sequence == sequence,
                (
                    AgentTaskEvent.delivery_message_id.is_(None)
                    | (AgentTaskEvent.delivery_message_id == delivery_message_id)
                ),
                select(AgentMessage.id)
                .where(
                    AgentMessage.id == delivery_message_id,
                    AgentMessage.user_id == user_id,
                    AgentMessage.direction == "outbound",
                )
                .exists(),
            )
            .values(delivery_message_id=delivery_message_id)
            .returning(AgentTaskEvent)
        )
        return (await self.session.execute(statement)).scalar_one_or_none()


__all__ = [
    "AgentRepository",
    "WeChatCredentialRepository",
    "WeChatBindingRepository",
    "AgentMessageRepository",
    "AgentPreferenceRepository",
    "AgentStatusHistoryRepository",
    "AgentTaskRepository",
]
