#!/usr/bin/env python3
"""Quick database access for development — tables, schema, query, search.

Usage:
  uv run python -m scripts.dbq tables                  # list all tables
  uv run python -m scripts.dbq schema [table]           # show column info
  uv run python -m scripts.dbq count [table]            # row counts
  uv run python -m scripts.dbq rows <table> [options]   # SELECT * LIMIT N
  uv run python -m scripts.dbq sql "SELECT ..."         # raw SQL
  uv run python -m scripts.dbq search <text>            # grep across tables
  uv run python -m scripts.dbq fkeys <table>            # foreign key graph
  uv run python -m scripts.dbq explain "SELECT ..."     # query plan

Options:
  -l, --limit N     Max rows (default 20, 0 = unlimited)
  -w, --where C     WHERE clause (for rows command)
  -o, --order C     ORDER BY clause (for rows command)
  --json            Output as JSON lines
  --raw             Raw output (no pretty formatting)
  --csv             CSV output
  -q, --quiet       Suppress header/footer info
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import sys
import textwrap
from pathlib import Path
from typing import Any

# Make app.* importable so we can reuse settings
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.core.config import get_settings  # noqa: E402


# ── connection helpers ────────────────────────────────────────────────────

def _parse_dsn(raw: str) -> str:
    """Convert sqlalchemy-style DSN (postgresql+asyncpg://) to asyncpg DSN."""
    return re.sub(r"^postgresql\+asyncpg://", "postgresql://", raw)


async def _connect():
    import asyncpg
    settings = get_settings()
    dsn = _parse_dsn(settings.database_url)
    ssl_setting = settings.db_ssl  # "prefer", "require", etc.
    connect_kwargs: dict[str, object] = {}
    if ssl_setting:
        # asyncpg.connect() accepts "prefer", "require", etc. as ssl=string
        connect_kwargs["ssl"] = ssl_setting
    return await asyncpg.connect(dsn, **connect_kwargs)


async def _fetch_with_user(conn, sql: str, user_id: str | None):
    """Execute a SQL statement. If user_id is set, wrap the execution
    in a transaction with `SET LOCAL app.user_id = '<uuid>'` first so
    RLS policies (for both reads AND writes) can resolve to a concrete
    user. Without this, RLS-protected tables will silently UPDATE 0
    rows (because current_setting('app.user_id') is NULL and the
    policy's USING clause fails).
    """
    sql = sql.strip()
    if user_id:
        async with conn.transaction():
            await conn.execute(f"SET LOCAL app.user_id = '{user_id}'")
            return await conn.fetch(sql)
    return await conn.fetch(sql)


# ── pretty printer ────────────────────────────────────────────────────────

def _fmt(val: Any, max_width: int = 48) -> str:
    """Format a single value for table display."""
    if val is None:
        return "NULL".ljust(6)
    if isinstance(val, (dict, list)):
        s = json.dumps(val, ensure_ascii=False)
    elif isinstance(val, bytes):
        s = val.hex()[:20] + "…" if len(val) > 20 else val.hex()
    else:
        s = str(val)
    if len(s) > max_width:
        s = s[: max_width - 1] + "…"
    return s


def _print_table(rows: list[tuple], names: list[str] | None = None) -> None:
    """Pretty-print a list of tuples as a grid table."""
    if not rows:
        print("(no rows)")
        return
    if names is None:
        names = [f"c{i}" for i in range(len(rows[0]))]

    widths = [len(n) for n in names]
    formatted: list[list[str]] = []
    for row in rows:
        formatted.append([_fmt(v) for v in row])
    for i in range(len(names)):
        for row_fmt in formatted:
            widths[i] = max(widths[i], len(row_fmt[i]))
        widths[i] = min(widths[i], 64)  # cap column width

    sep = "+-" + "-+-".join("-" * w for w in widths) + "-+"
    header = "| " + " | ".join(n.ljust(widths[i]) for i, n in enumerate(names)) + " |"

    print(sep)
    print(header)
    print(sep)
    for row_fmt in formatted:
        truncated = [v[: widths[i]] for i, v in enumerate(row_fmt)]
        print("| " + " | ".join(v.ljust(widths[i]) for i, v in enumerate(truncated)) + " |")
    print(sep)
    print(f"({len(rows)} row{'s' if len(rows) != 1 else ''})")


def _print_csv(rows: list[tuple], names: list[str] | None = None) -> None:
    """CSV output."""
    if names is None and rows:
        names = [f"c{i}" for i in range(len(rows[0]))]
    if names:
        print(",".join(names))
    for row in rows:
        print(",".join(_fmt(v).replace(",", "\\,") for v in row))


def _print_json(rows: list[tuple], names: list[str] | None = None) -> None:
    """JSON lines output."""
    if names is None and rows:
        names = [f"c{i}" for i in range(len(rows[0]))]
    for row in rows:
        obj = {names[i]: row[i] for i in range(len(row))}
        print(json.dumps(obj, ensure_ascii=False, default=str))


# ── commands ──────────────────────────────────────────────────────────────

async def cmd_tables(conn, args: argparse.Namespace) -> None:
    rows = await conn.fetch(
        "SELECT schemaname, tablename, "
        "  pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size "
        "FROM pg_catalog.pg_tables "
        "WHERE schemaname NOT IN ('pg_catalog','information_schema') "
        "ORDER BY schemaname, tablename"
    )
    names = ["schema", "table", "size"]
    data = [(r["schemaname"], r["tablename"], r["size"]) for r in rows]
    _print_table(data, names)


async def cmd_schema(conn, args: argparse.Namespace) -> None:
    table = args.table
    if table:
        parts = table.split(".", 1)
        schema = parts[0] if len(parts) > 1 else "public"
        tbl = parts[1] if len(parts) > 1 else table
        rows = await conn.fetch(
            """
            SELECT
              c.column_name,
              c.data_type,
              c.character_maximum_length,
              c.is_nullable,
              c.column_default,
              tc.constraint_type AS pk
            FROM information_schema.columns c
            LEFT JOIN information_schema.key_column_usage kcu
              ON c.table_schema = kcu.table_schema
             AND c.table_name = kcu.table_name
             AND c.column_name = kcu.column_name
            LEFT JOIN information_schema.table_constraints tc
              ON kcu.constraint_name = tc.constraint_name
             AND tc.constraint_type = 'PRIMARY KEY'
            WHERE c.table_schema = $1 AND c.table_name = $2
            ORDER BY c.ordinal_position
            """,
            schema, tbl,
        )
        if not rows:
            print(f"table '{table}' not found")
            return
        data = [
            (
                r["column_name"],
                r["data_type"] + (f"({r['character_maximum_length']})" if r["character_maximum_length"] else ""),
                r["is_nullable"],
                r["column_default"] or "",
                "PK" if r["pk"] else "",
            )
            for r in rows
        ]
        _print_table(data, ["column", "type", "nullable", "default", "key"])
    else:
        # List all tables with their column count
        rows = await conn.fetch(
            """
            SELECT schemaname, tablename, COUNT(*)::int AS cols
            FROM pg_catalog.pg_tables t
            JOIN information_schema.columns c
              ON c.table_schema = t.schemaname AND c.table_name = t.tablename
            WHERE t.schemaname NOT IN ('pg_catalog','information_schema')
            GROUP BY schemaname, tablename
            ORDER BY schemaname, tablename
            """
        )
        names = ["schema", "table", "columns"]
        data = [(r["schemaname"], r["tablename"], r["cols"]) for r in rows]
        _print_table(data, names)


async def cmd_count(conn, args: argparse.Namespace) -> None:
    table = args.table
    if table:
        # validate
        parts = table.split(".", 1)
        tbl = parts[-1]
        result = await conn.fetchrow(f'SELECT COUNT(*)::int AS cnt FROM "{tbl}"')
        print(f"{table}: {result['cnt']} rows")
    else:
        rows = await conn.fetch(
            """
            SELECT schemaname, tablename
            FROM pg_catalog.pg_tables
            WHERE schemaname NOT IN ('pg_catalog','information_schema')
            ORDER BY schemaname, tablename
            """
        )
        data = []
        for r in rows:
            cnt = await conn.fetchval(
                f'SELECT COUNT(*)::int FROM "{r["tablename"]}"'
            )
            data.append((r["schemaname"], r["tablename"], cnt))
        _print_table(data, ["schema", "table", "rows"])


async def cmd_rows(conn, args: argparse.Namespace) -> None:
    table = args.table
    limit = args.limit
    where = args.where
    order = args.order

    sql = f'SELECT * FROM "{table}"'
    if where:
        sql += f" WHERE {where}"
    if order:
        sql += f" ORDER BY {order}"
    if limit:
        sql += f" LIMIT {limit}"

    if args.explain:
        sql = f"EXPLAIN (ANALYZE, COSTS, VERBOSE, BUFFERS, FORMAT TEXT)\n{sql}"

    if not args.quiet:
        print(f"-- {sql}", file=sys.stderr)

    records = await _fetch_with_user(conn, sql, getattr(args, "user_id", None))
    if not records:
        print("(no rows)")
        return

    names = list(records[0].keys())
    data = [tuple(r.values()) for r in records]

    if args.csv:
        _print_csv(data, names)
    elif args.json:
        _print_json(data, names)
    else:
        _print_table(data, names)


async def cmd_sql(conn, args: argparse.Namespace) -> None:
    sql = args.sql.strip()
    if args.explain:
        sql = f"EXPLAIN (ANALYZE, COSTS, VERBOSE, BUFFERS, FORMAT TEXT)\n{sql}"

    if not args.quiet:
        print(f"-- {sql}", file=sys.stderr)

    records = await _fetch_with_user(conn, sql, getattr(args, "user_id", None))
    if not records:
        print("(ok, no rows returned)")
        return

    names = list(records[0].keys())
    data = [tuple(r.values()) for r in records]

    if args.csv:
        _print_csv(data, names)
    elif args.json:
        _print_json(data, names)
    else:
        _print_table(data, names)


async def cmd_search(conn, args: argparse.Namespace) -> None:
    """Grep across all text/varchar/jsonb columns."""
    term = args.search_term
    pattern = f"%{term}%"

    # Find all text-like columns
    cols = await conn.fetch(
        """
        SELECT table_name, column_name, data_type
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND data_type IN ('text', 'character varying', 'jsonb', 'name', 'inet')
          AND table_name NOT IN ('alembic_version')
        ORDER BY table_name, ordinal_position
        """
    )

    total = 0
    for c in cols:
        tbl, col, dtype = c["table_name"], c["column_name"], c["data_type"]
        try:
            if dtype == "jsonb":
                rows = await conn.fetch(
                    f'SELECT COUNT(*)::int AS cnt FROM "{tbl}" WHERE "{col}"::text ILIKE $1 LIMIT 5',
                    pattern,
                )
            else:
                rows = await conn.fetch(
                    f'SELECT COUNT(*)::int AS cnt FROM "{tbl}" WHERE "{col}"::text ILIKE $1 LIMIT 5',
                    pattern,
                )
            cnt = rows[0]["cnt"] if rows else 0
            if cnt:
                print(f"  {tbl}.{col}  ({dtype})  — {cnt} hit{'s' if cnt != 1 else ''}")
                total += cnt
        except Exception as e:
            print(f"  {tbl}.{col}  — ERROR: {e}")

    if total:
        print(f"\n{total} total matches for '{term}'")
    else:
        print(f"(no matches for '{term}')")


async def cmd_fkeys(conn, args: argparse.Namespace) -> None:
    table = args.table
    parts = table.split(".", 1)
    tbl = parts[-1]

    # foreign keys FROM this table
    print(f"── Foreign keys FROM {table} ──")
    rows = await conn.fetch(
        """
        SELECT
          tc.constraint_name,
          kcu.column_name,
          ccu.table_schema AS ref_schema,
          ccu.table_name AS ref_table,
          ccu.column_name AS ref_column
        FROM information_schema.table_constraints tc
        JOIN information_schema.key_column_usage kcu
          ON tc.constraint_name = kcu.constraint_name
        JOIN information_schema.constraint_column_usage ccu
          ON tc.constraint_name = ccu.constraint_name
        WHERE tc.constraint_type = 'FOREIGN KEY'
          AND tc.table_name = $1
        """,
        tbl,
    )
    if rows:
        data = [(r["constraint_name"], r["column_name"],
                  f"{r['ref_schema']}.{r['ref_table']}({r['ref_column']})") for r in rows]
        _print_table(data, ["constraint", "column", "references"])
    else:
        print("  (none)")

    # foreign keys REFERENCING this table
    print(f"\n── Foreign keys REFERENCING {table} ──")
    rows = await conn.fetch(
        """
        SELECT
          tc.constraint_name,
          tc.table_name,
          kcu.column_name
        FROM information_schema.table_constraints tc
        JOIN information_schema.key_column_usage kcu
          ON tc.constraint_name = kcu.constraint_name
        WHERE tc.constraint_type = 'FOREIGN KEY'
          AND tc.constraint_name IN (
            SELECT constraint_name
            FROM information_schema.constraint_column_usage
            WHERE table_name = $1
          )
        ORDER BY tc.table_name
        """,
        tbl,
    )
    if rows:
        data = [(r["constraint_name"], r["table_name"], r["column_name"]) for r in rows]
        _print_table(data, ["constraint", "from_table", "column"])
    else:
        print("  (none)")


async def cmd_explain(conn, args: argparse.Namespace) -> None:
    sql = args.sql.strip()
    plan_sql = f"EXPLAIN (ANALYZE, COSTS, VERBOSE, BUFFERS, FORMAT TEXT)\n{sql}"
    if not args.quiet:
        print(f"-- {plan_sql}", file=sys.stderr)
    rows = await conn.fetch(plan_sql)
    for r in rows:
        print(r[0])


# ── CLI dispatcher ────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Quick database access for development.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""\
            Examples:
              uv run python -m scripts.dbq tables
              uv run python -m scripts.dbq schema users
              uv run python -m scripts.dbq count
              uv run python -m scripts.dbq rows resume_branches -l 10
              uv run python -m scripts.dbq rows users -w "status='active'" --order created_at
              uv run python -m scripts.dbq sql "SELECT id, email FROM users LIMIT 3"
              uv run python -m scripts.dbq sql "SELECT * FROM resume_blocks" --json
              uv run python -m scripts.dbq search "demo@intercraft.io"
              uv run python -m scripts.dbq fkeys resume_blocks
              uv run python -m scripts.dbq explain "SELECT count(*) FROM users"
        """),
    )

    # Common output options (added to each subparser so they can follow the subcommand)
    common_output = argparse.ArgumentParser(add_help=False)
    common_output.add_argument("--json", action="store_true", help="JSON lines output")
    common_output.add_argument("--csv", action="store_true", help="CSV output")
    common_output.add_argument("--raw", action="store_true", help="Raw output")
    common_output.add_argument("-q", "--quiet", action="store_true", help="Suppress info messages")
    common_output.add_argument("--explain", action="store_true", help="Prefix with EXPLAIN ANALYZE")

    # Common query options
    common_query = argparse.ArgumentParser(add_help=False)
    common_query.add_argument("-l", "--limit", type=int, default=20, help="Max rows (0 = unlimited)")
    common_query.add_argument("-w", "--where", type=str, default=None, help="WHERE clause")
    common_query.add_argument("-o", "--order", type=str, default=None, help="ORDER BY clause")

    # Top-level flags only
    p.add_argument("--version", action="version", version="dbq 0.1")
    p.add_argument(
        "--user-id",
        default=None,
        help="UUID to set as app.user_id GUC before SELECTs (RLS bypass via SET LOCAL)",
    )

    sub = p.add_subparsers(dest="command", required=True)

    q = sub.add_parser("tables", parents=[common_output], help="List all tables")
    q = sub.add_parser("schema", parents=[common_output], help="Show table schemas")
    q.add_argument("table", nargs="?", default=None, help="Table name (optional)")

    q = sub.add_parser("count", parents=[common_output], help="Count rows")
    q.add_argument("table", nargs="?", default=None, help="Table name (optional)")

    q = sub.add_parser("rows", parents=[common_output, common_query], help="SELECT * FROM table")
    q.add_argument("table", help="Table name")

    q = sub.add_parser("sql", parents=[common_output, common_query], help="Run raw SQL")
    q.add_argument("sql", help="SQL statement")

    q = sub.add_parser("search", parents=[common_output], help="Search across all text columns")
    q.add_argument("search_term", help="Text to search for")

    q = sub.add_parser("fkeys", parents=[common_output], help="Show foreign key relationships")
    q.add_argument("table", help="Table name")

    q = sub.add_parser("explain", parents=[common_output], help="Show query execution plan")
    q.add_argument("sql", help="SQL statement to EXPLAIN")

    return p


async def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    # Validate dependencies
    try:
        import asyncpg  # noqa: F401
    except ImportError:
        print("error: asyncpg is not installed. Run: uv sync")
        sys.exit(1)

    conn = await _connect()
    try:
        if args.command == "tables":
            await cmd_tables(conn, args)
        elif args.command == "schema":
            await cmd_schema(conn, args)
        elif args.command == "count":
            await cmd_count(conn, args)
        elif args.command == "rows":
            await cmd_rows(conn, args)
        elif args.command == "sql":
            await cmd_sql(conn, args)
        elif args.command == "search":
            await cmd_search(conn, args)
        elif args.command == "fkeys":
            await cmd_fkeys(conn, args)
        elif args.command == "explain":
            await cmd_explain(conn, args)
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
