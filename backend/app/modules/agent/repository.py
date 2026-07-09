"""Agent repositories — CRUD for 6 agent tables (REQ-052 T012).

Each repository enforces RLS via explicit user_id filtering.
"""

from __future__ import annotations

from datetime import datetime, time as dt_time, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.agent.models import (
    Agent,
    AgentMessage,
    AgentPreference,
    AgentStatusHistory,
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
        await self.session.flush()

    async def mark_expired(self, user_id: UUID) -> None:
        stmt = (
            update(WeChatCredential)
            .where(WeChatCredential.user_id == user_id)
            .values(status="expired", updated_at=datetime.now(timezone.utc))
        )
        await self.session.execute(stmt)
        await self.session.flush()

    async def list_active(self, limit: int = 100) -> list[WeChatCredential]:
        stmt = (
            select(WeChatCredential)
            .where(WeChatCredential.status == "active")
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def list_active_no_rls(self, limit: int = 100) -> list[WeChatCredential]:
        """List active credentials bypassing RLS — for connection pool startup."""
        from sqlalchemy import text as sa_text
        await self.session.execute(sa_text("SET row_security = off"))
        stmt = (
            select(WeChatCredential)
            .where(WeChatCredential.status == "active")
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())


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

    async def list_by_user(
        self, user_id: UUID, limit: int = 50
    ) -> list[AgentMessage]:
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
        quiet_hours_start: Any | None = None,
        quiet_hours_end: Any | None = None,
        notification_mode: str | None = None,
    ) -> AgentPreference:
        pref = await self.get_by_user(user_id)
        if pref is None:
            pref = AgentPreference(user_id=user_id)
            self.session.add(pref)
        if display_name is not None:
            pref.display_name = display_name
        if quiet_hours_start is not None:
            pref.quiet_hours_start = quiet_hours_start
        if quiet_hours_end is not None:
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

    async def list_by_user(
        self, user_id: UUID, limit: int = 20
    ) -> list[AgentStatusHistory]:
        stmt = (
            select(AgentStatusHistory)
            .where(AgentStatusHistory.user_id == user_id)
            .order_by(AgentStatusHistory.changed_at.desc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())


__all__ = [
    "AgentRepository",
    "WeChatCredentialRepository",
    "WeChatBindingRepository",
    "AgentMessageRepository",
    "AgentPreferenceRepository",
    "AgentStatusHistoryRepository",
]
