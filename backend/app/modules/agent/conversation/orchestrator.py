"""ConversationOrchestrator — WeChat NL → tools state machine (REQ-054).

States: idle | awaiting_confirmation | in_interview
"""

from __future__ import annotations

import logging
import time
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.agent.conversation import metrics as m
from app.modules.agent.conversation.confirmations import is_cancel, is_confirm
from app.modules.agent.conversation.context_store import (
    RedisUnavailableError,
    default_context,
    get_context,
    set_context,
)
from app.modules.agent.conversation.intent_parser import (
    CONFIDENCE_THRESHOLD,
    IntentParser,
)
from app.modules.agent.conversation.interview.adapter import InterviewAdapter
from app.modules.agent.conversation.reply_formatter import (
    HELP_TEXT,
    LLM_UNAVAILABLE_TEXT,
    REDIS_UNAVAILABLE_TEXT,
    UNKNOWN_STREAK_TEXT,
    UNKNOWN_TEXT,
    WEB_GUIDE_DELETE,
    format_low_confidence,
)
from app.modules.agent.conversation.tools import create_job as tool_create_job
from app.modules.agent.conversation.tools import query_ability as tool_query_ability
from app.modules.agent.conversation.tools import query_jobs as tool_query_jobs
from app.modules.agent.conversation.tools import query_reports as tool_query_reports
from app.modules.agent.conversation.tools import update_fields as tool_update_fields
from app.modules.agent.conversation.tools import update_status as tool_update_status

logger = logging.getLogger(__name__)


