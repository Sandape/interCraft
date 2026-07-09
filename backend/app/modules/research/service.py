"""Service layer for the interview-research module (REQ-053).

Orchestrates:
- Keyword extraction (LLM)
- 4-dimension parallel search via Tavily with retry
- 24h same-company cache lookup
- User weakness query (local DB)
- Report generation via LLM with quality check + retry
- Delivery via WeChat / notification fallback

Metrics (FR-023) are emitted via app.modules.research.metrics.
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
import time
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session_factory
from app.modules.research.markdown_converter import (
    DEFAULT_WECHAT_MAX_CHARS,
    convert_markdown_to_plain,
    segment_for_wechat,
)
from app.modules.research.metrics import (
    report_generation_tokens,
    research_duration_seconds,
    research_tasks_total,
    web_search_api_calls_total,
)
from app.modules.research.quality_checker import check_report_quality
from app.modules.research.repository import ResearchResultRepository, ResearchTaskRepository
from app.modules.research.schemas import ResearchStats
from app.repositories.interview_report_repo import InterviewReportRepo

logger = logging.getLogger(__name__)


CACHE_TTL_HOURS = 24
CACHEABLE_DIMENSIONS = ("interview_experience", "company_product")
RETRY_BACKOFFS = [2.0, 4.0, 8.0]


class ResearchService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.task_repo = ResearchTaskRepository(session)
        self.result_repo = ResearchResultRepository(session)
        self.report_repo = InterviewReportRepo(session)

    # --- Scan & scheduling (T034) ---

    async def scan_and_enqueue_jobs(self, *, enqueue_fn) -> dict:
        """Find jobs with interview_time in [now+4h55m, now+5h5m] and enqueue
        research tasks for each. `enqueue_fn(task_id)` should be an
        ARQ-compatible enqueue (e.g. ctx["redis"].enqueue_job).
        """
        now = datetime.now(timezone.utc)
        lower = now + timedelta(hours=4, minutes=55)
        upper = now + timedelta(hours=5, minutes=5)

        matched = await self.task_repo.find_matching_jobs(lower=lower, upper=upper)
        enqueued = 0
        skipped_existing = 0
        for job in matched:
            task_id = await self.task_repo.create(
                job_id=job["job_id"],
                user_id=job["user_id"],
                interview_time=job["interview_time"],
            )
            if task_id is None:
                skipped_existing += 1
                continue
            await enqueue_fn(task_id=str(task_id))
            enqueued += 1

        return {
            "scanned_at": now.isoformat(),
            "matched": len(matched),
            "tasks_created": enqueued,
            "skipped_duplicate": skipped_existing,
        }

    # --- Main pipeline (T051) ---

    async def execute_research_task(self, task_id: UUID) -> dict:
        """Full pipeline: load task → search → generate → quality → save → deliver."""
        task = await self.task_repo.get_by_id(task_id)
        if task is None:
            return {"task_id": str(task_id), "status": "not_found"}
        if task["status"] != "pending":
            return {"task_id": str(task_id), "status": "skipped", "current_status": task["status"]}

        started_at = datetime.now(timezone.utc)
        await self.task_repo.update_status(
            task_id, "running", started_at=started_at
        )
        t0 = time.monotonic()

        try:
            # Load job details
            from app.modules.jobs.repository import JobRepository
            job_repo = JobRepository(self.session)
            job = await job_repo.get(task["job_id"], task["user_id"])
            if job is None:
                raise RuntimeError(f"Job {task['job_id']} not found")

            company = job.company
            position = job.position
            notes_md = job.notes_md or ""

            # 1. Extract business keywords via LLM
            keywords = await self._extract_business_keywords(position, notes_md)

            # 2. Execute 4 search dimensions with cache
            search_results = await self._execute_search_dimensions(
                task_id=task_id,
                company=company,
                position=position,
                keywords=keywords,
            )

            # 3. Read user weakness
            user_weakness = await self._query_user_weakness(task["user_id"])

            # 4. Generate report (with retry on quality fail)
            from app.modules.research.report_generator import generate_research_report
            round_label = self._interview_round_label(task["interview_time"], job.status)
            # REQ-053 US4-AC6: pull same-company history within 7 days for comparison
            historical_comparison = await self._find_historical_comparison(
                user_id=task["user_id"],
                company=company,
                current_dimensions=user_weakness.get("dimensions", []),
            )
            report_md, quality_passed = await self._generate_with_retry(
                company=company,
                position=position,
                interview_time_iso=task["interview_time"].isoformat() if isinstance(task["interview_time"], datetime) else str(task["interview_time"]),
                interview_round=round_label,
                search_results=search_results,
                user_weakness=user_weakness,
                historical_comparison=historical_comparison,
            )

            # 5. Save report
            from app.domain.interview_report import ResearchReportCreate
            report_create = ResearchReportCreate(
                job_id=task["job_id"],
                interview_time=task["interview_time"] if isinstance(task["interview_time"], datetime) else datetime.fromisoformat(str(task["interview_time"])),
                research_task_id=task_id,
                summary_md=report_md,
            )
            saved_report = await self.report_repo.create_research_report(
                report_create, quality_check_passed=quality_passed
            )
            # create_research_report commits; SET LOCAL app.user_id is lost.
            # Re-bind RLS before delivery touches agents / bindings / messages.
            try:
                from app.core.db import set_rls_user_id

                await set_rls_user_id(self.session, task["user_id"])
            except Exception as exc:
                logger.warning("Failed to re-bind RLS after report save: %s", exc)

            # 6. Deliver
            delivery_status = await self._deliver_report(
                user_id=task["user_id"],
                report_id=saved_report.id,
                summary_md=report_md,
                job_company=company,
            )

            # 7. Update task status
            final_status = "completed" if quality_passed else "quality_failed"
            await self.task_repo.update_status(
                task_id, final_status,
                search_dimensions={
                    dim: {"status": "completed" if results else "failed", "count": len(results)}
                    for dim, results in search_results.items()
                },
                report_id=saved_report.id,
                completed_at=datetime.now(timezone.utc),
            )
            # FR-023 metrics
            research_tasks_total.labels(status=final_status).inc()
            research_duration_seconds.observe(time.monotonic() - t0)

            # FR-024 audit log
            try:
                from app.modules.audit.service import AuditService
                duration_ms = int((time.monotonic() - t0) * 1000)
                async with get_session_factory()() as audit_session:
                    audit_svc = AuditService(audit_session)
                    await audit_svc.log(
                        actor_id=task["user_id"],
                        action="research_task_completed",
                        resource_type="interview_research_task",
                        resource_id=task_id,
                        new_values={
                            "report_id": str(saved_report.id),
                            "company": company,
                            "position": position,
                            "interview_time": str(task["interview_time"]),
                            "search_results_count": {k: len(v) for k, v in search_results.items()},
                            "report_length_chars": len(report_md),
                            "quality_check_passed": quality_passed,
                            "delivery_status": delivery_status,
                            "duration_ms": duration_ms,
                        },
                        duration_ms=duration_ms,
                    )
            except Exception as exc:
                logger.warning("Failed to write audit log: %s", exc)

            return {
                "task_id": str(task_id),
                "status": final_status,
                "report_id": str(saved_report.id),
                "delivery_status": delivery_status,
            }
        except Exception as exc:
            logger.exception("execute_research_task failed: %s", exc)
            await self.task_repo.update_status(
                task_id, "failed",
                error_message=str(exc)[:1000],
                completed_at=datetime.now(timezone.utc),
            )
            research_tasks_total.labels(status="failed").inc()
            return {"task_id": str(task_id), "status": "failed", "error": str(exc)}

    # --- Internal helpers ---

    async def _extract_business_keywords(self, position: str, notes_md: str) -> list[str]:
        """REQ-053: LLM extracts 2-3 business keywords from position + notes."""
        try:
            from app.agents.llm_client import get_llm_client
            client = get_llm_client()
            response = await client.invoke(
                messages=[
                    {
                        "role": "system",
                        "content": "从以下岗位信息中提取 2-3 个最核心的业务关键词（用逗号分隔），用于搜索该公司/产品相关信息。只输出关键词，不要解释。",
                    },
                    {"role": "user", "content": f"岗位名: {position}\n备注: {notes_md or '(无)'}"},
                ],
                estimated_tokens=300,
                user_id="research-pipeline",
                thread_id=f"keywords-{position[:20]}",
                node_name="research_keyword_extract",
                max_retries=2,
                timeout_ms=15_000,
            )
            content = response.get("content", "").strip()
            keywords = [k.strip() for k in content.replace("，", ",").split(",") if k.strip()]
            report_generation_tokens.labels(phase="keyword_extract").inc(
                response.get("prompt_tokens", 0) + response.get("completion_tokens", 0)
            )
            return keywords[:3] if keywords else [position]
        except Exception as exc:
            logger.warning("Keyword extraction failed, falling back to position: %s", exc)
            return [position]

    async def _execute_search_dimensions(
        self,
        *,
        task_id: UUID,
        company: str,
        position: str,
        keywords: list[str],
    ) -> dict[str, list[dict[str, Any]]]:
        """Execute 4 search dimensions with cache and retry."""
        results: dict[str, list[dict[str, Any]]] = {}

        # Check 24h cache for cacheable dimensions
        cached = await self.result_repo.get_cached_for_company(
            company, dimensions=CACHEABLE_DIMENSIONS, ttl_hours=CACHE_TTL_HOURS
        )
        cache_by_dim: dict[str, list[dict]] = {}
        for c in cached:
            cache_by_dim.setdefault(c["dimension"], []).append(c["results"][0] if c["results"] else {})
            # Use cached results' "results" array
            cache_by_dim[c["dimension"]] = c["results"]

        # 1. Interview experience (with cache)
        if "interview_experience" in cache_by_dim:
            results["interview_experience"] = cache_by_dim["interview_experience"]
        else:
            results["interview_experience"] = await self._search_with_retry(
                task_id=task_id,
                dimension="interview_experience",
                queries=[f"{company} {position} 面试经验 面经"],
                company=company,
            )

        # 2. Company product (with cache)
        keyword_str = " ".join(keywords[:2]) if keywords else position
        if "company_product" in cache_by_dim:
            results["company_product"] = cache_by_dim["company_product"]
        else:
            results["company_product"] = await self._search_with_retry(
                task_id=task_id,
                dimension="company_product",
                queries=[f"{company} {keyword_str} 产品 最新"],
                company=company,
            )

        # 3. Exam points (always fresh)
        results["exam_points"] = await self._search_with_retry(
            task_id=task_id,
            dimension="exam_points",
            queries=[f"{position} 面试知识点 考察点"],
            company=company,
        )

        # 4. User weakness (local DB)
        # The user_weakness is a structured dict, not search hits.
        # Caller will fetch via _query_user_weakness. We mark it as completed.
        results["user_weakness"] = []

        return results

    async def _search_with_retry(
        self,
        *,
        task_id: UUID,
        dimension: str,
        queries: list[str],
        company: str,
    ) -> list[dict[str, Any]]:
        """Execute a single search dimension with 3 retries (2s/4s/8s backoff)."""
        from app.agents.tools.tavily_search import tavily_search

        for attempt in range(3):
            try:
                # ``tavily_search`` is a LangChain ``@tool`` — call via
                # ``ainvoke`` (same pattern as planner_search_node). Direct
                # ``tavily_search(queries=...)`` raises
                # ``BaseTool.__call__() got an unexpected keyword argument``.
                hits = await tavily_search.ainvoke(
                    {"queries": queries, "max_results": 5}
                )
                # Persist result
                await self.result_repo.create(
                    task_id=task_id,
                    dimension=dimension,
                    query=" | ".join(queries),
                    company=company,
                    results=hits or [],
                )
                web_search_api_calls_total.labels(dimension=dimension, outcome="success").inc()
                return hits or []
            except Exception as exc:
                logger.warning(
                    "Tavily search failed (attempt %d/3) for %s: %s",
                    attempt + 1, dimension, exc,
                )
                if attempt < 2:
                    await asyncio.sleep(RETRY_BACKOFFS[attempt])
                else:
                    # All retries exhausted; persist failure marker
                    await self.result_repo.create(
                        task_id=task_id,
                        dimension=dimension,
                        query=" | ".join(queries),
                        company=company,
                        results=[],
                        error=str(exc)[:500],
                    )
                    web_search_api_calls_total.labels(dimension=dimension, outcome="failed").inc()
                    return []

    async def _query_user_weakness(self, user_id: UUID) -> dict[str, Any]:
        """Read user's 2 lowest ability dimensions + 20 freshest error questions.

        On RLS / schema errors (common in ARQ when ``app.user_id`` is unset),
        return an empty weakness payload so report generation can still proceed
        for new users (quality check skips the ability-dimension rule).
        """
        empty = {
            "dimensions": [],
            "error_question_tags": [],
            "has_ability_data": False,
        }
        try:
            from app.core.db import set_rls_user_id

            await set_rls_user_id(self.session, user_id)
        except Exception as exc:
            logger.warning("Failed to bind RLS for weakness query: %s", exc)

        try:
            from app.modules.abilities.repository import AbilityDimensionRepository
            from app.modules.errors.repository import ErrorQuestionRepository

            ability_repo = AbilityDimensionRepository(self.session)
            ability_list = await ability_repo.list_for_user(user_id, is_active=True)

            # Sort by actual_score ascending, take 2 lowest
            sorted_dims = sorted(
                ability_list,
                key=lambda d: float(d.actual_score or 0),
            )[:2]
            dimensions = [
                {
                    "key": d.key if hasattr(d, "key") else getattr(d, "dimension_key", ""),
                    "score": float(d.actual_score or 0),
                    "improvements": getattr(d, "improvements", None) or [],
                }
                for d in sorted_dims
            ]

            error_repo = ErrorQuestionRepository(self.session)
            # Freshest 20 'fresh' status questions
            error_questions = await error_repo.list(
                user_id, status="fresh", limit=20
            )
            # Extract tags from error questions
            tags: list[str] = []
            for eq in error_questions[:20]:
                if eq.tags:
                    if isinstance(eq.tags, list):
                        tags.extend(eq.tags)
                    elif isinstance(eq.tags, str):
                        tags.extend(eq.tags.split(","))
            # Deduplicate while preserving order
            seen: set[str] = set()
            unique_tags: list[str] = []
            for t in tags:
                t = (t or "").strip()
                if t and t not in seen:
                    seen.add(t)
                    unique_tags.append(t)

            return {
                "dimensions": dimensions,
                "error_question_tags": unique_tags[:10],
                "has_ability_data": bool(dimensions),
            }
        except Exception as exc:
            logger.warning("user weakness query failed, continuing without: %s", exc)
            try:
                await self.session.rollback()
            except Exception:
                pass
            return empty

    async def _generate_with_retry(
        self,
        *,
        company: str,
        position: str,
        interview_time_iso: str,
        interview_round: str,
        search_results: dict[str, list[dict[str, Any]]],
        user_weakness: dict[str, Any],
        historical_comparison: dict[str, Any] | None = None,
    ) -> tuple[str, bool]:
        """Generate the report; retry once if quality check fails (FR-018)."""
        from app.modules.research.report_generator import generate_research_report

        has_ability = user_weakness.get("has_ability_data", False)
        attempt = 0
        report_md = ""
        last_failures: list[str] = []
        while attempt < 2:
            report_md = await generate_research_report(
                company=company,
                position=position,
                interview_time_iso=interview_time_iso,
                interview_round=interview_round,
                search_results=search_results,
                user_weakness=user_weakness,
                historical_comparison=historical_comparison,
            )
            passed, failures = check_report_quality(
                report_md, company=company, user_has_ability_data=has_ability
            )
            if passed:
                return report_md, True
            last_failures = failures
            logger.warning(
                "Quality check failed (attempt %d): %s", attempt + 1, failures
            )
            attempt += 1

        return report_md, False

    async def _find_historical_comparison(
        self,
        *,
        user_id: UUID,
        company: str,
        current_dimensions: list[dict[str, Any]],
    ) -> dict[str, Any] | None:
        """REQ-053 US4-AC6: look up the most recent pre_interview_research
        report for the same company within the last 7 days and extract its
        weakness dimensions so the current report can show progress/regress.

        Returns ``None`` when no historical report exists, when it has no
        weakness section to compare against, or when the user has no current
        ability data. The caller passes the result through to the LLM and
        then to :func:`append_historical_comparison` for the final table.
        """
        if not current_dimensions:
            return None
        try:
            cutoff = datetime.now(timezone.utc) - timedelta(days=7)
            result = await self.session.execute(
                text(
                    """SELECT r.id, r.summary_md, r.generated_at
                    FROM interview_reports r
                    JOIN jobs j ON j.id = r.job_id
                    WHERE j.user_id = :uid
                      AND j.company = :co
                      AND r.report_type = 'pre_interview_research'
                      AND r.generated_at >= :cutoff
                      AND r.quality_check_passed = true
                    ORDER BY r.generated_at DESC
                    LIMIT 1"""
                ),
                {"uid": user_id, "co": company, "cutoff": cutoff},
            )
            row = result.fetchone()
            if row is None:
                return None
            previous_md: str = row[1] or ""
            previous_dims = _extract_weakness_dimensions(previous_md)
            if not previous_dims:
                return None
            return {
                "previous_report_id": str(row[0]),
                "previous_generated_at": row[2].isoformat() if row[2] else None,
                "previous_dimensions": previous_dims,
                "current_dimensions": current_dimensions,
            }
        except Exception as exc:
            logger.warning("historical_comparison lookup failed: %s", exc)
            return None

    @staticmethod
    def _interview_round_label(interview_time: datetime | str, status: str) -> str:
        if isinstance(interview_time, str):
            try:
                interview_time = datetime.fromisoformat(interview_time)
            except ValueError:
                interview_time = None  # type: ignore
        label_map = {
            "test": "笔试",
            "interview_1": "一面（1 轮）",
            "interview_2": "二面（2 轮）",
            "interview_3": "三面（3 轮）",
        }
        return label_map.get(status, "面试")

    async def _deliver_report(
        self,
        *,
        user_id: UUID,
        report_id: UUID,
        summary_md: str,
        job_company: str,
    ) -> str:
        """Convert report to plain text, segment, send via WeChat or notification."""
        plain = convert_markdown_to_plain(summary_md)
        # Prefer 1–2 long WeChat messages (chapter packs), not ~500-char spam.
        segments = segment_for_wechat(plain, max_chars=DEFAULT_WECHAT_MAX_CHARS)

        # Try WeChat delivery first
        try:
            from app.core.db import set_rls_user_id
            from app.modules.agent.repository import (
                AgentPreferenceRepository,
                WeChatBindingRepository,
            )

            await set_rls_user_id(self.session, user_id)
            bind_repo = WeChatBindingRepository(self.session)
            binding = await bind_repo.get_by_user(user_id)
            if binding is None:
                return await self._fallback_to_notification(
                    user_id, report_id, job_company, reason="wechat_not_bound"
                )

            # Check DND
            try:
                pref_repo = AgentPreferenceRepository(self.session)
                pref = await pref_repo.get_by_user(user_id)
                if pref and getattr(pref, "quiet_hours_start", None) and getattr(pref, "quiet_hours_end", None):
                    if _is_in_quiet_hours(pref.quiet_hours_start, pref.quiet_hours_end):
                        await self.report_repo.update_delivery_status(
                            report_id, delivery_status="delayed"
                        )
                        return "delayed"
            except Exception:
                pass

            # Send segments
            sent_ok = 0
            for seg in segments:
                success = await _send_wechat_message(user_id=user_id, content=seg, priority="high")
                if success:
                    sent_ok += 1

            if sent_ok == len(segments) and segments:
                from datetime import datetime, timezone
                await self.report_repo.update_delivery_status(
                    report_id, delivery_status="sent",
                    delivered_at=datetime.now(timezone.utc),
                )
                return "sent"
            else:
                return await self._fallback_to_notification(
                    user_id, report_id, job_company, reason="send_partial"
                )
        except Exception as exc:
            logger.exception("WeChat delivery failed: %s", exc)
            try:
                await self.session.rollback()
            except Exception:
                pass
            return await self._fallback_to_notification(
                user_id, report_id, job_company, reason="send_failed"
            )

    async def _fallback_to_notification(
        self, user_id: UUID, report_id: UUID, company: str, *, reason: str
    ) -> str:
        """Save to DB and create notification when WeChat is unavailable."""
        msg_map = {
            "wechat_not_bound": "面试备战报告已生成（微信未绑定，无法推送），点击查看",
            "send_failed": "面试备战报告已生成，微信发送失败，点击查看",
            "send_partial": "面试备战报告已生成（部分段落发送失败），点击查看",
        }
        title = f"{company} 面试备战报告"
        message = msg_map.get(reason, "面试备战报告已生成，点击查看")
        try:
            from app.core.db import set_rls_user_id

            await set_rls_user_id(self.session, user_id)
        except Exception:
            pass
        try:
            from app.modules.account.notification import NotificationService
            svc = NotificationService(self.session, user_id)
            await svc.create(
                type_="research_report_failed",
                title=title,
                message=message,
                related_task_id=report_id,
            )
        except Exception as exc:
            logger.warning("Failed to create notification: %s", exc)
            try:
                await self.session.rollback()
            except Exception:
                pass

        from datetime import datetime, timezone
        try:
            await self.report_repo.update_delivery_status(
                report_id, delivery_status="failed",
                delivered_at=datetime.now(timezone.utc),
            )
        except Exception as exc:
            logger.warning("Failed to mark delivery_status=failed: %s", exc)
            try:
                await self.session.rollback()
            except Exception:
                pass
        return "failed"

    async def get_stats(self, user_id: UUID) -> ResearchStats:
        data = await self.task_repo.stats_by_user(user_id)
        return ResearchStats(**data)


def _is_in_quiet_hours(start: str, end: str) -> bool:
    """Return True if current local time falls within HH:MM-HH:MM quiet hours."""
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).astimezone()
    cur_minutes = now.hour * 60 + now.minute
    try:
        sh, sm = (int(x) for x in start.split(":"))
        eh, em = (int(x) for x in end.split(":"))
        start_min = sh * 60 + sm
        end_min = eh * 60 + em
    except (ValueError, AttributeError):
        return False
    if start_min <= end_min:
        return start_min <= cur_minutes < end_min
    # Cross-midnight
    return cur_minutes >= start_min or cur_minutes < end_min


_WEAKNESS_HEADER = "⚠️ 你的薄弱环节"


def _extract_weakness_dimensions(report_md: str) -> list[dict[str, Any]]:
    """Extract ability dimensions referenced in the ⚠️ section of a previous
    report. Returns a list of ``{"key": ..., "score": ...}`` items where the
    score defaults to 0 when no numeric score is parseable — the comparison
    table only needs the dimension key plus the previous score to render.
    """
    if not report_md:
        return []
    sections = re.split(r"^##\s+", report_md, flags=re.MULTILINE)
    weakness_body = ""
    for sec in sections:
        if sec.startswith(_WEAKNESS_HEADER):
            weakness_body = sec[len(_WEAKNESS_HEADER):]
            break
    if not weakness_body:
        return []
    dims: list[dict[str, Any]] = []
    seen: set[str] = set()
    # Heuristic: each bullet line lists the dimension key + an optional
    # parenthetical score like "(得分 65)".
    for line in weakness_body.splitlines():
        line = line.strip()
        if not line.startswith(("-", "*", "•")):
            continue
        body = line.lstrip("-*• ").strip()
        # First token before punctuation is the dimension name
        m = re.match(r"([^\s(（:,，]+)", body)
        if not m:
            continue
        key = m.group(1).strip()
        if not key or key in seen:
            continue
        seen.add(key)
        score_m = re.search(r"(\d+(?:\.\d+)?)", body)
        score = float(score_m.group(1)) if score_m else 0.0
        dims.append({"key": key, "score": score})
    return dims


async def _send_wechat_message(*, user_id: UUID, content: str, priority: str) -> bool:
    """Persist one outbound WeChat segment and push it onto the send queue.

    ``content`` is already a single WeChat-ready segment from
    ``segment_for_wechat`` (including optional ``(i/N)`` numbering). Do NOT
    re-run ``split_text`` here — that would double-number and re-chunk.

    Uses raw SQL (not the AgentMessage ORM) so the ARQ / research worker does
    not need the full auth mapper graph (User ↔ UserAvatar) to be configured.
    The ``agents_outbound_drain`` cron then delivers pending rows via iLink.
    """
    try:
        from uuid import uuid4

        from sqlalchemy import text

        from app.core.db import get_db_session
        from app.core.redis import get_redis

        if not content or not content.strip():
            return False

        # Parse "(i/N)\\n..." if present so DB metadata matches the body.
        seg_total: int | None = None
        seg_index: int | None = None
        m = re.match(r"^\((\d+)/(\d+)\)\n", content)
        if m:
            seg_index = int(m.group(1))
            seg_total = int(m.group(2))

        msg_id = uuid4()
        client_id = uuid4()

        async for session in get_db_session(user_id=user_id):
            await session.execute(
                text(
                    """
                    INSERT INTO agent_messages
                        (id, user_id, direction, content, status, message_type,
                         segments_total, segment_index, client_id, created_at)
                    VALUES
                        (:id, :uid, 'outbound', :content, 'pending', 'text',
                         :total, :idx, :cid, NOW())
                    """
                ),
                {
                    "id": msg_id,
                    "uid": user_id,
                    "content": content,
                    "total": seg_total,
                    "idx": seg_index,
                    "cid": client_id,
                },
            )
            try:
                redis = await get_redis()
                await redis.lpush(f"wechat:send_queue:{user_id}", content)
            except Exception as redis_exc:
                logger.warning(
                    "outbound_redis_lpush_failed_continuing: %s", redis_exc
                )
            break
        logger.info(
            "research_outbound_enqueued user=%s msg=%s priority=%s",
            user_id, msg_id, priority,
        )
        return True
    except Exception as exc:
        logger.warning("send_wechat_message failed: %s", exc)
        return False


__all__ = ["ResearchService"]