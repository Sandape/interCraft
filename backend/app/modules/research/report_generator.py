"""Report generation: convert 4 search dimensions + user weakness data
into a structured 6-chapter Markdown report via LLM.

REQ-053 FR-015: DeepSeek V4 Pro via llm_client.invoke() with system prompt
that mandates exactly 6 chapters in fixed order and 2000-3000 Chinese chars.
"""
from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from typing import Any
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)

_BJ = ZoneInfo("Asia/Shanghai")

# Strip LLM conversational openers that are wrong for proactive push.
_FLUFF_OPENERS = re.compile(
    r"^(?:好的[，,]?\s*)?(?:这是为您生成的|以下是|为您整理了|已为您生成)"
    r"[^\n]{0,80}(?:报告|如下)[。.!！]?\s*\n*",
)


SYSTEM_PROMPT = """你是 InterCraft 的面试备战助手。系统会在面试前约 5 小时自动推送这份报告，用户并未主动索要。

直接输出 Markdown 报告正文，禁止任何开场白或客套（禁止「好的」「这是为您生成的…」「以下是…」等）。

报告必须严格按照以下 6 个章节结构输出：

## 📋 面试概览
用简洁列表给出：公司、岗位、面试时间（北京时间，写清日期与时刻）、面试轮次、倒计时。
倒计时必须写成具体相对时间（如「约 4 小时 50 分钟后」），禁止写「请根据当前日期计算」。

## 🏢 公司与产品速览
2-4 句说清公司与本岗位相关的业务；再列 2-4 个与岗位直接相关的产品/平台（名称 + 一句为何相关）。不要写与岗位无关的泛泛公司介绍。

## 📝 面经汇总
提炼 3-8 道具体面试题。每题格式：
**题 N**：题目原文（简体中文；若来源是繁体/口语，改写成规范简体，保留原意）
- 答：2-4 条可口述的要点（短句，不要长段落套娃列表）

题目要真实、具体；信息不足时如实说明，禁止编造。

## 🎯 高频考察点
5-10 条，按重要性排序。每条一行：`N. 【知识点】：一句考察方式/为何重要`。

## ⚠️ 你的薄弱环节
基于用户能力画像（最低 2 个维度得分）和错题本，给出 2-3 个薄弱主题。每项：
- 【主题】名称
- 【维度】维度名 + 得分
- 【速成】一条今晚就能做的具体动作（有时限、可验证）

若无能力画像：写「暂无足够模拟面试数据，完成一次模拟后面试前可生成个性化薄弱点」。不要编造分数。

## 💡 最后建议
恰好 3 条，今晚可执行、与上文面经/产品/薄弱点挂钩。禁止空话。

## 📊 历史对比（可选）
仅当提供了历史对比数据时才输出；否则整章省略，不要写「暂无数据」占位。

硬性要求：
- 全文简体中文（专有名词可保留英文）
- 字数 2000-3000（中文字符计 1，英文字母计 0.5）
- 只使用提供的搜索结果与用户数据，不得编造未经验证的信息
- 章节顺序固定，使用二级标题（##）
- 列表用 `- ` 或有序数字，避免过深嵌套（最多两层）
- 语气：主动推送的备战简报，像同事提醒，不像客服回复
"""


def _format_countdown(interview_time_iso: str, *, now: datetime | None = None) -> str:
    """Human countdown in Asia/Shanghai, e.g. '约 4 小时 50 分钟后'."""
    try:
        raw = interview_time_iso.replace("Z", "+00:00")
        when = datetime.fromisoformat(raw)
        if when.tzinfo is None:
            when = when.replace(tzinfo=timezone.utc)
        when_bj = when.astimezone(_BJ)
        now_bj = (now or datetime.now(timezone.utc)).astimezone(_BJ)
        delta = when_bj - now_bj
        secs = int(delta.total_seconds())
        if secs <= 0:
            return "已到或已过面试时间"
        hours, rem = divmod(secs, 3600)
        minutes = rem // 60
        if hours > 0 and minutes > 0:
            return f"约 {hours} 小时 {minutes} 分钟后"
        if hours > 0:
            return f"约 {hours} 小时后"
        return f"约 {minutes} 分钟后"
    except Exception:
        return ""


def _format_interview_local(interview_time_iso: str) -> str:
    try:
        raw = interview_time_iso.replace("Z", "+00:00")
        when = datetime.fromisoformat(raw)
        if when.tzinfo is None:
            when = when.replace(tzinfo=timezone.utc)
        bj = when.astimezone(_BJ)
        return f"{bj.year}年{bj.month}月{bj.day}日 {bj.hour:02d}:{bj.minute:02d}（北京时间）"
    except Exception:
        return interview_time_iso


def _strip_fluff(content: str) -> str:
    return _FLUFF_OPENERS.sub("", content.lstrip()).lstrip()


def _ensure_countdown(content: str, countdown: str) -> str:
    """Replace LLM placeholder countdown lines with a computed value."""
    if not countdown:
        return content
    # Common bad patterns from the model
    patterns = [
        re.compile(r"(-\s*\*?\*?倒计时\*?\*?[：:]\s*).+$", re.MULTILINE),
        re.compile(r"(-\s*【倒计时】[：:]\s*).+$", re.MULTILINE),
    ]
    replaced = False
    for pat in patterns:
        if pat.search(content):
            content = pat.sub(rf"\g<1>{countdown}", content)
            replaced = True
            break
    if not replaced and "倒计时" not in content and "## 📋 面试概览" in content:
        # Inject after overview heading block's first list if missing
        content = content.replace(
            "## 📋 面试概览\n",
            f"## 📋 面试概览\n- **倒计时**：{countdown}\n",
            1,
        )
    return content


