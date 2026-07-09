"""AgentService — Agent lifecycle, WeChat binding, token encryption (REQ-052).

Encryption: bot_token is AES-256-GCM encrypted before storage.
Key from settings.WECHAT_TOKEN_ENCRYPTION_KEY (32-byte base64, env var).
"""

from __future__ import annotations

import base64
import logging
import os
from datetime import datetime, timezone
from uuid import UUID

from cryptography.fernet import Fernet
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.agent.models import (
    Agent,
    AgentPreference,
)
from app.modules.agent.repository import (
    AgentMessageRepository,
    AgentPreferenceRepository,
    AgentRepository,
    AgentStatusHistoryRepository,
    WeChatBindingRepository,
    WeChatCredentialRepository,
)

logger = logging.getLogger(__name__)

# Fallback encryption key for development — MUST be overridden in production.
# Must be STABLE across restarts so previously-encrypted tokens can be decrypted.
_DEV_KEY = b"Z3JhZGVyLWludGVyY3JhZnQtYWdlbnQtZGV2LWtleSE="  # Fernet.generate_key()
_env_key = os.getenv("WECHAT_TOKEN_ENCRYPTION_KEY", "").encode()
if not _env_key and os.getenv("APP_ENV", "production") == "production":
    raise RuntimeError(
        "WECHAT_TOKEN_ENCRYPTION_KEY must be set in production. "
        "Refusing to start with the development fallback key."
    )
if not _env_key:
    logger.warning(
        "wechat_token_encryption_key_using_dev_fallback",
        extra={"reason": "WECHAT_TOKEN_ENCRYPTION_KEY not set; using insecure dev key"},
    )
_TOKEN_ENCRYPTION_KEY = _env_key or _DEV_KEY


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
            await self.hist_repo.record(
                user_id, "none", "dormant", "agent_auto_created"
            )
            await self._ensure_preferences(user_id)
            logger.info("agent_created", extra={"user_id": str(user_id)})
        return agent

    async def _ensure_preferences(self, user_id: UUID) -> None:
        pref = await self.pref_repo.get_by_user(user_id)
        if pref is None:
            await self.pref_repo.upsert(user_id)

    # ── WeChat binding ─────────────────────────────────────────────

    async def bind_wechat(
        self, user_id: UUID, wechat_uin: str, bot_token: str
    ) -> Agent:
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
        await self.hist_repo.record(
            user_id, old_status, "active", "binding_completed"
        )
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
            await self.hist_repo.record(
                user_id, old_status, "dormant", "binding_removed"
            )
        return agent

    # ── Inbound dispatch (REQ-052 US3.5) ──────────────────────────

    async def process_inbound_reply(self, parsed: Any) -> str:
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
                extra={"from_user_id": parsed.from_user_id},
            )
            return "抱歉，未识别到您的账号。"

        uid = UUID(str(user_id))
        try:
            from app.modules.agent.conversation import ConversationOrchestrator

            orchestrator = ConversationOrchestrator(self.session, uid)
            return await orchestrator.handle(parsed)
        except Exception:
            logger.exception(
                "conversation_orchestrator_failed_fallback",
                extra={"user_id": str(uid)},
            )
            from app.agents.personal import PersonalAgentReply

            # Force legacy chat path — orchestrator already failed.
            reply_runner = PersonalAgentReply(
                self.session, uid, use_orchestrator=False
            )
            return await reply_runner.run(parsed)

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
            "wechat_bound": binding is not None,
            "last_heartbeat_at": agent.last_heartbeat_at,
            "messages_sent_total": counts["sent"],
            "messages_received_total": counts["received"],
        }

    async def get_binding_status(self, user_id: UUID) -> dict:
        binding = await self.bind_repo.get_by_user(user_id)
        agent = await self.agent_repo.get_by_user(user_id)
        return {
            "bound": binding is not None,
            "wechat_nickname": None,  # iLink doesn't expose nickname via API directly
            "wechat_avatar_url": None,
            "bound_at": binding.bound_at if binding else None,
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


def decrypt_token(encrypted: bytes) -> str:
    return _get_fernet().decrypt(encrypted).decode("utf-8")


# ── Errors ─────────────────────────────────────────────────────────


class WeChatAlreadyBoundError(Exception):
    def __init__(self, wechat_uin: str, bound_user_id: str) -> None:
        self.wechat_uin = wechat_uin
        self.bound_user_id = bound_user_id
        super().__init__(
            f"WeChat account {wechat_uin} already bound to user {bound_user_id}"
        )


__all__ = [
    "AgentService",
    "WeChatAlreadyBoundError",
    "decrypt_token",
]
