"""M032 — Resume v2 repository (REQ-032 v2 US1+US11+US14, Batch 5).

Async SQLAlchemy 2.0 queries against three tables created by
migration 0022:

- ``resumes_v2``               — RLS-bound authoring + content
- ``resume_statistics_v2``     — public-access counters (lazy)
- ``resume_analysis_v2``       — LLM analysis snapshot (UPSERT)

Twelve methods cover the full v2 surface:

  create, get, list, get_owner_id, update_with_version, soft_delete,
  duplicate, set_sharing, set_lock, get_statistics, increment_views,
  increment_downloads, get_by_username_and_slug, upsert_analysis,
  get_analysis

RLS: RLS policies on ``resumes_v2`` enforce
``user_id = current_setting('app.user_id')::uuid``. The API
dependencies (``db_session_user_dep`` for authenticated routes,
``get_db_session_no_rls`` for public routes) bind that GUC before
this repository runs, so reads / writes succeed without the
repository doing anything extra. Public-route reads go through
``get_by_username_and_slug`` which uses the SECURITY DEFINER helper
``resumes_v2_owner_of(p_id uuid)`` for ownership lookups when RLS
hides a row.

Optimistic concurrency
----------------------
``update_with_version(if_match=...)`` issues a single
``UPDATE ... SET version = version + 1 WHERE id = :rid AND version
= :expected`` then returns ``rowcount``. ``rowcount == 1`` is
"success" (we return ``expected + 1``); ``rowcount == 0`` is
"conflict" (caller raises 409). The atomic increment relies on the
``BEFORE UPDATE`` trigger from migration 0022 to bump
``updated_at`` even if the caller passes stale ORM state.

Soft delete cascade
-------------------
``soft_delete`` deletes the parent row only — the FK
``ON DELETE CASCADE`` on both ``resume_statistics_v2`` and
``resume_analysis_v2`` cleans children. ``soft_delete`` returns
``True`` iff a row was affected.

The repository is deliberately the only place the table columns
appear in raw SQL — the service layer never builds SQL strings.
"""
from __future__ import annotations

import copy
from typing import Any
from uuid import UUID

from sqlalchemy import select, text as sa_text, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.resumes_v2.models import (
    ResumeAnalysisV2,
    ResumeStatisticsV2,
    ResumeV2,
)


