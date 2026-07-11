"""ARQ cron: agents_outbound_drain — every 30s, deliver pending outbound messages.

REQ-052 outbound reliability safety net. The primary outbound path is
``app/channels/ilink_pool._poll_loop`` calling
``enqueue_outbound_message`` then ``process_outbound_queue`` after every
inbound poll. If the long-poll task is degraded / cancelled / crashed,
outbound messages stay ``status='pending'`` in PG forever.

This cron is the fallback: every 30s it scans
``agent_messages WHERE status='pending' AND direction='outbound' AND
created_at > NOW() - INTERVAL '24 hours'``, finds the user's
credentials, builds an ILinkClient, and sends via iLink. On success
the row is updated to ``status='sent'``. On failure the row stays
``pending`` (we'll retry next tick) until the 24h cutoff at which
point we mark it ``status='failed'``.

Per-user isolation: each pending row carries its own user_id; we
process one user at a time, decrypt the bot_token via the per-user
agent_preferences/credentials table, send with that user's
``agents.wechat_uin`` (or the most recent inbound ``from_user_id``)
and ``context_token``. Concurrent ARQ workers may pick up different
users in parallel without conflict.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import select

from app.core.db import get_session_factory
from app.core.logging import get_logger
from app.modules.agent.models import AgentMessage
from app.modules.agent.repository import (
    AgentMessageRepository,
    AgentRepository,
    WeChatCredentialRepository,
)
from app.modules.agent.service import decrypt_token
from app.channels.ilink_client import ILinkClient
from app.channels.message_handler import process_outbound_queue

log = get_logger("workers.agents_outbound_drain")

# Bounded concurrency — we don't want 1000 outbound messages all hitting
# iLink at once. Each ARQ tick processes at most N users.
_MAX_USERS_PER_TICK = 32
# Don't retry messages older than this.
_MAX_AGE = timedelta(hours=24)
# Per-user iLink client timeout for short sends.
_SEND_TIMEOUT = 15.0


async def agents_outbound_drain(ctx: dict) -> dict:
    """Scan pending outbound messages and send them via iLink.

    Returns a small dict of counts for observability.
    """
    # Use the no-RLS session context manager so we can scan across
    # all users. RLS-protected sessions see zero rows because the
    # worker has no app.user_id GUC set.
    from app.core.db import get_db_session_no_rls

    sent_count = 0
    failed_count = 0
    skipped_count = 0

    # First pass: scan for pending rows. We use per-user RLS-bound
    # sessions because appuser is not a superuser and can't bypass RLS.
    # We fetch the list of users with active credentials via
    # `get_active_credentials()` (SECURITY DEFINER) and iterate.
    from app.core.db import get_db_session_no_rls
    from sqlalchemy import text as sa_text

    pending_rows = []
    async for session in get_db_session_no_rls():
        result = await session.execute(
            sa_text(
                "SELECT user_id FROM wechat_consumer_registrations "
                "WHERE active = true ORDER BY updated_at"
            )
        )
        active_user_ids = [str(row[0]) for row in result.fetchall()]
        break

    # For each active user, query their pending outbound via RLS session.
    from app.core.db import get_db_session
    for user_id_str in active_user_ids:
        try:
            async for session in get_db_session(user_id=UUID(user_id_str)):
                cutoff = datetime.now(timezone.utc) - _MAX_AGE
                recent_stmt = (
                    select(AgentMessage)
                    .where(
                        AgentMessage.direction == "outbound",
                        AgentMessage.status == "pending",
                        AgentMessage.created_at > cutoff,
                    )
                    .order_by(AgentMessage.created_at.asc())
                    .limit(_MAX_USERS_PER_TICK * 5)
                )
                result = await session.execute(recent_stmt)
                rows = list(result.scalars().all())
                pending_rows.extend(rows)
                old_result = await session.execute(
                    select(AgentMessage).where(
                        AgentMessage.direction == "outbound",
                        AgentMessage.status == "pending",
                        AgentMessage.created_at <= cutoff,
                    )
                )
                old_rows = list(old_result.scalars().all())
                for old_row in old_rows:
                    old_row.status = "failed"
                    old_row.delivery_status = "failed"
                    old_row.error_category = "retry_window_exceeded"
                    old_row.claim_owner = None
                    old_row.claim_until = None
                failed_count += len(old_rows)
                skipped_count += len(old_rows)
                break
        except Exception as exc:
            log.exception(
                "outbound_drain_user_scan_failed",
                extra={"user_id": user_id_str, "error": str(exc)[:120]},
            )

    log.info("agents_outbound_drain.start", pending=len(pending_rows))

    # Group by user_id
    by_user: dict[UUID, list[AgentMessage]] = {}
    for row in pending_rows:
        by_user.setdefault(row.user_id, []).append(row)

    for user_id, rows in list(by_user.items())[:_MAX_USERS_PER_TICK]:
        try:
            ok = await _drain_user(user_id, rows)
            sent_count += ok
        except Exception as exc:
            failed_count += len(rows)
            log.exception(
                "agents_outbound_drain_user_failed",
                extra={"user_id": str(user_id), "error": str(exc)[:120]},
            )

    log.info(
        "agents_outbound_drain.done",
        sent=sent_count,
        failed=failed_count,
        skipped=skipped_count,
    )
    return {"sent": sent_count, "failed": failed_count, "skipped": skipped_count}

async def _drain_user(
    user_id: UUID, rows: list[AgentMessage]
) -> int:
    """Send all pending outbound messages for one user via iLink.

    Returns the count of successfully sent messages.
    """
    from app.core.db import get_session_context

    async with get_session_context(user_id=user_id) as session:
        cred_repo = WeChatCredentialRepository(session)
        cred = await cred_repo.get_by_user(user_id)
        if cred is None or cred.bot_token_encrypted is None or cred.status != "active":
            log.warning(
                "agents_outbound_drain.no_active_cred",
                extra={"user_id": str(user_id)},
            )
            return 0
        bot_token = decrypt_token(cred.bot_token_encrypted)
        base_url = cred.base_url or "https://ilinkai.weixin.qq.com"

        agent_repo = AgentRepository(session)
        agent = await agent_repo.get_by_user(user_id)
        # Fall back to the wechat_uin stored on the binding (most recent
        # inbound from_user_id is preferred, but bindings.wechat_uin is
        # what we have here without the binding table lookup).
        to_user_id = agent.wechat_uin if agent else None
        if not to_user_id:
            log.warning(
                "agents_outbound_drain.no_to_user_id",
                extra={"user_id": str(user_id)},
            )
            return 0

    client = ILinkClient(bot_token=bot_token, base_url=base_url)
    await client.start()
    try:
        return await process_outbound_queue(
            str(user_id),
            to_user_id,
            client,
            session_factory=lambda: get_session_context(user_id=user_id),
        )
    finally:
        await client.stop()


__all__ = ["agents_outbound_drain"]
