"""Phase 7 — Global search service: ILIKE aggregation across user + platform data."""
from __future__ import annotations

import time
from typing import Any
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.abilities.api import DIMENSIONS_META_STATIC
from app.modules.abilities.models import AbilityDimension
from app.modules.content.models import HelpFAQ, Resource
from app.modules.interviews.models import InterviewSession
from app.modules.resumes.models import ResumeBranch

GROUP_LABELS = {
    "resume": "简历分支",
    "interview": "面试记录",
    "ability": "能力维度",
    "faq": "常见问题",
    "resource": "学习资源",
}

ABILITY_LABEL_EN = {
    "tech_depth": "Technical Depth",
    "architecture": "Architecture",
    "engineering_practice": "Engineering Practice",
    "communication": "Communication",
    "problem_solving": "Problem Solving",
    "product_thinking": "Product Thinking",
    "learning_agility": "Learning Agility",
    "ownership": "Ownership",
}

FAQ_CATEGORY_LABELS = {
    "account": "账号相关",
    "interview": "面试相关",
    "resume": "简历相关",
    "subscription": "订阅相关",
    "technical": "技术问题",
}


def _dimension_label(dimension_key: str) -> tuple[str, str]:
    """Return (label_zh, label_en) for a dimension key. Falls back to the key."""
    for dim in DIMENSIONS_META_STATIC["dimensions"]:
        if dim["key"] == dimension_key:
            return dim.get("label_zh", dimension_key), dim.get("label_en", dimension_key)
    return dimension_key, ABILITY_LABEL_EN.get(dimension_key, dimension_key)


