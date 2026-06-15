"""One-off cleanup: delete stale branches for demo user, keep the 2 newest."""
import asyncio
import asyncpg
import os
from pathlib import Path

env_file = Path(".env")
for line in env_file.read_text().splitlines():
    line = line.strip()
    if line and not line.startswith("#") and "=" in line:
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip())
d = os.environ["DATABASE_URL"].replace("postgresql+asyncpg", "postgresql")


async def main():
    c = await asyncpg.connect(d)
    uid = await c.fetchval("SELECT id FROM users WHERE email='demo@intercraft.io'")
    rows = await c.fetch(
        "SELECT id, name, is_main, created_at FROM resume_branches "
        "WHERE user_id=$1 ORDER BY created_at DESC",
        uid,
    )
    print(f"branches for demo: {len(rows)}")
    for r in rows:
        print(f"  id={r['id']}  name={r['name']!r}  main={r['is_main']}  at={r['created_at']}")
    keep = {str(r["id"]) for r in rows[:2]}
    for r in rows:
        if str(r["id"]) not in keep:
            await c.execute("DELETE FROM resume_blocks WHERE branch_id=$1", r["id"])
            await c.execute("DELETE FROM resume_versions WHERE branch_id=$1", r["id"])
            await c.execute("DELETE FROM resume_branches WHERE id=$1", r["id"])
            print(f"  deleted: {r['name']!r}")
    final = await c.fetchval("SELECT COUNT(*) FROM resume_branches WHERE user_id=$1", uid)
    print(f"final branch count: {final}")
    await c.close()


asyncio.run(main())
