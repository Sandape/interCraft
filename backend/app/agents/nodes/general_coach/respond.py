"""M19 node — respond: generate streaming response via LLM."""
from __future__ import annotations

from pathlib import Path

from app.agents.llm_client import get_llm_client
from app.agents.state.general_coach_state import GeneralCoachState

_PROMPT_DIR = Path(__file__).resolve().parent.parent.parent / "prompts" / "general_coach"


def _load_prompt(name: str) -> str:
    path = _PROMPT_DIR / name
    return path.read_text(encoding="utf-8")


async def respond_node(state: GeneralCoachState) -> dict:
    """Generate a response using LLM based on intent and question."""
    messages = state.get("messages", [])
    question = ""
    for msg in reversed(messages):
        if isinstance(msg, dict) and msg.get("role") == "user":
            question = msg.get("content", "")
            break

    intent = state.get("detected_intent", "chitchat")
    redirect = state.get("suggested_redirect")

    if redirect:
        response_text = f"根据您的问题，我建议您使用{redirect}功能来获得更针对性的帮助。"
    else:
        template = _load_prompt("respond.md")
        prompt = template.format(question=question, intent=intent)

        client = get_llm_client()
        try:
            result = await client.invoke(
                messages=[
                    {"role": "system", "content": "你是一位 AI 职业教练。回答要简洁实用。"},
                    {"role": "user", "content": prompt},
                ],
                estimated_tokens=1500,
                user_id=state.get("user_id", "unknown"),
                thread_id=state.get("thread_id", "unknown"),
                node_name="general_coach_respond",
            )
            response_text = result["content"]
        except Exception:
            response_text = "抱歉，我现在无法回答。请稍后再试。"

    return {
        "messages": [{"role": "assistant", "content": response_text}],
    }


__all__ = ["respond_node"]
