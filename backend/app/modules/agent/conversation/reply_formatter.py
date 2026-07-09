"""WeChat reply formatting helpers (REQ-054)."""

from __future__ import annotations

from typing import Any

from app.channels.ilink_utils import split_text
from app.domain.enums import JOB_STATUS_CN

HELP_TEXT = (
    "我是 InterCraft 求职助手，可以通过微信帮你：\n"
    "\n"
    "📝 岗位管理\n"
    "· 「帮我记一个腾讯的后端岗」— 新增岗位\n"
    "· 「字节进一面了，下周一 14:00」— 推进状态\n"
    "· 「把阿里岗位地点改成杭州」— 改地点/JD/备注\n"
    "\n"
    "📊 查询\n"
    "· 「我的求职进展」— 岗位概览\n"
    "· 「上次面试报告」— 报告摘要\n"
    "· 「能力画像」— 六维得分\n"
    "\n"
    "🎙️ 模拟面试\n"
    "· 「开始模拟面试」/「继续面试」/「暂停面试」/「结束面试」\n"
    "\n"
    "删除岗位、填写 Offer 请前往 InterCraft Web 端操作。"
)

LLM_UNAVAILABLE_TEXT = (
    "抱歉，我暂时无法理解你的消息（服务繁忙）。"
    "请稍后重试，回复「帮助」查看我能做什么，或前往 InterCraft Web 端操作。"
)

UNKNOWN_TEXT = (
    "抱歉，我主要专注于求职相关的事务。我可以帮你："
    "📝 新增/管理岗位 | 📊 查询求职进展 | 🎙️ 模拟面试 | 📋 查看报告。"
    "请告诉我你想做什么？"
)

UNKNOWN_STREAK_TEXT = (
    "我暂时无法理解你的需求。你可以："
    "1. 回复「帮助」查看我能做什么 "
    "2. 前往 InterCraft Web 端操作 "
    "3. 换个方式描述你的需求。我会继续尝试理解！"
)

WEB_GUIDE_DELETE = "删除或归档岗位请前往 InterCraft Web 端操作，微信端暂不支持。"
WEB_GUIDE_OFFER = "填写 Offer（薪资、HR 联系方式等）请前往 InterCraft Web 端操作。"

REDIS_UNAVAILABLE_TEXT = "暂时无法确认操作（会话服务繁忙），请稍后重试。"


def truncate(text: str, max_len: int = 500) -> str:
    text = text or ""
    if len(text) <= max_len:
        return text
    return text[: max_len - 1] + "…"


def segment(text: str, max_len: int = 500) -> list[str]:
    """Split long replies for WeChat using iLink split_text."""
    return split_text(text or "", max_len=max_len)


def format_confirmation_card(
    action_label: str,
    summary: str,
    extra_lines: list[str] | None = None,
) -> str:
    """Build the standard confirmation card (FR-008)."""
    lines = [f"即将{action_label}：{summary}"]
    if extra_lines:
        lines.extend(extra_lines)
    lines.append("确认？回复「确认」或「取消」")
    return "\n".join(lines)


def format_create_job_card(params: dict[str, Any]) -> str:
    company = params.get("company", "")
    position = params.get("position", "")
    extras: list[str] = []
    if params.get("base_location"):
        extras.append(f"地点：{params['base_location']}")
    if params.get("jd_url"):
        extras.append(f"JD：{params['jd_url']}")
    if params.get("notes_md"):
        extras.append(f"备注：{truncate(str(params['notes_md']), 80)}")
    return format_confirmation_card(
        "新增岗位",
        f"📮 {company} · {position}",
        extras or None,
    )


def format_update_status_card(params: dict[str, Any]) -> str:
    company = params.get("company", "")
    position = params.get("position", "")
    to = params.get("target_status", "")
    to_cn = JOB_STATUS_CN.get(to, to)
    extras: list[str] = []
    if params.get("interview_time_display"):
        extras.append(f"面试时间：{params['interview_time_display']}")
    if params.get("failure_note"):
        extras.append(f"备注：{params['failure_note']}")
    return format_confirmation_card(
        "更新状态",
        f"{company} · {position} → {to_cn}",
        extras or None,
    )


def format_update_fields_card(params: dict[str, Any]) -> str:
    company = params.get("company", "")
    position = params.get("position", "")
    extras: list[str] = []
    for key, label in (
        ("base_location", "地点"),
        ("jd_url", "JD"),
        ("notes_md", "备注"),
    ):
        if params.get(key) is not None:
            extras.append(f"{label}：{truncate(str(params[key]), 80)}")
    return format_confirmation_card(
        "更新岗位信息",
        f"{company} · {position}",
        extras or None,
    )


def format_low_confidence(alternatives: list[dict[str, Any]] | None) -> str:
    alts = alternatives or []
    if not alts:
        return UNKNOWN_TEXT
    labels = {
        "create_job": "新增岗位",
        "update_status": "更新岗位状态",
        "update_job_fields": "修改岗位信息",
        "query_jobs": "查询求职进展",
        "query_reports": "查看面试报告",
        "query_ability": "查看能力画像",
        "start_interview": "开始模拟面试",
        "continue_interview": "继续面试",
        "help": "查看帮助",
    }
    lines = ["我不太确定你的意思，你是想："]
    for i, alt in enumerate(alts[:3], 1):
        intent = alt.get("intent", "unknown")
        lines.append(f"{i}. {labels.get(intent, intent)}")
    lines.append("请回复序号或更具体地描述一下～")
    return "\n".join(lines)


def format_job_candidates(jobs: list[Any], prompt: str | None = None) -> str:
    header = prompt or "找到多个可能的岗位，请回复序号或公司名："
    lines = [header]
    for i, job in enumerate(jobs[:5], 1):
        company = getattr(job, "company", None) or (job.get("company") if isinstance(job, dict) else "")
        position = getattr(job, "position", None) or (job.get("position") if isinstance(job, dict) else "")
        status = getattr(job, "status", None) or (job.get("status") if isinstance(job, dict) else "")
        status_cn = JOB_STATUS_CN.get(status, status or "")
        lines.append(f"{i}. {company} · {position}（{status_cn}）")
    return "\n".join(lines)


__all__ = [
    "HELP_TEXT",
    "LLM_UNAVAILABLE_TEXT",
    "UNKNOWN_TEXT",
    "UNKNOWN_STREAK_TEXT",
    "WEB_GUIDE_DELETE",
    "WEB_GUIDE_OFFER",
    "REDIS_UNAVAILABLE_TEXT",
    "truncate",
    "segment",
    "format_confirmation_card",
    "format_create_job_card",
    "format_update_status_card",
    "format_update_fields_card",
    "format_low_confidence",
    "format_job_candidates",
]
