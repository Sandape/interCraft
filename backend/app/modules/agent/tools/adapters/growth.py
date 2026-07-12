"""Read-only error book, ability profile and job-progress Tools."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from app.modules.abilities.repository import AbilityDimensionRepository
from app.modules.abilities.service import AbilityService
from app.modules.agent.runtime.context import ToolContext
from app.modules.agent.tools.result import ToolError, ToolResult, ToolResultStatus
from app.modules.dashboard.service import DashboardService
from app.modules.errors.repository import ErrorQuestionRepository
from app.modules.errors.service import ErrorService


def _read_error() -> ToolResult:
    return ToolResult(
        status=ToolResultStatus.TERMINAL_ERROR,
        user_message="暂时无法读取该求职数据。",
        error=ToolError(category="internal", code="GROWTH_READ_FAILED"),
    )


async def error_book_summary(args: BaseModel, context: ToolContext) -> ToolResult:
    try:
        rows = await ErrorService(ErrorQuestionRepository(context.session)).list(
            context.user_id, limit=args.limit + args.offset + 1
        )
        page = rows[args.offset : args.offset + args.limit]
        items = [
            {
                "id": str(row.id),
                "dimension": row.dimension,
                "status": row.status,
                "frequency": row.frequency,
            }
            for row in page
        ]
        has_more = len(rows) > args.offset + args.limit
        return ToolResult.succeeded(
            "已查询错题本" if items else "错题本目前为空",
            data={
                "count": len(items),
                "items": items,
                "has_more": has_more,
                "next_offset": args.offset + len(items) if has_more else None,
            },
        )
    except Exception:
        return _read_error()


async def ability_profile_get(args: BaseModel, context: ToolContext) -> ToolResult:
    try:
        rows = await AbilityService(AbilityDimensionRepository(context.session)).read(
            context.user_id, is_active=True
        )
        return ToolResult.succeeded(
            "已查询能力画像",
            data={
                "items": [
                    {
                        "key": row.dimension_key,
                        "actual_score": float(row.actual_score) if row.actual_score is not None else None,
                        "ideal_score": float(row.ideal_score) if row.ideal_score is not None else None,
                    }
                    for row in rows
                ]
            },
        )
    except Exception:
        return _read_error()


async def job_progress_get(args: BaseModel, context: ToolContext) -> ToolResult:
    try:
        summary = await DashboardService(context.session).get_summary(
            context.user_id, use_cache=False
        )
        payload = summary.model_dump(mode="json")
        l0 = payload.get("l0") or {}
        l1 = payload.get("l1") or {}
        funnel = l1.get("job_funnel") or []
        return ToolResult.succeeded(
            "已查询求职进度",
            data={
                "job_counts": {
                    item["key"]: item["count"]
                    for item in funnel
                    if isinstance(item, dict) and "key" in item and "count" in item
                },
                "resume_counts": l1.get("resume_counts") or {},
                "next_interview": l0.get("next_interview"),
            },
        )
    except Exception:
        return _read_error()


def growth_executors() -> dict[str, Any]:
    return {
        "error_book_summary": error_book_summary,
        "ability_profile_get": ability_profile_get,
        "job_progress_get": job_progress_get,
    }


__all__ = ["growth_executors"]
