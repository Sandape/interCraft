"""M18 node — generate_insight: LLM produces improvement suggestions per dimension."""
from __future__ import annotations

import json
import re
from pathlib import Path

from app.agents.llm_client import get_llm_client
from app.agents.state.ability_diagnose_state import AbilityDiagnoseState

_PROMPT_DIR = Path(__file__).resolve().parent.parent.parent / "prompts" / "ability_diagnose"


def _load_prompt(name: str) -> str:
    path = _PROMPT_DIR / name
    return path.read_text(encoding="utf-8")


async def generate_insight_node(state: AbilityDiagnoseState) -> dict:
    """Generate improvement insights for each dimension using LLM."""
    diagnoses = state.get("diagnoses", [])

    template = _load_prompt("generate_insight.md")
    prompt = template.format(diagnoses=json.dumps(diagnoses, ensure_ascii=False, indent=2))

    client = get_llm_client()
    try:
        result = await client.invoke(
            messages=[
                {"role": "system", "content": "你是一位能力诊断专家。根据诊断数据生成改进建议。"},
                {"role": "user", "content": prompt},
            ],
            estimated_tokens=2000,
            user_id=state.get("user_id", "unknown"),
            thread_id=state.get("thread_id", "unknown"),
            node_name="ability_diagnose_insight",
        )
        content = result["content"]
        insights = _parse_insights(content, diagnoses)
    except Exception:
        insights = [{"dimension": d["dimension"], "suggestions": ["无法生成建议"], "priority": "medium"} for d in diagnoses]

    return {
        "insights": insights,
    }


def _parse_insights(content: str, diagnoses: list[dict]) -> list[dict]:
    """Parse LLM response into structured insights."""
    json_match = re.search(r"\{.*\}", content, re.DOTALL)
    if json_match:
        try:
            data = json.loads(json_match.group(0))
            insights_list = data.get("insights", [])
            if insights_list:
                return insights_list
        except json.JSONDecodeError:
            pass

    # Fallback: one generic insight per dimension
    return [
        {
            "dimension": d["dimension"],
            "suggestions": [f"继续提升 {d['dimension']} 能力，当前分数 {d.get('current_score', 0)}/{d.get('max_score', 10)}"],
            "priority": "high" if d.get("trend") == "down" else "medium",
            "trend": d.get("trend", "stable"),
        }
        for d in diagnoses
    ]


__all__ = ["generate_insight_node"]
