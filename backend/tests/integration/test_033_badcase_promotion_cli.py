"""REQ-033 US8 — badcase promotion CLI integration tests (T057).

Exercises the argparse CLI at ``app.modules.badcases.cli`` via
subprocess (matches the redaction CLI test pattern). The CLI writes to
PostgreSQL via the repository module and writes golden-case candidates
to ``$BADCASES_GOLDEN_DIR/<badcase_id>.candidate.json`` (default
``specs/033-eval-pm-dashboard/golden/``).

Subcommands exercised:

- ``create`` — writes a new badcase row, prints JSON.
- ``promote`` — appends a PROMOTE_CANDIDATE review action + writes the
  candidate file.
- ``close`` — appends a CLOSE review action + sets status=CLOSED.

Exit-code contract (per eval CLI discipline):

- ``0`` — success
- ``1`` — operational failure (DB error, IO)
- ``2`` — invalid args (missing required flag)
- ``3`` — policy violation (e.g. unknown type)

Skipped when ``DATABASE_URL`` is not set; this is a real-DB
integration test, consistent with the rest of the 033 suite.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import uuid
from pathlib import Path
from uuid import UUID

import httpx
import pytest
import pytest_asyncio
from httpx import ASGITransport

# Backend repo root (where ``uv run python -m app.X`` resolves).
_BACKEND = Path(__file__).resolve().parents[2]
_REPO_ROOT = _BACKEND.parent


def _run_cli(*args: str, cwd: Path | None = None, env: dict | None = None) -> subprocess.CompletedProcess:
    """Run ``python -m app.modules.badcases.cli`` with the given args."""
    cmd = [sys.executable, "-m", "app.modules.badcases.cli", *args]
    merged = dict(os.environ)
    if env:
        merged.update(env)
    return subprocess.run(
        cmd,
        cwd=str(cwd or _BACKEND),
        capture_output=True,
        text=True,
        env=merged,
        timeout=60,
    )


# Skip whole module when DB is unavailable.
pytestmark = pytest.mark.skipif(
    not os.environ.get("DATABASE_URL"),
    reason="DATABASE_URL not set; integration test needs real Postgres",
)


@pytest.fixture
def golden_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Override the candidate-write directory via env var."""
    target = tmp_path / "golden"
    target.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("BADCASES_GOLDEN_DIR", str(target))
    return target


@pytest_asyncio.fixture
async def cli_user_id(monkeypatch: pytest.MonkeyPatch) -> str:
    """Register a user via the auth endpoint and return the UUID string.

    The CLI binds badcases to ``--user-id`` for RLS; registering via
    /auth/register ensures the user exists in the users table so the
    badcases.user_id FK resolves.
    """
    from app.main import create_app

    suffix = uuid.uuid4().hex[:8]
    email = f"cli_bc_{suffix}@intercraft.io"
    fp = f"fp-{suffix}"
    app = create_app()
    async with httpx.AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test", timeout=30
    ) as client:
        resp = await client.post(
            "/api/v1/auth/register",
            json={
                "email": email,
                "password": "Demo1234",
                "display_name": suffix,
                "device_fingerprint": fp,
            },
            headers={"X-Device-Fingerprint": fp},
        )
        assert resp.status_code in (200, 201), resp.text
        body = resp.json()
        user_id = body["user"]["id"] if "user" in body else body["id"]
    # Pin the CLI to this user via env so all subprocesses in the same
    # test share the same owning user.
    monkeypatch.setenv("BADCASES_CLI_USER_ID", user_id)
    return user_id


# ---------------------------------------------------------------------------
# create
# ---------------------------------------------------------------------------


def test_cli_create_writes_new_badcase(golden_dir: Path, cli_user_id: str) -> None:
    """``create`` writes a row and prints a JSON envelope."""
    proc = _run_cli(
        "create",
        "--source", "eval_failure",
        "--type", "EVAL_REGRESSION",
        "--severity", "high",
        "--reviewer", "alice",
        "--json",
    )
    assert proc.returncode == 0, proc.stderr
    body = json.loads(proc.stdout)
    assert "badcase" in body
    bc = body["badcase"]
    assert bc["type"] == "EVAL_REGRESSION"
    assert bc["severity"] == "HIGH"
    assert bc["status"] == "OPEN"
    assert bc["reviewer"] == "alice"
    assert bc["badcaseId"].startswith("badcase-")


