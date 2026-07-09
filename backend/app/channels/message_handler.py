"""Message handler — inbound parser + outbound send pipeline (REQ-052 US2/US3).

Inbound:
  parse_inbound_message() — extract text/image/voice from iLink message dict
  Dedup via Redis SET with TTL (context_token or wechat_msg_id)

Outbound:
  enqueue_outbound_message() — INSERT agent_messages (status=pending) + LPUSH Redis
  process_outbound_queue() — consumer: RPOP Redis → send_text → UPDATE status=sent
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID

import httpx

from app.channels.ilink_client import ILinkClient
from app.channels.ilink_utils import split_text
from app.core.redis import get_redis

logger = logging.getLogger(__name__)

# Max dedup pool size (per-user, in Redis with TTL, but also limit keyspace)
_DEDUP_TTL_SEC = 3600  # 1 hour


@dataclass
class ParsedMessage:
    """Normalised inbound message after iLink parsing."""

    from_user_id: str
    to_user_id: str = ""
    context_token: str = ""
    group_id: str = ""
    msg_id: str = ""
    text: str = ""  # Plain text (merged from all text items, including ASR)
    message_type: str = "text"  # text / image / voice / file / video
    image_urls: List[str] = field(default_factory=list)
    raw_msg: Dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Inbound message parsing (adapted from CoPaw WeixinChannel._on_message)
# ---------------------------------------------------------------------------


def parse_inbound_message(msg: Dict[str, Any]) -> ParsedMessage | None:
    """Parse a single iLink WeixinMessage dict into a ParsedMessage.

    Returns None if the message should be skipped (not user→bot, empty, etc.).
    """
    from_user_id = str(msg.get("from_user_id", ""))
    to_user_id = str(msg.get("to_user_id", ""))
    context_token = str(msg.get("context_token", ""))
    group_id = str(msg.get("group_id", ""))
    msg_id = str(msg.get("msg_id", ""))
    msg_type_val = msg.get("message_type", 0)

    # Only process user→bot messages (message_type == 1)
    if msg_type_val != 1:
        logger.debug("skipping non-user message type=%s", msg_type_val)
        return None

    text_parts: List[str] = []
    image_urls: List[str] = []
    has_image = False
    has_voice = False
    has_file = False
    has_video = False

    item_list: List[Dict[str, Any]] = msg.get("item_list") or []
    for item in item_list:
        item_type = item.get("type", 0)

        if item_type == 1:
            # Text
            text = (item.get("text_item") or {}).get("text", "").strip()
            if text:
                text_parts.append(text)

        elif item_type == 2:
            # Image
            has_image = True
            img_item = item.get("image_item") or {}
            media = img_item.get("media") or {}
            cdn_url = media.get("encrypt_query_param", "") or media.get("url", "")
            if cdn_url:
                image_urls.append(cdn_url)
            text_parts.append("[图片]")

        elif item_type == 3:
            # Voice — prefer ASR transcription
            has_voice = True
            voice_item = item.get("voice_item") or {}
            asr_text = ""
            if isinstance(voice_item.get("text_item"), dict):
                asr_text = voice_item["text_item"].get("text", "").strip()
            else:
                asr_text = voice_item.get("text", "").strip()
            if asr_text:
                text_parts.append(asr_text)
            else:
                text_parts.append("[语音消息]")

        elif item_type == 4:
            # File
            has_file = True
            text_parts.append("[文件]")

        elif item_type == 5:
            # Video
            has_video = True
            text_parts.append("[视频]")

        else:
            text_parts.append(f"[不支持的消息类型: {item_type}]")

    text = "\n".join(text_parts).strip()
    if not text:
        logger.debug("skipping empty message from=%s", from_user_id[:20])
        return None

    # Determine primary message type
    if has_image and not has_voice and not has_file and not has_video:
        primary_type = "image"
    elif has_voice:
        primary_type = "voice"
    elif has_file:
        primary_type = "file"
    elif has_video:
        primary_type = "video"
    else:
        primary_type = "text"

    return ParsedMessage(
        from_user_id=from_user_id,
        to_user_id=to_user_id,
        context_token=context_token,
        group_id=group_id,
        msg_id=msg_id,
        text=text,
        message_type=primary_type,
        image_urls=image_urls,
        raw_msg=msg,
    )


# ---------------------------------------------------------------------------
# Dedup
# ---------------------------------------------------------------------------


async def is_duplicate(user_id: str, context_token: str, msg_id: str = "") -> bool:
    """Check if a message has already been processed.

    Uses Redis SET with TTL. Falls back to msg_id if context_token is empty.
    """
    dedup_key = context_token or f"{msg_id}" if msg_id else ""
    if not dedup_key:
        return False

    redis = await get_redis()
    key = f"wechat:dedup:{user_id}:{dedup_key}"
    # SET NX returns True if key was set (new), False if already existed (duplicate)
    was_new = await redis.set(key, "1", nx=True, ex=_DEDUP_TTL_SEC)
    return not was_new


# ---------------------------------------------------------------------------
# Outbound send pipeline
# ---------------------------------------------------------------------------


async def enqueue_outbound_message(
    user_id: UUID,
    content: str,
    *,
    msg_repo: Any = None,
    session: Any = None,
    priority: str = "normal",
    client_id: UUID | None = None,
    context_token: str | None = None,
    in_reply_to_msg_id: str | None = None,
) -> List[UUID]:
    """Persist outbound message to PG + push to Redis send queue.

    Args:
        user_id: Target InterCraft user ID.
        content: Message text (may be split into segments if > 500 chars).
        msg_repo: AgentMessageRepository instance (optional if session provided).
        session: SQLAlchemy AsyncSession.
        priority: "normal" or "high".
        client_id: iLink client_id (UUID) — spec FR-014: every outbound segment
            carries a unique client_id and is persisted to PG.
        context_token: iLink context_token (from the inbound message we are
            replying to). Required for iLink to route the reply to the right
            WeChat conversation window.
        in_reply_to_msg_id: The WeChat msg_id of the inbound message this
            outbound is replying to. Stored for traceability / dedup.

    Returns:
        List of message UUIDs (one per segment).
    """
    from app.modules.agent.models import AgentMessage

    if msg_repo is None and session is not None:
        from app.modules.agent.repository import AgentMessageRepository

        msg_repo = AgentMessageRepository(session)

    segments = split_text(content)
    message_ids: List[UUID] = []
    total = len(segments)

    redis = await get_redis()
    queue_key = f"wechat:send_queue:{user_id}"

    for i, segment in enumerate(segments):
        msg_id = UUID(bytes=__import__("os").urandom(16))  # simple UUID v4
        # Per-segment client_id (spec FR-014): generate if not provided.
        seg_client_id = client_id or UUID(bytes=__import__("os").urandom(16))
        msg = AgentMessage(
            id=msg_id,
            user_id=user_id,
            direction="outbound",
            content=segment,
            status="pending",
            message_type="text",
            segments_total=total if total > 1 else None,
            segment_index=(i + 1) if total > 1 else None,
            client_id=seg_client_id,
            context_token=context_token,
            wechat_msg_id=in_reply_to_msg_id,
        )
        if msg_repo is not None:
            await msg_repo.create(msg)

        # Push to Redis hot queue (raw text — consumer attaches client_id +
        # context_token by reading the latest PG row before sending).
        # NOTE: We treat Redis as best-effort here. In dev / staging the
        # configured Redis endpoint may be a read-only replica (sentinel
        # route). PG is the source of truth; drain cron reads PG directly.
        # If Redis is unavailable the outbound worker still works.
        try:
            await redis.lpush(queue_key, segment)
        except Exception as exc:
            logger.warning(
                "outbound_redis_lpush_failed_continuing",
                extra={"user_id": str(user_id), "error": str(exc)[:120]},
            )
        message_ids.append(msg_id)

    logger.info(
        "outbound_enqueued",
        extra={
            "user_id": str(user_id),
            "segments": total,
            "priority": priority,
            "client_id": str(client_id) if client_id else None,
            "context_token": bool(context_token),
        },
    )
    return message_ids


async def process_outbound_queue(
    user_id: str,
    to_user_id: str,
    client: ILinkClient,
    context_token: str = "",
    *,
    session_factory: Any = None,
) -> int:
    """Consume Redis send queue for a user and send via iLink.

    Called by the connection pool after each poll cycle (or as a background task).

    Args:
        user_id: InterCraft user ID (UUID string).
        to_user_id: WeChat recipient ID (from_user_id of last inbound message).
        client: Authenticated ILinkClient instance.
        context_token: Latest context_token for the conversation.
        session_factory: Callable that returns an AsyncSession.

    Returns:
        Number of messages sent.
    """
    # Read pending outbound messages from PG (not Redis — dev/staging
    # Redis may be a read-only replica). PG is the source of truth.
    sent_count = 0
    if session_factory is None:
        return 0

    from app.modules.agent.models import AgentMessage
    from app.modules.agent.repository import AgentMessageRepository

    # Use the caller-supplied session factory (an async context manager
    # that commits on exit) so status updates are persisted. Do NOT
    # create a separate session via get_db_session — the commit on that
    # path can be unreliable when called from inside _poll_loop's
    # already-active connection pool context.
    from uuid import UUID as _UUID
    async with session_factory() as session:
        repo = AgentMessageRepository(session)
        pending = await repo.list_pending(_UUID(user_id))
        for row in pending:
            content = row.content or ""
            try:
                await client.send_text(to_user_id, content, row.context_token or context_token)
                await repo.update_status(row.id, "sent")
                sent_count += 1
            except Exception as exc:
                logger.warning(
                    "outbound_send_failed",
                    extra={"user_id": user_id, "msg_id": str(row.id), "error": str(exc)[:120]},
                )
                break

    return sent_count


# ---------------------------------------------------------------------------
# Inbound persistence
# ---------------------------------------------------------------------------


async def persist_inbound_message(
    user_id: UUID,
    parsed: ParsedMessage,
    *,
    session: Any = None,
) -> UUID:
    """Persist a parsed inbound message to agent_messages table.

    Returns:
        The UUID of the created message row.
    """
    from app.modules.agent.models import AgentMessage

    msg_id = UUID(bytes=__import__("os").urandom(16))
    msg = AgentMessage(
        id=msg_id,
        user_id=user_id,
        direction="inbound",
        content=parsed.text,
        message_type=parsed.message_type,
        status="received",
        wechat_msg_id=parsed.msg_id or None,
        context_token=parsed.context_token or None,
        received_at=datetime.now(timezone.utc),
    )
    if session is not None:
        session.add(msg)
        await session.flush()

    logger.info(
        "inbound_persisted",
        extra={
            "user_id": str(user_id),
            "msg_id": str(msg_id),
            "message_type": parsed.message_type,
            "content_len": len(parsed.text),
        },
    )
    return msg_id


# ---------------------------------------------------------------------------
# Agent reply generation (REQ-052: message → LLM → WeChat)
# ---------------------------------------------------------------------------


_SYSTEM_PROMPT = """你是 InterCraft 求职助手，通过微信为用户提供求职相关帮助。

