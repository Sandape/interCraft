"""Runtime structured-log capture for create_root — runs without PostgreSQL.

Exercises all three log-emitting paths (preflight conflict, success,
unique-conflict recovery) with controlled fakes and asserts that every
``log.info(...)`` carries only safe identifiers — never the marker text,
JSON payload fragments, or raw exception PII/DSN/content.

Also contains the mock-only derive-error tests previously kept under
``tests/integration/`` (which was always skipped on PLACEHOLDER).
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from sqlalchemy.exc import IntegrityError

from app.modules.jobs.models import Job
from app.modules.resume_derive.service import DeriveError, ResumeDeriveService

_UNSAFE_LOG_KEYS = frozenset(
    {"marker", "payload", "source_markdown", "exc_orig", "db_error", "data", "exc"}
)
_UNSAFE_VALUE_PATTERNS = frozenset(
    {
        "secret marker",
        "marker text",
        "user marker",
        "marker#",
        "IntegrityError",
        "UniqueViolation",
        "psycopg",
        "asyncpg",
        "DSN",
        "postgres://",
        "postgresql://",
        "password=",
    }
)


def _assert_safe_log_event(log_entries: list) -> None:
    """Assert every captured log.info() uses safe keys AND values."""
    for call_args in log_entries:
        _kwargs = call_args.kwargs
        for kw_name in _kwargs:
            assert kw_name not in _UNSAFE_LOG_KEYS, f"log .info() uses unsafe key {kw_name!r}"
        serialized_values = repr((call_args.args, call_args.kwargs)).casefold()
        for pattern in _UNSAFE_VALUE_PATTERNS:
            assert pattern.casefold() not in serialized_values, (
                f"log .info() values contain unsafe pattern {pattern!r}: {serialized_values!r}"
            )
        _args = call_args.args
        if _args:
            assert isinstance(_args[0], str), (
                f"first log arg must be event name, got {type(_args[0])}"
            )
            assert _args[0].startswith("resume_derive.create_root."), (
                f"unexpected log event {_args[0]!r}"
            )


# ---------------------------------------------------------------------------
# 1. Preflight conflict path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_root_conflict_log_has_only_safe_keys():
    """get_root returns existing -> preflight conflict."""
    session = AsyncMock()
    svc = ResumeDeriveService(session)
    svc.resumes = AsyncMock()
    existing = MagicMock()
    existing.id = uuid4()
    svc.get_root = AsyncMock(return_value=existing)

    with patch("app.modules.resume_derive.service.log.info") as mock_info:
        with pytest.raises(DeriveError) as exc:
            await svc.create_root(user_id=uuid4(), name="Root", slug="root")
        assert exc.value.code == "ROOT_EXISTS"
        assert exc.value.status == 409
        _assert_safe_log_event(mock_info.call_args_list)


# ---------------------------------------------------------------------------
# 2. Success path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_root_success_log_has_only_safe_keys():
    """create_root completes normally."""
    session = AsyncMock()
    svc = ResumeDeriveService(session)
    svc.runs = AsyncMock()

    svc.get_root = AsyncMock(return_value=None)

    mock_row = MagicMock()
    mock_row.id = uuid4()
    mock_row.resume_kind = "root"
    mock_row.root_resume_id = None
    mock_row.job_id = None
    mock_row.target_page_count = None
    mock_row.derive_meta = {}
    svc.resumes.create = AsyncMock(return_value=mock_row)

    savepoint_cm = AsyncMock()
    savepoint_cm.__aenter__ = AsyncMock(return_value=None)
    savepoint_cm.__aexit__ = AsyncMock(return_value=None)
    session.begin_nested.return_value = savepoint_cm

    session.flush = AsyncMock()

    with patch("app.modules.resume_derive.service.log.info") as mock_info:
        result = await svc.create_root(
            user_id=uuid4(),
            name="根简历",
            slug="root-resume",
            data={"metadata": {"markdown": {"sourceMarkdown": "user marker text"}}},
        )
        assert result is mock_row

        _assert_safe_log_event(mock_info.call_args_list)
        call_events = [c[0][0] for c in mock_info.call_args_list if c[0]]
        assert "resume_derive.create_root.success" in call_events, (
            f"expected success event, got {call_events}"
        )


# ---------------------------------------------------------------------------
# 3. Unique-conflict recovery path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_root_unique_conflict_log_has_only_safe_keys():
    """IntegrityError with expected race constraint -> re-read winner -> 409.

    Simulates a concurrent winner via the cause chain (``__cause__``),
    which matches how asyncpg propagates constraint violations.
    """
    session = AsyncMock()
    svc = ResumeDeriveService(session)
    svc.runs = AsyncMock()

    winner_row = MagicMock()
    winner_row.id = uuid4()
    winner_row.resume_kind = "root"
    svc.get_root = AsyncMock(side_effect=[None, winner_row])

    mock_row = MagicMock()
    mock_row.id = uuid4()
    mock_row.resume_kind = "root"
    mock_row.root_resume_id = None
    mock_row.job_id = None
    mock_row.target_page_count = None
    mock_row.derive_meta = {}
    svc.resumes.create = AsyncMock(return_value=mock_row)

    savepoint_cm = AsyncMock()
    savepoint_cm.__aenter__ = AsyncMock(return_value=None)
    savepoint_cm.__aexit__ = AsyncMock(return_value=None)
    session.begin_nested.return_value = savepoint_cm

    orig = Exception("duplicate key value")
    cause = Exception()
    cause.constraint_name = "uq_resumes_v2_user_slug"
    orig.__cause__ = cause
    integ = IntegrityError("INSERT INTO resumes_v2 ...", {}, orig)

    svc.resumes.create = AsyncMock(side_effect=integ)

    with patch("app.modules.resume_derive.service.log.info") as mock_info:
        with pytest.raises(DeriveError) as exc:
            await svc.create_root(
                user_id=uuid4(),
                name="根简历",
                slug="root-resume",
            )
        assert exc.value.code == "ROOT_EXISTS"

        _assert_safe_log_event(mock_info.call_args_list)
        call_events = [c[0][0] for c in mock_info.call_args_list if c[0]]
        assert "resume_derive.create_root.conflict" in call_events, (
            f"expected conflict event, got {call_events}"
        )
        for call in mock_info.call_args_list:
            _kwargs = call.kwargs
            if "existing_root_id" in _kwargs:
                assert _kwargs["existing_root_id"] == str(winner_row.id)
                break
        else:
            pytest.fail("conflict log missing 'existing_root_id'")


# ---------------------------------------------------------------------------
# 4-5. Unexpected database/runtime failures must never be masked as 409
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_root_unknown_constraint_is_re_raised():
    session = AsyncMock()
    svc = ResumeDeriveService(session)
    svc.get_root = AsyncMock(return_value=None)

    savepoint = AsyncMock()
    session.begin_nested.return_value = savepoint

    orig = Exception("foreign key violation")
    cause = Exception()
    cause.constraint_name = "fk_resumes_v2_user_id"
    orig.__cause__ = cause
    integrity_error = IntegrityError("INSERT INTO resumes_v2 ...", {}, orig)
    svc.resumes.create = AsyncMock(side_effect=integrity_error)

    with pytest.raises(IntegrityError) as caught:
        await svc.create_root(user_id=uuid4(), name="Root", slug="root")

    assert caught.value is integrity_error
    savepoint.rollback.assert_awaited_once()


@pytest.mark.asyncio
async def test_create_root_runtime_error_is_not_masked_when_root_appears():
    session = AsyncMock()
    svc = ResumeDeriveService(session)

    winner = MagicMock()
    winner.id = uuid4()
    svc.get_root = AsyncMock(side_effect=[None, winner])

    savepoint = AsyncMock()
    session.begin_nested.return_value = savepoint
    svc.resumes.create = AsyncMock(side_effect=RuntimeError("real programming failure"))

    with pytest.raises(RuntimeError, match="real programming failure"):
        await svc.create_root(user_id=uuid4(), name="Root", slug="root")

    savepoint.rollback.assert_awaited_once()


# ---------------------------------------------------------------------------
# 6-8. Mock-only derive tests (moved from test_error_codes_runtime.py)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_start_run_no_root():
    session = AsyncMock()
    svc = ResumeDeriveService(session)
    svc.resumes = AsyncMock()
    svc.runs = AsyncMock()
    svc.get_root = AsyncMock(return_value=None)

    with pytest.raises(DeriveError) as exc:
        await svc.start_run(
            user_id=uuid4(),
            job_id=uuid4(),
            target_page_count=1,
        )
    assert exc.value.code == "NO_ROOT"


@pytest.mark.asyncio
async def test_start_run_no_jd():
    session = AsyncMock()
    svc = ResumeDeriveService(session)
    svc.runs = AsyncMock()
    root = MagicMock()
    root.id = uuid4()
    root.version = 1
    root.resume_kind = "root"
    svc.get_root = AsyncMock(return_value=root)

    job = Job(
        id=uuid4(),
        user_id=uuid4(),
        company="Acme",
        position="Engineer",
        status="applied",
        status_history=[],
        last_status_changed_at=None,
        base_location="",
        employment_type="unspecified",
        requirements_md="   ",
    )
    session.get = AsyncMock(return_value=job)

    with pytest.raises(DeriveError) as exc:
        await svc.start_run(
            user_id=job.user_id,
            job_id=job.id,
            target_page_count=2,
        )
    assert exc.value.code == "NO_JD"


@pytest.mark.asyncio
async def test_create_root_root_exists():
    session = AsyncMock()
    svc = ResumeDeriveService(session)
    svc.resumes = AsyncMock()
    existing = MagicMock()
    svc.get_root = AsyncMock(return_value=existing)

    with pytest.raises(DeriveError) as exc:
        await svc.create_root(user_id=uuid4(), name="Root", slug="root")
    assert exc.value.code == "ROOT_EXISTS"
    assert exc.value.status == 409
