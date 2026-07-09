"""[REQ-048 T-NEW-2] Backfill embeddings for EXISTING error_questions.

Enqueues ``compute_embedding_task`` for every ``error_questions`` row
where ``embedding IS NULL``. Run after the migration 0029 to populate
the pgvector column for legacy data.

Usage:
    cd backend && uv run python -m scripts.backfill_embeddings [--dry-run]

Verification (AC-11):
    PGPASSWORD=$DB_PASS psql -c "SELECT COUNT(*) FILTER (WHERE embedding IS NULL), COUNT(*) FROM error_questions;"
    # Expected after backfill: 0 / N (no NULL rows remain)
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path

# Ensure backend/ is on sys.path when invoked as ``python -m scripts.backfill_embeddings``.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sqlalchemy import text  # noqa: E402

from app.core.db import _session_cm  # noqa: E402
from app.core.redis import enqueue_job  # noqa: E402


logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")


async def list_unembedded_ids(limit: int = 1000) -> list[str]:
    """Return up to ``limit`` error_question IDs that lack embeddings."""
    async with _session_cm() as session:
        result = await session.execute(
            text(
                """
                SELECT id::text
                FROM error_questions
                WHERE deleted_at IS NULL AND embedding IS NULL
                ORDER BY created_at ASC
                LIMIT :limit
                """
            ),
            {"limit": int(limit)},
        )
        rows = result.scalars().all()
    return [str(r) for r in rows]


async def enqueue_backfill(ids: list[str], *, dry_run: bool = False) -> int:
    """Enqueue compute_embedding_task for each id. Returns count enqueued."""
    if dry_run:
        logger.info("backfill.dry_run", count=len(ids))
        return 0
    enqueued = 0
    for qid in ids:
        try:
            await enqueue_job("compute_embedding_task", error_question_id=qid)
            enqueued += 1
        except Exception as exc:  # noqa: BLE001
            logger.warning("backfill.enqueue_failed", id=qid, exc=str(exc))
    return enqueued


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=1000, help="Max rows to enqueue")
    parser.add_argument("--dry-run", action="store_true", help="List but don't enqueue")
    args = parser.parse_args()

    ids = await list_unembedded_ids(limit=args.limit)
    logger.info("backfill.found", count=len(ids), dry_run=args.dry_run)

    if not ids:
        logger.info("backfill.nothing_to_do")
        return 0

    enqueued = await enqueue_backfill(ids, dry_run=args.dry_run)
    logger.info("backfill.enqueued", count=enqueued)
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))