class SearchService:
    """Aggregates ILIKE matches across user-scoped + platform-wide sources."""

    PER_TYPE_LIMIT_DEFAULT = 5
    PER_TYPE_LIMIT_MAX = 5
    TOTAL_CAP = 25

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def search(
        self,
        query: str,
        per_type_limit: int = PER_TYPE_LIMIT_DEFAULT,
    ) -> dict[str, Any]:
        """Return the aggregated search response payload (groups + meta)."""
        started = time.perf_counter()
        q = query.strip()
        pattern = f"%{q}%"
        limit = max(1, min(per_type_limit, self.PER_TYPE_LIMIT_MAX))

        groups: list[dict[str, Any]] = []
        remaining = self.TOTAL_CAP

        # 1) Resume branches (user-scoped via RLS)
        if remaining > 0:
            branch_limit = min(limit, remaining)
            stmt = (
                select(ResumeBranch)
                .where(
                    or_(
                        ResumeBranch.name.ilike(pattern),
                        ResumeBranch.position.ilike(pattern),
                        ResumeBranch.company.ilike(pattern),
                    )
                )
                .order_by(ResumeBranch.is_main.desc(), ResumeBranch.updated_at.desc())
                .limit(branch_limit)
            )
            rows = (await self.db.execute(stmt)).scalars().all()
            count_stmt = select(ResumeBranch).where(
                or_(
                    ResumeBranch.name.ilike(pattern),
                    ResumeBranch.position.ilike(pattern),
                    ResumeBranch.company.ilike(pattern),
                )
            )
            total = len((await self.db.execute(count_stmt)).scalars().all())
            groups.append(
                {
                    "type": "resume",
                    "label": GROUP_LABELS["resume"],
                    "items": [
                        {
                            "id": str(b.id),
                            "type": "resume",
                            "title": b.name,
                            "subtitle": b.position or b.company or "—",
                            "destination": f"/resume/{b.id}",
                            "score": 1.0 if b.name and q.lower() in b.name.lower() else 0.6,
                            "meta": {
                                "branch_status": b.status,
                                "is_main": b.is_main,
                            },
                        }
                        for b in rows
                    ],
                    "total": total,
                }
            )
            remaining -= len(rows)

        # 2) Interview sessions (user-scoped via RLS)
        if remaining > 0:
            iv_limit = min(limit, remaining)
            stmt = (
                select(InterviewSession)
                .where(
                    InterviewSession.deleted_at.is_(None),
                    or_(
                        InterviewSession.position.ilike(pattern),
                        InterviewSession.company.ilike(pattern),
                    ),
                )
                .order_by(InterviewSession.created_at.desc())
                .limit(iv_limit)
            )
            rows = (await self.db.execute(stmt)).scalars().all()
            count_stmt = select(InterviewSession).where(
                InterviewSession.deleted_at.is_(None),
                or_(
                    InterviewSession.position.ilike(pattern),
                    InterviewSession.company.ilike(pattern),
                ),
            )
            total = len((await self.db.execute(count_stmt)).scalars().all())
            groups.append(
                {
                    "type": "interview",
                    "label": GROUP_LABELS["interview"],
                    "items": [
                        {
                            "id": str(s.id),
                            "type": "interview",
                            "title": s.position or s.company or "面试",
                            "subtitle": s.company or s.position or "—",
                            "destination": f"/interview/{s.id}/report",
                            "score": 1.0
                            if s.company and q.lower() in s.company.lower()
                            else 0.6,
                            "meta": {"session_status": s.status},
                        }
                        for s in rows
                    ],
                    "total": total,
                }
            )
            remaining -= len(rows)

        # 3) Ability dimensions (user-scoped via RLS, joined to static metadata)
        if remaining > 0:
            ab_limit = min(limit, remaining)
            stmt = select(AbilityDimension).limit(1000)  # small per-user set
            rows = (await self.db.execute(stmt)).scalars().all()
            # Match against dimension_key or label_zh/label_en from the static meta.
            q_lower = q.lower()
            matched = []
            for d in rows:
                label_zh, label_en = _dimension_label(d.dimension_key)
                haystack = " ".join(
                    [d.dimension_key or "", label_zh or "", label_en or ""]
                ).lower()
                if q_lower in haystack:
                    matched.append((d, label_zh, label_en))
            total = len(matched)
            matched = matched[:ab_limit]
            groups.append(
                {
                    "type": "ability",
                    "label": GROUP_LABELS["ability"],
                    "items": [
                        {
                            "id": f"ability::{d.dimension_key}",
                            "type": "ability",
                            "title": label_zh,
                            "subtitle": label_en,
                            "destination": f"/ability-profile/{d.dimension_key}",
                            "score": 1.0
                            if label_zh and q in label_zh
                            else 0.6,
                            "meta": {
                                "dimension_key": d.dimension_key,
                                "actual_score": float(d.actual_score or 0),
                            },
                        }
                        for (d, label_zh, label_en) in matched
                    ],
                    "total": total,
                }
            )
            remaining -= len(matched)

        # 4) FAQ (platform-wide, filtered by is_published)
        if remaining > 0:
            faq_limit = min(limit, remaining)
            stmt = (
                select(HelpFAQ)
                .where(
                    HelpFAQ.is_published.is_(True),
                    HelpFAQ.question.ilike(pattern),
                )
                .order_by(HelpFAQ.sort_order)
                .limit(faq_limit)
            )
            rows = (await self.db.execute(stmt)).scalars().all()
            count_stmt = select(HelpFAQ).where(
                HelpFAQ.is_published.is_(True),
                HelpFAQ.question.ilike(pattern),
            )
            total = len((await self.db.execute(count_stmt)).scalars().all())
            groups.append(
                {
                    "type": "faq",
                    "label": GROUP_LABELS["faq"],
                    "items": [
                        {
                            "id": str(f.id),
                            "type": "faq",
                            "title": f.question,
                            "subtitle": FAQ_CATEGORY_LABELS.get(f.category, f.category),
                            "destination": f"/help#faq/{f.id}",
                            "score": 0.6,
                            "meta": {"category": f.category},
                        }
                        for f in rows
                    ],
                    "total": total,
                }
            )
            remaining -= len(rows)

        # 5) Resources (platform-wide, filtered by is_published)
        if remaining > 0:
            res_limit = min(limit, remaining)
            stmt = (
                select(Resource)
                .where(
                    Resource.is_published.is_(True),
                    or_(
                        Resource.title.ilike(pattern),
                        Resource.summary.ilike(pattern),
                    ),
                )
                .order_by(Resource.sort_order)
                .limit(res_limit)
            )
            rows = (await self.db.execute(stmt)).scalars().all()
            count_stmt = select(Resource).where(
                Resource.is_published.is_(True),
                or_(
                    Resource.title.ilike(pattern),
                    Resource.summary.ilike(pattern),
                ),
            )
            total = len((await self.db.execute(count_stmt)).scalars().all())
            groups.append(
                {
                    "type": "resource",
                    "label": GROUP_LABELS["resource"],
                    "items": [
                        {
                            "id": str(r.id),
                            "type": "resource",
                            "title": r.title,
                            "subtitle": r.summary,
                            "destination": f"/help#resource/{r.id}",
                            "score": 0.6,
                            "meta": {"category": r.category},
                        }
                        for r in rows
                    ],
                    "total": total,
                }
            )
            remaining -= len(rows)

        # Drop empty groups to keep the response minimal.
        groups = [g for g in groups if g["items"]]

        # Stable group ordering for the client.
        order = {"resume": 0, "interview": 1, "ability": 2, "faq": 3, "resource": 4}
        groups.sort(key=lambda g: order.get(g["type"], 99))

        took_ms = int((time.perf_counter() - started) * 1000)
        return {"groups": groups, "query": q, "took_ms": took_ms}


__all__ = ["SearchService", "GROUP_LABELS"]