def _drop_empty_history_section(content: str) -> str:
    """Remove 📊 历史对比 when it only says there's no data."""
    m = re.search(r"\n## 📊 历史对比\s*\n([\s\S]*?)(?=\n## |\Z)", content)
    if not m:
        return content
    body = m.group(1).strip()
    empty_markers = ("还没有足够", "暂无", "完成一次模拟", "无法生成", "无历史")
    if any(k in body for k in empty_markers) and "|" not in body:
        return content[: m.start()] + content[m.end() :]
    return content


async def generate_research_report(
    *,
    company: str,
    position: str,
    interview_time_iso: str,
    interview_round: str,
    search_results: dict[str, list[dict[str, Any]]],
    user_weakness: dict[str, Any],
    historical_comparison: dict[str, Any] | None = None,
) -> str:
    """Generate the structured Markdown report via LLM.

    Args:
        company: Company name.
        position: Position name.
        interview_time_iso: Interview time in ISO 8601 format.
        interview_round: e.g. "面试 1 轮" / "笔试".
        search_results: dict keyed by dimension name with list of search hits.
        user_weakness: dict with dimensions (list of {key, score, improvements})
                       and error_questions (list of {tags}).
        historical_comparison: optional dict with previous report context.

    Returns:
        Markdown report content (2000-3000 chars target).
    """
    from app.agents.llm_client import get_llm_client

    countdown = _format_countdown(interview_time_iso)
    interview_local = _format_interview_local(interview_time_iso)

    user_payload = {
        "company": company,
        "position": position,
        "interview_time": interview_time_iso,
        "interview_time_beijing": interview_local,
        "countdown": countdown,
        "interview_round": interview_round,
        "search_results_by_dimension": {
            k: [{"title": r.get("title"), "url": r.get("url"), "content": (r.get("content") or "")[:500]} for r in v]
            for k, v in search_results.items()
        },
        "user_weakness": user_weakness,
        "historical_comparison": historical_comparison,
    }

    user_message = (
        "请基于以下信息生成面试备战报告。"
        "直接从「## 📋 面试概览」开始，不要开场白。"
        f"倒计时请使用：{countdown or '（按面试时间自行估算相对时间）'}。\n\n"
        + json.dumps(user_payload, ensure_ascii=False, indent=2)
    )

    client = get_llm_client()
    response = await client.invoke(
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ],
        estimated_tokens=12000,
        user_id="research-pipeline",  # internal pipeline user; metrics tracked separately
        thread_id=f"research-{company}-{position}",
        node_name="research_report_gen",
        max_retries=2,
        # Report generation is a long Chinese synthesis over 4 search
        # dimensions; 60s was too tight under DeepSeek load and caused
        # ARQ acceptance failures (ReadTimeout after 3 retries).
        timeout_ms=180_000,
    )

    # FR-023 metric: record LLM tokens used for report generation
    try:
        from app.modules.research.metrics import report_generation_tokens
        report_generation_tokens.labels(phase="report_gen").inc(
            int(response.get("prompt_tokens", 0)) + int(response.get("completion_tokens", 0))
        )
    except Exception:
        pass  # never let metrics collection break the pipeline

    content = response.get("content", "")
    if not content:
        raise RuntimeError("LLM returned empty report content")

    content = _strip_fluff(content.strip())
    content = _ensure_countdown(content, countdown)
    content = _drop_empty_history_section(content)

    required_headings = ["📋 面试概览", "🏢 公司与产品速览", "📝 面经汇总", "🎯 高频考察点", "⚠️ 你的薄弱环节", "💡 最后建议"]
    missing = [h for h in required_headings if h not in content]
    if missing:
        logger.warning("Generated report missing headings: %s", missing)

    # REQ-053 US4-AC6: append 📊 历史对比 table when we have previous + current
    # weakness dimensions for the same company within the last 7 days.
    if historical_comparison:
        prev_dims = historical_comparison.get("previous_dimensions") or []
        cur_dims = historical_comparison.get("current_dimensions") or []
        if prev_dims and cur_dims:
            content = append_historical_comparison(
                content,
                previous_dimensions=prev_dims,
                current_dimensions=cur_dims,
            )

    return content


def append_historical_comparison(
    report_md: str,
    *,
    previous_dimensions: list[dict[str, Any]],
    current_dimensions: list[dict[str, Any]],
) -> str:
    """Append a 📊 历史对比 section comparing previous vs current weakness."""
    if not previous_dimensions or not current_dimensions:
        return report_md

    # Drop any empty placeholder the LLM may have left
    report_md = _drop_empty_history_section(report_md)

    prev_map = {d["key"]: d["score"] for d in previous_dimensions}
    lines = ["\n\n## 📊 历史对比\n\n", "上次面试前的薄弱环节与本次对比：\n\n"]
    lines.append("| 维度 | 上次得分 | 本次得分 | 趋势 |\n")
    lines.append("|------|---------|---------|------|\n")
    for d in current_dimensions:
        prev_score = prev_map.get(d["key"])
        cur_score = d["score"]
        if prev_score is None:
            trend = "—"
        elif cur_score > prev_score + 0.1:
            trend = "↑ 进步"
        elif cur_score < prev_score - 0.1:
            trend = "↓ 退步"
        else:
            trend = "→ 持平"
        lines.append(f"| {d['key']} | {prev_score if prev_score is not None else '—'} | {cur_score} | {trend} |\n")

    return report_md.rstrip() + "".join(lines)


__all__ = [
    "generate_research_report",
    "append_historical_comparison",
    "_format_countdown",
    "_strip_fluff",
]
