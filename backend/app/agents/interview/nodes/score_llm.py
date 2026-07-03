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


def _load_prompt(name: str) -> str:
    path = _PROMPT_DIR / name
    return path.read_text(encoding="utf-8")


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

    latest_question = questions[-1]
    question_text = latest_question.get("question", "")
    dimension = latest_question.get("dimension", "tech_depth")

    # Get latest user answer from messages (supports both dicts and HumanMessage objects)
    messages = state.get("messages", [])
    answer = ""
    for msg in reversed(messages):
        if isinstance(msg, dict):
            role = msg.get("role", "")
            if role == "user":
                answer = msg.get("content", "")
                break
        else:
            # LangGraph HumanMessage object
            if getattr(msg, "type", "") == "human":
                answer = getattr(msg, "content", "") or ""
                break

    template = _load_prompt("score.md")
    prompt = template.format(
        question=question_text,
        dimension=dimension,
        difficulty=state.get("difficulty", "medium"),
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
    }

    return {
        "raw_score": raw_score,
        "scores": [*scores, new_score],
    }


# Re-export the threshold for callers that want to import it from the node module
# (test files use ``from app.agents.interview.nodes.score_llm import score_llm_node``).
__all__ = ["score_llm_node", "ERROR_THRESHOLD"]