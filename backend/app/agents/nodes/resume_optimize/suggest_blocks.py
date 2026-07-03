"""M16 node — suggest_blocks: generate JSON Patch from diff analysis.

Takes the diff_jd analysis and produces concrete JSON Patch operations.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from app.agents.llm_client import get_llm_client
from app.agents.state.resume_optimize_state import ResumeOptimizeState
from app.observability import traced_node

_PROMPT_DIR = Path(__file__).resolve().parent.parent.parent / "prompts" / "resume_optimize"


def _load_prompt(name: str) -> str:
    path = _PROMPT_DIR / name
    return path.read_text(encoding="utf-8")


@traced_node("resume_optimize.suggest_blocks")
async def suggest_blocks_node(state: ResumeOptimizeState) -> dict:
    """Generate proposed JSON Patch from the diff analysis."""
    target_jd = state.get("target_jd", "")
    current_blocks = state.get("current_blocks", [])

    # Get the last assistant message (diff_jd analysis)
    messages = state.get("messages", [])
    diff_analysis = ""
    for msg in reversed(messages):
        if isinstance(msg, dict) and msg.get("role") == "assistant":
            diff_analysis = msg.get("content", "")
            break

    template = _load_prompt("suggest_blocks.md")
    blocks_text = _serialize_blocks(current_blocks)
    prompt = template.format(
        target_jd=target_jd,
        blocks=blocks_text,
        diff_analysis=diff_analysis,
    )

    client = get_llm_client()
    try:
        result = await client.invoke(
            messages=[
                {"role": "system", "content": "你是一位简历优化专家。基于差距分析输出JSON Patch。"},
                {"role": "user", "content": prompt},
            ],
            estimated_tokens=2500,
            user_id=state.get("user_id", "unknown"),
            thread_id=state.get("thread_id", "unknown"),
            node_name="resume_optimize_suggest",
        )
        content = result["content"]
        patches, summary = _parse_result(content)
    except Exception:
        patches = []
        summary = "Unable to generate suggestions at this time."

    return {
        "proposed_patches": patches,
        "summary": summary,
    }


def _serialize_blocks(blocks: list[dict]) -> str:
    lines = []
    for i, block in enumerate(blocks):
        title = block.get("title", f"Block {i}")
        content = block.get("content_md", "")
        lines.append(f"## {title}\n{content}\n")
    return "\n".join(lines)


def _parse_result(content: str) -> tuple[list[dict], str]:
    """Parse LLM response into patches and summary."""
    # Try to extract JSON from the response
    json_match = re.search(r"\{.*\}", content, re.DOTALL)
    if json_match:
        try:
            data = json.loads(json_match.group(0))
            patches = data.get("patches", [])
            summary = data.get("summary", "AI suggested optimizations.")
            return patches, summary
        except json.JSONDecodeError:
            pass

    return [], content[:200] if content else "No suggestions generated."


__all__ = ["suggest_blocks_node"]