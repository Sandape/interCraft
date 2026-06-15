"""M17 node — evaluate: score user answer on 0-10 scale."""
from __future__ import annotations

import json
import re

from app.agents.llm_client import get_llm_client
from app.agents.state.error_coach_state import ErrorCoachState


async def evaluate_node(state: ErrorCoachState) -> dict:
    """Evaluate the latest user answer on a 0-10 scale (>= 8 = correct)."""
    question = state.get("question", {})
    question_text = question.get("question_text", "")
    reference_answer = question.get("reference_answer_md", "")

    # Get latest user message
    messages = state.get("messages", [])
    user_answer = ""
    for msg in reversed(messages):
        if isinstance(msg, dict) and msg.get("role") == "user":
            user_answer = msg.get("content", "")
            break

    prompt = f"""Evaluate this answer on a scale of 0-10 (10 = perfect).
Score >= 8 means correct.

Question: {question_text}
Reference answer: {reference_answer}
User answer: {user_answer}

Output ONLY a JSON object:
{{"score": <0-10>, "feedback": "<brief feedback in Chinese>"}}"""

    client = get_llm_client()
    try:
        result = await client.invoke(
            messages=[
                {"role": "system", "content": "你是一位严格的面试评分官。评分标准: ≥8 为答对, 0-10 分制。"},
                {"role": "user", "content": prompt},
            ],
            estimated_tokens=800,
            user_id=state.get("user_id", "unknown"),
            thread_id=state.get("thread_id", "unknown"),
            node_name="error_coach_evaluate",
        )
        content = result["content"]
        json_match = re.search(r"\{.*\}", content, re.DOTALL)
        if json_match:
            data = json.loads(json_match.group(0))
            score = int(data.get("score", 5))
        else:
            score = 5
    except Exception:
        score = 5

    correct_count = state.get("correct_count", 0)
    attempt_count = state.get("attempt_count", 0) + 1

    if score >= 8:
        correct_count += 1

    # Advance hint level based on attempts
    current_level = state.get("current_hint_level", "small")
    if attempt_count >= 3 and current_level == "small":
        current_level = "medium"
    elif attempt_count >= 5 and current_level == "medium":
        current_level = "detailed"

    return {
        "correct_count": correct_count,
        "attempt_count": attempt_count,
        "current_hint_level": current_level,
        "messages": [{"role": "system", "content": f"Score: {score}/10. {'Correct!' if score >= 8 else 'Incorrect.'}"}],
    }


__all__ = ["evaluate_node"]
