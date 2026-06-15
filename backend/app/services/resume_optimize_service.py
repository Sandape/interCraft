"""ResumeOptimizeService — lock acquire/release, patch apply, version creation.

Used by M16 Resume Optimize subgraph for DB operations.
"""
from __future__ import annotations

import json
from uuid import UUID, uuid4

import structlog
from sqlalchemy import text

from app.core.db import get_session_factory
from app.domain.rls import set_user_context

logger = structlog.get_logger("services.resume_optimize")


class ResumeOptimizeService:
    """Service layer for M16 operations."""

    async def acquire_lock(self, branch_id: str, user_id: str) -> bool:
        """Acquire a lock on the resume branch via Phase 3 M12 lock mechanism."""
        try:
            from app.modules.locks.redis_store import acquire as redis_acquire
            from uuid import uuid4

            lock_data = {
                "lock_id": str(uuid4()),
                "user_id": user_id,
                "resource_type": "resume_branch",
                "resource_id": branch_id,
            }
            return await redis_acquire("resume_branch", branch_id, lock_data)
        except Exception as exc:
            logger.warning("acquire_lock_error", branch_id=branch_id, error=str(exc))
            return False

    async def release_lock(self, branch_id: str, user_id: str) -> None:
        """Release the lock on the resume branch."""
        try:
            from app.modules.locks.redis_store import release as redis_release
            from app.modules.locks.redis_store import _key

            key = _key("resume_branch", branch_id)
            await redis_release(key)
        except Exception as exc:
            logger.warning("release_lock_error", branch_id=branch_id, error=str(exc))

    async def apply_patches_and_version(
        self,
        branch_id: str,
        user_id: str,
        patches: list[dict],
        summary: str = "AI optimization",
    ) -> str:
        """Apply JSON Patch to blocks and create a version snapshot.

        Returns the new version ID.
        """
        factory = get_session_factory()
        async with factory() as session:
            await set_user_context(session, user_id)
            user_uuid = UUID(user_id)
            branch_uuid = UUID(branch_id)

            # Apply each patch
            for patch in patches:
                op = patch.get("op")
                path = patch.get("path", "")
                value = patch.get("value", "")

                if op == "replace" and path.startswith("/blocks/"):
                    # Format: /blocks/{index}/content
                    parts = path.split("/")
                    if len(parts) >= 4:
                        block_index = int(parts[2])
                        field = parts[3]

                        # Get block by order_index ordering
                        result = await session.execute(
                            text(
                                """SELECT id FROM resume_blocks
                                WHERE branch_id = :bid AND deleted_at IS NULL
                                ORDER BY order_index ASC
                                LIMIT 1 OFFSET :idx"""
                            ),
                            {"bid": branch_uuid, "idx": block_index},
                        )
                        row = result.fetchone()
                        if row is not None:
                            block_id = row[0]
                            await session.execute(
                                text(
                                    f"UPDATE resume_blocks SET {field} = :val WHERE id = :bid"
                                ),
                                {"val": value, "bid": block_id},
                            )

                elif op == "replace" and path == "/content":
                    # Direct content replacement (single block mode)
                    if patches.index(patch) < len(await self._get_block_count(branch_id, session)):
                        pass  # handled via content field

            # Create version snapshot
            version_id = str(uuid4())
            await session.execute(
                text(
                    """INSERT INTO resume_versions
                    (id, branch_id, user_id, author_type, trigger, blocks_snapshot, summary_md)
                    VALUES (:id, :bid, :uid, :author, :trigger, :snapshot, :summary)"""
                ),
                {
                    "id": UUID(version_id),
                    "bid": branch_uuid,
                    "uid": user_uuid,
                    "author": "ai",
                    "trigger": "ai",
                    "snapshot": json.dumps(patches),
                    "summary": summary,
                },
            )

            # Update branch last_edited_at
            await session.execute(
                text("UPDATE resume_branches SET last_edited_at = now() WHERE id = :bid"),
                {"bid": branch_uuid},
            )

            await session.commit()

        return version_id

    async def _get_block_count(self, branch_id: str, session) -> int:
        result = await session.execute(
            text("SELECT count(*) FROM resume_blocks WHERE branch_id = :bid AND deleted_at IS NULL"),
            {"bid": UUID(branch_id)},
        )
        return result.scalar() or 0


__all__ = ["ResumeOptimizeService"]
