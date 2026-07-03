"""Tool: query_resume_blocks — list blocks for a resume branch (shared by M16).

Wraps ResumeBlockRepository.list_for_branch.
"""
from __future__ import annotations

from uuid import UUID

import structlog
from langchain_core.tools import tool

from app.core.db import get_session_factory
from app.modules.resumes.block_repository import ResumeBlockRepository

logger = structlog.get_logger("agents.tools.query_resume_blocks")


@tool
async def query_resume_blocks(
    branch_id: str,
    *,
    user_id: str | None = None,
    block_type: str | None = None,
) -> list[dict]:
    """Fetch all non-deleted blocks for the given branch.

    Returns a list of block dicts (or empty list if branch not found).
    """
    factory = get_session_factory()
    async with factory() as session:
        if user_id:
            from app.domain.rls import set_user_context

            await set_user_context(session, user_id)

        repo = ResumeBlockRepository(session)
        blocks = await repo.list_for_branch(UUID(branch_id), block_type=block_type)

        result = []
        for b in blocks:
            result.append({
                "id": str(b.id),
                "branch_id": str(b.branch_id),
                "type": b.type,
                "title": b.title,
                "content_md": b.content_md,
                "meta": b.meta,
                "order_index": b.order_index,
            })
        return result


__all__ = ["query_resume_blocks"]
