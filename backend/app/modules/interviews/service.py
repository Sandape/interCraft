"""InterviewSessionService — Phase 4 full business logic."""
from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid4

import structlog
from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
import json

from app.agents.interview.graph import get_interview_graph
from app.modules.interviews.repository import InterviewSessionRepository
from app.modules.interviews.schemas import InterviewSessionCreate
from app.repositories.interview_report_repo import InterviewReportRepo

logger = structlog.get_logger(__name__)

PLAN_PREWARM_TIMEOUT_SECONDS = 20.0


async def sync_ability_dimensions(
    session: AsyncSession, session_id: UUID, user_id: UUID
) -> None:
    """Synchronously upsert per-dimension scores from the interview report
    into `ability_dimensions` so `/ability-profile` reflects the new scores
    immediately after interview completion — no waiting on the async ARQ
    `ability_diagnose` worker.

    Mirrors `app.agents.nodes.ability_diagnose.update_dimensions` but is
    synchronous and LLM-free. Failures are logged and swallowed: an ability
    sync failure MUST NOT fail the interview completion request.

    Module-level (not a method) so it can be invoked from the WebSocket
    interview handler at ``app/api/v1/ws/interview.py`` which runs on its own
    session lifecycle, separate from the HTTP ``InterviewSessionService``.
    """
    try:
        report = await InterviewReportRepo(session).get_by_session_id(session_id)
        if report is None:
            logger.warning(
                "interview.ability_sync.no_report",
                session_id=str(session_id),
                user_id=str(user_id),
            )
            return

        dimension_scores = report.dimension_scores or {}
        if not dimension_scores:
            logger.warning(
                "interview.ability_sync.empty_dimensions",
                session_id=str(session_id),
                user_id=str(user_id),
            )
            return

        await session.execute(
            text("SELECT set_config('app.user_id', :uid, true)"),
            {"uid": str(user_id)},
        )

        upsert_dim = text(
            """INSERT INTO ability_dimensions
            (id, user_id, dimension_key, actual_score, ideal_score,
             sub_scores, is_active, source, last_updated_at,
             created_at, updated_at)
            VALUES (:id, :uid, :dim, :score, 10, '{}'::jsonb,
                    true, 'interview', :now, :now, :now)
            ON CONFLICT (user_id, dimension_key) DO UPDATE
            SET actual_score = EXCLUDED.actual_score,
                source = 'interview',
                last_updated_at = EXCLUDED.last_updated_at,
                updated_at = EXCLUDED.updated_at
            -- self_assessed_score intentionally NOT updated (dual-track)"""
        )

        now = datetime.now(UTC)
        for dim_key, score in dimension_scores.items():
            await session.execute(
                upsert_dim,
                {
                    "id": uuid4(),
                    "uid": user_id,
                    "dim": dim_key,
                    "score": Decimal(str(score)),
                    "now": now,
                },
            )

        # Caller owns the transaction; do not commit here (HTTP/WS session lifecycle).
        await session.flush()
        logger.info(
            "interview.ability_sync.completed",
            session_id=str(session_id),
            user_id=str(user_id),
            dimensions=list(dimension_scores.keys()),
        )
    except Exception:
        logger.error(
            "interview.ability_sync.failed",
            session_id=str(session_id),
            user_id=str(user_id),
            exc_info=True,
        )


