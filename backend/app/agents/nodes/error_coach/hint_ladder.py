"""M17 node — hint_ladder: generate gradient hint based on attempt_count."""
from __future__ import annotations

from pathlib import Path

from app.agents.llm_client import get_llm_client
from app.agents.state.error_coach_state import ErrorCoachState
from app.observability import traced_node

_PROMPT_DIR = Path(__file__).resolve().parent.parent.parent / "prompts" / "error_coach"


def _load_prompt(name: str) -> str:
    path = _PROMPT_DIR / name
    return path.read_text(encoding="utf-8")


_HINT_LEVELS = ["small", "medium", "detailed"]


@traced_node("error_coach.hint_ladder")
async def hint_ladder_node(state: ErrorCoachState) -> dict:
    """Generate a hint based on current hint level."""
    question = state.get("question", {})
    question_text = question.get("question_text", "")
    reference_answer = question.get("reference_answer_md", "")
    dimension = question.get("dimension", "general")
    attempt_count = state.get("attempt_count", 0)
    current_level = state.get("current_hint_level", "small")

    template = _load_prompt("hint_ladder.md")
    prompt = template.format(
        question_text=question_text,
        reference_answer=reference_answer,
        dimension=dimension,
        hint_level=current_level,
        attempt_count=attempt_count,
    )

    client = get_llm_client()
    try:
        result = await client.invoke(
            messages=[
                {"role": "system", "content": "你是一位面试辅导老师。根据当前提示等级给学生提供恰当的提示。"},
                {"role": "user", "content": prompt},
            ],
            estimated_tokens=1000,
            user_id=state.get("user_id", "unknown"),
            thread_id=state.get("thread_id", "unknown"),
            node_name="error_coach_hint",
        )
        hint_content = result["content"]
    except Exception:
        hint_content = "请仔细阅读题目，尝试回忆相关知识。"

    return {
        "messages": [{"role": "assistant", "content": hint_content}],
    }


__all__ = ["hint_ladder_node"]