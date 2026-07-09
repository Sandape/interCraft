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
            sa_text("SELECT user_id FROM get_active_credentials()")
        )
        active_user_ids = [str(row[0]) for row in result.fetchall()]
        break

    # For each active user, query their pending outbound via RLS session.
    from app.core.db import get_db_session
    for user_id_str in active_user_ids:
        try:
            async for session in get_db_session(user_id=UUID(user_id_str)):
                cutoff = datetime.now(timezone.utc) - _MAX_AGE
                stmt = (
                    select(AgentMessage)
                    .where(
                        AgentMessage.direction == "outbound",
                        AgentMessage.status == "pending",
                        AgentMessage.created_at > cutoff,
                    )
                    .order_by(AgentMessage.created_at.asc())
                    .limit(_MAX_USERS_PER_TICK * 5)
                )
                result = await session.execute(stmt)
                rows = list(result.scalars().all())
                pending_rows.extend(rows)
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

    # Mark old pending rows as failed. We use the same SECURITY DEFINER
    # scan but for rows older than the cutoff (which is the same as
    # "everything not in the recent scan"). The function returns all
    # pending; we update any whose created_at <= cutoff.
    from sqlalchemy import text as sa_text
    async for session in get_db_session_no_rls():
        max_age_hours = int(_MAX_AGE.total_seconds() // 3600)
        result = await session.execute(
            sa_text("SELECT * FROM get_outbound_drain_candidates(:max_age)"),
            {"max_age": max_age_hours},
        )
        all_pending = result.mappings().all()
        cutoff = datetime.now(timezone.utc) - _MAX_AGE
        old_rows = [
            r for r in all_pending
            if r["created_at"] and r["created_at"] <= cutoff
        ]
        if old_rows:
            msg_repo = AgentMessageRepository(session)
            for row in old_rows:
                await msg_repo.update_status(row["id"], "failed", error_message="exceeded_24h_retry_window")
            await session.commit()
            failed_count += len(old_rows)
            skipped_count = len(old_rows)
        break

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
    from app.core.db import get_db_session_no_rls

    async for session in get_db_session_no_rls():
        from sqlalchemy import text as sa_text
        await session.execute(sa_text("SET LOCAL row_security = off"))
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
        break

    client = ILinkClient(bot_token=bot_token, base_url=base_url)
    await client.start()
    try:
        sent = 0
        async for session in get_db_session_no_rls():
            from sqlalchemy import text as sa_text
            await session.execute(sa_text("SET LOCAL row_security = off"))
            msg_repo = AgentMessageRepository(session)
            for row in rows:
                ctx = row.context_token or ""
                try:
                    await asyncio.wait_for(
                        client.send_text(to_user_id, row.content, ctx),
                        timeout=_SEND_TIMEOUT,
                    )
                    await msg_repo.update_status(row.id, "sent")
                    sent += 1
                except Exception as exc:
                    log.warning(
                        "agents_outbound_drain.send_failed",
                        extra={
                            "user_id": str(user_id),
                            "msg_id": str(row.id),
                            "error": str(exc)[:120],
                        },
                    )
                    # Leave status=pending; next tick will retry.
                    break
            await session.commit()
            break
        return sent
    finally:
        await client.stop()


__all__ = ["agents_outbound_drain"]
