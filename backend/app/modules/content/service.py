"""Phase 6 — Content service: resources CRUD + FAQ CRUD + search."""
from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, or_, select, text as sa_text
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.content.models import HelpFAQ, Resource


class ContentService:
    """CRUD + search for resources and FAQ."""

    CATEGORY_LABELS = {
        "account": "账号相关",
        "interview": "面试相关",
        "resume": "简历相关",
        "subscription": "订阅相关",
        "technical": "技术问题",
    }

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # ---- Resources ----

    async def list_resources(
        self,
        category: str | None = None,
        tag: str | None = None,
        content_type: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[Resource], int]:
        query = select(Resource).where(Resource.is_published == True)  # noqa: E712

        if category:
            query = query.where(Resource.category == category)
        if tag:
            query = query.where(Resource.tags.any(tag))  # type: ignore[arg-type]
        if content_type:
            query = query.where(Resource.content_type == content_type)

        count_q = select(func.count()).select_from(query.subquery())
        total_result = await self.db.execute(count_q)
        total = total_result.scalar() or 0

        query = query.order_by(Resource.sort_order).limit(limit).offset(offset)
        result = await self.db.execute(query)
        items = list(result.scalars().all())

        return items, total

    async def get_resource(self, resource_id: UUID) -> Resource | None:
        result = await self.db.execute(
            select(Resource).where(
                Resource.id == resource_id,
                Resource.is_published == True,  # noqa: E712
            )
        )
        return result.scalar_one_or_none()

    async def get_related_resources(self, resource: Resource, limit: int = 3) -> list[Resource]:
        """Get related resources in the same category."""
        result = await self.db.execute(
            select(Resource)
            .where(
                Resource.category == resource.category,
                Resource.id != resource.id,
                Resource.is_published == True,  # noqa: E712
            )
            .order_by(Resource.sort_order)
            .limit(limit)
        )
        return list(result.scalars().all())

    # ---- FAQ ----

    async def list_faq(self, category: str | None = None) -> list[HelpFAQ]:
        query = select(HelpFAQ).where(HelpFAQ.is_published == True)  # noqa: E712
        if category:
            query = query.where(HelpFAQ.category == category)
        query = query.order_by(HelpFAQ.category, HelpFAQ.sort_order)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_faq(self, faq_id: UUID) -> HelpFAQ | None:
        result = await self.db.execute(
            select(HelpFAQ).where(
                HelpFAQ.id == faq_id,
                HelpFAQ.is_published == True,  # noqa: E712
            )
        )
        return result.scalar_one_or_none()

    async def search(self, q: str, scope: str = "all", limit: int = 10) -> dict:
        """Full-text search across FAQ and resources."""
        result: dict = {"faq": [], "resources": []}

        if scope in ("all", "faq"):
            faq_query = (
                select(
                    HelpFAQ.id,
                    HelpFAQ.question,
                    HelpFAQ.category,
                    func.ts_rank(
                        func.to_tsvector("simple", func.coalesce(HelpFAQ.question, "") + " " + func.coalesce(HelpFAQ.answer, "")),
                        func.plainto_tsquery("simple", q),
                    ).label("score"),
                )
                .where(
                    HelpFAQ.is_published == True,  # noqa: E712
                    func.to_tsvector("simple", func.coalesce(HelpFAQ.question, "") + " " + func.coalesce(HelpFAQ.answer, "")).op("@@")(
                        func.plainto_tsquery("simple", q)
                    ),
                )
                .order_by(sa_text("score DESC"))
                .limit(limit)
            )
            faq_rows = await self.db.execute(faq_query)
            for row in faq_rows:
                result["faq"].append({
                    "id": row.id,
                    "question": row.question,
                    "category": row.category,
                    "score": round(float(row.score), 4) if row.score else 0.0,
                })

        if scope in ("all", "resources"):
            res_query = (
                select(
                    Resource.id,
                    Resource.title,
                    Resource.category,
                    func.ts_rank(
                        func.to_tsvector("simple", func.coalesce(Resource.title, "") + " " + func.coalesce(Resource.summary, "")),
                        func.plainto_tsquery("simple", q),
                    ).label("score"),
                )
                .where(
                    Resource.is_published == True,  # noqa: E712
                    func.to_tsvector("simple", func.coalesce(Resource.title, "") + " " + func.coalesce(Resource.summary, "")).op("@@")(
                        func.plainto_tsquery("simple", q)
                    ),
                )
                .order_by(sa_text("score DESC"))
                .limit(limit)
            )
            res_rows = await self.db.execute(res_query)
            for row in res_rows:
                result["resources"].append({
                    "id": row.id,
                    "title": row.title,
                    "category": row.category,
                    "score": round(float(row.score), 4) if row.score else 0.0,
                })

        return result
