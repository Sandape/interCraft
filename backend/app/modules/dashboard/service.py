"""Dashboard summary aggregation service (REQ-057)."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.abilities.models import AbilityDimension
from app.modules.activities.models import Activity
from app.modules.dashboard import cache as dash_cache
from app.modules.dashboard.activity_labels import parse_payload_json, render_activity
from app.modules.dashboard.funnel import aggregate_funnel
from app.modules.dashboard.schemas import (
    AbilitySnapshotOut,
    ActivityViewOut,
    CommandCenterL0Out,
    CommandCenterL1Out,
    CommandCenterL2Out,
    CtaOut,
    DashboardSummaryOut,
    FunnelSegmentOut,
    InterviewTrendOut,
    NextActionOut,
    OnboardingProgressOut,
    OnboardingStepOut,
    PrepPackOut,
    ResumableSessionOut,
    ResumeCountsOut,
    ResumeSummaryOut,
    TodayInterviewItemOut,
    WeakDimensionOut,
)
from app.modules.interviews.models import InterviewSession
from app.modules.jobs.models import Job
from app.modules.resumes_v2.models import ResumeV2

logger = logging.getLogger(__name__)

DEFAULT_TZ = "Asia/Shanghai"
RESUME_LIMIT = 5
ACTIVITY_LIMIT = 5
RESUMABLE_LIMIT = 3


class DashboardService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_summary(
        self,
        user_id: UUID,
        *,
        tz: str = DEFAULT_TZ,
        use_cache: bool = True,
    ) -> DashboardSummaryOut:
        try:
            local_date = dash_cache.local_date_for_tz(tz)
        except ValueError:
            raise

        if use_cache:
            cached = await dash_cache.cache_get(user_id, local_date)
            if cached:
                logger.info(
                    "dashboard_summary_cache",
                    extra={"cache": "hit", "user_id": str(user_id), "local_date": str(local_date)},
                )
                return DashboardSummaryOut.model_validate(cached)

        logger.info(
            "dashboard_summary_cache",
            extra={"cache": "miss", "user_id": str(user_id), "local_date": str(local_date)},
        )
        summary = await self.build_summary(user_id, tz=tz, local_date=local_date)
        if use_cache:
            await dash_cache.cache_set(
                user_id,
                local_date,
                summary.model_dump(mode="json"),
                ttl_sec=dash_cache.DEFAULT_TTL_SEC,
            )
        return summary

    async def build_summary(
        self,
        user_id: UUID,
        *,
        tz: str = DEFAULT_TZ,
        local_date=None,
    ) -> DashboardSummaryOut:
        if local_date is None:
            local_date = dash_cache.local_date_for_tz(tz)
        zi = ZoneInfo(tz)
        now_utc = datetime.now(timezone.utc)

        jobs = await self._list_jobs(user_id)
        resumes = await self._list_resumes(user_id)
        resume_counts = await self._resume_counts(user_id)
        sessions = await self._list_sessions(user_id)
        activities = await self._list_activities(user_id)
        abilities = await self._list_abilities(user_id)

        today_items = self._today_interviews(jobs, local_date=local_date, zi=zi, now_utc=now_utc)
        next_interview = self._pick_next(today_items, now_utc=now_utc)
        completed = [s for s in sessions if s.status == "completed"]
        resumable = [
            s for s in sessions if s.status in ("pending", "in_progress")
        ][:RESUMABLE_LIMIT]

        has_resume = resume_counts.total > 0
        has_job = len(jobs) > 0
        has_completed_interview = len(completed) > 0

        onboarding = self._onboarding(has_resume, has_job, has_completed_interview)
        primary_cta = self._primary_cta(
            next_interview=next_interview,
            onboarding=onboarding,
            resumable=resumable,
        )
        greeting = self._greeting_context(
            today_count=len(today_items),
            next_interview=next_interview,
            onboarding=onboarding,
        )

        resume_summaries = self._resume_summaries(resumes)
        next_action = self._next_action(
            completed=completed,
            has_resume=has_resume,
            has_job=has_job,
            next_interview=next_interview,
        )
        funnel = [
            FunnelSegmentOut.model_validate(seg)
            for seg in aggregate_funnel(jobs, now=now_utc)
        ]
        prep_pack = self._prep_pack(next_interview or (today_items[0] if today_items else None), resumes)

        l0 = CommandCenterL0Out(
            greeting_context=greeting,
            next_interview=next_interview,
            today_interviews=today_items,
            primary_cta=primary_cta,
            onboarding=onboarding,
            resumable_sessions=[
                ResumableSessionOut(
                    session_id=s.id,
                    company=s.company,
                    position=s.position,
                    status=s.status,
                    href=f"/interview/{s.id}/live",
                )
                for s in resumable
            ],
        )
        l1 = CommandCenterL1Out(
            resume_summaries=resume_summaries,
            resume_counts=resume_counts,
            next_action=next_action,
            job_funnel=funnel,
            prep_pack=prep_pack,
        )  # resume_counts from full GROUP BY, not list slice
        l2 = CommandCenterL2Out(
            ability_snapshot=self._ability_snapshot(abilities),
            recent_activities=self._activity_views(activities),
            interview_trend=self._interview_trend(completed),
        )
        return DashboardSummaryOut(
            generated_at=now_utc,
            cache_ttl_sec=dash_cache.DEFAULT_TTL_SEC,
            tz=tz,
            local_date=local_date,
            l0=l0,
            l1=l1,
            l2=l2,
        )

    async def _list_jobs(self, user_id: UUID) -> list[Job]:
        stmt = (
            select(Job)
            .where(Job.user_id == user_id, Job.deleted_at.is_(None))
            .order_by(Job.updated_at.desc())
            .limit(100)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def _list_resumes(self, user_id: UUID) -> list[ResumeV2]:
        # RLS scopes by user; still filter for clarity in tests without RLS.
        stmt = (
            select(ResumeV2)
            .where(ResumeV2.user_id == user_id)
            .order_by(ResumeV2.updated_at.desc())
            .limit(RESUME_LIMIT)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def _resume_counts(self, user_id: UUID) -> ResumeCountsOut:
        stmt = (
            select(ResumeV2.resume_kind, func.count())
            .where(ResumeV2.user_id == user_id)
            .group_by(ResumeV2.resume_kind)
        )
        result = await self.session.execute(stmt)
        counts = ResumeCountsOut()
        for kind, n in result.all():
            k = kind or "standard"
            n = int(n)
            if k == "root":
                counts.root = n
            elif k == "derived":
                counts.derived = n
            else:
                counts.standard += n
            counts.total += n
        return counts

    async def _list_sessions(self, user_id: UUID) -> list[InterviewSession]:
        stmt = (
            select(InterviewSession)
            .where(InterviewSession.user_id == user_id, InterviewSession.deleted_at.is_(None))
            .order_by(InterviewSession.updated_at.desc())
            .limit(50)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def _list_activities(self, user_id: UUID) -> list[Activity]:
        stmt = (
            select(Activity)
            .where(Activity.user_id == user_id)
            .order_by(Activity.occurred_at.desc())
            .limit(ACTIVITY_LIMIT)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def _list_abilities(self, user_id: UUID) -> list[AbilityDimension]:
        stmt = select(AbilityDimension).where(AbilityDimension.user_id == user_id)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    def _today_interviews(
        self,
        jobs: list[Job],
        *,
        local_date,
        zi: ZoneInfo,
        now_utc: datetime,
    ) -> list[TodayInterviewItemOut]:
        items: list[TodayInterviewItemOut] = []
        for job in jobs:
            it = job.interview_time
            if it is None:
                continue
            if it.tzinfo is None:
                it = it.replace(tzinfo=timezone.utc)
            if it.astimezone(zi).date() != local_date:
                continue
            items.append(
                TodayInterviewItemOut(
                    job_id=job.id,
                    company=job.company,
                    position=job.position,
                    interview_time=it,
                    status=job.status,
                    relative_label=self._relative_label(it, now_utc=now_utc, zi=zi),
                    href=f"/jobs/{job.id}",
                )
            )
        items.sort(key=lambda x: x.interview_time)
        return items

    @staticmethod
    def _relative_label(when: datetime, *, now_utc: datetime, zi: ZoneInfo) -> str:
        local_when = when.astimezone(zi)
        local_now = now_utc.astimezone(zi)
        delta = local_when - local_now
        secs = int(delta.total_seconds())
        if secs < -60:
            mins = abs(secs) // 60
            if mins < 60:
                return f"已过点 {mins} 分钟"
            return f"已过点 {mins // 60} 小时"
        if secs < 3600:
            return f"{max(secs // 60, 1)} 分钟后"
        if secs < 86400:
            return f"{secs // 3600} 小时后"
        return local_when.strftime("%H:%M")

    @staticmethod
    def _pick_next(
        items: list[TodayInterviewItemOut],
        *,
        now_utc: datetime,
    ) -> TodayInterviewItemOut | None:
        if not items:
            return None
        upcoming = [i for i in items if i.interview_time >= now_utc]
        return upcoming[0] if upcoming else items[-1]

    @staticmethod
    def _onboarding(has_resume: bool, has_job: bool, has_interview: bool) -> OnboardingProgressOut | None:
        steps = [
            OnboardingStepOut(id="resume", done=has_resume, href="/resume"),
            OnboardingStepOut(id="job", done=has_job, href="/jobs?new=true"),
            OnboardingStepOut(id="interview", done=has_interview, href="/interview/mode"),
        ]
        show = not all(s.done for s in steps)
        if not show:
            return None
        return OnboardingProgressOut(show=True, steps=steps)

    @staticmethod
    def _greeting_context(
        *,
        today_count: int,
        next_interview: TodayInterviewItemOut | None,
        onboarding: OnboardingProgressOut | None,
    ) -> str:
        if today_count > 0 and next_interview:
            return f"今天有 {today_count} 场面试 · 下一场：{next_interview.company}（{next_interview.relative_label}）"
        if today_count > 0:
            return f"今天有 {today_count} 场面试"
        if onboarding and onboarding.show:
            pending = next((s for s in onboarding.steps if not s.done), None)
            if pending and pending.id == "resume":
                return "今天没有安排面试 · 先完善简历，建立你的素材库"
            if pending and pending.id == "job":
                return "今天没有安排面试 · 登记一个目标岗位开始追踪"
            if pending and pending.id == "interview":
                return "今天没有安排面试 · 完成首场模拟面试获取能力画像"
        return "今天没有安排面试 · 去求职追踪登记下一场，或开始模拟练习"

    @staticmethod
    def _primary_cta(
        *,
        next_interview: TodayInterviewItemOut | None,
        onboarding: OnboardingProgressOut | None,
        resumable: list[InterviewSession],
    ) -> CtaOut:
        if resumable:
            s = resumable[0]
            return CtaOut(label="继续模拟面试", href=f"/interview/{s.id}/live")
        if next_interview:
            return CtaOut(label="准备下一场面试", href=next_interview.href)
        if onboarding and onboarding.show:
            step = next((s for s in onboarding.steps if not s.done), None)
            if step:
                labels = {"resume": "去完善简历", "job": "去登记岗位", "interview": "开始模拟面试"}
                return CtaOut(label=labels[step.id], href=step.href)
        return CtaOut(label="开始模拟面试", href="/interview/mode")

    @staticmethod
    def _resume_summaries(resumes: list[ResumeV2]) -> list[ResumeSummaryOut]:
        return [
            ResumeSummaryOut(
                id=r.id,
                name=r.name,
                resume_kind=getattr(r, "resume_kind", None) or "standard",
                job_id=getattr(r, "job_id", None),
                updated_at=getattr(r, "updated_at", None),
                href=f"/resume/{r.id}",
            )
            for r in resumes[:RESUME_LIMIT]
        ]

    @staticmethod
    def _next_action(
        *,
        completed: list[InterviewSession],
        has_resume: bool,
        has_job: bool,
        next_interview: TodayInterviewItemOut | None,
    ) -> NextActionOut:
        if next_interview:
            return NextActionOut(
                id="prep-today-interview",
                title_zh=f"准备今日面试：{next_interview.company}",
                body_zh=f"{next_interview.position} · {next_interview.relative_label}。打开岗位详情核对 JD 与派生简历。",
                cta=CtaOut(label="打开岗位", href=next_interview.href),
                tier=1 if completed else 0,
            )
        if not completed:
            return NextActionOut(
                id="start-first-interview",
                title_zh="完成首场模拟面试，获取能力画像",
                body_zh="完成模拟面试后，我们会生成能力维度评分与个性化下一步建议。",
                cta=CtaOut(label="开始模拟面试", href="/interview/mode"),
                tier=0,
            )
        if not has_resume:
            return NextActionOut(
                id="create-resume",
                title_zh="在简历中心建立根简历",
                body_zh="根简历是长期素材库；有了它才能为一键派生与岗位匹配提供依据。",
                cta=CtaOut(label="前往简历中心", href="/resume"),
                tier=1,
            )
        if not has_job:
            return NextActionOut(
                id="add-job",
                title_zh="登记一个求职目标",
                body_zh="在求职追踪中记录公司与职位，方便安排面试时间与派生投递稿。",
                cta=CtaOut(label="去求职追踪", href="/jobs"),
                tier=1,
            )
        latest = sorted(
            completed,
            key=lambda s: s.ended_at or s.updated_at or s.created_at,
            reverse=True,
        )[0]
        label = " · ".join(p for p in (latest.company, latest.position) if p) or "最近一场面试"
        score = float(latest.overall_score) if latest.overall_score is not None else None
        body = (
            f"综合评分 {score:.1f} / 10，建议复盘薄弱维度并安排强化练习。"
            if score is not None
            else "复盘该场面试表现，针对性巩固薄弱环节。"
        )
        return NextActionOut(
            id="recap-latest-interview",
            title_zh=f"复盘：{label}",
            body_zh=body,
            cta=CtaOut(label="查看面试记录", href="/interview"),
            tier=2,
        )

    @staticmethod
    def _prep_pack(
        interview: TodayInterviewItemOut | None,
        resumes: list[ResumeV2],
    ) -> PrepPackOut | None:
        if interview is None:
            return None
        derived_id = None
        for r in resumes:
            if getattr(r, "resume_kind", None) == "derived" and getattr(r, "job_id", None) == interview.job_id:
                derived_id = r.id
                break
        actions = [CtaOut(label="打开岗位", href=interview.href)]
        if derived_id:
            actions.append(CtaOut(label="打开派生简历", href=f"/resume/{derived_id}"))
        else:
            actions.append(
                CtaOut(
                    label="去派生简历",
                    href=f"/resume?derive=true&job_id={interview.job_id}",
                )
            )
        return PrepPackOut(job_id=interview.job_id, derived_resume_id=derived_id, actions=actions)

    @staticmethod
    def _ability_snapshot(abilities: list[AbilityDimension]) -> AbilitySnapshotOut | None:
        if not abilities:
            return None
        from app.modules.ability_profile.service import DIMENSION_LABELS

        scores = []
        weak: list[WeakDimensionOut] = []
        for d in abilities:
            actual = float(d.actual_score or 0)
            scores.append(actual)
            weak.append(
                WeakDimensionOut(
                    key=d.dimension_key,
                    label_zh=DIMENSION_LABELS.get(d.dimension_key, d.dimension_key),
                    actual_score=actual,
                )
            )
        weak.sort(key=lambda w: w.actual_score)
        overall = round(sum(scores) / len(scores), 1) if scores else 0.0
        return AbilitySnapshotOut(
            overall_score=overall,
            weakest_dimensions=weak[:2],
            href="/ability-profile",
        )

    @staticmethod
    def _activity_views(activities: list[Activity]) -> list[ActivityViewOut]:
        out: list[ActivityViewOut] = []
        for a in activities:
            payload = parse_payload_json(getattr(a, "payload_json", None))
            title, detail, href = render_activity(a.type, payload)
            out.append(
                ActivityViewOut(
                    id=a.id,
                    type=a.type,
                    title_zh=title,
                    detail_zh=detail,
                    occurred_at=getattr(a, "occurred_at", None),
                    href=href,
                )
            )
        return out

    @staticmethod
    def _interview_trend(completed: list[InterviewSession]) -> InterviewTrendOut | None:
        if not completed:
            return None
        scores = [float(s.overall_score) for s in completed if s.overall_score is not None]
        avg = round(sum(scores) / len(scores), 1) if scores else 0.0
        return InterviewTrendOut(completed_count=len(completed), avg_score=avg)


__all__ = ["DEFAULT_TZ", "DashboardService"]
