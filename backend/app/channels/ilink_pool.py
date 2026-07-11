"""ILink Connection Pool — multi-user long-poll management (REQ-052 US3).

Central orchestrator for per-user iLink long-poll connections.

Architecture (adapted from CoPaw WeixinChannel + Bote SdkConnectionManager):
  - Each bound user gets an independent asyncio.Task running a poll loop.
  - All tasks share one httpx.AsyncClient with HTTP/2 connection pooling.
  - Per-user CircuitBreaker for fault isolation.
  - Credentials loaded from wechat_credentials table on startup; cursor
    persisted after every getupdates() call.
  - Dynamic add/remove on bind/unbind.

Lifecycle:
  startup()  → Load all active credentials from DB → spawn poll tasks.
  add(uid)   → Spawn poll task for newly bound user.
  remove(uid)→ Cancel task, clean up.
  shutdown() → Cancel all tasks, close shared HTTP client.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, Optional
from uuid import UUID

import httpx

from app.channels.circuit_breaker import BreakerState, CircuitBreaker
from app.channels.ilink_client import ILinkClient
from app.channels.message_handler import (
    parse_inbound_message,
    persist_inbound_message,
    process_outbound_queue,
)
from app.core.config import get_settings
from app.core.db import get_session_context
from app.modules.agent.service import decrypt_token

logger = logging.getLogger(__name__)

_POLL_TIMEOUT = 45.0  # httpx timeout for getupdates (server holds 35s)


class ILinkConnectionPool:
    """Singleton connection pool for per-user iLink long-poll tasks.

    Usage:
        pool = ILinkConnectionPool()
        await pool.startup()    # Call once at app startup
        await pool.add(user_id) # Call after QR bind confirmed
        await pool.remove(user_id) # Call after unbind
        await pool.shutdown()   # Call at app shutdown
    """

    def __init__(self) -> None:
        self._tasks: Dict[str, asyncio.Task] = {}       # user_id → poll task
        self._breakers: Dict[str, CircuitBreaker] = {}   # user_id → breaker
        self._stop_events: Dict[str, asyncio.Event] = {} # user_id → stop signal
        # REQ-054: serialize ConversationOrchestrator.handle per user so
        # confirmation / interview state is not raced by concurrent inbound.
        self._user_locks: Dict[str, asyncio.Lock] = {}
        self._shared_client: Optional[httpx.AsyncClient] = None
        self._started = False
        self._consumer_key: str | None = None
        self._consumer_owner_id: UUID | None = None
        self._consumer_fencing_token: int | None = None

    def configure_consumer_fence(
        self,
        *,
        consumer_key: str,
        owner_id: UUID,
        fencing_token: int,
    ) -> None:
        """Bind poll/cursor commits to the active process lease."""
        if self._started:
            raise RuntimeError("consumer fence must be configured before pool startup")
        self._consumer_key = consumer_key
        self._consumer_owner_id = owner_id
        self._consumer_fencing_token = fencing_token

    def _lock_for(self, user_id_str: str) -> asyncio.Lock:
        lock = self._user_locks.get(user_id_str)
        if lock is None:
            lock = asyncio.Lock()
            self._user_locks[user_id_str] = lock
        return lock

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def startup(self) -> None:
        """Load all active credentials from DB and spawn poll tasks.

        Safe to call multiple times — only runs once.
        """
        if self._started:
            logger.info("pool already started, skipping")
            return

        logger.info("pool_startup_begin")
        self._shared_client = httpx.AsyncClient(
            timeout=httpx.Timeout(_POLL_TIMEOUT),
            # iLink terminates long-poll connections early when HTTP/2
            # multiplexes another request for the same bot_token onto
            # the same TCP stream (returns errcode=-14). Force HTTP/1.1.
            # (httpx[http2] remains installed for other call sites.)
            http2=False,
            trust_env=False,
        )

        # Discover only user_id + cursor via the locked-down SECURITY
        # DEFINER function. Secret-bearing credential rows remain FORCE-RLS.
        try:
            from app.core.db import get_db_session_no_rls

            async for session in get_db_session_no_rls():
                from sqlalchemy import text as sa_text

                result = await session.execute(
                    sa_text(
                        "SELECT user_id, cursor FROM wechat_consumer_registrations "
                        "WHERE active = true ORDER BY updated_at"
                    )
                )
                rows = result.fetchall()
                logger.info("pool_startup_loaded", extra={"active_creds": len(rows)})

                for row in rows:
                    uid = str(row[0])
                    cursor = row[1] or ""
                    if uid not in self._tasks:
                        self._spawn_poll_task(uid, cursor)
                break
        except Exception:
            logger.exception("pool_startup_load_failed")

        self._started = True
        logger.info("pool_startup_done", extra={"tasks": len(self._tasks)})

    async def shutdown(self) -> None:
        """Cancel all poll tasks and close shared HTTP client."""
        logger.info("pool_shutdown_begin", extra={"tasks": len(self._tasks)})

        # Signal all tasks to stop
        for uid, event in self._stop_events.items():
            event.set()

        # Cancel all tasks
        for uid, task in self._tasks.items():
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
                except Exception:
                    logger.exception("pool_task_cancel_error", extra={"user_id": uid})

        self._tasks.clear()
        self._breakers.clear()
        self._stop_events.clear()

        if self._shared_client:
            await self._shared_client.aclose()
            self._shared_client = None

        self._started = False
        logger.info("pool_shutdown_done")

    # ------------------------------------------------------------------
    # Dynamic add / remove
    # ------------------------------------------------------------------

    async def add(self, user_id: UUID) -> None:
        """Spawn a poll task for a newly bound user."""
        uid = str(user_id)
        logger.info("pool_add", extra={"user_id": uid})

        # If already running, remove first (idempotent re-add)
        if uid in self._tasks:
            await self.remove(user_id)

        # Load cursor from DB
        cursor = ""
        try:
            async with get_session_context(user_id=user_id) as session:
                from app.modules.agent.repository import WeChatCredentialRepository

                cred_repo = WeChatCredentialRepository(session)
                cred = await cred_repo.get_by_user(user_id)
                if cred:
                    cursor = cred.cursor or ""
        except Exception:
            logger.exception("pool_add_load_cursor_failed", extra={"user_id": uid})

        self._spawn_poll_task(uid, cursor)

    async def remove(self, user_id: UUID) -> None:
        """Cancel poll task and clean up for an unbound user."""
        uid = str(user_id)
        logger.info("pool_remove", extra={"user_id": uid})

        # Signal stop
        event = self._stop_events.get(uid)
        if event:
            event.set()

        # Cancel task
        task = self._tasks.pop(uid, None)
        if task and not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
            except Exception:
                logger.exception("pool_remove_cancel_error", extra={"user_id": uid})

        self._breakers.pop(uid, None)
        self._stop_events.pop(uid, None)

    # ------------------------------------------------------------------
    # Status
    # ------------------------------------------------------------------

    @property
    def active_count(self) -> int:
        return len(self._tasks)

    def get_breaker(self, user_id: str) -> Optional[CircuitBreaker]:
        return self._breakers.get(user_id)

    def is_running(self, user_id: str) -> bool:
        task = self._tasks.get(user_id)
        return task is not None and not task.done()

    # ------------------------------------------------------------------
    # Internal: per-user poll task
    # ------------------------------------------------------------------

    def _spawn_poll_task(self, user_id: str, cursor: str = "") -> None:
        """Create and start a per-user poll asyncio.Task."""
        stop_event = asyncio.Event()
        self._stop_events[user_id] = stop_event

        # Circuit breaker state transitions fire the on_state_change
        # callback. We mirror breaker state into agents.status:
        #   OPEN        → degraded (operational issue, server should know)
        #   CLOSED      → active  (recovered, mark healthy)
        #   HALF_OPEN   → active  (probing; treat as healthy)
        async def _on_breaker_state(uid_str: str, new_state: BreakerState) -> None:
            try:
                target_status = "degraded" if new_state == BreakerState.OPEN else "active"
                async with get_session_context(user_id=UUID(uid_str)) as session:
                    from app.modules.agent.repository import (
                        AgentRepository,
                        AgentStatusHistoryRepository,
                    )
                    agent_repo = AgentRepository(session)
                    await agent_repo.update_status(UUID(uid_str), target_status)
                    if new_state == BreakerState.OPEN:
                        hist_repo = AgentStatusHistoryRepository(session)
                        await hist_repo.record(
                            UUID(uid_str),
                            old_status="active",
                            new_status="degraded",
                            reason="circuit_breaker_open",
                        )
                    await session.commit()
            except Exception:
                logger.exception(
                    "pool_breaker_state_sync_failed",
                    extra={"user_id": uid_str, "new_state": new_state.value},
                )

        breaker = CircuitBreaker(
            user_id=user_id,
            on_state_change=_on_breaker_state,
        )
        self._breakers[user_id] = breaker

        task = asyncio.create_task(
            self._poll_loop(user_id, cursor, stop_event, breaker),
            name=f"ilink-poll-{user_id[:8]}",
        )
        self._tasks[user_id] = task
        logger.info("pool_task_spawned", extra={"has_cursor": bool(cursor)})

    async def _poll_loop(
        self,
        user_id: str,
        cursor: str,
        stop_event: asyncio.Event,
        breaker: CircuitBreaker,
    ) -> None:
        """Per-user long-poll loop. Runs until stop_event is set or fatal error."""
        uid = UUID(user_id)
        backoff = 5.0  # Initial backoff in seconds, exponential to 60s cap

        # Load credential and create client
        bot_token = ""
        base_url = "https://ilinkai.weixin.qq.com"
        to_user_id = ""  # WeChat user ID to send replies to (from_user_id of last inbound msg)
        context_token = ""
        credential_id: UUID | None = None

        try:
            async with get_session_context(user_id=uid) as session:
                from app.modules.agent.repository import (
                    AgentRepository,
                    WeChatCredentialRepository,
                )

                cred_repo = WeChatCredentialRepository(session)
                cred = await cred_repo.get_by_user(uid)
                if cred is None or cred.bot_token_encrypted is None:
                    logger.error("pool_no_credential", extra={"user_id": user_id})
                    return
                bot_token = decrypt_token(cred.bot_token_encrypted)
                credential_id = cred.id
                base_url = cred.base_url or base_url
                context_token = cred.context_token or ""

                # Load saved to_user_id from DB (persisted from previous inbound messages)
                agent_repo = AgentRepository(session)
                agent = await agent_repo.get_by_user(uid)
                if agent:
                    to_user_id = agent.wechat_uin or ""
        except Exception:
            logger.exception("pool_load_cred_failed", extra={"user_id": user_id})
            return

        if not bot_token:
            logger.error("pool_empty_token", extra={"user_id": user_id})
            return

        client = ILinkClient(bot_token=bot_token, base_url=base_url)
        # Reuse the pool's shared httpx client (HTTP/2 multiplex) so 1000
        # bound users share 1 AsyncClient instead of 1000. stop() will see
        # _owns_client=False and skip aclose.
        await client.start(shared_client=self._shared_client)

        try:
            while not stop_event.is_set():
                # Check circuit breaker
                if not breaker.allow_request():
                    logger.warning(
                        "pool_circuit_open",
                        extra={"user_id": user_id, "breaker": repr(breaker)},
                    )
                    # Sleep with stop check
                    try:
                        await asyncio.wait_for(
                            stop_event.wait(),
                            timeout=min(breaker.cooldown_sec, 30),
                        )
                    except asyncio.TimeoutError:
                        pass
                    continue

                try:
                    data = await client.getupdates(cursor)
                    logger.info(
                        "pool_poll_response",
                        extra={
                            "ret": data.get("ret"),
                            "errcode": data.get("errcode"),
                            "message_count": len(data.get("msgs") or []),
                        },
                    )
                except Exception as exc:
                    logger.warning(
                        "pool_poll_error",
                        extra={"error_type": type(exc).__name__},
                    )
                    breaker.record_failure()
                    # Exponential backoff
                    try:
                        await asyncio.wait_for(stop_event.wait(), timeout=backoff)
                    except asyncio.TimeoutError:
                        pass
                    backoff = min(backoff * 2, 60.0)
                    continue

                # Successful poll — reset backoff, record success
                breaker.record_success()
                backoff = 5.0

                # iLink errcode=-14 means the bot session expired (e.g. bot
                # logged out, or credential revoked server-side). Do NOT
                # count this as a transport failure — break out of the
                # poll loop, mark the credential as expired, mark the agent
                # as degraded, and stop the task. The user must re-bind.
                if data.get("errcode") == -14 or data.get("ret") == -14:
                    logger.warning(
                        "ilink_session_expired",
                                extra={"stage": "dispatch"},
                    )
                    await _handle_session_expired(uid)
                    # Do NOT continue — task is stopping.
                    break

                ret = data.get("ret", -1)
                new_cursor = data.get("get_updates_buf") or ""
                msgs = data.get("msgs") or []

                # REQ-060: the complete provider response (including skipped
                # or malformed items) and cursor advance share one fenced DB
                # transaction. Redis is advisory only and never acknowledges
                # an inbound message.
                if (
                    credential_id is None
                    or self._consumer_key is None
                    or self._consumer_owner_id is None
                    or self._consumer_fencing_token is None
                ):
                    logger.error("pool_consumer_fence_missing")
                    break
                try:
                    from app.channels.durable_inbox import persist_poll_batch

                    persisted_poll = await persist_poll_batch(
                        user_id=uid,
                        credential_id=credential_id,
                        previous_cursor=cursor,
                        new_cursor=new_cursor,
                        raw_messages=msgs,
                        consumer_key=self._consumer_key,
                        owner_id=self._consumer_owner_id,
                        fencing_token=self._consumer_fencing_token,
                    )
                except Exception:
                    logger.exception(
                        "pool_poll_persist_failed",
                        extra={"credential_state": "expired"},
                    )
                    breaker.record_failure()
                    continue

                if new_cursor:
                    cursor = new_cursor
                processable_items = {
                    key: (inbox_id, binding_epoch)
                    for key, inbox_id, binding_epoch in persisted_poll.processable_items
                }

                # Process inbound messages
                latest_context_token = context_token
                for msg in msgs:
                    from app.channels.durable_inbox import message_dedupe_key

                    inbox_dedupe_key = message_dedupe_key(credential_id, msg)
                    inbox_item = processable_items.pop(inbox_dedupe_key, None)
                    if inbox_item is None:
                        continue
                    inbox_id, binding_epoch = inbox_item
                    parsed = parse_inbound_message(msg)
                    if parsed is None:
                        logger.info(
                            "pool_msg_parse_skipped",
                            extra={
                                "user_id": user_id,
                                "raw_msg_type": msg.get("message_type"),
                                "raw_keys": list(msg.keys())[:8],
                            },
                        )
                        continue

                    # Update to_user_id from the real sender (first message after bind).
                    # parsed.from_user_id is the actual WeChat user ID — more reliable
                    # than the wechat_uin returned during QR bind flow.
                    if parsed.from_user_id and not to_user_id:
                        to_user_id = parsed.from_user_id
                        await _update_to_user_id(uid, parsed.from_user_id)

                    # Update context_token for this conversation
                    if parsed.context_token:
                        latest_context_token = parsed.context_token
                        await _update_context_token(uid, parsed.context_token)

                    # Persist inbound message
                    try:
                        async with get_session_context(user_id=uid) as session:
                            inbound_message_id = await persist_inbound_message(
                                uid,
                                parsed,
                                session=session,
                                dedupe_key=inbox_dedupe_key,
                                binding_epoch=binding_epoch,
                            )
                            parsed.persisted_message_id = inbound_message_id
                            parsed.inbox_id = inbox_id
                            parsed.binding_epoch = binding_epoch
                    except Exception:
                        logger.exception("pool_persist_inbound_failed")
                        continue

                    from uuid import uuid4

                    from app.channels.durable_inbox import claim_inbox_item

                    inbox_claim_owner = uuid4()
                    claimed = await claim_inbox_item(
                        user_id=uid,
                        inbox_id=inbox_id,
                        binding_epoch=binding_epoch,
                        owner_id=inbox_claim_owner,
                        claim_seconds=get_settings().wechat_agent_message_claim_seconds,
                    )
                    if not claimed:
                        continue
                    parsed.inbox_claim_owner = inbox_claim_owner

                    # Log receipt
                    logger.info(
                        "pool_msg_received",
                        extra={
                            "type": parsed.message_type,
                            "len": len(parsed.text),
                        },
                    )

                    # Generate Agent reply. We delegate to AgentService (which
                    # in turn uses LLMClient for quota/audit/trace governance),
                    # then enqueue the reply — we do NOT send synchronously
                    # here. Synchronous sending would block the iLink long-poll
                    # hold (35s) while LLM takes 30s+ to respond, which iLink
                    # interprets as a connection drop and aborts the hold.
                    #
                    # Two-phase dispatch:
                    #   1. Enqueue an immediate "thinking..." placeholder so
                    #      the user sees a fast acknowledgement that their
                    #      message was received.
                    #   2. Spawn an async task that calls the Agent and
                    #      enqueues the real reply when the LLM finishes.
                    send_target = parsed.from_user_id or to_user_id
                    if parsed.text and send_target and parsed.context_token:
                        try:
                            from app.channels.message_handler import (
                                enqueue_outbound_message,
                            )
                            # Phase 1: immediate "thinking..." placeholder.
                            # Uses a stable client_id so the next poll cycle
                            # (within 35s) can pick it up and send it.
                            thinking_client_id = uuid4()
                            async with get_session_context(user_id=uid) as s:
                                await enqueue_outbound_message(
                                    uid,
                                    "💭 thinking…",
                                    session=s,
                                    client_id=thinking_client_id,
                                    context_token=parsed.context_token,
                                    in_reply_to_msg_id=parsed.msg_id,
                                    trace_id=getattr(parsed, "trace_id", None),
                                )
                            logger.info(
                                "pool_thinking_enqueued",
                                extra={
                                    "message_id": str(thinking_client_id),
                                },
                            )

                            # Phase 2: spawn the real Agent reply. The poll
                            # loop is NOT blocked — the LLM call happens in
                            # the background. When it finishes, the reply
                            # is enqueued and process_outbound_queue will
                            # send it on the next poll cycle.
                            reply_client_id = uuid4()
                            asyncio.create_task(
                                _dispatch_agent_reply(
                                    user_id_str=user_id,
                                    to_user_id=send_target,
                                    parsed=parsed,
                                    client_id=reply_client_id,
                                )
                            )
                        except Exception:
                            try:
                                from app.channels.durable_inbox import finish_inbox_item

                                await finish_inbox_item(
                                    user_id=uid,
                                    inbox_id=parsed.inbox_id,
                                    owner_id=parsed.inbox_claim_owner,
                                    succeeded=False,
                                    error_category="dispatch_enqueue_failed",
                                )
                            except Exception:
                                logger.exception("pool_dispatch_retry_schedule_failed")
                            logger.exception(
                                "pool_dispatch_failed",
                        extra={"stage": "poll_persist"},
                            )

                if latest_context_token != context_token:
                    context_token = latest_context_token

                # Process outbound queue (send pending messages)
                if to_user_id:
                    logger.info(
                        "pool_drain_calling",
                        extra={"has_target": True, "has_context": bool(context_token)},
                    )
                    try:
                        sent = await process_outbound_queue(
                            user_id,
                            to_user_id,
                            client,
                            context_token,
                            session_factory=lambda: get_session_context(user_id=uid),
                        )
                        if sent > 0:
                            logger.info("pool_outbound_sent", extra={"count": sent})
                    except Exception:
                        logger.exception("pool_outbound_process_failed")

                # Update heartbeat
                await _update_heartbeat(uid)

                # Normal long-poll timeout (ret=-1), just continue
                if ret != 0 and not msgs:
                    if ret != -1:
                        logger.debug("pool_poll_ret", extra={"user_id": user_id, "ret": ret})
                        try:
                            await asyncio.wait_for(stop_event.wait(), timeout=3)
                        except asyncio.TimeoutError:
                            pass

        except asyncio.CancelledError:
            logger.info("pool_task_cancelled", extra={"user_id": user_id})
        except Exception:
            logger.exception("pool_task_fatal", extra={"user_id": user_id})
        finally:
            await client.stop()
            logger.info("pool_task_stopped", extra={"user_id": user_id})


# ------------------------------------------------------------------
# ------------------------------------------------------------------
# Internal: DB helpers (lightweight, single-purpose)
# ------------------------------------------------------------------

async def _update_to_user_id(user_id: UUID, to_user_id: str) -> None:
    """Persist the real WeChat user ID (from inbound from_user_id) for outbound sends."""
    try:
        async with get_session_context(user_id=user_id) as session:
            from app.modules.agent.repository import AgentRepository
            repo = AgentRepository(session)
            await repo.set_wechat_uin(user_id, to_user_id)
    except Exception:
        logger.debug("pool_update_to_user_failed", extra={"user_id": str(user_id)}, exc_info=True)

async def _update_cursor(user_id: UUID, cursor: str) -> None:
    try:
        async with get_session_context(user_id=user_id) as session:
            from app.modules.agent.repository import WeChatCredentialRepository
            repo = WeChatCredentialRepository(session)
            await repo.update_cursor(user_id, cursor)
    except Exception:
        logger.debug("pool_update_cursor_failed", extra={"user_id": str(user_id)}, exc_info=True)

async def _update_context_token(user_id: UUID, context_token: str) -> None:
    try:
        async with get_session_context(user_id=user_id) as session:
            from app.modules.agent.repository import WeChatCredentialRepository
            repo = WeChatCredentialRepository(session)
            await repo.update_context_token(user_id, context_token)
    except Exception:
        logger.debug("pool_update_context_failed", extra={"user_id": str(user_id)}, exc_info=True)

async def _update_heartbeat(user_id: UUID) -> None:
    try:
        async with get_session_context(user_id=user_id) as session:
            from app.modules.agent.repository import AgentRepository
            repo = AgentRepository(session)
            await repo.update_heartbeat(user_id)
    except Exception:
        logger.debug("pool_heartbeat_failed", extra={"user_id": str(user_id)}, exc_info=True)

async def _handle_session_expired(user_id: UUID) -> None:
    """Mark credential as expired + agent as degraded, then stop the task.

    Called when iLink returns errcode=-14 (session expired). The poll
    loop will break out after this returns. We do NOT count this against
    the circuit breaker — it's an iLink-side auth issue, not a transport
    fault. The user must re-bind via the QR flow.
    """
    try:
        async with get_session_context(user_id=user_id) as session:
            from app.modules.agent.repository import (
                AgentRepository,
                AgentStatusHistoryRepository,
                WeChatCredentialRepository,
            )

            cred_repo = WeChatCredentialRepository(session)
            await cred_repo.mark_expired(user_id)

            agent_repo = AgentRepository(session)
            await agent_repo.update_status(user_id, "degraded")

            # Audit log entry — append-only
            hist_repo = AgentStatusHistoryRepository(session)
            await hist_repo.record(
                user_id,
                old_status="active",
                new_status="degraded",
                reason="expired_session_detected",
            )
            await session.commit()
    except Exception:
        logger.exception(
            "pool_handle_session_expired_failed",
            extra={"user_id": str(user_id)},
        )

    # Stop the task cleanly. The user must re-bind to resume.
    # Note: this is a module-level helper (not a method); use the pool
    # singleton. Called from inside the poll task, so stop_event is enough.
    try:
        pool = get_connection_pool()
        event = pool._stop_events.get(str(user_id))
        if event is not None:
            event.set()
    except Exception:
        logger.debug(
            "pool_stop_event_set_failed",
            extra={"user_id": str(user_id)},
            exc_info=True,
        )


# ------------------------------------------------------------------


# Background task: complete the agent reply for a previously-received
# inbound message. Created by ``_poll_loop`` so the long-poll hold is
# never blocked on the LLM call. When the LLM reply is enqueued, the
# next ``_poll_loop`` cycle picks it up via ``process_outbound_queue``
# and pushes it through iLink to the WeChat user.
# ------------------------------------------------------------------

async def _dispatch_agent_reply(  # noqa: F811 — module-level helper
    user_id_str: str,
    to_user_id: str,
    parsed: Any,
    client_id: UUID,
) -> None:
    """Run the Agent LLM call for one inbound message and enqueue the reply.

    Args:
        user_id_str: The InterCraft user ID (str from ``_poll_loop``).
        to_user_id: The WeChat openid of the sender (parsed.from_user_id).
        parsed: The ParsedMessage we just received.
        client_id: The per-message client_id used when the reply is enqueued.
    """
    from uuid import UUID, uuid4

    from app.channels.durable_inbox import finish_inbox_item
    from app.channels.message_handler import enqueue_outbound_message
    from app.core.db import get_session_context
    from app.modules.agent.service import AgentService

    uid = UUID(user_id_str)
    # REQ-054: serialize per-user so confirmation / interview state is consistent.
    pool = get_connection_pool()
    lock = pool._lock_for(user_id_str)
    async with lock:
        try:
            logger.info(
                "agent_dispatch_starting",
                extra={"content_length": len(parsed.text or "")},
            )

            async def send_interim(text: str) -> None:
                """Push interim WeChat notice (e.g. scoring) before final reply."""
                if not text or not str(text).strip():
                    return
                async with get_session_context(user_id=uid) as interim_sess:
                    await enqueue_outbound_message(
                        uid,
                        str(text),
                        session=interim_sess,
                        client_id=uuid4(),
                        context_token=parsed.context_token,
                        in_reply_to_msg_id=parsed.msg_id,
                        priority="high",
                        task_id=getattr(parsed, "task_id", None),
                        trace_id=getattr(parsed, "trace_id", None),
                    )
                logger.info(
                    "agent_interim_enqueued",
                    extra={"reply_length": len(str(text))},
                )

            # Call the Agent (this is the slow LLM call, up to 30s).
            async with get_session_context(user_id=uid) as svc_sess:
                svc = AgentService(svc_sess)
                reply_text = await svc.process_inbound_reply(
                    parsed, send_interim=send_interim
                )

            if not reply_text:
                logger.warning(
                    "agent_reply_empty",
                    extra={"message_id": str(parsed.persisted_message_id)},
                )
                await finish_inbox_item(
                    user_id=uid,
                    inbox_id=parsed.inbox_id,
                    owner_id=parsed.inbox_claim_owner,
                    succeeded=False,
                    error_category="empty_agent_reply",
                )
                return

            # Enqueue the real reply. The next _poll_loop cycle will pick
            # it up and push it to iLink.
            async with get_session_context(user_id=uid) as s:
                await enqueue_outbound_message(
                    uid,
                    reply_text,
                    session=s,
                    client_id=client_id,
                    context_token=parsed.context_token,
                    in_reply_to_msg_id=parsed.msg_id,
                    task_id=getattr(parsed, "task_id", None),
                    trace_id=getattr(parsed, "trace_id", None),
                )
            await finish_inbox_item(
                user_id=uid,
                inbox_id=parsed.inbox_id,
                owner_id=parsed.inbox_claim_owner,
                succeeded=True,
            )
            logger.info(
                "agent_reply_enqueued",
                extra={
                    "reply_length": len(reply_text),
                    "message_id": str(client_id),
                },
            )
        except Exception:
            try:
                if getattr(parsed, "inbox_id", None) and getattr(
                    parsed, "inbox_claim_owner", None
                ):
                    await finish_inbox_item(
                        user_id=uid,
                        inbox_id=parsed.inbox_id,
                        owner_id=parsed.inbox_claim_owner,
                        succeeded=False,
                        error_category="agent_dispatch_failed",
                    )
            except Exception:
                logger.exception("agent_dispatch_retry_schedule_failed")
            logger.exception(
                "agent_dispatch_task_failed",
                extra={"message_id": str(getattr(parsed, "persisted_message_id", ""))},
            )

# Singleton accessor
# ------------------------------------------------------------------

_pool: Optional[ILinkConnectionPool] = None


def get_connection_pool() -> ILinkConnectionPool:
    """Return the singleton ILinkConnectionPool, creating it if needed."""
    global _pool
    if _pool is None:
        _pool = ILinkConnectionPool()
    return _pool


async def shutdown_connection_pool() -> None:
    """Shutdown the singleton pool if it was started."""
    global _pool
    if _pool is not None:
        await _pool.shutdown()
        _pool = None


__all__ = [
    "ILinkConnectionPool",
    "get_connection_pool",
    "shutdown_connection_pool",
]
