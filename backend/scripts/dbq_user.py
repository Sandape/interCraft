#!/usr/bin/env python3
"""dbq_user — like dbq, but runs SELECT inside a transaction with
SET LOCAL app.user_id = '<uuid>' so RLS policies can resolve to a
concrete user. The original dbq.py does not set this GUC, so
user-scoped tables always return 0 rows under RLS.

Usage (mirrors dbq sql):
  uv run python -m scripts.dbq_user sql --user-id <uuid> "SELECT ..."

Output: same JSON / pretty format as dbq.
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts import dbq  # noqa: E402


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="dbq_user", add_help=True)
    p.add_argument("--user-id", required=True, help="UUID to set as app.user_id for RLS")
    sub = p.add_subparsers(dest="command", required=True)

    q = sub.add_parser("sql", help="Run raw SQL inside an RLS transaction")
    q.add_argument("sql", help="SQL statement")
    q.add_argument("--json", action="store_true")
    q.add_argument("--csv", action="store_true")
    q.add_argument("--raw", action="store_true")
    q.add_argument("-q", "--quiet", action="store_true")
    return p


async def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()
    if args.command != "sql":
        parser.error("only sql subcommand supported")

    user_id = args.user_id
    # Validate UUID format loosely
    if len(user_id) not in (32, 36):
        print(f"warning: user_id {user_id!r} does not look like a UUID", file=sys.stderr)

    conn = await dbq._connect()  # type: ignore[attr-defined]
    try:
        async with conn.transaction():
            await conn.execute(f"SET LOCAL app.user_id = '{user_id}'")
            # Reuse dbq.cmd_sql logic but with our own quiet/json flags
            sql = args.sql.strip()
            records = await conn.fetch(sql)
            if not records:
                if not args.quiet:
                    print("(ok, no rows returned)")
                return
            names = list(records[0].keys())
            data = [tuple(r.values()) for r in records]
            if args.csv:
                dbq._print_csv(data, names)  # type: ignore[attr-defined]
            elif args.json:
                dbq._print_json(data, names)  # type: ignore[attr-defined]
            else:
                dbq._print_table(data, names)  # type: ignore[attr-defined]
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())