"""Verify interview session soft delete by pre-setting RLS GUC."""
import asyncio
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.core.config import get_settings  # noqa: E402
import asyncpg  # noqa: E402


async def main(user_id: str, session_id: str) -> None:
    raw = get_settings().database_url
    dsn = re.sub(r"^postgresql\+asyncpg://", "postgresql://", raw)
    conn = await asyncpg.connect(dsn)
    try:
        # SET LOCAL only takes effect inside a transaction
        async with conn.transaction():
            # SET LOCAL does not accept bind parameters; escape single quotes
            safe_uid = user_id.replace("'", "''")
            await conn.execute(f"SET LOCAL app.user_id = '{safe_uid}'")
            row = await conn.fetchrow(
                """
                SELECT id, status, deleted_at, position, company
                FROM interview_sessions
                WHERE id = $1::uuid
                """,
                session_id,
            )
        if row is None:
            print(f"[not found] session {session_id} for user {user_id}")
            sys.exit(1)
        else:
            print(f"id         = {row['id']}")
            print(f"company    = {row['company']}")
            print(f"position   = {row['position']}")
            print(f"status     = {row['status']}")
            print(f"deleted_at = {row['deleted_at']}")
            if row["deleted_at"] is None:
                print("[FAIL] deleted_at is NULL — soft delete did NOT persist")
                sys.exit(1)
            else:
                print("[OK] soft delete persisted: deleted_at is set")
    finally:
        await conn.close()


if __name__ == "__main__":
    user_id = sys.argv[1]
    session_id = sys.argv[2]
    asyncio.run(main(user_id, session_id))