def test_cli_create_rejects_unknown_type(golden_dir: Path, cli_user_id: str) -> None:
    """Unknown type → exit 3 (policy violation)."""
    proc = _run_cli(
        "create",
        "--source", "manual",
        "--type", "ALIENS",
        "--severity", "high",
        "--reviewer", "alice",
        "--json",
    )
    assert proc.returncode in (2, 3), proc.stderr


def test_cli_create_requires_reviewer(golden_dir: Path, cli_user_id: str) -> None:
    """Missing reviewer → exit 2 (invalid args)."""
    proc = _run_cli(
        "create",
        "--source", "manual",
        "--type", "EVAL_REGRESSION",
        "--severity", "high",
        "--json",
    )
    assert proc.returncode == 2, proc.stderr


# ---------------------------------------------------------------------------
# promote
# ---------------------------------------------------------------------------


def test_cli_promote_writes_candidate_file(golden_dir: Path, cli_user_id: str) -> None:
    """``promote`` writes ``<badcase_id>.candidate.json`` to golden_dir."""
    # First create a badcase
    create_proc = _run_cli(
        "create",
        "--source", "eval_failure",
        "--type", "EVAL_REGRESSION",
        "--severity", "high",
        "--reviewer", "alice",
        "--json",
    )
    assert create_proc.returncode == 0, create_proc.stderr
    badcase_id = json.loads(create_proc.stdout)["badcase"]["badcaseId"]

    # Now promote it
    promote_proc = _run_cli(
        "promote",
        "--badcase-id", badcase_id,
        "--reviewer", "alice",
        "--redaction-audit-id", "audit-001",
        "--reason", "protect regression",
        "--json",
    )
    assert promote_proc.returncode == 0, promote_proc.stderr
    body = json.loads(promote_proc.stdout)
    assert "candidatePath" in body or "candidate_path" in body

    candidate_files = list(golden_dir.glob("*.candidate.json"))
    assert len(candidate_files) == 1
    payload = json.loads(candidate_files[0].read_text(encoding="utf-8"))
    assert payload["badcaseId"] == badcase_id
    assert payload["redactionAuditId"] == "audit-001"
    assert payload["reviewer"] == "alice"
    assert payload["reason"] == "protect regression"


def test_cli_promote_requires_reason(golden_dir: Path, cli_user_id: str) -> None:
    """Missing reason → exit 2."""
    create_proc = _run_cli(
        "create",
        "--source", "manual",
        "--type", "EVAL_REGRESSION",
        "--severity", "high",
        "--reviewer", "alice",
        "--json",
    )
    badcase_id = json.loads(create_proc.stdout)["badcase"]["badcaseId"]

    proc = _run_cli(
        "promote",
        "--badcase-id", badcase_id,
        "--reviewer", "alice",
        "--redaction-audit-id", "audit-001",
        "--json",
    )
    assert proc.returncode == 2, proc.stderr


# ---------------------------------------------------------------------------
# close
# ---------------------------------------------------------------------------


