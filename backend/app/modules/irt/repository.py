"""Repository layer for the IRT item bank (REQ-030 US1).

Three focused repositories, one per table. All take an `AsyncSession`
in their constructor (mirrors `agent_memory.repository` pattern from
028). The RLS user-scoping GUC (`app.user_id`) is the caller's
responsibility — these repos do not set it. `irt_items` queries are
global (no RLS), so no GUC needed for those.

US1 scope: the operations needed by `aggregate_scores` to read the
user's recent responses and write θ estimates, plus the seed-time
`upsert_seed_items` helper. Calibration-time operations
(increment_response_count, retire items, batch update parameters) are
US3 surface and not exposed here.
"""
from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from uuid import UUID

import structlog
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.ids import new_uuid_v7
from app.modules.irt.models import AbilityTheta, Item, ItemResponse
from app.modules.irt.schemas import ItemCreate

logger = structlog.get_logger(__name__)


# ── ItemRepository ─────────────────────────────────────────────────────────


class ItemRepository:
    """Reads + idempotent seed insertion for `irt_items`.

    The bank is global (no RLS), so these methods never set
    `app.user_id`. Calibration / retirement are US3 and intentionally
    not exposed here.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def upsert_seed_items(self, items: Sequence[ItemCreate]) -> int:
        """Idempotently insert seed items, returning the number inserted.

        The partial unique index `uq_irt_items_active_dim_hash` on
        (dimension, question_text_hash) WHERE status != 'retired' is the
        authoritative dedup gate. We use `ON CONFLICT DO NOTHING` so
        re-seeding is safe and the count returned reflects only newly
        inserted rows. Retired items (different status) bypass the
        constraint — they will be re-inserted, which is intentional for
        the re-introduction workflow.
        """
        if not items:
            return 0

        rows = [
            {
                "id": new_uuid_v7(),
                "dimension": i.dimension,
                "question_text_hash": i.question_text_hash,
                "difficulty_b": i.difficulty_b,
                "discrimination_a": i.discrimination_a,
                "model": i.model,
                "status": i.status,
            }
            for i in items
        ]
        stmt = (
            pg_insert(Item)
            .values(rows)
            .on_conflict_do_nothing(
                index_elements=["dimension", "question_text_hash"],
                index_where=Item.status != "retired",
            )
        )
        result = await self.session.execute(stmt)
        await self.session.flush()
        # rowcount reflects newly-inserted rows under ON CONFLICT DO NOTHING.
        inserted = int(getattr(result, "rowcount", 0) or 0)
        logger.info(
            "irt.items.seed",
            attempted=len(items),
            inserted=inserted,
        )
        return inserted

    async def get_by_id(self, item_id: UUID) -> Item | None:
        stmt = select(Item).where(Item.id == item_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_for_dimension(
        self, dimension: str, *, status: str | None = None
    ) -> list[Item]:
        """List items in one dimension, optionally filtered by status.

        Used by `aggregate_scores` to find calibrated items for θ
        estimation. `status=None` returns all items (any status).
        """
        stmt = select(Item).where(Item.dimension == dimension)
        if status is not None:
            stmt = stmt.where(Item.status == status)
        # Order by difficulty for reproducible estimation runs.
        stmt = stmt.order_by(Item.difficulty_b.asc())
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def list_calibrated(
        self, dimension: str, *, limit: int = 100
    ) -> list[Item]:
        """Return up to `limit` calibrated items for one dimension.

        US1 default: returns the calibrated subset. In US1 there are no
        calibrated items (all are seeded as `uncalibrated`); the method
        is here so the calibration transition (US3) is a no-op call-site
        change.
        """
        return await self.list_for_dimension(dimension, status="calibrated")


# ── ItemResponseRepository ─────────────────────────────────────────────────


class ItemResponseRepository:
    """CRUD for `irt_item_responses` (RLS-scoped by caller via app.user_id)."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def insert_response(
        self,
        *,
        user_id: UUID,
        item_id: UUID,
        response: str,
        score: float,
        source_interview_id: UUID | None = None,
    ) -> ItemResponse:
        """Record one user response. Caller is responsible for RLS GUC.

        Returns the persisted row. Does NOT bump `irt_items.response_count`
        — that's a US3 concern (the seed data + 5-mock-response integration
        test doesn't depend on the counter).
        """
        row = ItemResponse(
            id=new_uuid_v7(),
            user_id=user_id,
            item_id=item_id,
            response=response,
            score=score,
            source_interview_id=source_interview_id,
        )
        self.session.add(row)
        await self.session.flush()
        await self.session.refresh(row)
        return row

    async def list_for_user(
        self,
        user_id: UUID,
        *,
        dimension: str | None = None,
        since: datetime | None = None,
        limit: int = 200,
    ) -> list[ItemResponse]:
        """List a user's responses, optionally filtered by item dimension
        and time window. Newest first.

        The `dimension` filter joins to `irt_items` to get the item's
        dimension. When `dimension is None`, all dimensions are returned
        (used by `aggregate_scores` to fan out per-dimension θ).
        """
        stmt = select(ItemResponse).where(ItemResponse.user_id == user_id)
        if since is not None:
            stmt = stmt.where(ItemResponse.created_at >= since)
        if dimension is not None:
            # Join to filter by item dimension. LEFT OUTER JOIN because
            # item_id can be NULL (item retired) — those rows are
            # excluded by the dimension filter naturally.
            stmt = stmt.join(
                Item, ItemResponse.item_id == Item.id
            ).where(Item.dimension == dimension)
        stmt = stmt.order_by(ItemResponse.created_at.desc()).limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())


# ── AbilityThetaRepository ─────────────────────────────────────────────────


class AbilityThetaRepository:
    """CRUD for `irt_ability_thetas` (RLS-scoped by caller via app.user_id)."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def insert(
        self,
        *,
        user_id: UUID,
        dimension: str,
        theta: float,
        standard_error: float,
        n_items: int,
        source_interview_id: UUID | None = None,
        model: str = "2pl",
        converged: bool = True,
    ) -> AbilityTheta:
        """Persist a single θ estimate.

        US1 does not enforce uniqueness on (user, dim, time) — multiple
        rows per dimension are expected as the user completes more
        interviews. The latest row is the "current" value; the dashboard
        timeline uses the full history.
        """
        row = AbilityTheta(
            id=new_uuid_v7(),
            user_id=user_id,
            dimension=dimension,
            theta=theta,
            standard_error=standard_error,
            n_items=n_items,
            source_interview_id=source_interview_id,
            model=model,
            converged=converged,
        )
        self.session.add(row)
        await self.session.flush()
        await self.session.refresh(row)
        return row

    async def list_for_user(
        self,
        user_id: UUID,
        *,
        dimension: str | None = None,
        limit: int = 50,
    ) -> list[AbilityTheta]:
        """List a user's θ history, newest first. Optional dimension filter."""
        stmt = select(AbilityTheta).where(AbilityTheta.user_id == user_id)
        if dimension is not None:
            stmt = stmt.where(AbilityTheta.dimension == dimension)
        stmt = stmt.order_by(AbilityTheta.created_at.desc()).limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())


__all__ = [
    "AbilityThetaRepository",
    "ItemRepository",
    "ItemResponseRepository",
]
