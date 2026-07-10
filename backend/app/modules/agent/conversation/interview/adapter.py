"""WeChat async interview adapter (REQ-054 US4).

Reuses InterviewSessionService create/start/submit_answer/resume.
Formats short WeChat replies; slow scoring returns interim thinking text.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Callable, Awaitable
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.agent.conversation import metrics as m
from app.modules.agent.conversation.interview.mutex import has_active_session
from app.modules.agent.conversation.job_matcher import match_jobs
from app.modules.agent.conversation.reply_formatter import truncate
from app.modules.agent.conversation.tools import ToolResult, fail, ok

logger = logging.getLogger(__name__)

SCORE_THINKING_SECONDS = 30
THINKING_TEXT = "评分中，请稍候…"


class InterviewAdapter:
    def __init__(
        self,
        session: AsyncSession,
        user_id: UUID,
        *,
        send_interim: Callable[[str], Awaitable[None]] | None = None,
    ) -> None:
        self.session = session
        self.user_id = user_id
        self.send_interim = send_interim

    async def start(self, entities: dict[str, Any]) -> ToolResult:
        """Create + optionally prepare interview; enforce global mutex."""
        active = await has_active_session(self.session, self.user_id)
        if active is not None:
            channel = "Web/微信"
            m.interview_adapter_total.labels(action="start", outcome="mutex_blocked").inc()
            return fail(
                f"你已有一场进行中的模拟面试（{getattr(active, 'company', '')} · "
                f"{getattr(active, 'position', '')}，状态 {active.status}，渠道提示：{channel}）。"
                "请回复「继续面试」从中断处恢复，或「结束面试」后再开新场。",
                "mutex_blocked",
                {"session_id": str(active.id)},
            )

        mode = entities.get("mode") or "full"
        if mode not in ("full", "quick_drill"):
            mode = "full"

        # Need mode/job selection?
        if not entities.get("mode") and not entities.get("confirmed_start"):
            m.interview_adapter_total.labels(action="start", outcome="clarify").inc()
            return ok(
                "好的！请选择面试模式：\n"
                "A. 快速 Drill（5 道错题强化）\n"
                "B. 完整面试（综合面试）\n"
                "另外，是针对某个岗位的定向面试，还是通用面试？\n"
                "例：「B 字节跳动」或「通用面试」。"
            )

        job_id = entities.get("job_id")
        company = entities.get("company")
        general = bool(entities.get("general"))
        position = entities.get("position")

        from app.modules.interviews.schemas import InterviewSessionCreate
        from app.modules.interviews.service import InterviewSessionService
        from app.modules.jobs.service import JobService

        create_data: dict[str, Any] = {"mode": mode}
        if mode == "full":
            create_data["max_questions"] = 10

        if not general and (job_id or company):
            jobs = await JobService(self.session).list(self.user_id)
            match = match_jobs(jobs, company=company, position=position, job_id=job_id)
            if match.need_clarify and not match.unique:
                if not match.candidates:
                    return ok(
                        "未找到匹配岗位。可以说「通用面试」不关联岗位，或先新增岗位。"
                    )
                from app.modules.agent.conversation.reply_formatter import format_job_candidates

                return ok(format_job_candidates(match.candidates, prompt="请选择要面试的岗位："))
            job = match.matched
            create_data["job_id"] = job.id
            create_data["position"] = job.position
            create_data["company"] = job.company
        else:
            create_data["company"] = company or "通用"
            create_data["position"] = position or "综合面试"

        try:
            svc = InterviewSessionService(self.session)
            created = await svc.create(
                self.user_id, InterviewSessionCreate(**create_data)
            )
            session_id = created.id if hasattr(created, "id") else created["id"]
            await svc.start(session_id, self.user_id)
        except ValueError as exc:
            code = exc.args[0] if exc.args else "validation_error"
            if code == "INSUFFICIENT_ERROR_POOL":
                return fail(
                    "快速 Drill 需要至少 5 道未掌握错题。请先完成完整面试积累错题，或选择完整面试。",
                    "validation_error",
                )
            if code == "MISSING_INTERVIEW_TARGET":
                return ok("请指定岗位（公司名）或回复「通用面试」。")
            return fail(f"无法创建面试：{code}", "validation_error")
        except Exception as exc:
            logger.warning(
                "interview_start_failed",
                extra={"user_id": str(self.user_id), "error": type(exc).__name__},
            )
            m.interview_adapter_total.labels(action="start", outcome="error").inc()
            return fail("创建面试失败，请稍后重试。", "internal_error")

        target = f"{create_data.get('company')} · {create_data.get('position')}"
        mode_cn = "完整面试" if mode == "full" else "快速 Drill"
        m.interview_adapter_total.labels(action="start", outcome="ok").inc()
        return ok(
            f"面试准备就绪！目标：{target}（{mode_cn}）。"
            "我会逐题发送，你通过文字作答。准备好了吗？回复「开始」启动面试。",
            {
                "session_id": str(session_id),
                "state": "in_interview",
                "interview_round": 0,
                "awaiting_begin": True,
            },
        )

    async def begin_questions(self, session_id: UUID) -> ToolResult:
        """After user says 开始 — pull first question via resume/state."""
        from app.modules.interviews.service import InterviewSessionService

        svc = InterviewSessionService(self.session)
        try:
            state = await svc.resume(session_id, self.user_id)
            q = _extract_question(state)
            if not q:
                # Kick graph with empty submit path is heavy; give placeholder
                q = "请先做个自我介绍，并说明你最擅长的技术方向。"
            m.interview_adapter_total.labels(action="begin", outcome="ok").inc()
            return ok(
                truncate(f"【第 1 题】\n{q}", 500),
                {"session_id": str(session_id), "interview_round": 1},
            )
        except Exception:
            m.interview_adapter_total.labels(action="begin", outcome="error").inc()
            return fail("无法开始面试题目，请稍后重试或前往 Web 端。", "internal_error")

    async def continue_session(self, session_id: UUID | None = None) -> ToolResult:
        active = None
        if session_id:
            from app.modules.interviews.service import InterviewSessionService

            try:
                active = await InterviewSessionService(self.session).get(
                    session_id, self.user_id
                )
            except Exception:
                active = None
        if active is None:
            active = await has_active_session(self.session, self.user_id)
        if active is None:
            return fail(
                "没有进行中的面试。回复「开始模拟面试」开启一场吧！",
                "not_found",
            )

        sid = active.id if hasattr(active, "id") else UUID(str(active["id"]))
        from app.modules.interviews.service import InterviewSessionService

        try:
            state = await InterviewSessionService(self.session).resume(sid, self.user_id)
            q = _extract_question(state)
            round_no = _extract_round(state) or 1
            if not q:
                return ok(
                    f"已恢复面试（进度约第 {round_no} 轮）。请继续作答上一题，或说明需要我重新发题。",
                    {"session_id": str(sid), "interview_round": round_no},
                )
            m.interview_adapter_total.labels(action="continue", outcome="ok").inc()
            return ok(
                truncate(f"继续面试 — 【第 {round_no} 题】\n{q}", 500),
                {"session_id": str(sid), "interview_round": round_no},
            )
        except Exception:
            m.interview_adapter_total.labels(action="continue", outcome="error").inc()
            return fail("恢复面试失败，请稍后重试。", "internal_error")

    async def pause(self, session_id: UUID | None, round_no: int | None) -> ToolResult:
        # Keep session in_progress; only clear conversation in_interview flag upstream
        r = round_no or 0
        m.interview_adapter_total.labels(action="pause", outcome="ok").inc()
        return ok(
            f"面试已暂停。当前进度：{r}/5 轮。"
            "你可以稍后回复「继续面试」从中断处继续，或回复「结束面试」查看当前结果。",
            {"session_id": str(session_id) if session_id else None, "paused": True},
        )

    async def end(self, session_id: UUID | None, round_no: int | None) -> ToolResult:
        from app.modules.interviews.repository import InterviewSessionRepository
        from datetime import UTC, datetime

        if session_id is None:
            active = await has_active_session(self.session, self.user_id)
            if active is None:
                return fail("没有进行中的面试可结束。", "not_found")
            session_id = active.id
            round_no = round_no or 0

        repo = InterviewSessionRepository(self.session)
        sess = await repo.get(session_id, self.user_id)
        if sess is None:
            return fail("面试会话不存在。", "not_found")

        rounds = round_no or 0
        now = datetime.now(UTC)
        if rounds >= 3:
            await repo.update_status(session_id, "completed", ended_at=now)
            m.interview_adapter_total.labels(action="end", outcome="ok").inc()
            return ok(
                f"面试已结束（完成 {rounds} 轮）。已生成部分结果，完整报告请在 InterCraft 查看。",
                {"session_id": str(session_id), "status": "completed"},
            )

        await repo.update_status(session_id, "expired", ended_at=now)
        m.interview_adapter_total.labels(action="end", outcome="ok").inc()
        return ok(
            f"面试已结束（仅完成 {rounds} 轮，不足 3 轮不生成报告）。"
            "下次可以回复「开始模拟面试」再来。",
            {"session_id": str(session_id), "status": "expired"},
        )

    async def submit_answer(
        self,
        session_id: UUID,
        answer: str,
        sequence_no: int,
    ) -> ToolResult:
        """Submit answer; if scoring is slow, emit thinking interim text."""
        from app.modules.interviews.service import InterviewSessionService

        svc = InterviewSessionService(self.session)
        thinking_sent = False

        async def _run() -> dict:
            return await svc.submit_answer(
                session_id, self.user_id, answer, sequence_no
            )

        task = asyncio.create_task(_run())
        try:
            done, _ = await asyncio.wait({task}, timeout=SCORE_THINKING_SECONDS)
            if not done:
                thinking_sent = True
                if self.send_interim:
                    try:
                        await self.send_interim(THINKING_TEXT)
                    except Exception:
                        pass
                result = await task
            else:
                result = task.result()
        except Exception as exc:
            logger.warning(
                "interview_submit_failed",
                extra={"user_id": str(self.user_id), "error": type(exc).__name__},
            )
            m.interview_adapter_total.labels(action="submit", outcome="error").inc()
            return fail("评分失败，请稍后重试或换个方式作答。", "internal_error")

        reply = _format_score_and_next(result, sequence_no)
        if thinking_sent and not self.send_interim:
            # Caller should treat data.interim as first segment
            m.interview_adapter_total.labels(action="submit", outcome="ok_slow").inc()
            return ok(
                reply,
                {
                    "session_id": str(session_id),
                    "interim": THINKING_TEXT,
                    "interview_round": sequence_no + 1,
                    "completed": _is_complete(result),
                },
            )
        m.interview_adapter_total.labels(action="submit", outcome="ok").inc()
        return ok(
            reply,
            {
                "session_id": str(session_id),
                "interview_round": sequence_no + 1,
                "completed": _is_complete(result),
            },
        )


def _extract_question(state: Any) -> str | None:
    if not state:
        return None
    values = state.get("values") if isinstance(state, dict) else None
    if values is None and isinstance(state, dict):
        values = state
    if not isinstance(values, dict):
        return None
    for key in ("current_question", "question", "next_question"):
        q = values.get(key)
        if isinstance(q, str) and q.strip():
            return q.strip()
        if isinstance(q, dict):
            text = q.get("text") or q.get("question") or q.get("content")
            if text:
                return str(text).strip()
    questions = values.get("questions") or values.get("plan_questions")
    if isinstance(questions, list) and questions:
        idx = int(values.get("current_index") or values.get("sequence_no") or 0)
        if idx < len(questions):
            item = questions[idx]
            if isinstance(item, str):
                return item
            if isinstance(item, dict):
                return str(item.get("text") or item.get("question") or "")
    return None


def _extract_round(state: Any) -> int | None:
    if not isinstance(state, dict):
        return None
    values = state.get("values") if "values" in state else state
    if not isinstance(values, dict):
        return None
    for key in ("sequence_no", "current_index", "round", "interview_round"):
        if values.get(key) is not None:
            try:
                return int(values[key]) + (1 if key == "current_index" else 0)
            except (TypeError, ValueError):
                continue
    scores = values.get("scores")
    if isinstance(scores, list):
        return len(scores) + 1
    return None


def _is_complete(result: dict) -> bool:
    from app.modules.interviews.completion import is_interview_graph_complete

    return is_interview_graph_complete(result)


def _format_score_and_next(result: dict, sequence_no: int) -> str:
    scores = result.get("scores") or []
    last_score = None
    feedback = ""
    if scores:
        last = scores[-1]
        if isinstance(last, dict):
            last_score = last.get("score") or last.get("overall")
            feedback = last.get("feedback") or last.get("comment") or ""
        else:
            last_score = last

    parts: list[str] = []
    if last_score is not None:
        parts.append(f"本轮得分：{last_score}/10")
    if feedback:
        parts.append(truncate(str(feedback), 120))

    if _is_complete(result):
        overall = result.get("overall_score")
        parts.append(
            f"🎉 面试完成！总分 {overall if overall is not None else '-'}。"
            "📎 完整报告可在 InterCraft 中查看。"
        )
        return truncate("\n".join(parts), 500)

    nxt = _extract_question(result) or result.get("next_question")
    next_round = sequence_no + 1
    if nxt:
        parts.append(f"【第 {next_round} 题】\n{nxt}")
    else:
        parts.append(f"请继续作答（第 {next_round} 轮）。")
    return truncate("\n".join(parts), 500)


__all__ = ["InterviewAdapter", "THINKING_TEXT", "SCORE_THINKING_SECONDS"]
