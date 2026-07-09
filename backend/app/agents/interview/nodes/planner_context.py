"""Planner context node — reads resume and job data for plan generation (T012).

Loads resume_branches/resume_blocks and job/JD information from the DB,
then bundles them into ``planner_context`` on the graph state.

REQ-028 US1: also retrieves the user's active semantic memories (cross-session
long-term memory) and bundles them into ``planner_context["memories"]`` so
the planner_generate node can inject them into the LLM prompt. Memory
retrieval degrades gracefully — on any failure, ``memories=[]`` and the
planner proceeds with no long-term context (FR-013).

Gracefully handles missing data — never raises, always returns a dict with
``missing_fields`` populated when data is absent.
"""
from __future__ import annotations

from typing import Any
from uuid import UUID

import structlog
from sqlalchemy import text

from app.agents.interview.state import InterviewGraphState
from app.core.db import get_session_context

logger = structlog.get_logger(__name__)


def _resume_v2_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, list):
        return " ".join(_resume_v2_text(item) for item in value).strip()
    if isinstance(value, dict):
        parts: list[str] = []
        for key, item in value.items():
            if key in {"id", "hidden", "icon", "iconColor", "website"}:
                continue
            text_value = _resume_v2_text(item)
            if text_value:
                parts.append(text_value)
        return " ".join(parts).strip()
    return str(value).strip()


def _resume_v2_context(row: Any) -> dict:
    data = row[3] if isinstance(row[3], dict) else {}
    basics = data.get("basics") if isinstance(data.get("basics"), dict) else {}
    sections = data.get("sections") if isinstance(data.get("sections"), dict) else {}
    summary = data.get("summary") if isinstance(data.get("summary"), dict) else {}

    blocks: list[dict[str, Any]] = []
    skills: list[str] = []
    experiences: list[dict[str, Any]] = []
    projects: list[dict[str, Any]] = []
    education: list[dict[str, Any]] = []

    summary_text = _resume_v2_text(summary.get("content"))
    if summary_text:
        blocks.append(
            {
                "type": "summary",
                "title": summary.get("title") or "Summary",
                "content_md": summary_text,
                "meta": {},
                "order_index": len(blocks),
            }
        )

    for section_type, section in sections.items():
        if not isinstance(section, dict):
            continue
        items = section.get("items") if isinstance(section.get("items"), list) else []
        for item in items:
            if not isinstance(item, dict) or item.get("hidden") is True:
                continue
            title = (
                item.get("name")
                or item.get("company")
                or item.get("school")
                or item.get("title")
                or section.get("title")
                or section_type
            )
            content = _resume_v2_text(item)
            block = {
                "type": section_type,
                "title": str(title or ""),
                "content_md": content,
                "meta": item,
                "order_index": len(blocks),
            }
            blocks.append(block)
            if section_type == "skills":
                skills.append(content)
            elif section_type == "experience":
                experiences.append(block)
            elif section_type == "projects":
                projects.append(block)
            elif section_type == "education":
                education.append(block)

    return {
        "has_resume": True,
        "branch_id": str(row[0]),
        "resume_source": "resumes_v2",
        "name": row[1] or basics.get("name") or "",
        "slug": row[2] or "",
        "headline": basics.get("headline") or "",
        "location": basics.get("location") or "",
        "version": row[4],
        "blocks": blocks,
        "skills": skills,
        "experiences": experiences,
        "projects": projects,
        "education": education,
        "block_count": len(blocks),
    }


async def _load_user_memories(user_id: str) -> list[dict[str, Any]]:
    """Retrieve the user's active semantic memories for the interview planner.

    Returns a list of memory dicts (fact_key, fact_value, confidence, source).
    On any failure, returns ``[]`` — the planner proceeds with no memories
    (FR-013 graceful degrade).
    """
    if not user_id:
        return []
    try:
        # Local import to avoid importing the memory module at graph-build time
        # (keeps the import graph clean for tests that patch the LLM client).
        from app.modules.agent_memory.retriever import retrieve_active_memories

        async with get_session_context() as session:
            await session.execute(
                text("SELECT set_config('app.user_id', :uid, true)"),
                {"uid": user_id},
            )
            result = await retrieve_active_memories(
                user_id=UUID(user_id),
                graph="interview",
                node="planner_context",
                session=session,
                token_budget=500,
            )
        return [m.model_dump() for m in result.memories]
    except Exception:
        logger.warning("planner.load_memories_failed", exc_info=True)
        return []


