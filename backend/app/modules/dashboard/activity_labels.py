"""ActivityType → Chinese title/detail (REQ-057)."""
from __future__ import annotations

from typing import Any

from app.domain.enums import ActivityType

_STATUS_CN = {
    "applied": "已投递",
    "test": "笔试/测评",
    "interview_1": "一面",
    "interview_2": "二面",
    "interview_3": "三面",
    "failed": "未通过",
    "passed": "已通过",
}


def _company_position(payload: dict[str, Any]) -> str:
    parts = [payload.get("company"), payload.get("position")]
    return " · ".join(str(p) for p in parts if p)


def render_activity(
    activity_type: str,
    payload: dict[str, Any] | None,
) -> tuple[str, str, str | None]:
    """Return (title_zh, detail_zh, href)."""
    payload = payload or {}
    summary = payload.get("summary")
    if isinstance(summary, str) and summary.strip() and not summary.startswith(
        ("job_", "task_", "interview_", "branch_", "error_")
    ):
        # Prefer explicit Chinese summary when writers provide one.
        detail = _company_position(payload) or str(payload.get("title") or payload.get("detail") or "")
        href = _href_for(activity_type, payload)
        return summary.strip(), detail, href

    try:
        at = ActivityType(activity_type)
    except ValueError:
        return "系统更新", "", None

    if at == ActivityType.JOB_CREATED:
        return "新增投递", _company_position(payload), _job_href(payload)
    if at == ActivityType.JOB_STATUS_CHANGED:
        to_st = payload.get("to_status") or payload.get("to")
        to_cn = _STATUS_CN.get(str(to_st), str(to_st) if to_st else "")
        detail = _company_position(payload)
        if to_cn:
            detail = f"{detail} · {to_cn}" if detail else to_cn
        return "岗位状态更新", detail, _job_href(payload)
    if at == ActivityType.TASK_CREATED:
        return "新建任务", str(payload.get("title") or ""), None
    if at == ActivityType.TASK_COMPLETED:
        return "完成任务", str(payload.get("title") or ""), None
    if at == ActivityType.INTERVIEW_STARTED:
        return "开始模拟面试", _company_position(payload), _session_href(payload)
    if at == ActivityType.INTERVIEW_COMPLETED:
        detail = _company_position(payload)
        score = payload.get("overall_score")
        if isinstance(score, (int, float)):
            detail = f"{detail} · {score:.1f} 分" if detail else f"{score:.1f} 分"
        # Writers sometimes use title/content instead of company/position.
        if not detail:
            detail = str(payload.get("title") or payload.get("content") or "")
        sid = payload.get("session_id")
        href = f"/interview/{sid}/report" if sid else "/interview"
        return "完成模拟面试", detail, href
    if at == ActivityType.BRANCH_CREATED:
        name = payload.get("branch_name") or payload.get("name") or ""
        return "简历更新", str(name), None
    if at == ActivityType.ERROR_LOGGED:
        return "错题已记录", str(payload.get("title") or payload.get("detail") or ""), "/error-book"
    if at == ActivityType.MANUAL:
        return "手动记录", str(payload.get("title") or payload.get("detail") or ""), None
    return "系统更新", "", None


def _job_href(payload: dict[str, Any]) -> str | None:
    jid = payload.get("job_id")
    if jid:
        return f"/jobs/{jid}"
    return "/jobs"


def _session_href(payload: dict[str, Any]) -> str | None:
    sid = payload.get("session_id")
    if sid:
        return f"/interview/{sid}"
    return "/interview"


def _href_for(activity_type: str, payload: dict[str, Any]) -> str | None:
    if "job" in activity_type:
        return _job_href(payload)
    if "interview" in activity_type or "session" in activity_type:
        return _session_href(payload)
    if "error" in activity_type:
        return "/error-book"
    return None


def parse_payload_json(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str) and raw.strip():
        import json

        try:
            data = json.loads(raw)
            return data if isinstance(data, dict) else {}
        except json.JSONDecodeError:
            return {}
    return {}


__all__ = ["parse_payload_json", "render_activity"]