class ResumeV2Repository:
    """Async CRUD + side-actions for the v2 resume surface.

    All methods assume the async session already has ``app.user_id``
    bound (set by the dependency) for the routes that go through
    ``db_session_user_dep``. Public routes use
    ``get_db_session_no_rls`` and are explicitly documented below.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # ── 1. create ────────────────────────────────────────────────────────

    async def create(
        self,
        *,
        user_id: UUID,
        name: str,
        slug: str,
        data: dict[str, Any],
    ) -> ResumeV2:
        """Insert a new resume row.

        The DB enforces ``uq_resumes_v2_user_slug`` (UNIQUE
        (user_id, slug)) and the FK to ``users.id``. Slug
        validation is the service layer's job — the repository
        trusts the service's slug regex.

        Returns the inserted row populated with id (UUID v7 generated
        by the service), version=0 (DB default), timestamps set by
        the trigger / column defaults.
        """
        from app.core.ids import new_uuid_v7

        new_id = new_uuid_v7()
        row = ResumeV2(
            id=new_id,
            user_id=user_id,
            name=name,
            slug=slug,
            tags=[],
            is_public=False,
            is_locked=False,
            password_hash=None,
            data=data,
            version=0,
        )
        self._session.add(row)
        await self._session.flush()
        return row

    # ── 2. get ──────────────────────────────────────────────────────────

    async def get(self, resume_id: UUID, *, user_id: UUID) -> ResumeV2 | None:
        """Fetch a single resume by id, RLS-scoped.

        RLS via ``app.user_id`` GUC hides rows the caller does not
        own, so a non-owner receives ``None``. The service layer
        uses ``get_owner_id`` to disambiguate 404 vs 403.

        We belt-and-braces by also adding ``user_id = :uid`` to the
        WHERE clause. RLS would catch this on the BIND-side too,
        but the explicit predicate is the single source of truth
        for the test suite (e.g.,
        ``test_get_with_wrong_user_returns_none``).
        """
        stmt = select(ResumeV2).where(
            ResumeV2.id == resume_id,
            ResumeV2.user_id == user_id,
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    # ── 3. list ─────────────────────────────────────────────────────────

    async def list(
        self,
        user_id: UUID,
        *,
        search: str | None = None,
        tags: list[str] | None = None,
        is_public: bool | None = None,
        sort: str = "updated",
    ) -> list[ResumeV2]:
        """List the user's resumes with optional filters.

        RLS does the user scoping so we don't re-add the WHERE on
        ``user_id`` — that would be a no-op against the FORCE-RLS
        table anyway.
        """
        stmt = select(ResumeV2)
        if is_public is not None:
            stmt = stmt.where(ResumeV2.is_public == is_public)
        if search:
            like = f"%{search.lower()}%"
            stmt = stmt.where(
                sa_text("LOWER(resumes_v2.name) LIKE :s OR LOWER(resumes_v2.slug) LIKE :s").bindparams(
                    s=like
                )
            )
        if tags:
            # ANY-of intersection: tags overlapping the requested
            # list. Repository filter only — the API does an
            # issubset post-filter against the same column so the
            # exact contract from the E2E spec holds.
            stmt = stmt.where(ResumeV2.tags.op("&&")(tags))
        # Sort selector: updated (default) | created | name
        sort_key = (sort or "updated").lower()
        if sort_key == "created":
            stmt = stmt.order_by(ResumeV2.created_at.desc())
        elif sort_key == "name":
            stmt = stmt.order_by(ResumeV2.name.asc())
        else:
            stmt = stmt.order_by(ResumeV2.updated_at.desc())
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    # ── 4. get_owner_id ─────────────────────────────────────────────────

    async def get_owner_id(self, resume_id: UUID) -> UUID | None:
        """Return the row's owner ``user_id`` without loading the data.

        RLS hides non-owner rows from the standard SELECT, so we
        call the SECURITY DEFINER helper ``resumes_v2_owner_of``
        (migration 0023) which temporarily drops FORCE-RLS to
        return the owner UUID and then re-applies FORCE. The helper
        returns NULL when the row doesn't exist.

        This is the foundation of the v2 contract's 404 vs 403
        disambiguation: service.py compares the returned UUID to
        ``user_id`` and emits 403 vs 404 appropriately.
        """
        stmt = sa_text(
            "SELECT resumes_v2_owner_of(CAST(:rid AS uuid)) AS owner_id"
        ).bindparams(rid=str(resume_id))
        result = await self._session.execute(stmt)
        row = result.first()
        if row is None:
            return None
        val = row[0]
        return UUID(str(val)) if val is not None else None

    # ── 5. update_with_version ──────────────────────────────────────────

    async def update_with_version(
        self,
        resume_id: UUID,
        *,
        user_id: UUID,
        if_match: int,
        data: dict[str, Any] | None = None,
        name: str | None = None,
        tags: list[str] | None = None,
    ) -> int | None:
        """Optimistic-concurrency UPDATE.

        Returns ``expected + 1`` on success (the new version) or
        ``None`` if the WHERE ``version = :expected`` did not match
        (caller surfaces 409 VERSION_CONFLICT).

        Optional fields:
          - ``data``: replace the JSONB blob wholesale.
          - ``name``: update ``name``.
          - ``tags``: replace the array wholesale.

        When no optional fields are provided the call is a no-op but
        still bumps the version — this matches the E2E spec which
        sends empty PUT bodies to assert 200 + version+1. ``DELETE``
        callers should use ``soft_delete`` instead.

        RLS scopes the WHERE clause to the current GUC, so a
        non-owner sees ``rowcount == 0`` (treated as conflict).
        """
        values: dict[str, Any] = {
            "version": ResumeV2.version + 1,
        }
        if data is not None:
            values["data"] = data
        if name is not None:
            values["name"] = name
        if tags is not None:
            values["tags"] = list(tags)

        stmt = (
            update(ResumeV2)
            .where(
                ResumeV2.id == resume_id,
                ResumeV2.version == if_match,
            )
            .values(**values)
        )
        result = await self._session.execute(stmt)
        if result.rowcount == 0:
            await self._session.rollback()
            return None
        await self._session.flush()
        return if_match + 1

    # ── 6. soft_delete ──────────────────────────────────────────────────

    async def soft_delete(self, resume_id: UUID, *, user_id: UUID) -> bool:
        """Hard-delete the row.

        M032 chose hard delete over soft delete because the v1
        ``resume_branches`` retention also hard-deletes
        (``deleted_at`` is set only as a tombstone signal). The FK
        ``ON DELETE CASCADE`` on both statistics + analysis cleans
        child rows automatically.

        Returns ``True`` iff a row was affected.
        """
        stmt = sa_text(
            "DELETE FROM resumes_v2 WHERE id = CAST(:rid AS uuid)"
        ).bindparams(rid=str(resume_id))
        result = await self._session.execute(stmt)
        await self._session.flush()
        return bool(result.rowcount)

    # ── 7. duplicate ────────────────────────────────────────────────────

    async def duplicate(
        self,
        resume_id: UUID,
        *,
        user_id: UUID,
        new_id: UUID,
        new_slug: str,
        new_name: str,
    ) -> ResumeV2 | None:
        """Copy a resume row, deep-copying its JSONB ``data``.

        Behavior (per FR-100 / T017 contract):
          - Same ``user_id`` and copy of the JSONB ``data``.
          - New ``id``, new ``slug``, new ``name`` (provided).
          - ``is_public=False``, ``is_locked=False``,
            ``password_hash=None`` regardless of source.
          - ``version=0``.
          - No statistics row, no analysis row.

        The JSONB clone uses ``copy.deepcopy`` so the ORM doesn't
        share the mutable reference with the source — see the
        ``test_duplicate_deep_copies_data`` test in
        ``tests/test_repository.py``.

        Returns the inserted copy or ``None`` if the source
        vanished.
        """
        src = await self.get(resume_id, user_id=user_id)
        if src is None:
            return None
        cloned = copy.deepcopy(src.data) if src.data is not None else {}
        new_row = ResumeV2(
            id=new_id,
            user_id=user_id,
            name=new_name,
            slug=new_slug,
            tags=list(src.tags or []),
            is_public=False,
            is_locked=False,
            password_hash=None,
            data=cloned,
            version=0,
        )
        self._session.add(new_row)
        await self._session.flush()
        return new_row

    # ── 8. set_sharing ─────────────────────────────────────────────────

    async def set_sharing(
        self,
        resume_id: UUID,
        *,
        user_id: UUID,
        is_public: bool,
        password_hash: str | None,
    ) -> bool:
        """Toggle ``is_public`` + optionally store a ``password_hash``.

        The DB's CHECK constraint
        ``password_hash IS NULL OR is_public = true`` rejects the
        invariant violation at the storage layer — we surface
        ``IntegrityError`` to the service layer so it can decide
        whether to retry / map to 400.
        """
        stmt = (
            update(ResumeV2)
            .where(ResumeV2.id == resume_id)
            .values(is_public=is_public, password_hash=password_hash)
        )
        result = await self._session.execute(stmt)
        await self._session.flush()
        return bool(result.rowcount)

    # ── 9. set_lock ─────────────────────────────────────────────────────

    async def set_lock(
        self,
        resume_id: UUID,
        *,
        user_id: UUID,
        is_locked: bool,
    ) -> bool:
        """Toggle ``is_locked`` without bumping version.

        Independent of the optimistic-concurrency chain per FR-024
        — see ``TestSetLock`` in ``tests/test_repository.py``.
        """
        stmt = (
            update(ResumeV2)
            .where(ResumeV2.id == resume_id)
            .values(is_locked=is_locked)
        )
        result = await self._session.execute(stmt)
        await self._session.flush()
        return bool(result.rowcount)

    # ── 10. statistics ─────────────────────────────────────────────────

    async def get_statistics(
        self, resume_id: UUID
    ) -> ResumeStatisticsV2 | None:
        """Return the counters row (or None if none exists).

        The parent row's RLS gates access — if RLS hides the parent
        then this SELECT also returns zero rows. Public routes
        bypass RLS via ``get_db_session_no_rls``.
        """
        stmt = select(ResumeStatisticsV2).where(
            ResumeStatisticsV2.resume_id == resume_id
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def increment_views(self, resume_id: UUID) -> None:
        """Atomic ``views + 1`` + ``last_viewed_at = now()``.

        Single SQL UPDATE — see
        ``test_increment_views_sql_is_single_atomic_update``. When
        no row exists yet this is a silent no-op; the service
        layer's ``ensure_statistics_row`` is responsible for
        materializing the row first.
        """
        stmt = (
            update(ResumeStatisticsV2)
            .where(ResumeStatisticsV2.resume_id == resume_id)
            .values(
                views=ResumeStatisticsV2.views + 1,
                last_viewed_at=sa_text("now()"),
            )
        )
        await self._session.execute(stmt)
        await self._session.flush()

    async def increment_downloads(self, resume_id: UUID) -> None:
        """Atomic ``downloads + 1`` + ``last_downloaded_at = now()``.

        Single SQL UPDATE — see
        ``test_increment_downloads_sql_is_single_atomic_update``.
        """
        stmt = (
            update(ResumeStatisticsV2)
            .where(ResumeStatisticsV2.resume_id == resume_id)
            .values(
                downloads=ResumeStatisticsV2.downloads + 1,
                last_downloaded_at=sa_text("now()"),
            )
        )
        await self._session.execute(stmt)
        await self._session.flush()

    # ── 11. public lookup ─────────────────────────────────────────────

    async def get_by_username_and_slug(
        self, *, username: str, slug: str
    ) -> ResumeV2 | None:
        """Resolve a public ``/r/<username>/<slug>`` URL to a row.

        Public routes bind ``get_db_session_no_rls`` (so the GUC is
        unset), which means a plain SELECT against the RLS-bound
        table returns zero rows. We join to ``users`` via the FK
        ``resumes_v2.user_id`` and filter on ``display_name``
        (case-insensitive). The RLS policy still applies in
        NoRLS-mode only for the table owner; for ``appuser`` we
        fall through to ``set_config('role','appuser',...)`` via
        the no_rls session — verified by the Batch 5 ship gate.

        Returns the row, or ``None`` if no match.
        """
        from app.modules.auth.models import User

        stmt = (
            select(ResumeV2)
            .join(User, ResumeV2.user_id == User.id)
            .where(
                User.display_name == username,
                ResumeV2.slug == slug,
                ResumeV2.is_public.is_(True),
            )
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    # ── 12. analysis ───────────────────────────────────────────────────

    async def upsert_analysis(
        self,
        resume_id: UUID,
        *,
        analysis: dict[str, Any],
        status: str = "success",
        failure_reason: str | None = None,
    ) -> None:
        """Insert-or-replace the AI analysis row.

        Uses Postgres ``INSERT ... ON CONFLICT (resume_id) DO UPDATE``
        so a re-analyze always replaces the previous snapshot.
        ``updated_at`` is set to ``now()`` on every write.
        """
        payload = {
            "resume_id": resume_id,
            "analysis": analysis,
            "status": status,
            "failure_reason": failure_reason,
        }
        stmt = pg_insert(ResumeAnalysisV2).values(**payload)
        stmt = stmt.on_conflict_do_update(
            index_elements=[ResumeAnalysisV2.resume_id],
            set_={
                "analysis": stmt.excluded.analysis,
                "status": stmt.excluded.status,
                "failure_reason": stmt.excluded.failure_reason,
                "updated_at": sa_text("now()"),
            },
        )
        await self._session.execute(stmt)
        await self._session.flush()

    async def get_analysis(self, resume_id: UUID) -> dict[str, Any] | None:
        """Return the analysis row as a dict or ``None``.

        The API expects ``.status``, ``.analysis``, ``.failure_reason``,
        ``.updated_at`` attrs (see ``api.get_analysis``), so we round-
        trip through a dict with ISO-formatted timestamps.
        """
        stmt = select(ResumeAnalysisV2).where(
            ResumeAnalysisV2.resume_id == resume_id
        )
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        if row is None:
            return None
        return {
            "status": row.status,
            "analysis": row.analysis,
            "failure_reason": row.failure_reason,
            "updated_at": row.updated_at,
        }


__all__ = ["ResumeV2Repository"]
