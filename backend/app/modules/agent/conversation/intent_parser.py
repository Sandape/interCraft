"""LLM intent parser for WeChat conversational agent (REQ-054)."""

from __future__ import annotations

import json
import logging
import re
import time
from typing import Any
from uuid import UUID

from app.modules.agent.conversation import metrics as m
from app.modules.agent.conversation.confirmations import is_cancel, is_confirm
from app.modules.agent.conversation.reply_formatter import (
    HELP_TEXT,
    LLM_UNAVAILABLE_TEXT,
    WEB_GUIDE_DELETE,
    WEB_GUIDE_OFFER,
)

logger = logging.getLogger(__name__)

CONFIDENCE_THRESHOLD = 0.6

VALID_INTENTS = frozenset(
    {
        "create_job",
        "update_status",
        "update_job_fields",
        "query_jobs",
        "query_reports",
        "query_ability",
        "start_interview",
        "continue_interview",
        "pause_interview",
        "end_interview",
        "help",
        "unknown",
        "confirm",
        "cancel",
    }
)

# Out-of-scope intents mapped to rejection replies (not executed).
REJECTED_INTENT_HINTS = frozenset(
    {
        "delete_job",
        "archive_job",
        "update_offer",
        "set_salary",
        "set_hr_contact",
        "delete",
        "archive",
        "offer",
    }
)

_INTENT_SYSTEM_PROMPT = """你是 InterCraft 求职助手的意图解析器。根据用户微信消息，输出严格 JSON：
{
  "intent": "<枚举>",
  "entities": {},
  "confidence": 0.0到1.0,
  "alternatives": [{"intent": "...", "confidence": 0.0}]
}

intent 枚举（只能用这些，不要 invent）：
create_job, update_status, update_job_fields, query_jobs, query_reports, query_ability,
start_interview, continue_interview, pause_interview, end_interview, help, unknown,
delete_job, archive_job, update_offer, set_salary, set_hr_contact

岗位状态（update_status.target_status）只能是：
applied, test, interview_1, interview_2, interview_3, failed, passed
中文口语映射：已投递=applied，笔试/笔试中=test，一面=interview_1，二面=interview_2，
三面=interview_3，挂了/没过=failed，过了/拿了offer意向=passed。

实体 schema：
- create_job: company(必填), position(必填), base_location?, jd_url?, notes_md?, employment_type?, salary_range_text?
- update_status: company?, position?, job_id?, target_status(必填), interview_time_raw?, failure_note?
- update_job_fields: company?, position?, job_id?, base_location?, jd_url?, notes_md?
- query_jobs: filter_status?, company?, horizon_days?
- query_reports: limit?, company?
- query_ability: {}
- start_interview: mode(full|quick_drill)?, job_id?, company?, general?
- 其他面试/help/unknown: {}

复合意图：若一条消息含多个操作，用 intent="compound" 并在 entities.steps 放数组，每项 {intent, entities, confidence}。
不确定时降低 confidence，并填 alternatives（2-3个）。
只输出 JSON，不要 markdown。"""


def _empty_result(
    *,
    intent: str = "unknown",
    entities: dict | None = None,
    confidence: float = 0.0,
    alternatives: list | None = None,
    error: str | None = None,
) -> dict[str, Any]:
    return {
        "intent": intent,
        "entities": entities or {},
        "confidence": confidence,
        "alternatives": alternatives or [],
        "error": error,
    }


def _extract_json(text: str) -> dict[str, Any] | None:
    if not text:
        return None
    text = text.strip()
    # Strip markdown fences
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if fence:
        text = fence.group(1).strip()
    try:
        data = json.loads(text)
        return data if isinstance(data, dict) else None
    except json.JSONDecodeError:
        # Try first {...} block
        m = re.search(r"\{[\s\S]*\}", text)
        if not m:
            return None
        try:
            data = json.loads(m.group(0))
            return data if isinstance(data, dict) else None
        except json.JSONDecodeError:
            return None


