"""Root/derived resume and intelligence Tool adapters."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel

from app.modules.agent.models import AgentCommandDispatchQueue, AgentCommandOutbox
from app.modules.agent.runtime.context import ToolContext
from app.modules.agent.tools.adapters.resume_intelligence import (
    resume_intelligence_executors,
)
from app.modules.agent.tools.result import ResourceRef, ToolError, ToolResult, ToolResultStatus
from app.modules.resume_derive.root_completeness import compute_root_completeness
from app.modules.resume_derive.service import ResumeDeriveService


def _error(exc: Exception) -> ToolResult:
    status = int(getattr(exc, "status", getattr(exc, "status_code", 500)))
    category = {400: "validation", 404: "not_found", 409: "conflict", 503: "dependency"}.get(status, "internal")
    retryable = status >= 500
    return ToolResult(
        status=ToolResultStatus.RETRYABLE_ERROR if retryable else ToolResultStatus.TERMINAL_ERROR,
        user_message="简历操作未完成，请检查根简历、岗位和任务状态。",
        error=ToolError(category=category, code=str(getattr(exc, "code", "RESUME_TOOL_ERROR")), retryable=retryable),
    )


async def resume_root_get(args: BaseModel, context: ToolContext) -> ToolResult:
    root = await ResumeDeriveService(context.session).get_root(context.user_id)
    if root is None:
        return ToolResult.succeeded("当前还没有根简历", data={"exists": False})
    return ToolResult.succeeded(
        f"根简历：{root.name}",
        data={"exists": True, "version": root.version, "completeness": compute_root_completeness(root.data or {})},
        resource_refs=[ResourceRef(type="resume", id=str(root.id), url=f"/resume/{root.id}")],
    )


async def resume_root_create(args: BaseModel, context: ToolContext) -> ToolResult:
    try:
        root = await ResumeDeriveService(context.session).create_root(
            user_id=context.user_id,
            name=args.title,
            slug=f"root-{context.user_id.hex[:12]}",
        )
        committed_at = datetime.now(UTC)
        await context.session.flush()
        return ToolResult.succeeded(
            "根简历已创建，可继续补充经历和技能。",
            data={"completeness": compute_root_completeness(root.data or {})},
            resource_refs=[ResourceRef(type="resume", id=str(root.id), url=f"/resume/{root.id}")],
            committed=True,
            committed_at=committed_at,
        )
    except Exception as exc:
        return _error(exc)


async def resume_root_completeness(args: BaseModel, context: ToolContext) -> ToolResult:
    root = await ResumeDeriveService(context.session).get_root(context.user_id)
    if root is None:
        return ToolResult.succeeded("当前还没有根简历", data={"exists": False})
    return ToolResult.succeeded(
        "已检查根简历完整度",
        data={"exists": True, **compute_root_completeness(root.data or {})},
    )


async def resume_derive_start(args: BaseModel, context: ToolContext) -> ToolResult:
    try:
        run = await ResumeDeriveService(context.session).start_run(
            user_id=context.user_id,
            job_id=args.job_id,
            root_resume_id=args.root_resume_id,
            target_page_count=2,
            idempotency_key=context.idempotency_key,
            enqueue_immediately=False,
        )
        command = AgentCommandOutbox(
            user_id=context.user_id,
            command_type="resume_derive.execute",
            aggregate_id=run.id,
            idempotency_key=context.idempotency_key,
            payload_json={"run_id": str(run.id), "user_id": str(context.user_id)},
        )
        context.session.add(command)
        await context.session.flush()
        context.session.add(
            AgentCommandDispatchQueue(
                outbox_id=command.id,
                user_id=context.user_id,
            )
        )
        await context.session.flush()
        committed_at = datetime.now(UTC)
        return ToolResult.succeeded(
            "派生简历任务已启动",
            data={"status": run.status},
            resource_refs=[ResourceRef(type="resume_derive_run", id=str(run.id), url=None)],
            committed=True,
            committed_at=committed_at,
        )
    except Exception as exc:
        return _error(exc)


async def resume_derive_status(args: BaseModel, context: ToolContext) -> ToolResult:
    try:
        run = await ResumeDeriveService(context.session).get_run(args.run_id, user_id=context.user_id)
        return ToolResult.succeeded(
            f"派生任务状态：{run.status}",
            data={"status": run.status, "resume_id": str(run.derived_resume_id) if run.derived_resume_id else None, "error_code": run.error_code},
        )
    except Exception as exc:
        return _error(exc)


def resume_executors() -> dict[str, Any]:
    return {
        "resume_root_get": resume_root_get,
        "resume_root_create": resume_root_create,
        "resume_root_completeness": resume_root_completeness,
        "resume_derive_start": resume_derive_start,
        "resume_derive_status": resume_derive_status,
        **resume_intelligence_executors(),
    }


__all__ = ["resume_executors"]