async def _load_resume_data(branch_id: str | None, user_id: str) -> dict:
    """Load resume branch and blocks from DB for the given branch_id.

    Returns a structured resume context dict, or a fallback dict with
    ``has_resume=False`` on any failure / missing branch.
    """
    if not branch_id or not user_id:
        logger.info("planner.skip_resume_load", reason="missing_branch_id_or_user_id")
        return {"has_resume": False, "missing_fields": ["resume_data"]}

    try:
        async with get_session_context() as session:
            await session.execute(
                text("SELECT set_config('app.user_id', :uid, true)"),
                {"uid": user_id},
            )

            # Load the main branch row
            branch_row = (
                await session.execute(
                    text(
                        "SELECT id, name, company, position, status, match_score "
                        "FROM resume_branches "
                        "WHERE id = :bid AND deleted_at IS NULL "
                        "LIMIT 1"
                    ),
                    {"bid": str(UUID(branch_id))},
                )
            ).first()

            if not branch_row:
                resume_v2_row = (
                    await session.execute(
                        text(
                            "SELECT id, name, slug, data, version "
                            "FROM resumes_v2 "
                            "WHERE id = :rid AND user_id = :uid "
                            "LIMIT 1"
                        ),
                        {"rid": str(UUID(branch_id)), "uid": user_id},
                    )
                ).first()
                if resume_v2_row:
                    logger.info("planner.resume_v2_loaded", resume_id=branch_id)
                    return _resume_v2_context(resume_v2_row)

                logger.info("planner.resume_branch_not_found", branch_id=branch_id)
                return {"has_resume": False, "missing_fields": ["resume_branch"]}

            # Load all non-deleted blocks for this branch
            block_rows = (
                await session.execute(
                    text(
                        "SELECT type, title, content_md, meta, order_index "
                        "FROM resume_blocks "
                        "WHERE branch_id = :bid AND deleted_at IS NULL "
                        "ORDER BY order_index"
                    ),
                    {"bid": str(UUID(branch_id))},
                )
            ).all()

        blocks = [
            {
                "type": r[0],
                "title": r[1] or "",
                "content_md": r[2] or "",
                "meta": r[3] or {},
                "order_index": r[4],
            }
            for r in block_rows
        ]

        # Categorise blocks for convenient access
        skills: list[str] = []
        experiences: list[dict] = []
        projects: list[dict] = []
        education: list[dict] = []
        for b in blocks:
            if b["type"] == "skill":
                skills.append(b["content_md"])
            elif b["type"] == "experience":
                experiences.append(b)
            elif b["type"] == "project":
                projects.append(b)
            elif b["type"] == "education":
                education.append(b)

        return {
            "has_resume": True,
            "branch_id": str(branch_row[0]),
            "name": branch_row[1] or "",
            "branch_company": branch_row[2] or "",
            "branch_position": branch_row[3] or "",
            "status": branch_row[4] or "",
            "match_score": float(branch_row[5]) if branch_row[5] is not None else None,
            "blocks": blocks,
            "skills": skills,
            "experiences": experiences,
            "projects": projects,
            "education": education,
            "block_count": len(blocks),
        }

    except Exception:
        logger.warning(
            "planner.load_resume_failed",
            branch_id=branch_id,
            exc_info=True,
        )
        return {"has_resume": False, "missing_fields": ["resume_data"]}


async def _load_job_data(job_id: str | None, user_id: str) -> dict:
    """Load job / JD information from the DB.

    Returns a structured job context dict, or a fallback dict with
    ``has_job=False`` on any failure.
    """
    if not job_id or not user_id:
        logger.info("planner.skip_job_load", reason="missing_job_id_or_user_id")
        return {"has_job": False, "missing_fields": ["job_data"]}

    try:
        async with get_session_context() as session:
            await session.execute(
                text("SELECT set_config('app.user_id', :uid, true)"),
                {"uid": user_id},
            )

            row = (
                await session.execute(
                    text(
                        "SELECT id, company, position, requirements_md, "
                        "base_location, employment_type, salary_range_text "
                        "FROM jobs "
                        "WHERE id = :jid AND deleted_at IS NULL "
                        "LIMIT 1"
                    ),
                    {"jid": str(UUID(job_id))},
                )
            ).first()

        if not row:
            logger.info("planner.job_not_found", job_id=job_id)
            return {"has_job": False, "missing_fields": ["job_record"]}

        return {
            "has_job": True,
            "job_id": str(row[0]),
            "company": row[1] or "",
            "position": row[2] or "",
            "requirements_md": row[3] or "",
            "base_location": row[4] or "",
            "employment_type": row[5] or "",
            "salary_range_text": row[6] or "",
        }

    except Exception:
        logger.warning(
            "planner.load_job_failed",
            job_id=job_id,
            exc_info=True,
        )
        return {"has_job": False, "missing_fields": ["job_data"]}


async def planner_context_node(state: InterviewGraphState) -> dict:
    """Load resume and JD context from DB for interview plan generation.

    Reads ``resume_branches`` / ``resume_blocks`` for the session's
    ``branch_id`` and job info for the session's ``job_id``. Handles
    every failure gracefully — missing or partial data is flagged in
    ``missing_fields`` instead of raising an error.

    Returns
    -------
    dict
        Graph state update containing ``planner_context`` with keys:
        ``resume``, ``job``, and optionally ``missing_fields``.
    """
    branch_id = state.get("branch_id")
    job_id = state.get("job_id")
    user_id = state.get("user_id")

    # Load data (sequential DB calls, each is isolated and safe)
    resume_data = await _load_resume_data(branch_id, user_id)
    job_data = await _load_job_data(job_id, user_id)
    # REQ-028 US1 — Long-term semantic memories (cross-session recall).
    # Failures degrade gracefully (empty list) — the planner still runs.
    memories = await _load_user_memories(user_id)

    # Aggregate missing-field markers
    missing_fields: list[str] = []
    if not resume_data.get("has_resume"):
        mf = resume_data.get("missing_fields")
        if mf:
            missing_fields.extend(mf)
        else:
            missing_fields.append("resume_data")
    if not job_data.get("has_job"):
        mf = job_data.get("missing_fields")
        if mf:
            missing_fields.extend(mf)
        else:
            missing_fields.append("job_data")

    planner_context: dict[str, Any] = {
        "resume": resume_data,
        "job": job_data,
    }
    if memories:
        planner_context["memories"] = memories
    if missing_fields:
        planner_context["missing_fields"] = missing_fields
        logger.info(
            "planner.context_incomplete",
            missing_fields=missing_fields,
            branch_id=branch_id,
            job_id=job_id,
            memories_count=len(memories),
        )
    else:
        logger.info(
            "planner.context_loaded",
            branch_id=branch_id,
            job_id=job_id,
            skills_count=len(resume_data.get("skills", [])),
            experiences_count=len(resume_data.get("experiences", [])),
            memories_count=len(memories),
        )

    return {"planner_context": planner_context}


__all__ = ["planner_context_node"]