class InterviewSessionService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = InterviewSessionRepository(session)

    async def list(self, user_id: UUID, **filters) -> list:
        return await self.repo.list(user_id, **filters)

    async def get(self, id: UUID, user_id: UUID) -> dict:
        session = await self.repo.get(id, user_id)
        if session is None:
            raise HTTPException(status_code=404, detail="Interview session not found")
        return session

    async def create(self, user_id: UUID, data: InterviewSessionCreate) -> dict:
        # 019 — validate job_id (must exist, belong to user, branch_id consistent)
        job = None
        if data.job_id is not None:
            from app.modules.jobs.repository import JobRepository
            job = await JobRepository(self.session).get(data.job_id, user_id)
            if job is None:
                raise HTTPException(
                    status_code=404,
                    detail={
                        "error": {
                            "code": "job.not_found",
                            "message": "Job not found or not owned by current user",
                            "details": {"job_id": str(data.job_id)},
                        }
                    },
                )
            if data.branch_id is not None and job.branch_id is not None \
                    and str(job.branch_id) != str(data.branch_id):
                raise HTTPException(
                    status_code=409,
                    detail={
                        "error": {
                            "code": "job.branch_mismatch",
                            "message": "branch_id does not match job's bound branch",
                            "details": {
                                "job_id": str(data.job_id),
                                "job_branch_id": str(job.branch_id),
                                "session_branch_id": str(data.branch_id),
                            },
                        }
                    },
                )

        # REQ-048 — mode-aware validation (AC-02 / AC-01).
        # INSUFFICIENT_ERROR_POOL: quick_drill requires user has ≥5 status≠mastered errors.
        if job is not None:
            position = job.position
            company = job.company
            branch_id = data.branch_id or job.branch_id
        else:
            position = (data.position or "").strip()
            company = (data.company or "").strip()
            branch_id = data.branch_id
            if not position or not company:
                raise ValueError(
                    "MISSING_INTERVIEW_TARGET",
                    {"required": ["job_id", "position", "company"]},
                )

        if data.mode != "quick_drill" and data.use_variants:
            raise ValueError(
                "INVALID_COMBINATION",
                {"mode": data.mode, "field": "use_variants"},
            )

        if data.mode == "quick_drill":
            available = await self._count_active_errors(user_id)
            if available < 5:
                raise ValueError(
                    "INSUFFICIENT_ERROR_POOL",
                    {"available": available, "required": 5},
                )
        # INVALID_MAX_QUESTIONS: full mode requires max_questions in [10, 15].
        if data.mode == "full":
            if data.max_questions is None:
                data.max_questions = 10
            if data.max_questions not in (10, 15):
                raise ValueError(
                    "INVALID_MAX_QUESTIONS",
                    {"allowed": [10, 15]},
                )

        # REQ-048 — analytics埋点 (event_type='mode_selected') per AC-01.
        await self._record_mode_analytics(user_id, data)

        session = await self.repo.create(
            user_id=user_id,
            position=position,
            company=company,
            branch_id=branch_id,
            mode=data.mode,
            job_id=data.job_id,
        )

        # REQ-048 — persist max_questions + error_question_ids + use_variants.
        if data.mode == "full" and data.max_questions is not None:
            await self.repo.update_max_questions(session.id, data.max_questions)
        if data.mode == "quick_drill" and data.error_question_ids:
            await self.repo.update_error_question_ids(session.id, [str(x) for x in data.error_question_ids])
        if data.mode == "quick_drill" and data.use_variants:
            await self.repo.update_use_variants(session.id, True)

        # Use session.id as the LangGraph thread_id so that the WebSocket
        # handler (which only knows session_id) and the resume service both
        # look up the same checkpoint namespace. Generating a separate uuid4
        # here caused the resume API to find an empty state after restart.
        thread_id = str(session.id)

        await self.repo.update_status(session.id, "pending", thread_id=thread_id)
        await self._invalidate_dashboard(user_id)
        return await self.repo.get(session.id, user_id)

    async def _count_active_errors(self, user_id: UUID) -> int:
        """Count the user's error_questions where status != mastered.

        Used by AC-02 quick_drill mode gating.
        """
        from sqlalchemy import text
        try:
            result = await self.session.execute(
                text(
                    "SELECT COUNT(*) FROM error_questions "
                    "WHERE user_id = :uid AND status != 'mastered' AND deleted_at IS NULL"
                ),
                {"uid": str(user_id)},
            )
            return int(result.scalar() or 0)
        except Exception:
            # On schema/RLS failure fall back to 0 so AC-02 fails closed (422).
            logger.warning("interview.count_active_errors.failed", exc_info=True)
            return 0

    async def _record_mode_analytics(self, user_id: UUID, data: InterviewSessionCreate) -> None:
        """Write an analytics_events row with event_type='mode_selected'.

        Phase 1+2: minimal payload (mode + max_questions if applicable).
        Payload deliberately omits question_text/score/answer per FR-055.
        """
        try:
            from sqlalchemy import text
            payload: dict = {"mode": data.mode}
            if data.max_questions is not None:
                payload["max_questions"] = data.max_questions
            if data.error_question_ids:
                payload["error_question_count"] = len(data.error_question_ids)
            if data.use_variants:
                payload["use_variants"] = True
            async with self.session.begin_nested():
                await self.session.execute(
                    text(
                        "INSERT INTO analytics_events (user_id, event_type, payload) "
                        "VALUES (:uid, 'mode_selected', CAST(:payload AS jsonb))"
                    ),
                    {"uid": str(user_id), "payload": json.dumps(payload, ensure_ascii=False)},
                )
        except Exception:
            # Analytics is best-effort; never fail the create call.
            logger.warning("interview.mode_analytics.failed", exc_info=True)

    async def start(self, id: UUID, user_id: UUID) -> dict:
        session = await self.repo.get(id, user_id)
        if session is None:
            raise HTTPException(status_code=404, detail="Interview session not found")
        if session.status != "pending":
            raise HTTPException(status_code=409, detail=f"Cannot start interview with status '{session.status}'")

        now = datetime.now(UTC)
        thread_id = str(session.id)
        started = await self.repo.update_status(
            id,
            "in_progress",
            thread_id=thread_id,
            started_at=now,
            expected_statuses={"pending"},
        )
        if not started:
            raise HTTPException(
                status_code=409,
                detail="Interview status changed before start",
            )
        await self._invalidate_dashboard(user_id)

        plan_fields = {
            "plan_status": getattr(session, "plan_status", None),
            "plan_error_code": getattr(session, "plan_error_code", None),
            "plan_error_message": getattr(session, "plan_error_message", None),
            "degraded": bool(getattr(session, "degraded", False)),
        }
        # REQ-058 — prewarm plan for full mode on start (contracts/plan-lifecycle.md)
        if (session.mode or "full") == "full":
            try:
                plan_fields = await asyncio.wait_for(
                    self._ensure_plan(id, user_id),
                    timeout=PLAN_PREWARM_TIMEOUT_SECONDS,
                )
            except TimeoutError:
                msg = "面试计划生成超时，请稍后重试或确认降级后继续。"
                await self.repo.update_plan_lifecycle(
                    id,
                    plan_status="failed",
                    plan_error_code="PLAN_PREWARM_TIMEOUT",
                    plan_error_message=msg,
                    degraded=False,
                )
                logger.warning(
                    "plan.failed_visible",
                    session_id=str(id),
                    code="PLAN_PREWARM_TIMEOUT",
                    timeout_seconds=PLAN_PREWARM_TIMEOUT_SECONDS,
                )
                plan_fields = {
                    "plan_status": "failed",
                    "plan_error_code": "PLAN_PREWARM_TIMEOUT",
                    "plan_error_message": msg,
                    "degraded": False,
                }

        return {
            "id": str(session.id),
            "status": "in_progress",
            "thread_id": thread_id,
            "started_at": now.isoformat(),
            "job_id": str(session.job_id) if session.job_id else None,
            "branch_id": str(session.branch_id) if session.branch_id else None,
            **plan_fields,
        }

    async def _ensure_plan(self, id: UUID, user_id: UUID) -> dict:
        """Idempotent plan ensure: reuse ready plan or generate; map quota → failed.

        Returns plan_status fields for API responses. Logs ``plan.prewarm`` /
        ``plan.reuse`` / ``plan.failed_visible``.
        """
        from app.agents.interview.plan_questions import is_plan_content_ready
        from app.agents.llm_client import QuotaExceededError

        session = await self.repo.get(id, user_id)
        if session is None:
            raise HTTPException(status_code=404, detail="Interview session not found")

        if bool(getattr(session, "degraded", False)):
            return {
                "plan_status": "degraded",
                "plan_error_code": getattr(session, "plan_error_code", None),
                "plan_error_message": getattr(session, "plan_error_message", None),
                "degraded": True,
            }

        existing_status = getattr(session, "plan_status", None)
        if existing_status == "ready" and is_plan_content_ready(session.interview_plan):
            logger.info("plan.reuse", session_id=str(id), reason="already_ready")
            return {
                "plan_status": "ready",
                "plan_error_code": None,
                "plan_error_message": None,
                "degraded": False,
            }

        if existing_status == "failed":
            logger.info("plan.failed_visible", session_id=str(id), reused=True)
            return {
                "plan_status": "failed",
                "plan_error_code": getattr(session, "plan_error_code", None),
                "plan_error_message": getattr(session, "plan_error_message", None),
                "degraded": False,
            }

        await self.repo.update_plan_lifecycle(id, plan_status="pending", clear_errors=True)
        logger.info("plan.prewarm", session_id=str(id), mode=session.mode)

        try:
            result = await self.generate_plan(id, user_id, _from_ensure=True)
        except QuotaExceededError as exc:
            msg = "本月 AI 额度不足，无法生成面试计划。请升级套餐或确认降级后继续通用题面试。"
            await self.repo.update_plan_lifecycle(
                id,
                plan_status="failed",
                plan_error_code="QUOTA_EXCEEDED",
                plan_error_message=msg,
                degraded=False,
            )
            logger.warning(
                "plan.failed_visible",
                session_id=str(id),
                code="QUOTA_EXCEEDED",
                used=getattr(exc, "used", None),
                quota=getattr(exc, "quota", None),
            )
            return {
                "plan_status": "failed",
                "plan_error_code": "QUOTA_EXCEEDED",
                "plan_error_message": msg,
                "degraded": False,
            }
        except Exception as exc:
            msg = "面试计划生成失败，请稍后重试或确认降级后继续。"
            await self.repo.update_plan_lifecycle(
                id,
                plan_status="failed",
                plan_error_code="PLAN_GENERATE_FAILED",
                plan_error_message=msg,
                degraded=False,
            )
            logger.warning(
                "plan.failed_visible",
                session_id=str(id),
                code="PLAN_GENERATE_FAILED",
                error=str(exc),
            )
            return {
                "plan_status": "failed",
                "plan_error_code": "PLAN_GENERATE_FAILED",
                "plan_error_message": msg,
                "degraded": False,
            }

        plan = result.get("interview_plan") if isinstance(result, dict) else None
        if result.get("plan_status") == "failed":
            return {
                "plan_status": "failed",
                "plan_error_code": result.get("plan_error_code"),
                "plan_error_message": result.get("plan_error_message"),
                "degraded": False,
            }

        if is_plan_content_ready(plan if isinstance(plan, dict) else None):
            await self.repo.update_plan_lifecycle(
                id, plan_status="ready", clear_errors=True, degraded=False
            )
            logger.info("plan.prewarm", session_id=str(id), outcome="ready")
            return {
                "plan_status": "ready",
                "plan_error_code": None,
                "plan_error_message": None,
                "degraded": False,
            }

        msg = "面试计划内容不完整，无法开始正式出题。请重试或确认降级。"
        await self.repo.update_plan_lifecycle(
            id,
            plan_status="failed",
            plan_error_code="PLAN_GENERATE_FAILED",
            plan_error_message=msg,
            degraded=False,
        )
        logger.warning("plan.failed_visible", session_id=str(id), code="EMPTY_PLAN")
        return {
            "plan_status": "failed",
            "plan_error_code": "PLAN_GENERATE_FAILED",
            "plan_error_message": msg,
            "degraded": False,
        }

    async def confirm_plan_degrade(self, id: UUID, user_id: UUID, *, confirm: bool = True) -> dict:
        """REQ-058 US4 / REQ-061 — user confirms continuing without a ready plan."""
        from app.modules.ai_runtime.adapters import interview as iv

        session = await self.repo.get(id, user_id)
        if session is None:
            raise HTTPException(status_code=404, detail="Interview session not found")
        if not confirm:
            raise HTTPException(status_code=400, detail="confirm must be true")
        decision = iv.decide_degradation(
            plan_status=str(getattr(session, "plan_status", None) or ""),
            user_consented=True,
            allow_degrade_on_quote=True,
        )
        if not decision.allowed:
            raise HTTPException(
                status_code=409,
                detail=decision.metadata.get("reason_code")
                or decision.reason
                or "degradation not allowed",
            )
        await self.repo.update_plan_lifecycle(
            id,
            plan_status="degraded",
            degraded=True,
        )
        logger.info("plan.failed_visible", session_id=str(id), degraded=True)
        runtime = self._build_runtime_envelope(session, domain_status="in_progress")
        return {
            "id": str(id),
            "plan_status": "degraded",
            "degraded": True,
            "plan_error_code": getattr(session, "plan_error_code", None),
            "plan_error_message": getattr(session, "plan_error_message", None),
            "runtime": runtime,
            "available_actions": runtime["available_actions"],
            "task_id": runtime["task_id"],
            "execution_id": runtime["execution_id"],
        }

    def _plan_seed_kwargs(self, session) -> dict:
        """Build graph seed fields from a ready/degraded session plan."""
        from app.agents.interview.plan_questions import is_plan_content_ready

        plan = session.interview_plan if isinstance(session.interview_plan, dict) else None
        status = getattr(session, "plan_status", None)
        degraded = bool(getattr(session, "degraded", False))
        seed: dict = {
            "plan_status": status,
            "degraded": degraded,
        }
        if plan and (status in ("ready", "degraded") or is_plan_content_ready(plan)):
            seed["interview_plan"] = plan
            if session.web_research is not None:
                seed["web_research"] = session.web_research
            difficulty = plan.get("interview_difficulty") or plan.get("difficulty")
            if isinstance(difficulty, str) and difficulty.strip():
                seed["difficulty"] = difficulty.strip().lower()
            focuses = plan.get("focus_areas") or []
            seed["planner_focus_area_count"] = len(
                [a for a in focuses if isinstance(a, dict) and a.get("area")]
            )
        return seed

    async def generate_plan(
        self, id: UUID, user_id: UUID, *, _from_ensure: bool = False
    ) -> dict:
        session = await self.repo.get(id, user_id)
        if session is None:
            raise HTTPException(status_code=404, detail="Interview session not found")

        from app.agents.interview.plan_questions import is_plan_content_ready

        if session.interview_plan and is_plan_content_ready(session.interview_plan):
            if not _from_ensure:
                logger.info("plan.reuse", session_id=str(id), via="generate_plan")
            return {
                "id": str(session.id),
                "interview_plan": session.interview_plan,
                "web_research": session.web_research,
                "plan_status": getattr(session, "plan_status", None) or "ready",
            }

        from app.agents.interview.nodes.planner_context import planner_context_node
        from app.agents.interview.nodes.planner_generate import planner_generate_node
        from app.agents.interview.nodes.planner_search import planner_search_node
        from app.agents.llm_client import QuotaExceededError

        state = {
            "messages": [],
            "thread_id": session.thread_id or str(session.id),
            "user_id": str(user_id),
            "position": session.position or "",
            "company": session.company or "",
            "branch_id": str(session.branch_id) if session.branch_id else None,
            "job_id": str(session.job_id) if session.job_id else None,
            "mode": session.mode,
            "max_questions": session.max_questions,
            "error_question_ids": [str(x) for x in session.error_question_ids or []],
            "interview_plan": None,
            "web_research": None,
        }

        try:
            state.update(await planner_context_node(state))
            state.update(await planner_search_node(state))
            state.update(await planner_generate_node(state))
        except QuotaExceededError:
            raise

        planner_values = self._extract_planner_outputs(state)
        plan = planner_values.get("interview_plan")
        plan_error = None
        if isinstance(state, dict):
            plan_error = state.get("plan_error") or (
                plan.get("_error") if isinstance(plan, dict) else None
            )

        if isinstance(plan, dict):
            plan = self._merge_session_targets_into_plan(
                plan,
                position=session.position,
                company=session.company,
            )
            # Strip internal error marker before persist
            plan.pop("_error", None)
            plan.pop("plan_error_code", None)

        failed = False
        error_code = None
        error_message = None
        if isinstance(plan_error, dict):
            failed = True
            error_code = plan_error.get("code") or "PLAN_GENERATE_FAILED"
            error_message = plan_error.get("message") or "面试计划生成失败"
        elif not is_plan_content_ready(plan if isinstance(plan, dict) else None):
            failed = True
            error_code = "PLAN_GENERATE_FAILED"
            error_message = "面试计划生成失败或内容为空"

        await self.repo.update_planner_outputs(
            id,
            interview_plan=plan if isinstance(plan, dict) and not failed else (
                plan if isinstance(plan, dict) else None
            ),
            web_research=planner_values.get("web_research"),
        )

        if failed:
            await self.repo.update_plan_lifecycle(
                id,
                plan_status="failed",
                plan_error_code=error_code,
                plan_error_message=error_message,
                degraded=False,
            )
            logger.warning(
                "plan.failed_visible",
                session_id=str(id),
                code=error_code,
            )
            return {
                "id": str(session.id),
                "interview_plan": None,
                "web_research": planner_values.get("web_research"),
                "plan_status": "failed",
                "plan_error_code": error_code,
                "plan_error_message": error_message,
            }

        await self.repo.update_plan_lifecycle(
            id, plan_status="ready", clear_errors=True, degraded=False
        )
        return {
            "id": str(session.id),
            "interview_plan": plan if isinstance(plan, dict) else None,
            "web_research": planner_values.get("web_research"),
            "plan_status": "ready",
        }

    async def get_report(self, id: UUID, user_id: UUID) -> dict | None:
        session = await self.repo.get(id, user_id)
        if session is None:
            raise HTTPException(status_code=404, detail="Interview session not found")
        if session.status != "completed":
            return None

        report_repo = InterviewReportRepo(self.session)
        report = await report_repo.get_by_session_id(id)
        if report is None:
            return None
        report_dict = report.model_dump()
        report_dict["interview_plan"] = session.interview_plan
        report_dict["web_research"] = session.web_research

        per_q = report_dict.get("per_question_score", []) or []
        needs_backfill = any(
            isinstance(q, dict) and not q.get("question_text")
            for q in per_q
        )
        if needs_backfill:
            from app.agents.checkpointer import get_graph_config
            from app.agents.interview.graph import get_interview_graph

            # Historical bug: checkpoints are stored under session_id, not the
            # recorded thread_id. Try both keys for safety.
            lookup_keys = [str(id)]
            if session.thread_id and str(session.thread_id) != str(id):
                lookup_keys.append(str(session.thread_id))

            try:
                graph = await get_interview_graph().build_graph()
                questions = None
                user_answers = None
                for key in lookup_keys:
                    try:
                        state = await graph.aget_state(await get_graph_config(key))
                    except Exception:
                        continue
                    values = state.values if state.values else {}
                    qs = values.get("questions") or []
                    if not qs:
                        continue
                    questions = qs
                    msgs = values.get("messages") or []
                    user_answers = [
                        (m.get("content", "") if isinstance(m, dict) else getattr(m, "content", "") or "")
                        for m in msgs
                        if (isinstance(m, dict) and m.get("role") == "user")
                        or (not isinstance(m, dict) and getattr(m, "type", "") == "human")
                    ]
                    break

                if questions:
                    # user_answers[0] is the self-intro at the intake step. Skip it.
                    answers_for_q = user_answers[1:1 + len(questions)] if user_answers else []
                    for i, q in enumerate(per_q):
                        if not isinstance(q, dict):
                            continue
                        if not q.get("question_text") and i < len(questions):
                            q["question_text"] = questions[i].get("question", "")
                        if not q.get("user_answer") and i < len(answers_for_q):
                            q["user_answer"] = answers_for_q[i]
                    report_dict["per_question_score"] = per_q
            except Exception:
                # On any error, return the report as-is — UI shows fallback placeholders.
                pass

        return report_dict

    async def submit_answer(self, id: UUID, user_id: UUID, answer: str, sequence_no: int) -> dict:
        session = await self.repo.get(id, user_id)
        if session is None:
            raise HTTPException(status_code=404, detail="Interview session not found")
        if session.status != "in_progress":
            raise HTTPException(status_code=409, detail=f"Cannot submit answer for status '{session.status}'")

        thread_id = session.thread_id
        if not thread_id:
            raise HTTPException(status_code=400, detail="No active interview thread")

        graph = get_interview_graph()
        plan_seed = self._plan_seed_kwargs(session)
        try:
            result = await graph.submit_answer(
                thread_id=thread_id,
                answer=answer,
                sequence_no=sequence_no,
                user_id=str(user_id),
                position=session.position,
                company=session.company,
                branch_id=str(session.branch_id) if session.branch_id else None,
                job_id=str(session.job_id) if session.job_id else None,
                mode=session.mode,
                max_questions=session.max_questions,
                error_question_ids=[str(x) for x in session.error_question_ids or []],
                use_variants=bool(getattr(session, "use_variants", False)),
                **plan_seed,
            )
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"Graph execution failed: {exc}") from exc

        planner_values = self._extract_planner_outputs(result)
        if not planner_values.get("interview_plan"):
            try:
                graph_state = await graph.get_current_state(thread_id)
                planner_values = self._extract_planner_outputs(
                    graph_state.get("values", {})
                )
            except Exception:
                logger.warning(
                    "interview.planner_outputs.lookup_failed",
                    session_id=str(id),
                    exc_info=True,
                )
        if planner_values.get("interview_plan") or planner_values.get("web_research"):
            if (
                session.mode == "doubao"
                and isinstance(planner_values.get("interview_plan"), dict)
            ):
                planner_values["interview_plan"] = self._merge_session_targets_into_plan(
                    planner_values["interview_plan"],
                    position=session.position,
                    company=session.company,
                )
            await self.repo.update_planner_outputs(
                id,
                interview_plan=planner_values.get("interview_plan"),
                web_research=planner_values.get("web_research"),
            )

        # Check if interview completed (report node ran — not a fixed score count).
        from app.modules.interviews.completion import is_interview_graph_complete

        if is_interview_graph_complete(result):
            overall = result.get("overall_score", 0)
            now = datetime.now(UTC)
            started = session.started_at
            duration = int((now - started).total_seconds()) if started else 0
            await self.repo.update_status(
                id, "completed", ended_at=now, duration_sec=duration, overall_score=float(overall)
            )

            # Write report
            report_data = result.get("interview_report", {})
            if report_data:
                from app.domain.interview_report import InterviewReportCreate
                report_repo = InterviewReportRepo(self.session)
                await report_repo.create(InterviewReportCreate(
                    overall_score=float(overall),
                    per_question_score=report_data.get("per_question_score", []),
                    dimension_scores=report_data.get("dimension_scores", {}),
                    strengths=report_data.get("strengths", []),
                    improvements=report_data.get("improvements", []),
                    summary_md=report_data.get("summary_md", ""),
                    session_id=id,
                ))

            # Synchronously upsert per-dimension scores so /ability-profile
            # reflects the new scores immediately. The async arq job below
            # still runs for LLM-generated insights and history snapshots.
            await sync_ability_dimensions(self.session, id, user_id)

            # Enqueue ability diagnosis so the dashboard reflects interview scores.
            # Best-effort — failure here must not fail the API request.
            try:
                from app.core.redis import enqueue_job
                await enqueue_job(
                    "ability_diagnose",
                    user_id=str(user_id),
                    session_id=str(id),
                )
            except Exception:
                import logging
                logging.getLogger(__name__).warning(
                    "ability_diagnose.enqueue_failed", exc_info=True
                )

        return result

    @staticmethod
    def _extract_planner_outputs(payload: object) -> dict[str, dict | None]:
        if hasattr(payload, "model_dump"):
            payload = payload.model_dump()
        if not isinstance(payload, dict):
            return {"interview_plan": None, "web_research": None}
        values = payload.get("values")
        if isinstance(values, dict):
            payload = values
        return {
            "interview_plan": payload.get("interview_plan"),
            "web_research": payload.get("web_research"),
        }

    @staticmethod
    def _merge_session_targets_into_plan(
        plan: dict,
        *,
        position: str | None,
        company: str | None,
    ) -> dict:
        merged = dict(plan)
        if position and position.strip():
            merged["target_position"] = position.strip()
        if company and company.strip():
            merged["target_company"] = company.strip()
        return merged

    async def render_card(
        self,
        session_id: UUID,
        user_id: UUID,
        size_variant: str = "4_3",
    ) -> dict:
        """REQ-048 US4 / T087 — Render the doubao card for a session.

        Flow (per AC-22 + AC-24):
        1. Load the session row + interview_plan.
        2. If mode != 'doubao' OR interview_plan missing → raise ValueError
           (``INTERVIEW_PLAN_NOT_READY`` → 422 per AC-22).
        3. Compute plan hash → check Redis cache; on hit, return bytes
           + ``cache_hit=True``.
        4. Otherwise, call :class:`CardRenderer` → write cache (7-day
           TTL per AC-24) → return envelope.

        Side effect: writes an ``analytics_events`` row with
        ``event_type='doubao_card_rendered'`` and a PII-free payload
        (size_variant + duration_ms + cache_hit + file_size_bytes per
        AC-19 / AC-19b).
        """
        from app.services.card_renderer.cache import (
            build_card_cache_key,
            compute_plan_hash,
            default_ttl_seconds,
            get_cached,
            set_cached,
            CardCacheEntry,
        )
        from app.services.card_renderer.renderer import CardRenderer
        import base64
        import json
        import time
        from datetime import UTC, datetime

        session = await self.repo.get(session_id, user_id)
        if session is None:
            raise ValueError("INTERVIEW_PLAN_NOT_READY")

        mode = getattr(session, "mode", None)
        if mode != "doubao":
            raise ValueError("INTERVIEW_PLAN_NOT_READY")

        plan = getattr(session, "interview_plan", None) or {}
        if not isinstance(plan, dict) or not plan:
            raise ValueError("INTERVIEW_PLAN_NOT_READY")
        plan = self._merge_session_targets_into_plan(
            plan,
            position=getattr(session, "position", None),
            company=getattr(session, "company", None),
        )

        # The cache key is hash(JD + plan fields). Use position +
        # company as the JD surrogate so the hash stays stable when
        # the same user re-renders the same session.
        jd_text = f"{getattr(session, 'position', None) or ''}|{getattr(session, 'company', None) or ''}"
        plan_hash = compute_plan_hash(plan)

        cache_key = build_card_cache_key(str(user_id), jd_text, plan_hash)

        # 1. Try cache (AC-24).
        cached_entry = None
        try:
            from app.core.redis import get_redis

            redis_client = await get_redis()
            cached_entry = await get_cached(redis_client, str(user_id), jd_text, plan_hash)
        except Exception:
            cached_entry = None

        if cached_entry is not None:
            image_bytes = cached_entry.image_bytes()
            result = {
                "image_bytes": image_bytes,
                "size_variant": cached_entry.size_variant or size_variant,
                "sha256_hex": cached_entry.sha256_hex,
                "bytes_total": cached_entry.bytes_total,
                "cache_hit": True,
            }
            await self._record_card_render_analytics(
                user_id=user_id,
                size_variant=result["size_variant"],
                duration_ms=0,
                cache_hit=True,
                file_size_bytes=result["bytes_total"],
            )
            return result

        # 2. Render via the renderer (AC-17a / AC-17b).
        start_ms = int(time.time() * 1000)
        renderer = CardRenderer()
        rendered = await renderer.render(plan, size_variant=size_variant)
        duration_ms = int(time.time() * 1000) - start_ms

        # 3. Write cache (best-effort — failure is not fatal).
        try:
            from app.core.redis import get_redis

            redis_client = await get_redis()
            entry = CardCacheEntry(
                user_id=str(user_id),
                cache_key=cache_key,
                image_bytes_b64=base64.b64encode(rendered.image_bytes).decode("ascii"),
                sha256_hex=rendered.sha256_hex,
                bytes_total=rendered.bytes_total,
                size_variant=rendered.size_variant,
                cached_at_iso=datetime.now(UTC).isoformat(),
                ttl_seconds=default_ttl_seconds(),
            )
            await set_cached(redis_client, entry)
        except Exception as exc:
            logger.warning("interview.card.cache_write_failed", exc_info=True)

        # 4. Analytics — payload is PII-free per AC-19 + AC-19b.
        await self._record_card_render_analytics(
            user_id=user_id,
            size_variant=rendered.size_variant,
            duration_ms=duration_ms,
            cache_hit=False,
            file_size_bytes=rendered.bytes_total,
        )

        return {
            "image_bytes": rendered.image_bytes,
            "size_variant": rendered.size_variant,
            "sha256_hex": rendered.sha256_hex,
            "bytes_total": rendered.bytes_total,
            "cache_hit": False,
        }

    async def _record_card_render_analytics(
        self,
        *,
        user_id: UUID,
        size_variant: str,
        duration_ms: int,
        cache_hit: bool,
        file_size_bytes: int,
    ) -> None:
        """REQ-048 US4 / T088 — analytics_events INSERT (PII-free per AC-19)."""
        try:
            from sqlalchemy import text

            payload = {
                "size_variant": size_variant,
                "duration_ms": int(duration_ms),
                "cache_hit": bool(cache_hit),
                "file_size_bytes": int(file_size_bytes),
            }
            async with self.session.begin_nested():
                await self.session.execute(
                    text(
                        "INSERT INTO analytics_events (user_id, event_type, payload) "
                        "VALUES (:uid, 'doubao_card_rendered', CAST(:payload AS jsonb))"
                    ),
                    {"uid": str(user_id), "payload": json.dumps(payload, ensure_ascii=False)},
                )
        except Exception:
            logger.warning("interview.card_analytics.failed", exc_info=True)

    async def delete(self, id: UUID, user_id: UUID) -> None:
        session = await self.repo.get(id, user_id)
        if session is None:
            raise HTTPException(status_code=404, detail="Interview session not found")
        deleted = await self.repo.soft_delete(id, user_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="Interview session not found")

    async def _sync_ability_dimensions(self, session_id: UUID, user_id: UUID) -> None:
        """Backwards-compat shim — delegates to the module-level
        :func:`sync_ability_dimensions`. Kept so any external caller that
        bound to the method still works. New callers should use the module
        function so it can be invoked from non-service paths (e.g. the
        WebSocket interview handler that runs on its own session).
        """
        await sync_ability_dimensions(self.session, session_id, user_id)

    async def resume(self, id: UUID, user_id: UUID) -> dict:
        session = await self.repo.get(id, user_id)
        if session is None:
            raise HTTPException(status_code=404, detail="Interview session not found")
        if session.status == "completed":
            raise HTTPException(status_code=409, detail="Interview already completed")
        if session.status == "expired":
            raise HTTPException(status_code=410, detail="Interview session expired")

        thread_id = session.thread_id
        if not thread_id:
            raise HTTPException(status_code=400, detail="No active interview thread")

        graph = get_interview_graph()
        # Try session_id first (WebSocket handler always writes under
        # session_id, and new sessions store thread_id == session_id).
        # Fall back to the recorded thread_id for backwards compat with
        # legacy sessions whose thread_id was a separate uuid4.
        candidate_keys: list[str] = []
        for key in (str(id), str(thread_id)):
            if key and key not in candidate_keys:
                candidate_keys.append(key)

        state: dict = {}
        for key in candidate_keys:
            state = await graph.get_current_state(key)
            if state and state.get("values"):
                break
        if not state:
            state = await graph.get_current_state(candidate_keys[0])

        runtime = self._build_runtime_envelope(session)
        values = state.get("values") or {}
        scores = values.get("scores") or []
        saved_explanation = None
        if scores:
            saved_explanation = (
                f"已恢复第 {len(scores)} 轮评分与回答，可继续作答。"
            )
        runtime["saved_round_explanation"] = saved_explanation
        return {
            **state,
            "task_id": runtime["task_id"],
            "execution_id": runtime["execution_id"],
            "available_actions": runtime["available_actions"],
            "points_summary": runtime["points_summary"],
            "saved_round_explanation": saved_explanation,
            "runtime": runtime,
        }

    # ---- REQ-061 US4 runtime / pause / retry / active-end --------------------

    @staticmethod
    def _runtime_ids(session_id: UUID) -> tuple[UUID, UUID]:
        """Stable task/execution IDs derived from session until acceptance binds."""
        from uuid import NAMESPACE_URL, uuid5

        task_id = uuid5(NAMESPACE_URL, f"interview-task:{session_id}")
        execution_id = uuid5(NAMESPACE_URL, f"interview-exec:{session_id}")
        return task_id, execution_id

    @staticmethod
    def _read_pause_meta(session) -> dict | None:
        wr = session.web_research if isinstance(getattr(session, "web_research", None), dict) else {}
        meta = wr.get("_ai_runtime") if isinstance(wr, dict) else None
        return meta if isinstance(meta, dict) else None

    async def _write_pause_meta(self, session, *, deadline: str | None, paused: bool) -> None:
        wr = dict(session.web_research) if isinstance(session.web_research, dict) else {}
        runtime = dict(wr.get("_ai_runtime") or {})
        if paused and deadline:
            runtime["paused"] = True
            runtime["pause_deadline"] = deadline
        else:
            runtime.pop("paused", None)
            runtime.pop("pause_deadline", None)
        if runtime:
            wr["_ai_runtime"] = runtime
        elif "_ai_runtime" in wr:
            del wr["_ai_runtime"]
        await self.repo.update_planner_outputs(session.id, web_research=wr or None)

    def _pause_deadline_for(self, session) -> str | None:
        meta = self._read_pause_meta(session)
        if meta and meta.get("pause_deadline"):
            return str(meta["pause_deadline"])
        return None

    def _domain_status_for(self, session) -> str:
        meta = self._read_pause_meta(session)
        if meta and meta.get("paused"):
            return "paused"
        return str(getattr(session, "status", "pending") or "pending")

    def _build_runtime_envelope(
        self,
        session,
        *,
        domain_status: str | None = None,
        events: list | None = None,
        failure: dict | None = None,
        settled_points: int = 0,
        chargeable: list[str] | None = None,
    ) -> dict:
        from app.modules.ai_runtime.adapters import interview as iv

        status = domain_status or self._domain_status_for(session)
        task_id, execution_id = self._runtime_ids(session.id)
        actions = iv.projection_actions(status)
        pause_deadline = self._pause_deadline_for(session)
        points = {
            "reserved": 200,
            "settled": settled_points,
            "currency": "points",
            "chargeable_milestones": list(chargeable or []),
        }
        return {
            "task_id": str(task_id),
            "execution_id": str(execution_id),
            "available_actions": actions,
            "events": list(events or []),
            "points_summary": points,
            "failure": failure,
            "pause_deadline": pause_deadline,
            "saved_round_explanation": None,
        }

    async def pause_session(self, id: UUID, user_id: UUID) -> dict:
        """REQ-061 — pause interview (waiting_user) with 7-day deadline.

        Domain status ``paused`` is projected via web_research._ai_runtime so we
        do not need a DB CHECK constraint change for interview_sessions.status.
        """
        from app.agents.graphs.interview import InterviewRuntimeBridge
        from app.modules.ai_runtime.adapters import interview as iv

        session = await self.repo.get(id, user_id)
        if session is None:
            raise HTTPException(status_code=404, detail="Interview session not found")
        # Map pending/in_progress onto pausable domain states.
        domain = "awaiting_answer" if session.status in {"pending", "in_progress"} else str(session.status)
        decision = iv.decide_pause(domain_status=domain)
        if not decision.allowed:
            raise HTTPException(status_code=409, detail=decision.reason)

        deadline = decision.metadata.get("pause_deadline")
        await self._write_pause_meta(session, deadline=deadline, paused=True)
        session = await self.repo.get(id, user_id)
        bridge = InterviewRuntimeBridge()
        checkpoint = bridge.pause_checkpoint(
            session_id=str(id),
            round_no=0,
            scores=[],
            schema_version="2",
        )
        runtime = self._build_runtime_envelope(session, domain_status="paused")
        runtime["pause_deadline"] = deadline
        runtime["available_actions"] = iv.projection_actions("paused")
        return {
            "id": str(id),
            "status": "paused",
            "pause_deadline": deadline,
            "checkpoint": checkpoint,
            "task_id": runtime["task_id"],
            "execution_id": runtime["execution_id"],
            "available_actions": runtime["available_actions"],
            "points_summary": runtime["points_summary"],
            "runtime": runtime,
        }

    async def resume_from_pause(self, id: UUID, user_id: UUID) -> dict:
        """REQ-061 — resume a paused interview within the 7-day window."""
        from app.modules.ai_runtime.adapters import interview as iv

        session = await self.repo.get(id, user_id)
        if session is None:
            raise HTTPException(status_code=404, detail="Interview session not found")
        deadline = self._pause_deadline_for(session)
        decision = iv.decide_resume(
            domain_status="paused",
            pause_deadline=deadline,
        )
        if not decision.allowed:
            code = decision.metadata.get("reason_code")
            status = 410 if code == "PAUSE_EXPIRED" else 409
            raise HTTPException(status_code=status, detail=decision.reason)

        await self._write_pause_meta(session, deadline=None, paused=False)
        if session.status == "pending":
            await self.repo.update_status(id, "in_progress", started_at=datetime.now(UTC))
        session = await self.repo.get(id, user_id)
        runtime = self._build_runtime_envelope(session, domain_status="in_progress")
        return {
            "id": str(id),
            "status": "in_progress",
            "task_id": runtime["task_id"],
            "execution_id": runtime["execution_id"],
            "available_actions": runtime["available_actions"],
            "points_summary": runtime["points_summary"],
            "runtime": runtime,
        }

    async def active_end_session(
        self,
        id: UUID,
        user_id: UUID,
        *,
        scored_rounds: int = 0,
        generate_partial_report: bool | None = None,
    ) -> dict:
        """REQ-061 — active end with optional partial report milestone settlement."""
        from app.modules.ai_runtime.adapters import interview as iv

        session = await self.repo.get(id, user_id)
        if session is None:
            raise HTTPException(status_code=404, detail="Interview session not found")
        decision = iv.decide_active_end(
            domain_status=str(session.status or "in_progress"),
            scored_rounds=int(scored_rounds),
            generate_partial_report=generate_partial_report,
        )
        if not decision.allowed:
            raise HTTPException(status_code=409, detail=decision.reason)
        if decision.metadata.get("requires_partial_report_choice"):
            runtime = self._build_runtime_envelope(session)
            return {
                "id": str(id),
                "status": session.status,
                "requires_partial_report_choice": True,
                "scored_rounds": scored_rounds,
                "available_actions": ["confirm_partial_report", "skip_report", "cancel"],
                "runtime": runtime,
                "task_id": runtime["task_id"],
                "execution_id": runtime["execution_id"],
                "points_summary": runtime["points_summary"],
            }

        chargeable = list(decision.metadata.get("chargeable_milestones") or [])
        # Soft-complete without forcing report node when partial report declined.
        now = datetime.now(UTC)
        await self.repo.update_status(
            id,
            "completed" if generate_partial_report else "completed",
            ended_at=now,
        )
        session = await self.repo.get(id, user_id)
        runtime = self._build_runtime_envelope(
            session,
            domain_status="partial_report",
            settled_points=40 * max(1, int(scored_rounds)),
            chargeable=chargeable,
        )
        return {
            "id": str(id),
            "status": "partially_succeeded",
            "generate_partial_report": bool(generate_partial_report),
            "scored_rounds": scored_rounds,
            "chargeable_milestones": chargeable,
            "task_id": runtime["task_id"],
            "execution_id": runtime["execution_id"],
            "available_actions": runtime["available_actions"],
            "points_summary": runtime["points_summary"],
            "runtime": runtime,
        }

    async def retry_score_delivery(
        self,
        session_id: UUID,
        user_id: UUID,
        *,
        round_no: int = 1,
        score_payload: dict | None = None,
        dry_run: bool = False,
    ) -> dict:
        """Independently retry score delivery; evidence-gated (T075)."""
        from app.modules.ai_runtime.adapters import interview as iv

        decision = iv.decide_retry(domain_status="retry_wait", component="score_delivery")
        gate = iv.evaluate_quality_gate(
            milestone_code="round_score",
            result_payload=score_payload
            or {"round_no": round_no, "score": 0, "feedback": ""},
        )
        allowed = decision.allowed and (gate.deliverable if score_payload else True)
        result = {
            "allowed": allowed,
            "component": "score_delivery",
            "dry_run": dry_run,
            "gate": {
                "code": gate.code,
                "deliverable": gate.deliverable,
                "chargeable": gate.chargeable,
            },
            "new_execution_required": decision.metadata.get("new_execution_required"),
        }
        if dry_run or not allowed:
            return result
        # Live path: evidence must pass before marking deliverable.
        if not gate.deliverable:
            result["allowed"] = False
            return result
        result["delivered"] = True
        return result

    async def retry_next_question(
        self,
        session_id: UUID,
        user_id: UUID,
        *,
        dry_run: bool = False,
        evidence: dict | None = None,
    ) -> dict:
        from app.modules.ai_runtime.adapters import interview as iv

        decision = iv.decide_retry(domain_status="failed", component="next_question")
        has_evidence = bool(evidence and evidence.get("question"))
        allowed = decision.allowed and (has_evidence or dry_run)
        return {
            "allowed": allowed,
            "component": "next_question",
            "dry_run": dry_run,
            "evidence_gated": True,
            "new_execution_required": True,
        }

    async def retry_report_assembly(
        self,
        session_id: UUID,
        user_id: UUID,
        *,
        dry_run: bool = False,
        report_payload: dict | None = None,
    ) -> dict:
        from app.modules.ai_runtime.adapters import interview as iv

        decision = iv.decide_retry(domain_status="partial_report", component="report")
        gate = iv.evaluate_quality_gate(
            milestone_code="report",
            result_payload=report_payload,
        )
        allowed = decision.allowed and (gate.deliverable if report_payload else dry_run)
        return {
            "allowed": bool(allowed),
            "component": "report",
            "dry_run": dry_run,
            "gate": {
                "code": gate.code,
                "deliverable": gate.deliverable,
                "chargeable": gate.chargeable,
                "partial": gate.metadata.get("partial"),
            },
            "new_execution_required": True,
        }

    async def retry_plan_fallback(
        self,
        session_id: UUID,
        user_id: UUID,
        *,
        dry_run: bool = False,
        consented: bool = False,
    ) -> dict:
        from app.modules.ai_runtime.adapters import interview as iv

        decision = iv.decide_retry(domain_status="failed", component="plan_fallback")
        degrade = iv.decide_degradation(
            plan_status="failed",
            user_consented=consented,
            allow_degrade_on_quote=True,
        )
        allowed = decision.allowed and (degrade.allowed or dry_run)
        return {
            "allowed": bool(allowed),
            "component": "plan_fallback",
            "dry_run": dry_run,
            "consented": consented,
            "degrade_allowed": degrade.allowed,
            "new_execution_required": True,
        }

    @staticmethod
    async def _invalidate_dashboard(user_id: UUID) -> None:
        try:
            from app.modules.dashboard.cache import cache_invalidate

            await cache_invalidate(user_id)
        except Exception:
            pass


__all__ = ["InterviewSessionService"]
