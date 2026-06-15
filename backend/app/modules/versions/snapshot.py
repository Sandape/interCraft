"""Snapshot builder + restoration."""
from __future__ import annotations

from typing import Any
from uuid import UUID

import jsonpatch

from app.core.exceptions import VersionRestoreDepthExceededError
from app.modules.versions.models import ResumeVersion

MAX_RESTORE_DEPTH = 100


def build_snapshot(branch, blocks) -> dict[str, Any]:
    """Canonical snapshot shape (data-model §7)."""
    return {
        "branch": {
            "id": str(branch.id),
            "name": branch.name,
            "company": branch.company,
            "position": branch.position,
            "status": branch.status,
        },
        "blocks": [
            {
                "id": str(b.id),
                "type": b.type,
                "title": b.title,
                "content_md": b.content_md,
                "meta": b.meta,
                "order_index": b.order_index,
            }
            for b in sorted(blocks, key=lambda x: x.order_index)
        ],
    }


async def restore_version(
    session,
    version_id: UUID,
    *,
    _depth: int = 0,
    _cache: dict[UUID, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Recursively apply diff chain to a base full snapshot.

    Bounded by `MAX_RESTORE_DEPTH`. Caches intermediate results in
    `_cache` to avoid re-applying patches repeatedly.
    """
    if _depth > MAX_RESTORE_DEPTH:
        raise VersionRestoreDepthExceededError()
    _cache = _cache if _cache is not None else {}
    if version_id in _cache:
        return _cache[version_id]
    # Optional repo injection hook — kept as `_repo` to signal intentional ignore.
    _repo = getattr(session, "_repo_cache", None)
    del _repo
    # We always go through a fresh query for clarity.
    from sqlalchemy import select

    stmt = select(ResumeVersion).where(ResumeVersion.id == version_id)
    result = await session.execute(stmt)
    v = result.scalar_one_or_none()
    if v is None:
        raise VersionRestoreDepthExceededError()
    if v.is_full_snapshot:
        snap = v.snapshot_json or {}
        _cache[version_id] = snap
        return snap
    if v.base_version_id is None or v.diff_patch is None:
        raise VersionRestoreDepthExceededError()
    base = await restore_version(
        session, v.base_version_id, _depth=_depth + 1, _cache=_cache
    )
    restored = jsonpatch.apply_patch(base, v.diff_patch, in_place=False)
    _cache[version_id] = restored
    return restored


__all__ = ["MAX_RESTORE_DEPTH", "build_snapshot", "restore_version"]
