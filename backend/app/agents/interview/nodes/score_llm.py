"""[AC-040-US2 FR-004] score_llm node — LLM-only scoring.

Splits the legacy ``score_node`` into two responsibilities (US2 AC-4.3):

- ``score_llm`` (this file): invoke the LLM, parse the JSON, return the
  raw_score + feedback. **No DB writes**.
- ``sink_error`` (``sink_error.py``): conditional DB write to
  ``error_questions`` when ``raw_score < ERROR_THRESHOLD``. **No LLM calls**.

The split was driven by the US2 R5'' lesson: the legacy single function
silently swallowed DB errors with ``try/except: pass``, masking root
causes. With the split, a DB write failure is visible as an independent
OTel span + can be retried in isolation (AC-4.7a).

Per the routing table in ``graph.py``:

- ``raw_score < ERROR_THRESHOLD`` → route to ``sink_error``
- ``current_question < MAX_QUESTIONS`` → route back to ``interviewer``
- otherwise → ``report``
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from app.agents.interview.config import ERROR_THRESHOLD
from app.agents.interview.state import InterviewGraphState
from app.agents.llm_client import get_llm_client
from app.agents.utils.node_error_handler import node_error_handler
from app.observability import traced_node

_PROMPT_DIR = Path(__file__).resolve().parent.parent / "prompts"

_DETAIL_SIGNALS = (
    "目标",
    "负责",
    "设计",
    "难点",
    "解决",
    "验证",
    "指标",
    "上线",
    "日志",
    "评估",
    "回放",
    "状态",
    "重试",
    "拆",
)

_TECH_SIGNALS = (
    "Agent",
    "RAG",
    "LangGraph",
    "MCP",
    "Tool",
    "工具",
    "向量",
    "检索",
    "FastAPI",
    "React",
    "TypeScript",
    "LLM",
    "Prompt",
    "embedding",
)

_WEAK_SIGNALS = (
    "不算深入",
    "不充分",
    "比较弱",
    "信心一般",
    "没有完整",
    "没有系统",
    "没有长期",
    "没有主导",
    "还没有",
    "缺少",
    "只能说",
    "需要提示",
    "看题解",
    "不保证",
)


def _load_prompt(name: str) -> str:
    path = _PROMPT_DIR / name
    return path.read_text(encoding="utf-8")


def _count_signals(text: str, signals: tuple[str, ...]) -> int:
    return sum(1 for signal in signals if signal in text)


def _score_degraded_template_answer(answer: str) -> tuple[int, str, dict[str, int]]:
    """Deterministic fallback for template-degraded interviews.

    This is intentionally labelled as local degraded scoring so reports do
    not present it as an external AI evaluation.
    """
    stripped = (answer or "").strip()
    length = len(stripped)
    detail_count = _count_signals(stripped, _DETAIL_SIGNALS)
    tech_count = _count_signals(stripped, _TECH_SIGNALS)
    weak_count = _count_signals(stripped, _WEAK_SIGNALS)

    score = 5
    if length >= 90:
        score += 2
    elif length >= 45:
        score += 1

    if detail_count >= 4:
        score += 2
    elif detail_count >= 2:
        score += 1

    if tech_count >= 2:
        score += 1

    if weak_count >= 2:
        score = min(score, 4)
    elif weak_count == 1:
        score = min(score - 1, 5)

    raw_score = max(1, min(9, score))
    if raw_score >= ERROR_THRESHOLD:
        feedback = "降级评分：回答包含具体项目、技术动作与验证方式，具备继续追问价值。"
    else:
        feedback = "降级评分：回答暴露了明显短板，需要补充具体方案、关键取舍和验证证据。"

    sub_scores = {
        "clarity": max(1, min(10, 4 + (1 if length >= 45 else 0) + min(detail_count, 3))),
        "depth": raw_score,
        "relevance": max(1, min(10, 5 + min(tech_count, 3) - min(weak_count, 3))),
    }
    return raw_score, feedback, sub_scores


@node_error_handler(fallback_strategy="retry")
@traced_node("interview.score_llm")
async def score_llm_node(state: InterviewGraphState) -> dict:
    """Score the latest user answer against the current question (LLM only).

    Returns ``{"raw_score": int, "scores": [..., new_score]}`` and never
    touches the DB. Downstream ``sink_error`` reads ``raw_score`` and
    decides whether to persist the question to ``error_questions``.
    """
    questions = state.get("questions", [])
    scores = state.get("scores", [])
    current_q = state.get("current_question", 0)

    if not questions:
        return {"raw_score": 0, "scores": scores, "error": "No question to score against"}

    latest_user_sequence: int | None = None
    messages = state.get("messages", [])
    answer = ""
    for msg in reversed(messages):
        if isinstance(msg, dict):
            role = msg.get("role", "")
            if role == "user":
                answer = msg.get("content", "")
                seq = msg.get("sequence_no")
                if isinstance(seq, int):
                    latest_user_sequence = seq
                break
        else:
            # LangGraph HumanMessage object
            if getattr(msg, "type", "") == "human":
                answer = getattr(msg, "content", "") or ""
                seq = getattr(msg, "sequence_no", None)
                if not isinstance(seq, int):
                    extra = getattr(msg, "additional_kwargs", {}) or {}
                    seq = extra.get("sequence_no")
                if isinstance(seq, int):
                    latest_user_sequence = seq
                break

    # The graph may already contain the next generated question by the time
    # scoring runs. Score against the question the submitted answer belongs to,
    # not blindly against the newest question in state.
    question_index = None
    if latest_user_sequence is not None and latest_user_sequence > 0:
        question_index = latest_user_sequence - 1
    if question_index is not None and 0 <= question_index < len(questions):
        latest_question = questions[question_index]
    else:
        latest_question = questions[-1]
    question_text = latest_question.get("question", "")
    dimension = latest_question.get("dimension", "tech_depth")
    expected_points = latest_question.get("expected_points") or []

    # REQ-058 — short / empty answer fast path (no LLM)
    stripped = (answer or "").strip()
    if len(stripped) < 8:
        raw_score = 1 if not stripped else 2
        feedback = (
            "未作答或回答过短，无法评估。请针对题目给出具体技术细节与思路。"
            if not stripped
            else "回答过短，缺少与题目相关的实质内容。请补充关键步骤、权衡与例子。"
        )
        new_score = {
            "question_no": current_q,
            "dimension": dimension,
            "score": raw_score,
            "feedback": feedback,
            "sub_scores": {"clarity": raw_score, "depth": raw_score, "relevance": 1},
            "question_text": question_text,
            "user_answer": answer if answer else "",
            "off_topic": True,
            "scoring_method": "local_short_answer",
        }
        return {"raw_score": raw_score, "scores": [*scores, new_score]}

    if bool(state.get("degraded", False)) or latest_question.get("source") == "template_degraded":
        raw_score, feedback, sub_scores = _score_degraded_template_answer(answer)
        new_score = {
            "question_no": current_q,
            "dimension": dimension,
            "score": raw_score,
            "feedback": feedback,
            "sub_scores": sub_scores,
            "question_text": question_text,
            "user_answer": answer if answer else "",
            "off_topic": raw_score < ERROR_THRESHOLD,
            "expected_points": expected_points,
            "source": latest_question.get("source", "template_degraded"),
            "scoring_method": "local_degraded_template",
        }
        return {"raw_score": raw_score, "scores": [*scores, new_score]}

    points_text = (
        json.dumps(expected_points, ensure_ascii=False)
        if expected_points
        else "（本题未提供明确得分点，请按题目本身评估完整性）"
    )
    template = _load_prompt("score.md")
    prompt = template.format(
        question=question_text,
        dimension=dimension,
        difficulty=state.get("difficulty", "medium"),
        expected_points=points_text,
        answer=answer if answer else "(no answer provided)",
    )

    client = get_llm_client()
    # NOTE: AC-4.6 — score_llm must NOT swallow LLM exceptions. The legacy
    # code had `except Exception: ...` which masked all LLM failures and
    # broke failure isolation. We re-raise so the graph can route to a
    # sink_error / report decision based on raw_score, and the OTel span
    # (via @traced_node) marks ERROR + record_exception automatically.
    try:
        result = await client.invoke(
            messages=[
                {"role": "system", "content": "你是一位面试评估官，负责对候选人的回答进行打分。所有 JSON 字段值必须使用中文（zh-CN），仅 JSON 的 key 保持英文。`dimension` 字段值必须使用英文 key，`feedback` 字段值必须为中文。只返回 JSON，不要包含任何解释或 markdown 标记。"},
                {"role": "user", "content": prompt},
            ],
            estimated_tokens=1800,
            user_id=state.get("user_id", "unknown"),
            thread_id=state.get("thread_id", "unknown"),
            node_name="score_llm",
        )
        content = result["content"]
        json_match = re.search(r"\{.*\}", content, re.DOTALL)
        if json_match:
            s_data = json.loads(json_match.group(0))
        else:
            s_data = {"score": 5, "dimension": dimension, "feedback": "Unable to parse score."}
    except json.JSONDecodeError:
        # JSON decode errors are recoverable: use a fallback score rather
        # than failing the whole interview. The OTel span still records
        # the parse failure via @traced_node's trace context.
        s_data = {"score": 5, "dimension": dimension, "feedback": "Unable to parse score."}

    raw_score = s_data.get("score", 5)
    new_score = {
        "question_no": current_q,
        "dimension": dimension,
        "score": raw_score,
        "feedback": s_data.get("feedback", ""),
        "sub_scores": s_data.get("sub_scores", {}),
        "question_text": question_text,
        "user_answer": answer if answer else "",
        "off_topic": bool(s_data.get("off_topic", False)),
        "expected_points": expected_points,
    }

    return {
        "raw_score": raw_score,
        "scores": [*scores, new_score],
    }


# Re-export the threshold for callers that want to import it from the node module
# (test files use ``from app.agents.interview.nodes.score_llm import score_llm_node``).
__all__ = ["score_llm_node", "ERROR_THRESHOLD"]
