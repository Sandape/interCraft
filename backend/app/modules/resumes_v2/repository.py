"""M032 — Resume v2 repository (REB-032 v2 MVP stub).

The real repository lives in feature 032 v2 US1 (T018 — RLS-bound
async CRUD + optimistic concurrency). For the REB-032 v2 MVP we
only need the class to import cleanly so
``app.modules.resumes_v2.service`` can hold a reference to it
(``self.repo = ResumeV2Repository(session)``). The full SQL
implementation (create, get, list, update_with_version, soft_delete,
duplicate, set_sharing, set_lock, get_owner_id, get_statistics,
upsert_analysis, get_analysis) ships in a later US phase.

Runtime calls into this stub will raise ``NotImplementedError`` — that
is the intended behavior for the MVP. The backend only needs to
*start* so the v2 endpoints can be probed; the smoke test
(``uv run python -c "from app.main import app"``) does not exercise
any v2 CRUD path.
"""
from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession


class ResumeV2Repository:
    """Stub repository — real SQL lives in 032 v2 US1 (T018)."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, **_kwargs: Any) -> Any:
        raise NotImplementedError("ResumeV2Repository.create — ships in 032 v2 US1 (T018).")

    async def get(self, _resume_id: UUID, *, user_id: UUID) -> Any:
        raise NotImplementedError("ResumeV2Repository.get — ships in 032 v2 US1 (T018).")

    async def list(self, _user_id: UUID, **_filters: Any) -> list[Any]:
        raise NotImplementedError("ResumeV2Repository.list — ships in 032 v2 US1 (T018).")

    async def get_owner_id(self, _resume_id: UUID) -> UUID | None:
        raise NotImplementedError("ResumeV2Repository.get_owner_id — ships in 032 v2 US1 (T018).")

    async def update_with_version(self, **_kwargs: Any) -> int | None:
        raise NotImplementedError("ResumeV2Repository.update_with_version — ships in 032 v2 US1 (T018).")

    async def soft_delete(self, _resume_id: UUID, *, user_id: UUID) -> bool:
        raise NotImplementedError("ResumeV2Repository.soft_delete — ships in 032 v2 US1 (T018).")

    async def duplicate(self, **_kwargs: Any) -> Any:
        raise NotImplementedError("ResumeV2Repository.duplicate — ships in 032 v2 US1 (T018).")

    async def set_sharing(self, **_kwargs: Any) -> Any:
        raise NotImplementedError("ResumeV2Repository.set_sharing — ships in 032 v2 US11 (T161).")

    async def set_lock(self, **_kwargs: Any) -> bool:
        raise NotImplementedError("ResumeV2Repository.set_lock — ships in 032 v2 US1 (T018).")

    async def get_statistics(self, _resume_id: UUID) -> Any:
        raise NotImplementedError("ResumeV2Repository.get_statistics — ships in 032 v2 US11 (T161).")

    async def upsert_analysis(self, **_kwargs: Any) -> None:
        raise NotImplementedError("ResumeV2Repository.upsert_analysis — ships in 032 v2 US14 (T151).")

    async def get_analysis(self, _resume_id: UUID) -> Any:
        raise NotImplementedError("ResumeV2Repository.get_analysis — ships in 032 v2 US14 (T151).")


__all__ = ["ResumeV2Repository"]