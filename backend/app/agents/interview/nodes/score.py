"""Score node — evaluates candidate answers (T027)."""
from __future__ import annotations

import json
import re
from pathlib import Path

from app.agents.interview.state import InterviewGraphState
from app.agents.llm_client import get_llm_client

_PROMPT_DIR = Path(__file__).resolve().parent.parent / "prompts"


def _load_prompt(name: str) -> str:
    path = _PROMPT_DIR / name
    return path.read_text(encoding="utf-8")


async def score_node(state: InterviewGraphState) -> dict:
    """Score the latest user answer against the current question."""
    questions = state.get("questions", [])
    scores = state.get("scores", [])
    current_q = state.get("current_question", 0)

    if not questions:
        return {"scores": scores, "error": "No question to score against"}

    latest_question = questions[-1]
    question_text = latest_question.get("question", "")
    dimension = latest_question.get("dimension", "tech_depth")

    # Get latest user answer from messages (supports both dicts and HumanMessage objects)
    messages = state.get("messages", [])
    answer = ""
    for msg in reversed(messages):
        if isinstance(msg, dict):
            role = msg.get("role", "")
            if role == "user":
                answer = msg.get("content", "")
                break
        else:
            # LangGraph HumanMessage object
            if getattr(msg, "type", "") == "human":
                answer = getattr(msg, "content", "") or ""
                break

    template = _load_prompt("score.md")
    prompt = template.format(
        question=question_text,
        dimension=dimension,
        difficulty=state.get("difficulty", "medium"),
        answer=answer if answer else "(no answer provided)",
    )

    client = get_llm_client()
    try:
        result = await client.invoke(
            messages=[
                {"role": "system", "content": "你是一位面试评估官，负责对候选人的回答进行打分。所有 JSON 字段值必须使用中文（zh-CN），仅 JSON 的 key 保持英文。`dimension` 字段值必须使用英文 key，`feedback` 字段值必须为中文。只返回 JSON，不要包含任何解释或 markdown 标记。"},
                {"role": "user", "content": prompt},
            ],
            estimated_tokens=1800,
            user_id=state.get("user_id", "unknown"),
            thread_id=state.get("thread_id", "unknown"),
            node_name="score",
        )
        content = result["content"]
        json_match = re.search(r"\{.*\}", content, re.DOTALL)
        if json_match:
            s_data = json.loads(json_match.group(0))
        else:
            s_data = {"score": 5, "dimension": dimension, "feedback": "Unable to parse score."}
    except Exception:
        s_data = {"score": 5, "dimension": dimension, "feedback": "Scoring unavailable."}

    new_score = {
        "question_no": current_q,
        "dimension": dimension,
        "score": s_data.get("score", 5),
        "feedback": s_data.get("feedback", ""),
        "sub_scores": s_data.get("sub_scores", {}),
        "question_text": question_text,
        "user_answer": answer if answer else "",
    }

    return {
        "scores": [*scores, new_score],
    }


__all__ = ["score_node"]
