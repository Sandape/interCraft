"""Score node — evaluates candidate answers (T027).

019 (US4): auto-sinks low-scoring answers (score < 6) to error_questions
via a deterministic source_question_id (UUID v5 = session_id || question_no),
so re-scoring the same question UPSERTs instead of creating duplicates.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from uuid import UUID, uuid5

from app.agents.interview.state import InterviewGraphState
from app.agents.llm_client import get_llm_client
from app.modules.errors.repository import ErrorQuestionRepository

_PROMPT_DIR = Path(__file__).resolve().parent.parent / "prompts"

# 019 — Error threshold: scores below this sink to error_questions.
ERROR_THRESHOLD = 6

# Stable namespace for source_question_id derivation (UUID v5).
_SOURCE_NS = UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")


def _load_prompt(name: str) -> str:
    path = _PROMPT_DIR / name
    return path.read_text(encoding="utf-8")


def _derive_source_qid(session_id: str, question_no: int) -> UUID:
    """Deterministic source_question_id = UUID5(session_id_namespace, str(question_no))."""
    return uuid5(UUID(session_id), str(question_no))


async def _sink_to_error_book(
    state: InterviewGraphState,
    question_text: str,
    answer: str,
    dimension: str,
    score: int,
    current_q: int,
) -> None:
    """Persist a low-scoring question to error_questions (UPSERT)."""
    thread_id = state.get("thread_id", "")
    user_id = state.get("user_id", "")
    if not thread_id or not user_id:
        return

    source_session_id = UUID(thread_id)
    source_question_id = _derive_source_qid(thread_id, current_q)

    from app.core.db import get_session_context

    async with get_session_context() as session:
        repo = ErrorQuestionRepository(session)
        await repo.upsert_by_source(
            user_id=UUID(user_id),
            source_session_id=source_session_id,
            source_question_id=source_question_id,
            question_text=question_text,
            answer_text=answer,
            dimension=dimension,
            score=score,
        )


async def score_node(state: InterviewGraphState) -> dict:
    """Score the latest user answer against the current question."""
    questions = state.get("questions", [])
    scores = state.get("scores", [])
    current_q = state.get("current_question", 0)

    if not questions:
        return {"scores": scores, "error": "No question to score against"}

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
    try:
        result = await client.invoke(
            messages=[
                {"role": "system", "content": "你是一位面试评估官，负责对候选人的回答进行打分。所有 JSON 字段值必须使用中文（zh-CN），仅 JSON 的 key 保持英文。`dimension` 字段值必须使用英文 key，`feedback` 字段值必须为中文。只返回 JSON，不要包含任何解释或 markdown 标记。"},
                {"role": "user", "content": prompt},
            ],
            estimated_tokens=1800,
            user_id=state.get("user_id", "unknown"),
            thread_id=state.get("thread_id", "unknown"),
            node_name="score",
        )
        content = result["content"]
        json_match = re.search(r"\{.*\}", content, re.DOTALL)
        if json_match:
            s_data = json.loads(json_match.group(0))
        else:
            s_data = {"score": 5, "dimension": dimension, "feedback": "Unable to parse score."}
    except Exception:
        s_data = {"score": 5, "dimension": dimension, "feedback": "Scoring unavailable."}

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

    # 019 — Auto-sink low-scoring answers to error_questions.
    if raw_score < ERROR_THRESHOLD:
        try:
            await _sink_to_error_book(
                state, question_text, answer, dimension, raw_score, current_q,
            )
        except Exception:
            # Non-critical: scoring should not fail even if error-sink fails.
            pass

    return {
        "scores": [*scores, new_score],
    }


__all__ = ["score_node", "ERROR_THRESHOLD", "_derive_source_qid"]
