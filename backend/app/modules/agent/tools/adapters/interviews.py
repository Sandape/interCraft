"""Interview Tool adapters reusing the existing WeChat interview adapter."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel

from app.modules.agent.conversation.interview.adapter import InterviewAdapter, _extract_round
from app.modules.agent.runtime.context import ToolContext
from app.modules.agent.tools.result import ResourceRef, ToolError, ToolResult, ToolResultStatus
from app.modules.interviews.service import InterviewSessionService


def _convert(result: dict, *, write: bool = False) -> ToolResult:
    if not result.get("ok"):
        if result.get("error_code") == "mutex_blocked":
            return ToolResult(
                status=ToolResultStatus.CLARIFY,
                user_message=result.get("reply_text")
                or "已有进行中的面试，请选择继续或结束。",
                data=result.get("data"),
            )
        return ToolResult(
            status=ToolResultStatus.TERMINAL_ERROR,
            user_message=result.get("reply_text") or "面试操作未完成",
            data=result.get("data"),
            error=ToolError(category="validation", code=result.get("error_code")),
        )
    data = result.get("data") or {}
    session_id = data.get("session_id")
    if write and not session_id:
        return ToolResult(
            status=ToolResultStatus.CLARIFY,
            user_message=result.get("reply_text") or "需要补充面试目标",
            data=data,
        )
    refs = [ResourceRef(type="interview_session", id=session_id, url=f"/interview/{session_id}")] if session_id else []
    now = datetime.now(UTC) if write else None
    return ToolResult.succeeded(
        result.get("reply_text") or "面试操作完成",
        data=data,
        resource_refs=refs,
        committed=write,
        committed_at=now,
    )


async def interview_start(args: BaseModel, context: ToolContext) -> ToolResult:
    if args.resume_id is not None:
        from app.modules.resumes_v2.repository import ResumeV2Repository

        resume = await ResumeV2Repository(context.session).get(
            args.resume_id, user_id=context.user_id
        )
        if resume is None:
            return ToolResult(
                status=ToolResultStatus.TERMINAL_ERROR,
                user_message="未找到可用于本次面试的本人简历。",
                error=ToolError(category="not_found", code="RESUME_NOT_FOUND"),
            )
    result = await InterviewAdapter(context.session, context.user_id).start(
        {
            "job_id": args.job_id,
            "resume_id": args.resume_id,
            "mode": args.mode,
            "confirmed_start": True,
        }
    )
    return _convert(result, write=True)


async def interview_continue(args: BaseModel, context: ToolContext) -> ToolResult:
    adapter = InterviewAdapter(context.session, context.user_id)
    try:
        if args.answer.strip() in {"开始", "开始面试", "准备好了"}:
            interview = await InterviewSessionService(context.session).get(
                args.session_id, context.user_id
            )
            if interview.plan_status == "failed" and not interview.degraded:
                return ToolResult(
                    status=ToolResultStatus.TERMINAL_ERROR,
                    user_message="定制面试计划生成失败。请明确回复“降级继续面试”后再开始。",
                    error=ToolError(
                        category="conflict",
                        code="PLAN_DEGRADE_CONFIRMATION_REQUIRED",
                    ),
                )
            result = await adapter.begin_questions(args.session_id)
            return _convert(result, write=True)
        if args.answer.strip() == "继续面试":
            service = InterviewSessionService(context.session)
            interview = await service.get(args.session_id, context.user_id)
            if interview.status == "pending":
                await service.start(args.session_id, context.user_id)
            result = await adapter.continue_session(args.session_id)
            return _convert(result, write=True)
        service = InterviewSessionService(context.session)
        interview = await service.get(args.session_id, context.user_id)
        if interview.status == "pending":
            await service.start(args.session_id, context.user_id)
        state = await service.resume(args.session_id, context.user_id)
        sequence = max((_extract_round(state) or 1) - 1, 0)
        result = await adapter.submit_answer(args.session_id, args.answer, sequence)
        return _convert(result, write=True)
    except Exception:
        return ToolResult(
            status=ToolResultStatus.TERMINAL_ERROR,
            user_message="面试回答未提交成功。",
            error=ToolError(category="internal", code="INTERVIEW_CONTINUE_FAILED"),
        )


async def interview_pause(args: BaseModel, context: ToolContext) -> ToolResult:
    result = await InterviewAdapter(context.session, context.user_id).pause(args.session_id, None)
    return _convert(result, write=True)


async def interview_end(args: BaseModel, context: ToolContext) -> ToolResult:
    result = await InterviewAdapter(context.session, context.user_id).end(args.session_id, None)
    return _convert(result, write=True)


async def interview_report_list(args: BaseModel, context: ToolContext) -> ToolResult:
    try:
        svc = InterviewSessionService(context.session)
        sessions = await svc.list(context.user_id)
        page = sessions[args.offset : args.offset + args.limit]
        items = []
        for session in page:
            report = await svc.get_report(session.id, context.user_id)
            summary = None
            if isinstance(report, dict):
                summary = {
                    "overall_score": report.get("overall_score"),
                    "dimension_scores": report.get("dimension_scores") or {},
                    "strengths": (report.get("strengths") or [])[:3],
                    "improvements": (report.get("improvements") or [])[:3],
                    "summary": str(report.get("summary_md") or "")[:500],
                }
            items.append(
                {
                    "session_id": str(session.id),
                    "status": session.status,
                    "report_summary": summary,
                }
            )
        has_more = len(sessions) > args.offset + args.limit
        return ToolResult.succeeded(
            "已查询面试报告" if items else "目前还没有面试报告",
            data={
                "items": items,
                "has_more": has_more,
                "next_offset": args.offset + len(items) if has_more else None,
            },
        )
    except Exception:
        return ToolResult(
            status=ToolResultStatus.TERMINAL_ERROR,
            user_message="面试报告暂时无法读取。",
            error=ToolError(category="internal", code="INTERVIEW_REPORT_FAILED"),
        )


async def interview_plan_degrade(args: BaseModel, context: ToolContext) -> ToolResult:
    try:
        result = await InterviewSessionService(context.session).confirm_plan_degrade(
            args.session_id,
            context.user_id,
            confirm=True,
        )
        return ToolResult.succeeded(
            "已按你的明确指令切换为通用题面试，可以回复“开始”。",
            data=result,
            resource_refs=[
                ResourceRef(
                    type="interview_session",
                    id=str(args.session_id),
                    url=f"/interview/{args.session_id}",
                )
            ],
            committed=True,
            committed_at=datetime.now(UTC),
        )
    except Exception:
        return ToolResult(
            status=ToolResultStatus.TERMINAL_ERROR,
            user_message="无法切换该面试的降级模式。",
            error=ToolError(category="not_found", code="INTERVIEW_DEGRADE_FAILED"),
        )


def interview_executors() -> dict[str, Any]:
    return {
        "interview_start": interview_start,
        "interview_continue": interview_continue,
        "interview_pause": interview_pause,
        "interview_end": interview_end,
        "interview_report_list": interview_report_list,
        "interview_plan_degrade": interview_plan_degrade,
    }


__all__ = ["interview_executors"]
