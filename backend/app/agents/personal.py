"""Personal Agent reply — inbound WeChat message → LLM-generated text.

REQ-052 US3.5: When a WeChat user sends a message, the backend's iLink
long-poll task receives it, parses it via ``parse_inbound_message``, and
hands the parsed message to ``PersonalAgentReply.run`` which:

  1. Loads the user's agent_preferences (display_name, notification_mode).
  2. Loads the last 6 message turns from ``agent_messages`` as
     conversation_history.
  3. Builds a system prompt using the template (interview-assistant style
     "求职助手") and the user's display_name.
  4. Calls ``LLMClient.invoke(messages=..., user_id=..., thread_id=...,
     node_name="personal_reply")`` which goes through the full governance
     stack: pre-deduct token quota, call DeepSeek V4 Pro, write
     ``ai_messages`` audit row, emit Prometheus metrics + OTel spans, and
     adjust the user's ``monthly_token_used`` after the call.
  5. Returns the reply text. The caller (ilink_pool._poll_loop) is
     responsible for enqueuing the outbound message — we do NOT call
     iLink.send_text directly from here.

This module intentionally has no LLM client of its own — all LLM
governance lives in ``app.agents.llm_client.LLMClient``.
"""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


# ── System prompt template ─────────────────────────────────────────

# Loaded lazily; placeholder for per-user display_name and notification_mode.
# Translation: "You are InterCraft's personal job-search assistant. Help
# the user with job-search topics: resumes, interviews, salary
# negotiation, etc. Respond in Chinese unless the user writes in another
# language. Be concise — replies are delivered via WeChat."
_SYSTEM_PROMPT_TEMPLATE = (
    "你是 InterCraft 的个人求职助手，正在通过微信与用户 {display_name} 对话。"
    "帮助用户处理简历优化、面试准备、薪资谈判、职业规划等问题。"
    "回复简短有力（不超过 300 字），用中文，除非用户用其他语言。"
    "通知模式：{notification_mode}。如果用户开启免打扰，请用文字提示而非主动推送。"
)


_DEFAULT_REPLY = "抱歉，AI 暂时不可用，请稍后再试。"


class PersonalAgentReply:
    """Fallback chat reply OR thin wrapper around ConversationOrchestrator.

    REQ-054: Prefer ``ConversationOrchestrator`` when ``use_orchestrator``
    is True (default). The legacy LLM chat path remains as an explicit
    fallback used by ``AgentService.process_inbound_reply`` when the
    orchestrator fails to import/run.
    """

    def __init__(
        self,
        session: AsyncSession,
        user_id: UUID,
        *,
        use_orchestrator: bool = True,
    ):
        self.session = session
        self.user_id = user_id
        self.use_orchestrator = use_orchestrator

    async def run(self, parsed: Any) -> str:
        """Generate a reply string for the parsed inbound message.

        ``parsed`` is a ``ParsedMessage`` (app.channels.message_handler).
        We accept ``Any`` here to avoid an import cycle; the only fields
        we use are ``.text`` and ``.from_user_id``.
        """
        if self.use_orchestrator:
            try:
                from app.modules.agent.conversation import ConversationOrchestrator

                return await ConversationOrchestrator(self.session, self.user_id).handle(
                    parsed
                )
            except Exception:
                logger.exception(
                    "personal_agent_orchestrator_fallback",
                    extra={"user_id": str(self.user_id)},
                )

        return await self._legacy_chat_reply(parsed)

    async def _legacy_chat_reply(self, parsed: Any) -> str:
        """REQ-052 chat-only path (no tool calling)."""
        from app.agents.llm_client import LLMClient
        from app.modules.agent.repository import (
            AgentMessageRepository,
            AgentPreferenceRepository,
        )

        # 1. Load preferences (display_name, notification_mode)
        pref_repo = AgentPreferenceRepository(self.session)
        pref = await pref_repo.get_by_user(self.user_id)
        display_name = (pref.display_name if pref else None) or "朋友"
        notification_mode = (pref.notification_mode if pref else None) or "realtime"

        # 2. Load last 6 messages as conversation history
        msg_repo = AgentMessageRepository(self.session)
        history = await msg_repo.list_by_user(self.user_id, limit=6)
        history_messages = self._format_history(history)

        # 3. Build the messages list
        system_prompt = _SYSTEM_PROMPT_TEMPLATE.format(
            display_name=display_name,
            notification_mode=notification_mode,
        )
        messages: list[dict[str, str]] = [{"role": "system", "content": system_prompt}]
        messages.extend(history_messages)
        messages.append({"role": "user", "content": parsed.text or ""})

        # 4. Call LLMClient (quota pre-deduct + call + adjust + audit)
        thread_id = parsed.context_token or str(self.user_id)
        try:
            client = LLMClient()
            response = await client.invoke(
                messages=messages,
                user_id=str(self.user_id),
                thread_id=thread_id,
                node_name="personal_reply",
            )
            # LLMResponse is a TypedDict — access via [] not attribute.
            content = response.get("content", "") or ""
            reply_text = content.strip() or _DEFAULT_REPLY
        except Exception as exc:
            logger.exception(
                "personal_agent_reply_failed",
                extra={"user_id": str(self.user_id), "error": str(exc)[:120]},
            )
            reply_text = _DEFAULT_REPLY

        return reply_text

    def _format_history(self, history: list[Any]) -> list[dict[str, str]]:
        """Convert AgentMessage rows to OpenAI chat messages.

        We use the message direction to assign roles:
          - direction='inbound'  → 'user'
          - direction='outbound' → 'assistant'
        """
        out: list[dict[str, str]] = []
        for m in history:
            role = "user" if m.direction == "inbound" else "assistant"
            out.append({"role": role, "content": m.content or ""})
        return out
