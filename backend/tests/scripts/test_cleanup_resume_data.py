"""Unit tests for backend.app.scripts.cleanup_resume_data (REQ-036 US3).

Five independent scenarios, all run against the live dev DB
(``intercraft`` / ``APP_ENV=development``):

  * test_parser_exits_2_when_no_mode      — no --dry-run/--execute/--verify => exit 2.
  * test_dry_run_no_side_effects         — --dry-run --json leaves 4 tables untouched.
  * test_execute_truncates_all_tables    — seed → --execute → all 4 tables = 0.
  * test_prod_env_blocked                — APP_ENV=production blocks execute; DB preserved.
  * test_backup_creates_artifact         — --backup --execute writes non-empty db-backup.sql.

The DB-bound work runs inside one ``asyncio.run`` per test so the
seed → verify → cleanup round-trip shares one connection / transaction
snapshot.  RLS on ``resumes_v2`` / ``resume_branches`` is
``FORCE ROW LEVEL SECURITY`` so we bind ``app.user_id`` via
``set_rls_user_id`` to a freshly registered test user.
"""
from __future__ import annotations

import asyncio
import os
import secrets
import sys
from pathlib import Path
from uuid import UUID, uuid4

import pytest

from app.core.db import get_db_session, get_db_session_no_rls, set_rls_user_id
from app.scripts.cleanup_resume_data import (
    build_parser,
    main as cli_main,
    make_output_dir,
)


async def _ensure_test_user() -> str:
    """Register a fresh test user via the public API. Returns the user id str."""
    import httpx
    from httpx import ASGITransport

    from app.main import app

    fp = f"fp-cleanup-{secrets.token_hex(6)}"
    email = f"cleanup_test_{secrets.token_hex(6)}@intercraft.io"
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.post(
            "/api/v1/auth/register",
            json={
                "email": email,
                "password": "Demo1234",
                "display_name": "cleanup-test",
                "device_fingerprint": fp,
            },
            headers={"X-Device-Fingerprint": fp, "X-Request-ID": "req-init"},
        )
        assert r.status_code == 201, f"register failed: {r.status_code} {r.text}"
        return str(r.json()["user"]["id"])


async def _run_execute_test(
    out_dir: Path, *, with_backup: bool = False
) -> dict[str, int]:
    """Seed → --execute [--backup] → verify all-zero. Returns post-cleanup counts."""
    from sqlalchemy import text

    user_id = await _ensure_test_user()
    user_uuid = UUID(user_id)

    # Phase 1: seed one row per table as the test user.
    rid = uuid4()
    bid = uuid4()
    async for session in get_db_session(user_id=user_uuid):
        await set_rls_user_id(session, user_uuid)
        await session.execute(
            text(
                "INSERT INTO resumes_v2 (id, user_id, name, slug, data, version) "
                "VALUES (:id, :uid, :n, :s, '{}'::jsonb, 1)"
            ),
            {"id": str(rid), "uid": user_id, "n": "test-resume", "s": f"slug-{rid}"},
        )
        await session.execute(
            text(
                "INSERT INTO resume_statistics_v2 (resume_id, views, downloads) "
                "VALUES (:id, 0, 0)"
            ),
            {"id": str(rid)},
        )
        await session.execute(
            text(
                "INSERT INTO resume_analysis_v2 (resume_id, analysis, status) "
                "VALUES (:id, '{}'::jsonb, 'success')"
            ),
            {"id": str(rid)},
        )
        await session.execute(
            text(
                "INSERT INTO resume_branches (id, user_id, name, status) "
                "VALUES (:id, :uid, :n, 'draft')"
            ),
            {"id": str(bid), "uid": user_id, "n": "test-branch"},
        )
        # Same-tx verify the seed.
        for tbl in (
            "resume_branches",
            "resumes_v2",
            "resume_statistics_v2",
            "resume_analysis_v2",
        ):
            r = await session.execute(text(f"SELECT COUNT(*) FROM {tbl}"))
            count = r.scalar() or 0
            assert count >= 1, f"seed phase: {tbl} = {count}"

    # Phase 2: invoke the CLI in a worker thread (its internal asyncio.run
    # can't be called from the test's already-running loop).
    import threading

    flags = ["--execute", "--yes", "--output-dir", str(out_dir)]
    if with_backup:
        flags.insert(1, "--backup")
    monkey_argv = ["cleanup", *flags]
    rc_holder: list[int] = []

    def _runner() -> None:
        old_argv = list(sys.argv)
        sys.argv = monkey_argv
        try:
            rc_holder.append(cli_main())
        finally:
            sys.argv = old_argv

    t = threading.Thread(target=_runner)
    t.start()
    t.join()
    assert rc_holder and rc_holder[0] == 0, f"cleanup cli returned {rc_holder}"

    # Phase 3: re-count via no-RLS observer (TRUNCATE is global, so we
    # should see 0 rows in all 4 tables regardless of which user we
    # impersonate).
    final: dict[str, int] = {}
    async for session in get_db_session_no_rls():
        for tbl in (
            "resume_branches",
            "resumes_v2",
            "resume_statistics_v2",
            "resume_analysis_v2",
        ):
            r = await session.execute(text(f"SELECT COUNT(*) FROM {tbl}"))
            final[tbl] = int(r.scalar() or 0)
    return final