def _normalize_result(raw: dict[str, Any]) -> dict[str, Any]:
    intent = str(raw.get("intent") or "unknown").strip()
    entities = raw.get("entities") if isinstance(raw.get("entities"), dict) else {}
    try:
        confidence = float(raw.get("confidence", 0))
    except (TypeError, ValueError):
        confidence = 0.0
    confidence = max(0.0, min(1.0, confidence))
    alternatives = raw.get("alternatives") if isinstance(raw.get("alternatives"), list) else []
    clean_alts = []
    for alt in alternatives[:3]:
        if isinstance(alt, dict) and alt.get("intent"):
            clean_alts.append(
                {
                    "intent": str(alt["intent"]),
                    "confidence": float(alt.get("confidence") or 0),
                }
            )

    # Map rejected intents
    intent_l = intent.lower()
    if intent_l in REJECTED_INTENT_HINTS or any(
        h in intent_l for h in ("delete", "archive", "offer", "salary", "hr_contact")
    ):
        if "delete" in intent_l or "archive" in intent_l:
            return _empty_result(
                intent="rejected_web_guide",
                entities={"guide": "delete", "reply": WEB_GUIDE_DELETE},
                confidence=confidence or 0.9,
            )
        return _empty_result(
            intent="rejected_web_guide",
            entities={"guide": "offer", "reply": WEB_GUIDE_OFFER},
            confidence=confidence or 0.9,
        )

    if intent == "compound":
        return _empty_result(
            intent="compound",
            entities=entities,
            confidence=confidence,
            alternatives=clean_alts,
        )

    if intent not in VALID_INTENTS:
        intent = "unknown"

    return _empty_result(
        intent=intent,
        entities=entities,
        confidence=confidence,
        alternatives=clean_alts,
    )


# High-confidence Chinese patterns used before / after LLM.
_CREATE_JOB_PATTERNS = (
    # 新增岗位：腾讯，后端开发工程师 / 新增岗位 腾讯 后端
    re.compile(
        r"^(?:新增|添加|创建)?(?:一个)?岗位[：:\s]+(?P<company>[^，,、\s]+)[，,、\s]+(?P<position>.+)$"
    ),
    # 帮我记一个字节跳动的AI应用开发工程师岗位
    re.compile(
        r"(?:帮我)?(?:记|记一下|记下|加|添加|新增)(?:一个)?(?P<company>[^的\s]{2,20})的(?P<position>.+?)(?:岗位|职位)?$"
    ),
    # 加一个阿里的岗位 — incomplete (no position) → still create_job for clarify
    re.compile(
        r"(?:帮我)?(?:记|加|添加|新增)(?:一个)?(?P<company>[^的\s]{2,20})的(?:岗位|职位)$"
    ),
)

_QUERY_JOBS_EXACT = frozenset(
    {"我的求职进展", "求职进展", "求职状态", "我的岗位", "岗位列表", "看看我的岗位"}
)
_QUERY_ABILITY_EXACT = frozenset({"我的能力画像", "能力画像", "查看能力画像", "我的画像"})
_QUERY_REPORTS_EXACT = frozenset(
    {"面试报告", "查看面试报告", "我的面试报告", "备战报告", "查看报告"}
)
_START_INTERVIEW_EXACT = frozenset(
    {"开始模拟面试", "模拟面试", "开始面试", "来一场模拟面试"}
)
_CONTINUE_INTERVIEW_EXACT = frozenset({"继续面试", "继续模拟面试"})
_PAUSE_INTERVIEW_EXACT = frozenset({"暂停面试", "暂停", "先暂停", "不做了"})
_END_INTERVIEW_EXACT = frozenset({"结束面试", "结束模拟面试", "退出面试"})


