"""Owner-scoped job Tool adapters using the existing JobService."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from fastapi import HTTPException
from pydantic import BaseModel

from app.modules.agent.runtime.context import ToolContext
from app.modules.agent.tools.result import ResourceRef, ToolError, ToolResult, ToolResultStatus
from app.modules.jobs.service import JobService

_PATCHABLE = frozenset(
    {
        "company", "position", "jd_url", "branch_id", "notes_md",
        "base_location", "requirements_md", "employment_type",
        "salary_range_text", "headcount", "interview_time",
    }
)


def _failure(exc: Exception) -> ToolResult:
    if isinstance(exc, HTTPException):
        category = {404: "not_found", 409: "conflict", 422: "validation"}.get(
            exc.status_code, "validation"
        )
        return ToolResult(
            status=ToolResultStatus.TERMINAL_ERROR,
            user_message="岗位操作未完成，请检查目标岗位和参数。",
            error=ToolError(category=category, code=f"HTTP_{exc.status_code}"),
        )
    return ToolResult(
        status=ToolResultStatus.TERMINAL_ERROR,
        user_message="岗位服务暂时无法完成该操作。",
        error=ToolError(category="internal", code="JOB_TOOL_INTERNAL"),
    )


async def job_create(args: BaseModel, context: ToolContext) -> ToolResult:
    try:
        job = await JobService(context.session).create(
            context.user_id,
            {
                "company": args.company,
                "position": args.title,
                "requirements_md": args.jd_text,
            },
        )
        committed_at = datetime.now(UTC)
        await context.session.flush()
        return ToolResult.succeeded(
            f"已登记目标岗位：{job.company} · {job.position}",
            data={"status": job.status},
            resource_refs=[ResourceRef(type="job", id=str(job.id), url=f"/jobs/{job.id}")],
            committed=True,
            committed_at=committed_at,
        )
    except Exception as exc:
        return _failure(exc)


async def job_list(args: BaseModel, context: ToolContext) -> ToolResult:
    try:
        jobs = await JobService(context.session).list(context.user_id)
        data = [
            {
                "id": str(job.id),
                "company": job.company,
                "title": job.position,
                "status": job.status,
            }
            for job in jobs[: args.limit]
        ]
        return ToolResult.succeeded(
            "已查询目标岗位" if data else "当前还没有目标岗位",
            data={"items": data},
        )
    except Exception as exc:
        return _failure(exc)


async def job_update_fields(args: BaseModel, context: ToolContext) -> ToolResult:
    unknown = set(args.fields) - _PATCHABLE
    if unknown:
        return ToolResult(
            status=ToolResultStatus.TERMINAL_ERROR,
            user_message="包含不允许修改的岗位字段。",
            error=ToolError(category="validation", code="JOB_FIELDS_NOT_ALLOWED"),
        )
    try:
        job = await JobService(context.session).patch(args.job_id, context.user_id, args.fields)
        committed_at = datetime.now(UTC)
        await context.session.flush()
        return ToolResult.succeeded(
            "岗位信息已更新",
            resource_refs=[ResourceRef(type="job", id=str(job.id), url=f"/jobs/{job.id}")],
            committed=True,
            committed_at=committed_at,
        )
    except Exception as exc:
        return _failure(exc)


async def job_update_status(args: BaseModel, context: ToolContext) -> ToolResult:
    try:
        job = await JobService(context.session).update_status(
            args.job_id,
            context.user_id,
            args.status,
            note=args.note,
            interview_time=args.interview_time,
        )
        committed_at = datetime.now(UTC)
        await context.session.flush()
        return ToolResult.succeeded(
            f"岗位状态已更新为 {job.status}",
            resource_refs=[ResourceRef(type="job", id=str(job.id), url=f"/jobs/{job.id}")],
            committed=True,
            committed_at=committed_at,
        )
    except Exception as exc:
        return _failure(exc)


def job_executors() -> dict[str, Any]:
    return {
        "job_create": job_create,
        "job_list": job_list,
        "job_update_fields": job_update_fields,
        "job_update_status": job_update_status,
    }


__all__ = ["job_executors"]