class ConversationOrchestrator:
    """Handle one inbound WeChat message for a bound user."""

    def __init__(
        self,
        session: AsyncSession,
        user_id: UUID,
        *,
        intent_parser: IntentParser | None = None,
        send_interim: Any | None = None,
    ) -> None:
        self.session = session
        self.user_id = user_id
        self.parser = intent_parser or IntentParser()
        self.send_interim = send_interim

    async def handle(self, parsed: Any) -> str:
        """Entry point. ``parsed`` has ``.text`` (and optional context fields)."""
        start = time.perf_counter()
        text = (getattr(parsed, "text", None) or "").strip()
        try:
            reply = await self._handle(text, parsed)
        except Exception as exc:
            logger.error(
                "orchestrator_handle_failed",
                extra={"error_type": type(exc).__name__},
            )
            reply = "抱歉，处理消息时出错了，请稍后重试。"
        m.orchestrator_handle_latency_seconds.observe(time.perf_counter() - start)
        # Join segments with blank line; outbound layer may re-split
        if isinstance(reply, list):
            return "\n\n".join(reply)
        return reply

    async def _handle(self, text: str, parsed: Any) -> str:
        if not text:
            return "请发送文字消息，我可以帮你管理求职和模拟面试。"

        try:
            ctx = await get_context(self.user_id)
        except RedisUnavailableError:
            # Read path: treat as idle but block write confirmations later
            ctx = default_context()
            ctx["_redis_down"] = True

        state = ctx.get("state") or "idle"

        # ── awaiting_confirmation ──────────────────────────────────
        if state == "awaiting_confirmation":
            return await self._handle_confirmation(text, ctx)

        # ── in_interview ───────────────────────────────────────────
        if state == "in_interview":
            return await self._handle_interview(text, ctx)

        # ── idle: parse intent ─────────────────────────────────────
        return await self._handle_idle(text, ctx, parsed)

    async def _handle_confirmation(self, text: str, ctx: dict) -> str:
        if is_confirm(text):
            pending = ctx.get("pending_action") or {}
            action_type = pending.get("type")
            params = pending.get("params") or {}
            result = await self._execute_pending(action_type, params)
            m.confirmation_total.labels(
                action=action_type or "unknown",
                outcome="confirm",
            ).inc()
            ctx["state"] = "idle"
            ctx["pending_action"] = None
            queued = list(ctx.get("queued_after_confirm") or [])
            ctx["queued_after_confirm"] = []
            await self._safe_set(ctx)

            parts = [result.get("reply_text") or "已完成。"]
            # Process queued intents sequentially after confirm
            for item in queued:
                follow = await self._dispatch_intent(
                    item.get("intent", "unknown"),
                    item.get("entities") or {},
                    ctx,
                    confidence=float(item.get("confidence") or 1.0),
                )
                parts.append(follow)
            return "\n\n".join(p for p in parts if p)

        if is_cancel(text):
            action_type = (ctx.get("pending_action") or {}).get("type") or "unknown"
            m.confirmation_total.labels(action=action_type, outcome="cancel").inc()
            ctx["state"] = "idle"
            ctx["pending_action"] = None
            ctx["queued_after_confirm"] = []
            await self._safe_set(ctx)
            return "已取消操作。"

        # Queue non-confirm message intent for after confirmation
        queued = list(ctx.get("queued_after_confirm") or [])
        queued.append({"raw_hint": True, "text_len": len(text)})
        # Try light parse to store intent (no write execution)
        try:
            parsed_intent = await self.parser.parse(
                text, user_id=self.user_id, skip_confirm_rules=True
            )
            if parsed_intent.get("intent") not in ("confirm", "cancel", "unknown"):
                queued[-1] = {
                    "intent": parsed_intent["intent"],
                    "entities": parsed_intent.get("entities") or {},
                    "confidence": parsed_intent.get("confidence") or 0,
                }
        except Exception:
            pass
        ctx["queued_after_confirm"] = queued[:5]
        await self._safe_set(ctx)
        return "请先回复「确认」或「取消」完成当前操作。你刚才的消息我会在确认后处理。"

    async def _handle_interview(self, text: str, ctx: dict) -> str:
        adapter = InterviewAdapter(self.session, self.user_id, send_interim=self.send_interim)
        session_id = ctx.get("interview_session_id")
        sid = UUID(str(session_id)) if session_id else None
        round_no = int(ctx.get("interview_round") or 0)

        # Meta commands inside interview
        lower = text.strip()
        if lower in ("暂停面试", "暂停", "不做了", "先暂停"):
            result = await adapter.pause(sid, round_no)
            ctx["state"] = "idle"  # flagged paused; session stays in_progress
            ctx["interview_session_id"] = str(sid) if sid else ctx.get("interview_session_id")
            await self._safe_set(ctx)
            return result["reply_text"]

        if lower in ("结束面试", "结束", "不面了"):
            result = await adapter.end(sid, round_no)
            ctx["state"] = "idle"
            ctx["interview_session_id"] = None
            ctx["interview_round"] = None
            await self._safe_set(ctx)
            return result["reply_text"]

        if lower in ("继续面试", "继续"):
            result = await adapter.continue_session(sid)
            if result.get("data") and result["data"].get("session_id"):
                ctx["interview_session_id"] = result["data"]["session_id"]
                ctx["interview_round"] = result["data"].get("interview_round") or round_no
                ctx["state"] = "in_interview"
                await self._safe_set(ctx)
            return result["reply_text"]

        if lower in ("开始", "开始吧", "准备好了") and ctx.get("awaiting_begin"):
            if sid is None:
                return "面试会话丢失，请重新「开始模拟面试」。"
            result = await adapter.begin_questions(sid)
            ctx["awaiting_begin"] = False
            ctx["interview_round"] = (result.get("data") or {}).get("interview_round") or 1
            await self._safe_set(ctx)
            return result["reply_text"]

        # Detect non-answer intents (help / query) — prompt user
        if lower in ("帮助", "help") or lower.startswith("查"):
            return (
                f"当前正在进行模拟面试（第 {round_no or '?'}/5 轮）。"
                "如需中断面试，请回复「暂停面试」。否则请先完成当前题目作答。"
            )

        # Treat as answer
        if sid is None:
            ctx["state"] = "idle"
            await self._safe_set(ctx)
            return "面试会话已失效，请重新「开始模拟面试」。"

        seq = max(round_no, 1)
        result = await adapter.submit_answer(sid, text, seq)
        data = result.get("data") or {}
        interim = data.get("interim")
        if data.get("completed"):
            ctx["state"] = "idle"
            ctx["interview_session_id"] = None
            ctx["interview_round"] = None
        else:
            ctx["interview_round"] = data.get("interview_round") or (seq + 1)
            ctx["state"] = "in_interview"
        await self._safe_set(ctx)

        reply = result.get("reply_text") or ""
        if interim:
            return f"{interim}\n\n{reply}"
        return reply

    async def _handle_idle(self, text: str, ctx: dict, parsed: Any) -> str:
        result = await self.parser.parse(text, user_id=self.user_id)
        intent = result.get("intent") or "unknown"
        entities = result.get("entities") or {}
        confidence = float(result.get("confidence") or 0)
        error = result.get("error")

        if error in ("llm_unavailable", "parse_error"):
            ctx["unknown_streak"] = int(ctx.get("unknown_streak") or 0) + 1
            await self._safe_set(ctx)
            return entities.get("reply") or LLM_UNAVAILABLE_TEXT

        if intent == "rejected_web_guide":
            ctx["unknown_streak"] = 0
            await self._safe_set(ctx)
            return entities.get("reply") or WEB_GUIDE_DELETE

        if intent == "compound":
            steps = entities.get("steps") or []
            if not steps:
                return UNKNOWN_TEXT
            replies: list[str] = []
            for step in steps:
                if not isinstance(step, dict):
                    continue
                r = await self._dispatch_intent(
                    step.get("intent", "unknown"),
                    step.get("entities") or {},
                    ctx,
                    confidence=float(step.get("confidence") or confidence or 1.0),
                )
                replies.append(r)
                # If we entered confirmation, stop and queue remaining
                fresh = await self._safe_get()
                if fresh.get("state") == "awaiting_confirmation":
                    remaining = steps[steps.index(step) + 1 :]
                    queued = [
                        {
                            "intent": s.get("intent"),
                            "entities": s.get("entities") or {},
                            "confidence": s.get("confidence") or 1.0,
                        }
                        for s in remaining
                        if isinstance(s, dict)
                    ]
                    fresh["queued_after_confirm"] = queued
                    await self._safe_set(fresh)
                    break
            return "\n\n".join(replies)

        # Low confidence gate (except meta)
        if (
            intent not in ("help", "confirm", "cancel", "unknown")
            and confidence < CONFIDENCE_THRESHOLD
        ):
            ctx["unknown_streak"] = int(ctx.get("unknown_streak") or 0) + 1
            await self._safe_set(ctx)
            return format_low_confidence(result.get("alternatives"))

        return await self._dispatch_intent(intent, entities, ctx, confidence=confidence)

    async def _dispatch_intent(
        self,
        intent: str,
        entities: dict[str, Any],
        ctx: dict,
        *,
        confidence: float = 1.0,
    ) -> str:
        if intent == "help":
            ctx["unknown_streak"] = 0
            await self._safe_set(ctx)
            return HELP_TEXT

        if intent == "confirm":
            return "当前没有待确认的操作。你可以「新增岗位」或「查询求职进展」。"

        if intent == "cancel":
            return "当前没有可取消的操作。"

        if intent == "unknown":
            streak = int(ctx.get("unknown_streak") or 0) + 1
            ctx["unknown_streak"] = streak
            await self._safe_set(ctx)
            if streak >= 3:
                return UNKNOWN_STREAK_TEXT
            return UNKNOWN_TEXT

        # Write tools need Redis for confirmation state
        if intent in ("create_job", "update_status", "update_job_fields"):
            if ctx.get("_redis_down"):
                return REDIS_UNAVAILABLE_TEXT
            return await self._prepare_write(intent, entities, ctx)

        if intent == "query_jobs":
            # Heuristic: upcoming interviews phrasing often in entities
            result = await tool_query_jobs.execute(self.session, self.user_id, entities)
            ctx["unknown_streak"] = 0
            await self._safe_set(ctx)
            return result["reply_text"]

        if intent == "query_reports":
            result = await tool_query_reports.execute(self.session, self.user_id, entities)
            ctx["unknown_streak"] = 0
            await self._safe_set(ctx)
            return result["reply_text"]

        if intent == "query_ability":
            result = await tool_query_ability.execute(self.session, self.user_id, entities)
            ctx["unknown_streak"] = 0
            await self._safe_set(ctx)
            return result["reply_text"]

        if intent == "start_interview":
            adapter = InterviewAdapter(self.session, self.user_id, send_interim=self.send_interim)
            result = await adapter.start(entities)
            data = result.get("data") or {}
            if data.get("session_id"):
                ctx["state"] = "in_interview"
                ctx["interview_session_id"] = data["session_id"]
                ctx["interview_round"] = data.get("interview_round") or 0
                ctx["awaiting_begin"] = bool(data.get("awaiting_begin"))
                ctx["unknown_streak"] = 0
                await self._safe_set(ctx)
            return result["reply_text"]

        if intent == "continue_interview":
            adapter = InterviewAdapter(self.session, self.user_id, send_interim=self.send_interim)
            result = await adapter.continue_session(
                UUID(str(ctx["interview_session_id"])) if ctx.get("interview_session_id") else None
            )
            data = result.get("data") or {}
            if result.get("ok") and data.get("session_id"):
                ctx["state"] = "in_interview"
                ctx["interview_session_id"] = data["session_id"]
                ctx["interview_round"] = data.get("interview_round")
                ctx["unknown_streak"] = 0
                await self._safe_set(ctx)
            return result["reply_text"]

        if intent == "pause_interview":
            adapter = InterviewAdapter(self.session, self.user_id)
            sid = (
                UUID(str(ctx["interview_session_id"])) if ctx.get("interview_session_id") else None
            )
            result = await adapter.pause(sid, ctx.get("interview_round"))
            ctx["state"] = "idle"
            await self._safe_set(ctx)
            return result["reply_text"]

        if intent == "end_interview":
            adapter = InterviewAdapter(self.session, self.user_id)
            sid = (
                UUID(str(ctx["interview_session_id"])) if ctx.get("interview_session_id") else None
            )
            result = await adapter.end(sid, ctx.get("interview_round"))
            ctx["state"] = "idle"
            ctx["interview_session_id"] = None
            ctx["interview_round"] = None
            await self._safe_set(ctx)
            return result["reply_text"]

        return UNKNOWN_TEXT

    async def _prepare_write(self, intent: str, entities: dict[str, Any], ctx: dict) -> str:
        if intent == "create_job":
            result = await tool_create_job.prepare(self.session, self.user_id, entities)
        elif intent == "update_status":
            result = await tool_update_status.prepare(self.session, self.user_id, entities)
        else:
            result = await tool_update_fields.prepare(self.session, self.user_id, entities)

        data = result.get("data") or {}
        if data.get("needs_confirmation") and data.get("pending_action"):
            try:
                ctx["state"] = "awaiting_confirmation"
                ctx["pending_action"] = data["pending_action"]
                ctx["unknown_streak"] = 0
                await set_context(self.user_id, ctx)
            except RedisUnavailableError:
                return REDIS_UNAVAILABLE_TEXT
            return result["reply_text"]

        # clarify / fail — no state change to awaiting
        ctx["unknown_streak"] = 0
        await self._safe_set(ctx)
        return result["reply_text"]

    async def _execute_pending(
        self, action_type: str | None, params: dict[str, Any]
    ) -> dict[str, Any]:
        if action_type == "create_job":
            return await tool_create_job.execute(self.session, self.user_id, params)
        if action_type == "update_job_status":
            return await tool_update_status.execute(self.session, self.user_id, params)
        if action_type == "update_job_fields":
            return await tool_update_fields.execute(self.session, self.user_id, params)
        return {
            "ok": False,
            "reply_text": "未知的待确认操作，已取消。",
            "data": None,
            "error_code": "unknown_action",
        }

    async def _safe_set(self, ctx: dict) -> None:
        try:
            clean = {k: v for k, v in ctx.items() if not str(k).startswith("_")}
            await set_context(self.user_id, clean)
        except RedisUnavailableError:
            logger.warning(
                "conversation_context_persist_skipped",
                extra={"user_id": str(self.user_id)},
            )

    async def _safe_get(self) -> dict:
        try:
            return await get_context(self.user_id)
        except RedisUnavailableError:
            return default_context()


__all__ = ["ConversationOrchestrator"]