def try_rule_parse(text: str) -> dict[str, Any] | None:
    """Deterministic high-confidence intents without LLM.

    Returns a normalized result dict, or ``None`` when no rule matches.
    """
    stripped = (text or "").strip()
    if not stripped:
        return None

    if stripped in _QUERY_JOBS_EXACT:
        return _empty_result(intent="query_jobs", confidence=0.95, entities={})
    if stripped in _QUERY_ABILITY_EXACT:
        return _empty_result(intent="query_ability", confidence=0.95, entities={})
    if stripped in _QUERY_REPORTS_EXACT:
        return _empty_result(intent="query_reports", confidence=0.95, entities={})
    if stripped in _START_INTERVIEW_EXACT:
        return _empty_result(intent="start_interview", confidence=0.95, entities={})
    if stripped in _CONTINUE_INTERVIEW_EXACT:
        return _empty_result(intent="continue_interview", confidence=0.95, entities={})
    if stripped in _PAUSE_INTERVIEW_EXACT:
        return _empty_result(intent="pause_interview", confidence=0.95, entities={})
    if stripped in _END_INTERVIEW_EXACT:
        return _empty_result(intent="end_interview", confidence=0.95, entities={})

    # Explicit delete / archive → web guide (no write)
    if re.search(r"(删掉|删除|归档).{0,20}(岗位|职位)", stripped):
        return _empty_result(
            intent="rejected_web_guide",
            entities={"guide": "delete", "reply": WEB_GUIDE_DELETE},
            confidence=0.95,
        )

    for pat in _CREATE_JOB_PATTERNS:
        m_obj = pat.search(stripped)
        if not m_obj:
            continue
        company = (m_obj.groupdict().get("company") or "").strip(" 「」\"'")
        position = (m_obj.groupdict().get("position") or "").strip(" 「」\"'")
        entities: dict[str, Any] = {}
        if company:
            entities["company"] = company
        if position:
            entities["position"] = position.rstrip("岗位职位。.!！")
        if not entities.get("company"):
            continue
        return _empty_result(
            intent="create_job",
            entities=entities,
            confidence=0.9 if entities.get("position") else 0.75,
        )

    # Status update: 「字节进一面了」/「腾讯二面了」/「阿里的笔试」
    status_m = re.search(
        r"(?P<company>[\u4e00-\u9fffA-Za-z0-9]{2,20})"
        r"(?:的|进)?"
        r"(?P<label>一面|二面|三面|笔试|已投递|挂了|没过|过了)"
        r"(?:了|啦|咯)?",
        stripped,
    )
    if status_m:
        label = status_m.group("label")
        status_map = {
            "一面": "interview_1",
            "二面": "interview_2",
            "三面": "interview_3",
            "笔试": "test",
            "已投递": "applied",
            "挂了": "failed",
            "没过": "failed",
            "过了": "passed",
        }
        target = status_map.get(label)
        if target:
            company = status_m.group("company")
            # Strip trailing connector accidentally absorbed before optional group
            # (should not happen with non-greedy split, but keep safe).
            if company.endswith(("的", "进")):
                company = company[:-1]
            entities = {
                "company": company,
                "target_status": target,
            }
            # Optional relative interview time phrase after comma / 「，」
            time_m = re.search(
                r"(?:，|,|。)\s*(?P<raw>(?:下|这)?[周天日].{0,20}\d{1,2}[:：]\d{2})",
                stripped,
            )
            if time_m:
                entities["interview_time_raw"] = time_m.group("raw").strip()
            return _empty_result(
                intent="update_status",
                entities=entities,
                confidence=0.88,
            )

    return None


