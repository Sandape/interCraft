"""Owner-scoped read adapters for persisted resume intelligence results."""

from __future__ import annotations

from pydantic import BaseModel

from app.modules.agent.runtime.context import ToolContext
from app.modules.agent.tools.result import ToolResult
from app.modules.resume_intelligence.repository import ResumeIntelligenceRepository


async def _latest_analysis(args: BaseModel, context: ToolContext):
    rows = await ResumeIntelligenceRepository(context.session).list_analyses(
        args.resume_id,
        user_id=context.user_id,
        mode="job_fit" if args.job_id else None,
    )
    return next(
        (row for row in rows if args.job_id is None or row.job_id == args.job_id),
        None,
    )


async def resume_match_analysis_get(
    args: BaseModel, context: ToolContext
) -> ToolResult:
    row = await _latest_analysis(args, context)
    if row is None:
        return ToolResult.succeeded(
            "尚无匹配分析，请先生成或分析岗位简历。", data={"exists": False}
        )
    return ToolResult.succeeded(
        "已查询匹配分析",
        data={
            "exists": True,
            "analysis_id": str(row.id),
            "score": float(row.overall_score)
            if row.overall_score is not None
            else None,
            "dimensions": row.dimensions,
            "summary": row.summary,
        },
    )


async def resume_gap_analysis_get(
    args: BaseModel, context: ToolContext
) -> ToolResult:
    row = await _latest_analysis(args, context)
    if row is None:
        return ToolResult.succeeded("尚无差距分析。", data={"exists": False})
    return ToolResult.succeeded(
        "已查询差距分析",
        data={
            "exists": True,
            "analysis_id": str(row.id),
            "requirements": row.requirements,
            "hard_blockers": row.hard_blockers,
        },
    )


async def resume_suggestions_get(
    args: BaseModel, context: ToolContext
) -> ToolResult:
    row = await _latest_analysis(args, context)
    if row is None:
        return ToolResult.succeeded(
            "尚无优化建议。", data={"exists": False, "items": []}
        )
    suggestions = await ResumeIntelligenceRepository(
        context.session
    ).list_suggestions(
        user_id=context.user_id,
        resume_id=args.resume_id,
        analysis_id=row.id,
    )
    return ToolResult.succeeded(
        "已查询优化建议",
        data={
            "exists": True,
            "analysis_id": str(row.id),
            "items": [
                {
                    "id": str(item.id),
                    "title": item.title,
                    "priority": item.priority,
                    "status": item.status,
                }
                for item in suggestions[:20]
            ],
        },
    )


def resume_intelligence_executors():
    return {
        "resume_match_analysis_get": resume_match_analysis_get,
        "resume_gap_analysis_get": resume_gap_analysis_get,
        "resume_suggestions_get": resume_suggestions_get,
    }


__all__ = [
    "resume_gap_analysis_get",
    "resume_intelligence_executors",
    "resume_match_analysis_get",
    "resume_suggestions_get",
]

