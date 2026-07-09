"""M19 node — intent: classify user message with LLM + few-shot."""
from __future__ import annotations

import json
import re
from pathlib import Path

from app.agents.llm_client import get_llm_client
from app.agents.state.general_coach_state import GeneralCoachState
from app.agents.utils.node_error_handler import node_error_handler
from app.agents.tools.approval import bind_tools_with_approval  # REQ-041-P0-APPROVAL AC-5.1/5.2 wiring
from app.observability import traced_node

_PROMPT_DIR = Path(__file__).resolve().parent.parent.parent / "prompts" / "general_coach"


def _load_prompt(name: str) -> str:
    path = _PROMPT_DIR / name
    return path.read_text(encoding="utf-8")


@node_error_handler(fallback_strategy="retry")
@traced_node("general_coach.intent")
async def intent_node(state: GeneralCoachState) -> dict:
    """Classify the user's latest message intent."""
    messages = state.get("messages", [])
    question = ""
    for msg in reversed(messages):
        if isinstance(msg, dict) and msg.get("role") == "user":
            question = msg.get("content", "")
            break

    if not question:
        return {"detected_intent": "chitchat", "confidence": 0.5}

    template = _load_prompt("intent.md")
    prompt = template.format(question=question)

    client = get_llm_client()
    # REQ-041-P0-APPROVAL (AC-5.1/5.2): exercise the gate wiring surface. Same
    # defensive pattern as ``nodes/resume_optimize/diff_jd.py`` — gated by
    # ``hasattr`` so the production ``LLMClient`` (no ``bind_tools`` attr) does
    # not crash. The gate becomes load-bearing when ``intent`` promotes tool
    # calls (MarkComplete) into the prompt.
    if hasattr(client, "bind_tools"):
        bind_tools_with_approval(client, [])  # AC-5.1 wiring surface
    try:
        result = await client.invoke(
            messages=[
                {"role": "system", "content": "You are an intent classifier. Output only JSON."},
                {"role": "user", "content": prompt},
            ],
            estimated_tokens=500,
            user_id=state.get("user_id", "unknown"),
            thread_id=state.get("thread_id", "unknown"),
            node_name="general_coach_intent",
        )
        content = result["content"]
        json_match = re.search(r"\{.*\}", content, re.DOTALL)
        if json_match:
            data = json.loads(json_match.group(0))
            intent = data.get("intent", "chitchat")
            confidence = float(data.get("confidence", 0.5))
        else:
            intent = "chitchat"
            confidence = 0.5
    except Exception:
        intent = "chitchat"
        confidence = 0.5

    return {
        "detected_intent": intent,
        "confidence": confidence,
    }


__all__ = ["intent_node"]