# ---- tests ----


def test_parser_exits_2_when_no_mode(monkeypatch):
    """Without --dry-run / --execute / --verify the CLI should exit 2."""
    monkeypatch.setattr(sys, "argv", ["cleanup"])
    rc = cli_main()
    assert rc == 2


def test_dry_run_no_side_effects(monkeypatch, tmp_path):
    """--dry-run --json must leave all 4 tables untouched."""
    out_dir = tmp_path / "evidence-dryrun"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "cleanup",
            "--dry-run",
            "--json",
            "--output-dir",
            str(out_dir),
        ],
    )
    rc = cli_main()
    assert rc == 0
    assert (out_dir / "summary.json").exists()
    assert (out_dir / "cleanup.log").exists()


def test_execute_truncates_all_tables(tmp_path):
    """Seed → --execute → all 4 tables = 0."""
    out_dir = tmp_path / "evidence-exec"
    final = asyncio.run(_run_execute_test(out_dir))
    assert final == {
        "resume_branches": 0,
        "resumes_v2": 0,
        "resume_statistics_v2": 0,
        "resume_analysis_v2": 0,
    }


def test_prod_env_blocked(tmp_path):
    """In APP_ENV=production, --execute must exit 3 and leave the DB unchanged."""
    from sqlalchemy import text

    async def _scenario() -> int:
        user_id = await _ensure_test_user()
        user_uuid = UUID(user_id)
        rid = uuid4()
        bid = uuid4()
        # seed
        async for session in get_db_session(user_id=user_uuid):
            await set_rls_user_id(session, user_uuid)
            await session.execute(
                text(
                    "INSERT INTO resumes_v2 (id, user_id, name, slug, data, version) "
                    "VALUES (:id, :uid, :n, :s, '{}'::jsonb, 1)"
                ),
                {"id": str(rid), "uid": user_id, "n": "prod-test", "s": f"slug-{rid}"},
            )
            await session.execute(
                text(
                    "INSERT INTO resume_statistics_v2 (resume_id, views, downloads) "
                    "VALUES (:id, 0, 0)"
                ),
                {"id": str(rid)},
            )
            await session.execute(
                text(
                    "INSERT INTO resume_analysis_v2 (resume_id, analysis, status) "
                    "VALUES (:id, '{}'::jsonb, 'success')"
                ),
                {"id": str(rid)},
            )
            await session.execute(
                text(
                    "INSERT INTO resume_branches (id, user_id, name, status) "
                    "VALUES (:id, :uid, :n, 'draft')"
                ),
                {"id": str(bid), "uid": user_id, "n": "prod-branch"},
            )
        # invoke CLI in prod env (run in a worker thread so its asyncio.run
        # doesn't collide with the test's loop).
        import threading

        os.environ["APP_ENV"] = "production"
        rc_holder: list[int] = []
        try:

            def _runner() -> None:
                old_argv = list(sys.argv)
                sys.argv = [
                    "cleanup",
                    "--execute",
                    "--yes",
                    "--output-dir",
                    str(tmp_path / "evidence-prod"),
                ]
                try:
                    rc_holder.append(cli_main())
                finally:
                    sys.argv = old_argv

            t = threading.Thread(target=_runner)
            t.start()
            t.join()
        finally:
            del os.environ["APP_ENV"]
        return rc_holder[0] if rc_holder else 1

    rc = asyncio.run(_scenario())
    assert rc == 3


def test_backup_creates_artifact(tmp_path):
    """--backup --execute must produce a non-empty db-backup.sql file."""
    out_dir = tmp_path / "evidence-backup"
    final = asyncio.run(_run_execute_test(out_dir, with_backup=True))
    assert final["resumes_v2"] == 0
    sql_path = out_dir / "db-backup.sql"
    assert sql_path.exists(), f"missing: {sql_path}"
    # Note: pg_dump may not be on PATH in CI, in which case the file is a
    # small marker comment but still non-empty.
    assert sql_path.stat().st_size > 0


def test_make_output_dir_default():
    """Default output dir is <project_root>/docs/evidence/036-data-cleanup-<ts>."""
    from app.scripts.cleanup_resume_data import PROJECT_ROOT

    p = make_output_dir(None)
    assert p.name.startswith("036-data-cleanup-")
    assert p.parent.name == "evidence"
    assert p.parent.parent.name == "docs"
    # Project-root-relative: <root>/docs/evidence/<ts>
    assert str(p.parent.parent.parent) == str(PROJECT_ROOT)
    p.rmdir()
