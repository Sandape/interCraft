"""Generic BaseRepository with soft-delete + tenant scoping defaults."""
from __future__ import annotations

import builtins
from collections.abc import Sequence
from datetime import UTC
from typing import Any, Generic, TypeVar

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import Base

T = TypeVar("T", bound=Base)


class BaseRepository(Generic[T]):
    """Common CRUD over a SQLAlchemy ORM model.

    All read methods filter out soft-deleted rows by default. Use
    `include_deleted=True` to bypass (e.g., for admin flows).
    """

    model: type[T]

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, id: Any, *, include_deleted: bool = False) -> T | None:
        stmt = select(self.model).where(self.model.id == id)
        if not include_deleted and hasattr(self.model, "deleted_at"):
            stmt = stmt.where(self.model.deleted_at.is_(None))
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list(
        self,
        *,
        filters: Sequence[Any] | None = None,
        order_by: Sequence[Any] | None = None,
        limit: int = 50,
        include_deleted: bool = False,
    ) -> builtins.list[T]:
        stmt = select(self.model)
        if filters:
            for f in filters:
                stmt = stmt.where(f)
        if not include_deleted and hasattr(self.model, "deleted_at"):
            stmt = stmt.where(self.model.deleted_at.is_(None))
        if order_by:
            stmt = stmt.order_by(*order_by)
        stmt = stmt.limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def create(self, instance: T) -> T:
        self.session.add(instance)
        await self.session.flush()
        await self.session.refresh(instance)
        return instance

    async def update(self, id: Any, patch: dict) -> T | None:
        instance = await self.get(id)
        if instance is None:
            return None
        for k, v in patch.items():
            if hasattr(instance, k):
                setattr(instance, k, v)
        await self.session.flush()
        await self.session.refresh(instance)
        return instance

    async def soft_delete(self, id: Any) -> bool:
        if not hasattr(self.model, "deleted_at"):
            return False
        from datetime import datetime

        instance = await self.get(id, include_deleted=True)
        if instance is None or getattr(instance, "deleted_at", None) is not None:
            return False
        instance.deleted_at = datetime.now(UTC)  # type: ignore[attr-defined]
        await self.session.flush()
        return True

    async def count(self, *, filters: Sequence[Any] | None = None) -> int:
        from sqlalchemy import func as sa_func

        stmt = select(sa_func.count()).select_from(self.model)
        if filters:
            for f in filters:
                stmt = stmt.where(f)
        if hasattr(self.model, "deleted_at"):
            stmt = stmt.where(self.model.deleted_at.is_(None))
        result = await self.session.execute(stmt)
        return int(result.scalar() or 0)

    async def find_or_create(self, **fields: Any) -> T:
        """SELECT-then-INSERT with IntegrityError retry (DEC-P2-3).

        Used by TaskService for idempotent find_or_create.
        """
        from sqlalchemy import func as sa_func
        from sqlalchemy.exc import IntegrityError

        # Build SELECT filters from the provided fields
        filters = [getattr(self.model, k) == v for k, v in fields.items()]
        if hasattr(self.model, "deleted_at"):
            filters.append(self.model.deleted_at.is_(None))

        stmt = select(self.model).where(*filters).limit(1)
        result = await self.session.execute(stmt)
        existing = result.scalar_one_or_none()
        if existing is not None:
            return existing

        instance = self.model(**fields)
        self.session.add(instance)
        try:
            await self.session.flush()
        except IntegrityError:
            await self.session.rollback()
            # Retry once — the row should now exist
            result = await self.session.execute(stmt)
            existing = result.scalar_one_or_none()
            if existing is not None:
                return existing
            raise
        await self.session.refresh(instance)
        return instance


__all__ = ["BaseRepository"]