def test_cli_close_sets_status_closed(golden_dir: Path, cli_user_id: str) -> None:
    """``close`` writes closure_reason + closed_at + sets status=CLOSED.

    The FSM requires walking OPEN → TRIAGED → IN_PROGRESS →
    AWAITING_VALIDATION → CLOSED. The CLI's ``classify`` subcommand
    advances to TRIAGED; we use the repository helpers directly to
    walk the remaining intermediate states (the public surface for
    those is internal because they don't carry semantic meaning for
    the CLI user).
    """
    import asyncio
    from app.core.db import get_db_session_no_rls, set_rls_user_id
    from app.modules.badcases import repository as _repo

    create_proc = _run_cli(
        "create",
        "--source", "manual",
        "--type", "EVAL_REGRESSION",
        "--severity", "high",
        "--reviewer", "alice",
        "--json",
    )
    assert create_proc.returncode == 0, create_proc.stderr
    badcase_id = json.loads(create_proc.stdout)["badcase"]["badcaseId"]
    user_uuid = UUID(cli_user_id)

    async def _walk_to_awaiting() -> None:
        async for session in get_db_session_no_rls():
            await set_rls_user_id(session, user_uuid)
            await _repo.update_status(
                session, badcase_id=badcase_id, user_id=user_uuid,
                new_status="TRIAGED", reviewer="alice",
            )
            await _repo.update_status(
                session, badcase_id=badcase_id, user_id=user_uuid,
                new_status="IN_PROGRESS", reviewer="alice",
            )
            await _repo.update_status(
                session, badcase_id=badcase_id, user_id=user_uuid,
                new_status="AWAITING_VALIDATION", reviewer="alice",
            )
            await session.commit()

    asyncio.run(_walk_to_awaiting())

    close_proc = _run_cli(
        "close",
        "--badcase-id", badcase_id,
        "--reviewer", "alice",
        "--closure-reason", "fixed",
        "--evidence-ref", "https://example.com/evidence",
        "--json",
    )
    assert close_proc.returncode == 0, close_proc.stderr
    body = json.loads(close_proc.stdout)
    bc = body["badcase"]
    assert bc["status"] == "CLOSED"
    assert bc["closureReason"] == "fixed"
    assert bc["closedAt"] is not None


def test_cli_close_requires_closure_reason(golden_dir: Path, cli_user_id: str) -> None:
    """Missing --closure-reason → exit 2."""
    create_proc = _run_cli(
        "create",
        "--source", "manual",
        "--type", "EVAL_REGRESSION",
        "--severity", "high",
        "--reviewer", "alice",
        "--json",
    )
    badcase_id = json.loads(create_proc.stdout)["badcase"]["badcaseId"]

    proc = _run_cli(
        "close",
        "--badcase-id", badcase_id,
        "--reviewer", "alice",
        "--evidence-ref", "link",
        "--json",
    )
    assert proc.returncode == 2, proc.stderr


# ---------------------------------------------------------------------------
# list
# ---------------------------------------------------------------------------


def test_cli_list_returns_rows(golden_dir: Path, cli_user_id: str) -> None:
    """``list`` returns the recently-created badcases."""
    _run_cli(
        "create",
        "--source", "manual",
        "--type", "EVAL_REGRESSION",
        "--severity", "high",
        "--reviewer", "alice",
        "--json",
    )
    proc = _run_cli("list", "--json")
    assert proc.returncode == 0, proc.stderr
    body = json.loads(proc.stdout)
    items = body.get("items") or body.get("data") or body.get("badcases") or []
    assert isinstance(items, list)
    assert len(items) >= 1


# ---------------------------------------------------------------------------
# get
# ---------------------------------------------------------------------------


def test_cli_get_returns_single_record(golden_dir: Path, cli_user_id: str) -> None:
    """``get`` returns a single badcase by id."""
    create_proc = _run_cli(
        "create",
        "--source", "manual",
        "--type", "EVAL_REGRESSION",
        "--severity", "high",
        "--reviewer", "alice",
        "--json",
    )
    badcase_id = json.loads(create_proc.stdout)["badcase"]["badcaseId"]

    proc = _run_cli("get", "--badcase-id", badcase_id, "--json")
    assert proc.returncode == 0, proc.stderr
    body = json.loads(proc.stdout)
    bc = body["badcase"]
    assert bc["badcaseId"] == badcase_id


def test_cli_get_404_returns_exit_1(golden_dir: Path, cli_user_id: str) -> None:
    """Missing badcase → exit 1."""
    proc = _run_cli(
        "get",
        "--badcase-id", "badcase-does-not-exist",
        "--json",
    )
    assert proc.returncode == 1, proc.stderr


# ---------------------------------------------------------------------------
# Smoke — --help works
# ---------------------------------------------------------------------------


def test_cli_help_succeeds() -> None:
    """``--help`` exits 0 and prints usage."""
    proc = _run_cli("--help")
    assert proc.returncode == 0
    assert "create" in proc.stdout
    assert "promote" in proc.stdout
    assert "close" in proc.stdout