你的能力范围：
- 解答求职相关问题（简历优化、面试准备、职业规划）
- 查询用户的求职数据（投递进度、面试记录、能力评估）
- 提供学习建议和错题回顾

回复要求：
- 简洁友好，适合微信阅读（每次不超过 300 字）
- 如果用户问的问题超出你的能力范围，礼貌说明
- 始终使用中文回复
- 用户称呼为"你"，自称"我"
"""

# Module-level shared httpx client for LLM calls (lazy-init, reused across calls)
_llm_client: Optional[httpx.AsyncClient] = None


def _get_llm_client() -> httpx.AsyncClient:
    """Return (and lazily create) a shared httpx client for LLM API calls."""
    global _llm_client
    if _llm_client is None or _llm_client.is_closed:
        _llm_client = httpx.AsyncClient(timeout=30.0)
    return _llm_client


async def shutdown_llm_client() -> None:
    """Close the shared LLM httpx client (called at app shutdown)."""
    global _llm_client
    if _llm_client and not _llm_client.is_closed:
        await _llm_client.aclose()
    _llm_client = None


async def generate_reply(
    user_message: str,
    *,
    user_id: str = "",
    conversation_history: list[dict[str, str]] | None = None,
) -> str:
    """Call LLM to generate a reply to the user's WeChat message.

    Uses DeepSeek V4 Pro via OpenAI-compatible API.
    Returns the reply text (may be empty on error).
    """
    from app.core.config import get_settings

    settings = get_settings()
    api_key = settings.deepseek_api_key or ""
    api_base = settings.deepseek_base_url or "https://api.deepseek.com"
    model = settings.deepseek_model or "deepseek-chat"

    if not api_key:
        logger.warning("no_deepseek_api_key")
        return "（系统提示：LLM API key 未配置，请设置 DEEPSEEK_API_KEY 环境变量）"

    messages: list[dict[str, str]] = [{"role": "system", "content": _SYSTEM_PROMPT}]
    if conversation_history:
        messages.extend(conversation_history[-6:])  # Keep last 3 exchanges
    messages.append({"role": "user", "content": user_message})

    client = _get_llm_client()
    try:
        resp = await client.post(
            f"{api_base}/v1/chat/completions",
            json={
                "model": model,
                "messages": messages,
                "max_tokens": 600,
                "temperature": 0.7,
            },
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
        )
        if resp.status_code != 200:
            logger.warning(
                "llm_reply_error",
                extra={"status": resp.status_code, "body": resp.text[:200]},
            )
            return "（抱歉，AI 服务暂时不可用，请稍后再试）"

        data = resp.json()
        reply = data["choices"][0]["message"]["content"].strip()
        logger.info(
            "llm_reply_generated",
            extra={"user_id": user_id, "len": len(reply)},
        )
        return reply
    except Exception:
        logger.exception("llm_reply_failed")
        return "（抱歉，处理你的消息时出现了错误，请稍后再试）"


__all__ = [
    "ParsedMessage",
    "parse_inbound_message",
    "is_duplicate",
    "enqueue_outbound_message",
    "process_outbound_queue",
    "persist_inbound_message",
    "generate_reply",
]
