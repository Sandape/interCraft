"""Intake node — extracts position/company/difficulty from user input (T025)."""
from __future__ import annotations

import json
import re
from pathlib import Path

from app.agents.interview.state import InterviewGraphState
from app.agents.llm_client import get_llm_client
from app.agents.interview.requirements_block import build_requirements_block
from app.observability import traced_node
import structlog

logger = structlog.get_logger(__name__)

_PROMPT_DIR = Path(__file__).resolve().parent.parent / "prompts"


def _load_prompt(name: str) -> str:
    path = _PROMPT_DIR / name
    return path.read_text(encoding="utf-8")


async def _load_job_context(job_id: str | None) -> dict:
    """Read base_location + requirements_md from the jobs table for the
    given job_id. Returns an empty dict on any failure so the rest of the
    pipeline can still run.
    """
    if not job_id:
        return {}
    try:
        from uuid import UUID
        from sqlalchemy import text
        from app.core.db import get_session_context
        async with get_session_context() as session:
            await session.execute(
                text("SELECT set_config('app.user_id', :uid, true)"),
                {"uid": "system"},
            )
            # The session_id in this row will be looked up without RLS
            # because we only need the job's text fields, not the user's
            # row. Use a permissive query here — the API layer already
            # validated ownership before we got to the agent.
            row = (
                await session.execute(
                    text(
                        "SELECT base_location, requirements_md FROM jobs "
                        "WHERE id = :jid LIMIT 1"
                    ),
                    {"jid": str(UUID(job_id))},
                )
            ).first()
        if not row:
            return {}
        return {
            "base_location": row[0] or None,
            "requirements_md": row[1] or None,
        }
    except Exception:
        logger.warning("intake.load_job_context_failed", job_id=job_id, exc_info=True)
        return {}


@traced_node("interview.intake_locate")
async def intake_node(state: InterviewGraphState) -> dict:
    """Process user input to extract interview parameters.

    Uses LLM to extract structured position/company/difficulty,
    falling back to regex parsing on failure.
    """
    position = state.get("position", "")
    company = state.get("company", "")
    base_location = state.get("base_location")
    job_id = state.get("job_id")

    # 019 — pull job context (base_location + requirements_md) from DB
    if job_id and (not base_location or state.get("requirements_md") is None):
        ctx = await _load_job_context(job_id)
        if not base_location and ctx.get("base_location"):
            base_location = ctx["base_location"]
        if state.get("requirements_md") is None and ctx.get("requirements_md"):
            # 019 — build the block eagerly so downstream nodes can read it
            block, provided, truncated, original = build_requirements_block(
                ctx["requirements_md"]
            )
            state["requirements_md"] = ctx["requirements_md"]
            state["requirements_provided"] = provided
            state["requirements_truncated"] = truncated
            state["requirements_original_chars"] = original

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
        "base_location": base_location,
        "difficulty": data.get("difficulty", "medium"),
        "current_question": 0,
        # 019 — forward the requirements fields so the next node can read
        # them. (The block text is built inside question_gen.)
        "requirements_md": state.get("requirements_md"),
        "requirements_provided": bool(state.get("requirements_provided", False)),
        "requirements_truncated": bool(state.get("requirements_truncated", False)),
        "requirements_original_chars": int(state.get("requirements_original_chars", 0)),
    }


__all__ = ["intake_node"]
