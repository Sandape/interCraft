"""REQ-060 InterCraft job-search Tool catalog."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.modules.agent.tools.registry import (
    Atomicity,
    ConfirmationPolicy,
    SideEffect,
    ToolDefinition,
    ToolExecutor,
    ToolRegistry,
)
from app.modules.agent.tools.result import ToolResult


class StrictInput(BaseModel):
    model_config = ConfigDict(extra="forbid")


class EmptyInput(StrictInput):
    pass


class JobCreateInput(StrictInput):
    company: str = Field(min_length=1, max_length=200)
    title: str = Field(min_length=1, max_length=200)
    jd_text: str | None = Field(default=None, max_length=30000)


class JobListInput(StrictInput):
    limit: int = Field(default=10, ge=1, le=50)


class JobUpdateFieldsInput(StrictInput):
    job_id: UUID
    fields: dict[str, Any]


class JobUpdateStatusInput(StrictInput):
    job_id: UUID
    status: str
    note: str = Field(default="", max_length=500)
    interview_time: datetime | None = None


class ResumeRootCreateInput(StrictInput):
    title: str = Field(default="根简历", min_length=1, max_length=200)


class ResumeDeriveStartInput(StrictInput):
    job_id: UUID
    root_resume_id: UUID | None = None


class ResumeRunInput(StrictInput):
    run_id: UUID


class ResumeAnalysisInput(StrictInput):
    resume_id: UUID
    job_id: UUID | None = None


class InterviewStartInput(StrictInput):
    job_id: UUID
    resume_id: UUID | None = None
    mode: str = "full"


class InterviewContinueInput(StrictInput):
    session_id: UUID
    answer: str = Field(min_length=1, max_length=10000)


class InterviewControlInput(StrictInput):
    session_id: UUID


class LimitInput(StrictInput):
    limit: int = Field(default=10, ge=1, le=50)
    offset: int = Field(default=0, ge=0, le=1000)


_CATALOG: tuple[tuple[str, type[BaseModel], SideEffect, ConfirmationPolicy, Atomicity], ...] = (
    (
        "job_create",
        JobCreateInput,
        SideEffect.WRITE,
        ConfirmationPolicy.ALWAYS,
        Atomicity.LOCAL_TRANSACTION,
    ),
    (
        "job_list",
        JobListInput,
        SideEffect.READ,
        ConfirmationPolicy.NEVER,
        Atomicity.LOCAL_TRANSACTION,
    ),
    (
        "job_update_fields",
        JobUpdateFieldsInput,
        SideEffect.WRITE,
        ConfirmationPolicy.ALWAYS,
        Atomicity.LOCAL_TRANSACTION,
    ),
    (
        "job_update_status",
        JobUpdateStatusInput,
        SideEffect.WRITE,
        ConfirmationPolicy.ALWAYS,
        Atomicity.LOCAL_TRANSACTION,
    ),
    (
        "resume_root_get",
        EmptyInput,
        SideEffect.READ,
        ConfirmationPolicy.NEVER,
        Atomicity.LOCAL_TRANSACTION,
    ),
    (
        "resume_root_create",
        ResumeRootCreateInput,
        SideEffect.WRITE,
        ConfirmationPolicy.ALWAYS,
        Atomicity.LOCAL_TRANSACTION,
    ),
    (
        "resume_root_completeness",
        EmptyInput,
        SideEffect.READ,
        ConfirmationPolicy.NEVER,
        Atomicity.LOCAL_TRANSACTION,
    ),
    (
        "resume_derive_start",
        ResumeDeriveStartInput,
        SideEffect.WRITE,
        ConfirmationPolicy.ALWAYS,
        Atomicity.COMMAND_OUTBOX,
    ),
    (
        "resume_derive_status",
        ResumeRunInput,
        SideEffect.READ,
        ConfirmationPolicy.NEVER,
        Atomicity.LOCAL_TRANSACTION,
    ),
    (
        "resume_match_analysis_get",
        ResumeAnalysisInput,
        SideEffect.READ,
        ConfirmationPolicy.NEVER,
        Atomicity.LOCAL_TRANSACTION,
    ),
    (
        "resume_gap_analysis_get",
        ResumeAnalysisInput,
        SideEffect.READ,
        ConfirmationPolicy.NEVER,
        Atomicity.LOCAL_TRANSACTION,
    ),
    (
        "resume_suggestions_get",
        ResumeAnalysisInput,
        SideEffect.READ,
        ConfirmationPolicy.NEVER,
        Atomicity.LOCAL_TRANSACTION,
    ),
    (
        "interview_start",
        InterviewStartInput,
        SideEffect.WRITE,
        ConfirmationPolicy.ALWAYS,
        Atomicity.LOCAL_TRANSACTION,
    ),
    (
        "interview_continue",
        InterviewContinueInput,
        SideEffect.WRITE,
        ConfirmationPolicy.EXPLICIT_COMMAND,
        Atomicity.LOCAL_TRANSACTION,
    ),
    (
        "interview_pause",
        InterviewControlInput,
        SideEffect.WRITE,
        ConfirmationPolicy.EXPLICIT_COMMAND,
        Atomicity.LOCAL_TRANSACTION,
    ),
    (
        "interview_end",
        InterviewControlInput,
        SideEffect.WRITE,
        ConfirmationPolicy.EXPLICIT_COMMAND,
        Atomicity.LOCAL_TRANSACTION,
    ),
    (
        "interview_report_list",
        LimitInput,
        SideEffect.READ,
        ConfirmationPolicy.NEVER,
        Atomicity.LOCAL_TRANSACTION,
    ),
    (
        "interview_plan_degrade",
        InterviewControlInput,
        SideEffect.WRITE,
        ConfirmationPolicy.EXPLICIT_COMMAND,
        Atomicity.LOCAL_TRANSACTION,
    ),
    (
        "error_book_summary",
        LimitInput,
        SideEffect.READ,
        ConfirmationPolicy.NEVER,
        Atomicity.LOCAL_TRANSACTION,
    ),
    (
        "ability_profile_get",
        EmptyInput,
        SideEffect.READ,
        ConfirmationPolicy.NEVER,
        Atomicity.LOCAL_TRANSACTION,
    ),
    (
        "job_progress_get",
        EmptyInput,
        SideEffect.READ,
        ConfirmationPolicy.NEVER,
        Atomicity.LOCAL_TRANSACTION,
    ),
)


_DESCRIPTIONS = {
    "job_create": "登记一个新的目标岗位。缺少公司或岗位名称时先向用户追问；参数完整时调用以创建待确认提案。",
    "job_list": "查询当前用户的目标岗位列表及状态，用于消歧或查看求职进度。",
    "job_update_fields": "更新本人目标岗位的白名单字段；不要传 user_id 等身份字段；调用以创建待确认提案。",
    "job_update_status": "推进本人岗位状态；进入面试轮次时必须同时提供未来的 interview_time；调用以创建待确认提案。",
    "resume_root_get": "查询当前用户唯一的根简历及完整度，不返回完整简历正文。",
    "resume_root_create": "为当前用户创建唯一根简历；已存在时不要重复创建；调用以创建待确认提案。",
    "resume_root_completeness": "检查根简历完整度与缺失项。",
    "resume_derive_start": "基于本人根简历和目标岗位创建岗位定制派生简历的待确认提案；调用本身不执行派生。",
    "resume_derive_status": "查询本人派生简历任务的真实状态和结果资源。",
    "resume_match_analysis_get": "查询本人简历对目标岗位的匹配分析与分数。",
    "resume_gap_analysis_get": "查询本人简历与目标岗位要求之间的差距和硬性阻塞项。",
    "resume_suggestions_get": "查询本人简历的可执行优化建议摘要。",
    "interview_start": "为本人目标岗位创建模拟面试启动提案，可指定本人简历；调用后由运行时确认。",
    "interview_continue": "提交当前模拟面试的一次明确回答；仅在用户确实回答当前问题时调用。",
    "interview_pause": "暂停指定的本人模拟面试；仅响应明确暂停命令。",
    "interview_end": "结束指定的本人模拟面试；仅响应明确结束命令。",
    "interview_report_list": "查询本人最近的模拟面试状态与报告摘要。",
    "interview_plan_degrade": "当定制面试计划失败后，仅根据用户明确的“降级继续”指令切换为通用题模式。",
    "error_book_summary": "查询本人错题本摘要，不返回完整答案或敏感正文。",
    "ability_profile_get": "查询本人能力画像的维度分数摘要。",
    "job_progress_get": "查询本人岗位漏斗、简历数量和下一场面试摘要。",
}


def catalog_names() -> tuple[str, ...]:
    return tuple(item[0] for item in _CATALOG)


def build_intercraft_registry(executors: Mapping[str, ToolExecutor]) -> ToolRegistry:
    missing = set(catalog_names()) - set(executors)
    if missing:
        raise ValueError(f"missing Tool executors: {sorted(missing)}")
    registry = ToolRegistry(version="intercraft-agent-tools.v1")
    for name, input_model, side_effect, confirmation, atomicity in _CATALOG:
        registry.register(
            ToolDefinition(
                name=name,
                version="1.0.0",
                description=_DESCRIPTIONS[name],
                input_model=input_model,
                output_model=ToolResult,
                side_effect=side_effect,
                confirmation=confirmation,
                permission=f"agent.{name}",
                timeout_seconds=30,
                max_attempts=3 if side_effect in {SideEffect.READ, SideEffect.NONE} else 1,
                retryable_errors=frozenset({"rate_limit", "timeout", "dependency"}),
                atomicity=atomicity,
                executor=executors[name],
                reconciliation="domain_status_lookup"
                if atomicity != Atomicity.LOCAL_TRANSACTION
                else None,
            )
        )
    return registry


__all__ = ["build_intercraft_registry", "catalog_names"]
