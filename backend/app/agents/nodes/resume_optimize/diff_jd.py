"""M16 node — diff_jd: analyze gap between resume and target JD.

Calls LLM to compare current blocks with target JD, identifying gaps.
"""
from __future__ import annotations

from pathlib import Path

from app.agents.llm_client import get_llm_client
from app.agents.state.resume_optimize_state import ResumeOptimizeState
from app.agents.utils.node_error_handler import node_error_handler
from app.observability import traced_node

_PROMPT_DIR = Path(__file__).resolve().parent.parent.parent / "prompts" / "resume_optimize"


def _load_prompt(name: str) -> str:
    path = _PROMPT_DIR / name
    return path.read_text(encoding="utf-8")


@node_error_handler(fallback_strategy="retry")
@traced_node("resume_optimize.diff_jd")
async def diff_jd_node(state: ResumeOptimizeState) -> dict:
    """Analyze the gap between current resume blocks and target JD."""
    target_jd = state.get("target_jd", "")
    current_blocks = state.get("current_blocks", [])

    template = _load_prompt("diff_jd.md")
    blocks_text = _serialize_blocks(current_blocks)
    prompt = template.format(target_jd=target_jd, blocks=blocks_text)

    client = get_llm_client()
    try:
        result = await client.invoke(
            messages=[
                {"role": "system", "content": "你是一位简历优化专家。分析简历与目标岗位的差距，输出JSON格式的分析结果。"},
                {"role": "user", "content": prompt},
            ],
            estimated_tokens=2000,
            user_id=state.get("user_id", "unknown"),
            thread_id=state.get("thread_id", "unknown"),
            node_name="resume_optimize_diff_jd",
        )
        content = result["content"]
    except Exception:
        content = '{"gap_analysis": "Analysis unavailable.", "suggested_changes": []}'

    return {
        "messages": [{"role": "assistant", "content": content}],
    }


def _serialize_blocks(blocks: list[dict]) -> str:
    """Serialize blocks to text for LLM consumption."""
    lines = []
    for i, block in enumerate(blocks):
        title = block.get("title", f"Block {i}")
        content = block.get("content_md", "")
        lines.append(f"## {title}\n{content}\n")
    return "\n".join(lines)


__all__ = ["diff_jd_node"]