"""Question generation node — generates interview questions (T026)."""
from __future__ import annotations

import json
import re
from pathlib import Path

from app.agents.interview.state import InterviewGraphState
from app.agents.llm_client import get_llm_client
from app.agents.interview.requirements_block import build_requirements_block
from app.agents.utils.node_error_handler import node_error_handler
from app.observability import traced_node
import structlog

logger = structlog.get_logger(__name__)

_PROMPT_DIR = Path(__file__).resolve().parent.parent / "prompts"

# Dimension rotation: cycle through 5 dimensions
DIMENSIONS = [
    "tech_depth",
    "architecture",
    "engineering_practice",
    "communication",
    "algorithm",
]


def _load_prompt(name: str) -> str:
    path = _PROMPT_DIR / name
    return path.read_text(encoding="utf-8")


@node_error_handler(fallback_strategy="retry")
@traced_node("interview.question_gen")
async def question_gen_node(state: InterviewGraphState) -> dict:
    """Generate the next interview question based on state context.

    Rotates through dimensions: tech_depth → architecture →
    engineering_practice → communication → algorithm.
    """
    current = state.get("current_question", 0)
    dimension = DIMENSIONS[current % len(DIMENSIONS)]

    questions = state.get("questions", [])
    previous_questions = json.dumps(
        [q.get("question", "") for q in questions], ensure_ascii=False
    )

    # 019 — inject requirements_md block (capped at MAX_REQUIREMENTS_TOKENS)
    raw_req = state.get("requirements_md")
    block, provided, truncated, original_chars = build_requirements_block(raw_req)
    if raw_req and provided and not state.get("requirements_provided"):
        # The state was missing the booleans (e.g. resumed session without
        # them). Re-stamp them so the report node still gets correct values.
        state["requirements_provided"] = True
        state["requirements_truncated"] = truncated
        state["requirements_original_chars"] = original_chars

    template = _load_prompt("question_gen.md")
    prompt = template.format(
        position=state.get("position", ""),
        company=state.get("company", ""),
        difficulty=state.get("difficulty", "medium"),
        current_question=current + 1,
        dimension=dimension,
        topics_to_probe="根据岗位要求自动选择",
        previous_questions=previous_questions if previous_questions else "无",
        requirements_md_block=block if block else "",
    )

    client = get_llm_client()
    try:
        result = await client.invoke(
            messages=[
                {"role": "system", "content": "你是一位技术面试官，负责生成面试题。所有 JSON 字段值必须使用中文（zh-CN），仅 JSON 的 key 保持英文。`dimension` 字段值必须使用英文 key，其余字段（question、expected_points、hints）必须为中文。只返回 JSON，不要包含任何解释或 markdown 标记。"},
                {"role": "user", "content": prompt},
            ],
            estimated_tokens=2500,
            user_id=state.get("user_id", "unknown"),
            thread_id=state.get("thread_id", "unknown"),
            node_name="question_gen",
        )
        content = result["content"]
        json_match = re.search(r"\{.*\}", content, re.DOTALL)
        if json_match:
            q_data = json.loads(json_match.group(0))
        else:
            q_data = {"question": content, "dimension": dimension, "difficulty": state.get("difficulty", "medium")}
    except Exception:
        q_data = {
            "question": f"请分享你在{dimension}方面的经验和理解。",
            "dimension": dimension,
            "difficulty": state.get("difficulty", "medium"),
        }

    new_question = {
        "question_no": current + 1,
        "dimension": dimension,
        "question": q_data.get("question", ""),
        "expected_points": q_data.get("expected_points", []),
        "hints": q_data.get("hints", []),
    }

    return {
        "questions": [*questions, new_question],
        "current_question": current + 1,
    }


__all__ = ["question_gen_node"]
