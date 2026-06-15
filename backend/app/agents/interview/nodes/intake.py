"""Intake node — extracts position/company/difficulty from user input (T025)."""
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


async def intake_node(state: InterviewGraphState) -> dict:
    """Process user input to extract interview parameters.

    Uses LLM to extract structured position/company/difficulty,
    falling back to regex parsing on failure.
    """
    position = state.get("position", "")
    company = state.get("company", "")

    if not position or not company:
        # Try to extract from last user message
        messages = state.get("messages", [])
        if messages:
            last_msg = messages[-1]
            content = last_msg.get("content", "") if isinstance(last_msg, dict) else str(last_msg)
            if not position:
                position = content
            if not company:
                company = "通用"

    prompt = _load_prompt("intake.md").format(position=position, company=company)

    client = get_llm_client()
    try:
        result = await client.invoke(
            messages=[
                {"role": "system", "content": "你负责从用户输入中提取结构化面试信息。所有 JSON 字段值必须使用中文（zh-CN），仅 JSON 的 key 保持英文。只返回 JSON，不要包含任何解释或 markdown 标记。"},
                {"role": "user", "content": prompt},
            ],
            estimated_tokens=700,
            user_id=state.get("user_id", "unknown"),
            thread_id=state.get("thread_id", "unknown"),
            node_name="intake",
        )
        # Parse JSON from response
        content = result["content"]
        json_match = re.search(r"\{.*\}", content, re.DOTALL)
        data = json.loads(json_match.group(0)) if json_match else {}
    except Exception:
        data = {}

    return {
        "position": data.get("position", position or "未指定岗位"),
        "company": data.get("company", company or "通用公司"),
        "difficulty": data.get("difficulty", "medium"),
        "current_question": 0,
    }


__all__ = ["intake_node"]