class IntentParser:
    """Parse user WeChat text into IntentParseResult via LLMClient."""

    def __init__(self, llm_client: Any | None = None) -> None:
        self._llm = llm_client

    def _get_llm(self) -> Any:
        if self._llm is not None:
            return self._llm
        from app.agents.llm_client import LLMClient

        self._llm = LLMClient()
        return self._llm

    async def parse(
        self,
        text: str,
        *,
        user_id: UUID | str,
        thread_id: str | None = None,
        skip_confirm_rules: bool = False,
    ) -> dict[str, Any]:
        """Parse intent. Rule-based confirm/cancel / fast-path first unless skipped."""
        stripped = (text or "").strip()
        if not stripped:
            return _empty_result(intent="unknown", confidence=0.0)

        if not skip_confirm_rules:
            if is_confirm(stripped):
                return _empty_result(intent="confirm", confidence=1.0)
            if is_cancel(stripped):
                return _empty_result(intent="cancel", confidence=1.0)
            # Soft help keywords without LLM
            if stripped in ("帮助", "帮助一下", "你能做什么", "功能", "help", "Help"):
                return _empty_result(intent="help", confidence=1.0, entities={})
            rule_hit = try_rule_parse(stripped)
            if rule_hit is not None:
                m.intent_parse_total.labels(
                    intent=rule_hit["intent"], outcome="ok"
                ).inc()
                logger.info(
                    "intent_parsed_rule",
                    extra={
                        "user_id": str(user_id),
                        "intent": rule_hit["intent"],
                        "confidence": rule_hit["confidence"],
                    },
                )
                return rule_hit

        start = time.perf_counter()
        last_error: str | None = None
        for attempt in range(2):  # initial + 1 retry
            try:
                raw_text = await self._invoke_llm(
                    stripped,
                    user_id=str(user_id),
                    thread_id=thread_id or str(user_id),
                )
                parsed = _extract_json(raw_text)
                if parsed is None:
                    last_error = "parse_error"
                    m.intent_parse_total.labels(intent="unknown", outcome="error").inc()
                    continue
                result = _normalize_result(parsed)
                elapsed = time.perf_counter() - start
                m.intent_parse_latency_seconds.observe(elapsed)
                outcome = "ok"
                if result["intent"] == "rejected_web_guide":
                    outcome = "rejected"
                elif result["confidence"] < CONFIDENCE_THRESHOLD and result["intent"] not in (
                    "help",
                    "confirm",
                    "cancel",
                ):
                    outcome = "low_confidence"
                m.intent_parse_total.labels(
                    intent=result["intent"], outcome=outcome
                ).inc()
                logger.info(
                    "intent_parsed",
                    extra={
                        "user_id": str(user_id),
                        "intent": result["intent"],
                        "confidence": result["confidence"],
                        "attempt": attempt,
                        # Never log raw user message
                    },
                )
                return result
            except Exception as exc:
                last_error = "llm_unavailable"
                logger.warning(
                    "intent_parse_llm_failed",
                    extra={
                        "user_id": str(user_id),
                        "attempt": attempt,
                        "error": type(exc).__name__,
                    },
                )
                continue

        # LLM down: try rule fallback even when skip_confirm_rules was set
        # (queued-after-confirm path), or when rules were already tried.
        fallback = try_rule_parse(stripped)
        if fallback is not None:
            m.intent_parse_total.labels(
                intent=fallback["intent"], outcome="ok"
            ).inc()
            m.intent_parse_latency_seconds.observe(time.perf_counter() - start)
            logger.info(
                "intent_parsed_rule_fallback",
                extra={
                    "user_id": str(user_id),
                    "intent": fallback["intent"],
                    "confidence": fallback["confidence"],
                },
            )
            return fallback

        m.intent_parse_total.labels(intent="unknown", outcome="error").inc()
        m.intent_parse_latency_seconds.observe(time.perf_counter() - start)
        return _empty_result(
            intent="unknown",
            confidence=0.0,
            error=last_error or "llm_unavailable",
            entities={"reply": LLM_UNAVAILABLE_TEXT},
        )

    async def _invoke_llm(
        self, text: str, *, user_id: str, thread_id: str
    ) -> str:
        client = self._get_llm()
        messages = [
            {"role": "system", "content": _INTENT_SYSTEM_PROMPT},
            {"role": "user", "content": text},
        ]
        response = await client.invoke(
            messages=messages,
            user_id=user_id,
            thread_id=thread_id,
            node_name="intent_parse",
            max_retries=0,
        )
        if isinstance(response, dict):
            return (response.get("content") or "").strip()
        return str(getattr(response, "content", "") or "").strip()


__all__ = [
    "CONFIDENCE_THRESHOLD",
    "VALID_INTENTS",
    "IntentParser",
    "HELP_TEXT",
    "try_rule_parse",
]
