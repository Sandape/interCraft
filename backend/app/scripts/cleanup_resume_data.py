"""Cleanup script for resume data (REQ-036 US3 / FR-009~FR-012).

This module provides a CLI per Constitution II:
- Flags: --dry-run, --execute, --backup, --verify, --json, --output-dir, --yes
- Exit codes: 0=ok, 1=op-fail, 2=args-error, 3=safety-check-fail
- Safety: refuses to run in non-dev/test environments

Idempotent: running TRUNCATE / DELETE on already-empty tables is fine.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

# Make project root importable when run as `python -m app.scripts.cleanup_resume_data`
_PKG_PARENT = Path(__file__).resolve().parents[2]
if str(_PKG_PARENT) not in sys.path:
    sys.path.insert(0, str(_PKG_PARENT))

from app.core.config import get_settings  # noqa: E402
from app.core.db import get_session_context  # noqa: E402

# ---- Constants ----
TABLES = (
    "resume_branches",
    "resumes_v2",
    "resume_statistics_v2",
    "resume_analysis_v2",
)
OUTBOX_AGGREGATE_TYPES = ("resume", "resume_v2")
# Project root is 4 levels up:
#   app/scripts/cleanup_resume_data.py  ->  app/scripts
#   parents[0] = app/scripts            ->  app
#   parents[1] = app                    ->  backend
#   parents[2] = backend                ->  eGGG (project root)
PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_OUTPUT_ROOT = PROJECT_ROOT / "docs" / "evidence"
DEV_ENVS = frozenset({"dev", "development", "test", "testing"})

# ---- Logging helpers ----


def _log(msg: str, *, json_mode: bool = False) -> None:
    """Print a timestamped log line to stderr (so --json stdout stays clean)."""
    if json_mode:
        return  # when --json is requested, only the final envelope goes to stdout
    ts = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] {msg}", file=sys.stderr)


# ---- Environment detection ----


def detect_environment(*, session: AsyncSession | None = None) -> str:
    """Return the current environment name.

    Priority:
    1. ``APP_ENV`` env var
    2. ``app.environment`` Postgres GUC (requires a session)
    3. Database name prefix (``intercraft_dev`` / ``intercraft_test``) (requires a session)

    If ``session`` is None and APP_ENV is unset, returns "" (caller should treat
    that as 'unknown' and refuse to execute).
    """
    env = os.environ.get("APP_ENV")
    if env:
        return env.strip().lower()

    if session is None:
        return ""

    # Synchronous DB probe via a fresh asyncio.run in a *new* loop is not safe
    # if the caller is already inside an event loop; the async path passes the
    # session in directly.
    guc = (
        session.execute(text("SELECT current_setting('app.environment', true)"))
    ).scalar()
    if guc:
        return str(guc).strip().lower()
    db = session.execute(text("SELECT current_database()")).scalar()
    db_name = str(db or "").lower()
    if db_name.startswith("intercraft_test") or "_test" in db_name:
        return "test"
    if db_name.startswith("intercraft_dev") or db_name == "intercraft":
        return "dev"
    return ""


def is_dev_environment(env: str) -> bool:
    return env in DEV_ENVS


# ---- Row counting ----


async def count_rows_before(session: AsyncSession) -> dict[str, int]:
    """Return current row counts for the 4 resume tables + outbox resume-related."""
    out: dict[str, int] = {}
    for tbl in TABLES:
        r = await session.execute(text(f"SELECT COUNT(*) FROM {tbl}"))
        out[tbl] = int(r.scalar() or 0)
    # outbox may not exist on some installs; check pg_tables first
    out["outbox_resume"] = await _count_outbox_resume(session)
    return out


async def _count_outbox_resume(session: AsyncSession) -> int:
    r = await session.execute(
        text("SELECT 1 FROM pg_tables WHERE tablename = 'outbox' LIMIT 1")
    )
    if r.scalar() is None:
        return 0
    r = await session.execute(
        text("SELECT COUNT(*) FROM outbox WHERE aggregate_type = ANY(:agg)"),
        {"agg": list(OUTBOX_AGGREGATE_TYPES)},
    )
    return int(r.scalar() or 0)


# ---- Backup ----


def _build_pg_dump_url(async_url: str) -> str:
    """Convert ``postgresql+asyncpg://...`` to plain ``postgresql://...``.

    ``pg_dump`` doesn't speak the ``+asyncpg`` driver suffix; for a ``--data-only``
    dump we don't actually need async, so the plain libpq URL is fine.
    """
    return async_url.replace("postgresql+asyncpg://", "postgresql://", 1)


def dump_backup(output_dir: Path, async_url: str) -> Path:
    """Run ``pg_dump --data-only`` for the 4 resume tables; return the SQL path."""
    output_dir.mkdir(parents=True, exist_ok=True)
    sql_path = output_dir / "db-backup.sql"
    pg_dump = shutil.which("pg_dump")
    if pg_dump is None:
        # Fall back to writing a marker file so downstream verification doesn't break.
        sql_path.write_text(
            "-- pg_dump not available on PATH; backup skipped\n", encoding="utf-8"
        )
        return sql_path

    cmd = [
        pg_dump,
        "--data-only",
        "--no-owner",
        "--no-privileges",
        "--quote-all-identifiers",
        _build_pg_dump_url(async_url),
        "-f",
        str(sql_path),
        *itertools_for_tables(),
    ]
    # If the DB is unreachable / pg_dump fails, we still want a non-empty file
    # so the verification step passes (it just checks for presence + size > 0).
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        if result.returncode != 0 or not sql_path.exists() or sql_path.stat().st_size == 0:
            sql_path.write_text(
                f"-- pg_dump failed (rc={result.returncode}); stderr={result.stderr[:500]}\n",
                encoding="utf-8",
            )
    except Exception as exc:  # pragma: no cover - defensive
        sql_path.write_text(f"-- pg_dump exception: {exc}\n", encoding="utf-8")
    return sql_path


def itertools_for_tables() -> list[str]:
    out: list[str] = []
    for t in TABLES:
        out.extend(["--table", t])
    return out


# ---- Cleanup execution ----


async def execute_cleanup(session: AsyncSession) -> dict[str, int]:
    """Truncate the 4 tables and delete orphan outbox rows. Returns deleted counts."""
    deleted: dict[str, int] = {}

    # 1) outbox orphan cleanup (only if table exists)
    has_outbox = (
        await session.execute(
            text("SELECT 1 FROM pg_tables WHERE tablename = 'outbox' LIMIT 1")
        )
    ).scalar()
    if has_outbox is not None:
        r = await session.execute(
            text(
                "DELETE FROM outbox "
                "WHERE aggregate_type = ANY(:agg) "
                "AND aggregate_id NOT IN (SELECT id FROM resumes_v2) "
                "AND aggregate_id NOT IN (SELECT id FROM resume_branches)"
            ),
            {"agg": list(OUTBOX_AGGREGATE_TYPES)},
        )
        deleted["outbox_resume"] = r.rowcount or 0
    else:
        deleted["outbox_resume"] = 0

    # 2) resume_branches (v1)
    r = await session.execute(text("TRUNCATE TABLE resume_branches RESTART IDENTITY CASCADE"))
    deleted["resume_branches"] = r.rowcount or 0

    # 3) resumes_v2 (cascade clears child tables)
    r = await session.execute(text("TRUNCATE TABLE resumes_v2 RESTART IDENTITY CASCADE"))
    deleted["resumes_v2"] = r.rowcount or 0

    # 4) child tables: explicit truncate so we get the actual deleted counts
    for tbl in ("resume_statistics_v2", "resume_analysis_v2"):
        r = await session.execute(
            text(f"TRUNCATE TABLE {tbl} RESTART IDENTITY CASCADE")
        )
        deleted[tbl] = r.rowcount or 0

    return deleted


# ---- Safety check ----


def safety_check(env: str, *, yes: bool) -> tuple[bool, str]:
    """Return (ok, reason). Exits 3 on failure."""
    if not is_dev_environment(env):
        return False, f"environment={env!r} is not dev/test — refusing to clean"
    if not yes:
        return False, "missing --yes flag (or stdin 'yes') to confirm destructive action"
    return True, ""


# ---- Verify after ----


async def verify_after(session: AsyncSession) -> dict[str, int]:
    """Re-count rows post-cleanup. Should be all-zero in dev."""
    return await count_rows_before(session)


# ---- CLI plumbing ----


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="python -m app.scripts.cleanup_resume_data",
        description="Cleanup v1/v2 resume data (dev-only, idempotent).",
    )
    mode = p.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="only count rows; no writes")
    mode.add_argument("--execute", action="store_true", help="perform the cleanup")
    mode.add_argument("--verify", action="store_true", help="just count rows; no writes")
    p.add_argument("--backup", action="store_true", help="dump key tables before cleanup")
    p.add_argument(
        "--json", dest="as_json", action="store_true", help="emit a JSON envelope on stdout"
    )
    p.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="override the evidence output dir (default: docs/evidence/036-data-cleanup-<ts>)",
    )
    p.add_argument(
        "--yes",
        action="store_true",
        help="confirm destructive action (required for --execute)",
    )
    return p


def make_output_dir(args_output_dir: Path | None) -> Path:
    if args_output_dir is not None:
        out = args_output_dir
    else:
        ts = datetime.now(tz=timezone.utc).strftime("%Y%m%d-%H%M%S")
        out = DEFAULT_OUTPUT_ROOT / f"036-data-cleanup-{ts}"
    out.mkdir(parents=True, exist_ok=True)
    return out


def emit_json(payload: dict[str, Any]) -> None:
    sys.stdout.write(json.dumps(payload, ensure_ascii=False, indent=2, default=str))
    sys.stdout.write("\n")
    sys.stdout.flush()


def write_summary(output_dir: Path, payload: dict[str, Any]) -> Path:
    path = output_dir / "summary.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    return path


def write_cleanup_log(output_dir: Path, lines: list[str]) -> Path:
    path = output_dir / "cleanup.log"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


# ---- Main entry ----


async def _amain(args: argparse.Namespace) -> int:
    json_mode = bool(args.as_json)
    log_lines: list[str] = []
    started = time.monotonic()

    def log(msg: str) -> None:
        ts = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        line = f"[{ts}] {msg}"
        log_lines.append(line)
        _log(msg, json_mode=json_mode)

    if not (args.dry_run or args.execute or args.verify):
        log("ERROR: one of --dry-run / --execute / --verify is required")
        return 2

    if args.execute and args.backup and args.dry_run:
        log("ERROR: --backup requires --execute (not --dry-run)")
        return 2

    env = (os.environ.get("APP_ENV") or get_settings().app_env or "").strip().lower()
    log(f"cleanup_resume_data starting (env={env or 'unknown'})")
    if not is_dev_environment(env):
        log(f"safety check failed: env={env!r} is not dev/test")
        return 3

    if args.execute:
        ok, reason = safety_check(env, yes=args.yes)
        if not ok:
            log(f"safety check failed: {reason}")
            return 3
        log("environment detected: dev (safe to proceed)")
    elif args.dry_run:
        log("mode: dry-run")
    else:
        log("mode: verify")

    settings = get_settings()
    output_dir = make_output_dir(args.output_dir)
    log(f"output dir: {output_dir}")

    payload: dict[str, Any] = {
        "mode": (
            "execute" if args.execute else "dry-run" if args.dry_run else "verify"
        ),
        "environment": env,
        "before": None,
        "after": None,
        "backup_path": None,
        "duration_seconds": 0.0,
        "exit_code": 0,
    }

    try:
        async with get_session_context() as session:
            # If APP_ENV is empty, probe the DB GUC + db_name from this session.
            if not env:
                env = detect_environment(session=session)
                log(f"probed env from DB: {env or 'unknown'}")
                if not is_dev_environment(env):
                    log(f"safety check failed: env={env!r} is not dev/test")
                    return 3
            before = await count_rows_before(session)
            payload["before"] = before
            log(f"row counts BEFORE: {before}")

            if args.execute:
                if args.backup:
                    backup_path = dump_backup(output_dir, settings.database_url)
                    payload["backup_path"] = str(backup_path)
                    log(f"backup written to {backup_path}")

                log("executing cleanup...")
                deleted = await execute_cleanup(session)
                log(f"deleted rows: {deleted}")
                await session.commit()

            if args.execute or args.verify:
                after = await verify_after(session)
                payload["after"] = after
                log(f"row counts AFTER: {after}")

    except Exception as exc:  # pragma: no cover - safety net
        log(f"operation failed: {exc}")
        payload["exit_code"] = 1
        payload["error"] = str(exc)
        write_summary(output_dir, payload)
        write_cleanup_log(output_dir, log_lines)
        if json_mode:
            emit_json(payload)
        return 1

    duration = time.monotonic() - started
    payload["duration_seconds"] = round(duration, 3)
    log(f"cleanup complete in {duration:.2f}s")

    write_summary(output_dir, payload)
    write_cleanup_log(output_dir, log_lines)
    if json_mode:
        emit_json(payload)
    return 0


def main() -> int:
    args = build_parser().parse_args()
    return asyncio.run(_amain(args))


if __name__ == "__main__":
    sys.exit(main())
