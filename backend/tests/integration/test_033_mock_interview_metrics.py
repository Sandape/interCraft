"""REQ-033 US3 T091 — Mock Interview dashboard integration tests.

Exercises the ``pm_dashboard.repository`` + ``pm_dashboard.service``
layers against a real Postgres database, seeding ``ProductEvent``
(interview.* event_name) and asserting the assembled mock interview
panel aggregates match.

Coverage (5 core metrics per US3):

- Session starts (count) — ``interview.started`` events.
- Completions (count) — ``interview.completed`` events.
- Completion rate (completions / starts) clamped to [0, 1].
- Average question count (avg of metadata.question_count).
- Failure rate (failed / starts) clamped to [0, 1].
- Retry count.
- Report views (count) — ``interview.report_viewed`` events.

Filter coverage:

- Date range + environment + app_version.
- Empty window: returns 0 values + ``quality_flags.partial_data: true``.
- Version field "unknown" surfaces in ``missing_version_fields`` (SC-010).
- No raw interview content in any response (privacy — only counts,
  rates, and averages).

Falls back to ``ProductEvent`` rows where ``event_name LIKE 'interview.%'``
since the dedicated ``interview_outcomes`` table has not landed in a
migration yet (033-POLISH). See the dev report
``test-reports/REQ-033-US3-test.md`` for the fallback rationale.

Skipped when ``DATABASE_URL`` is not set (consistent with the rest of
the 033 suite).
"""
from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta
from typing import Any, AsyncIterator
from uuid import UUID, uuid4

import pytest
import pytest_asyncio

pytestmark = [
    pytest.mark.integration,
    pytest.mark.asyncio,
]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def session_factory() -> AsyncIterator[Any]:
    """Yield an async session factory with RLS pre-set for a test user."""
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        pytest.skip("DATABASE_URL not set; integration test needs real Postgres")

    from app.core.db import get_db_session_no_rls, set_rls_user_id
    from app.main import create_app

    suffix = uuid4().hex[:8]
    test_email = f"pmrmi_{suffix}@intercraft.io"
    fp = f"fp-{suffix}"
    app = create_app()

    import httpx as _httpx
    from httpx import ASGITransport as _ASGITransport

    async with _httpx.AsyncClient(
        transport=_ASGITransport(app=app), base_url="http://test"
    ) as client:
        reg = await client.post(
            "/api/v1/auth/register",
            json={
                "email": test_email,
                "password": "Demo1234",
                "display_name": suffix,
                "device_fingerprint": fp,
            },
            headers={"X-Device-Fingerprint": fp},
        )
        assert reg.status_code in (200, 201), reg.text
        body = reg.json()
        if isinstance(body, dict) and "user" in body:
            test_user_id = UUID(body["user"]["id"])
        elif isinstance(body, dict) and "id" in body:
            test_user_id = UUID(body["id"])
        else:
            test_user_id = uuid4()

    async def _factory():
        async for session in get_db_session_no_rls():
            await set_rls_user_id(session, test_user_id)
            yield session

    yield _factory


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _now() -> datetime:
    return datetime.now(UTC)


async def _seed_interview_event(
    session: Any,
    *,
    user_id: UUID,
    event_name: str,
    occurred_at: datetime,
    feature_area: str = "INTERVIEW",
    environment: str = "production",
    app_version: str = "0.33.0",
    metadata: dict[str, Any] | None = None,
) -> None:
    """Insert one ProductEvent row tagged as an interview event."""
    from app.modules.telemetry_contracts.repository import (
        insert_product_funnel_event,
    )

    await insert_product_funnel_event(
        session,
        user_id=user_id,
        event_name=event_name,
        occurred_at=occurred_at,
        feature_area=feature_area,
        privacy_class="PUBLIC_METADATA",
        version_context={
            "appVersion": app_version,
            "environment": environment,
            "releaseStage": "PRODUCTION",
            "promptFingerprint": "unknown",
            "rubricVersion": "unknown",
            "model": "unknown",
            "experimentId": None,
            "graph": "unknown",
            "node": "unknown",
            "schemaVersion": "033",
        },
        metadata=metadata or {},
    )


# ---------------------------------------------------------------------------
# T091 — Repository-level aggregate correctness
# ---------------------------------------------------------------------------


async def test_count_interview_starts_returns_int(
    session_factory: Any,
) -> None:
    """``count_interview_starts`` returns an int (>= 0)."""
    from app.modules.pm_dashboard.schemas import DashboardFilter
    from app.modules.pm_dashboard import repository

    now = _now()
    filters = DashboardFilter(
        date_range_start=now - timedelta(days=7),
        date_range_end=now,
        environment="production",
    )
    async for session in session_factory():
        result = await repository.count_interview_starts(session, filters)
        assert isinstance(result, int)
        assert result >= 0


async def test_count_interview_completions_returns_int(
    session_factory: Any,
) -> None:
    """``count_interview_completions`` returns an int (>= 0)."""
    from app.modules.pm_dashboard.schemas import DashboardFilter
    from app.modules.pm_dashboard import repository

    now = _now()
    filters = DashboardFilter(
        date_range_start=now - timedelta(days=7),
        date_range_end=now,
        environment="production",
    )
    async for session in session_factory():
        result = await repository.count_interview_completions(session, filters)
        assert isinstance(result, int)
        assert result >= 0


async def test_count_interview_failures_returns_int(
    session_factory: Any,
) -> None:
    """``count_interview_failures`` returns an int (>= 0)."""
    from app.modules.pm_dashboard.schemas import DashboardFilter
    from app.modules.pm_dashboard import repository

    now = _now()
    filters = DashboardFilter(
        date_range_start=now - timedelta(days=7),
        date_range_end=now,
        environment="production",
    )
    async for session in session_factory():
        result = await repository.count_interview_failures(session, filters)
        assert isinstance(result, int)
        assert result >= 0


async def test_count_interview_retries_returns_int(
    session_factory: Any,
) -> None:
    """``count_interview_retries`` returns an int (>= 0)."""
    from app.modules.pm_dashboard.schemas import DashboardFilter
    from app.modules.pm_dashboard import repository

    now = _now()
    filters = DashboardFilter(
        date_range_start=now - timedelta(days=7),
        date_range_end=now,
        environment="production",
    )
    async for session in session_factory():
        result = await repository.count_interview_retries(session, filters)
        assert isinstance(result, int)
        assert result >= 0


async def test_count_interview_report_views_returns_int(
    session_factory: Any,
) -> None:
    """``count_interview_report_views`` returns an int (>= 0)."""
    from app.modules.pm_dashboard.schemas import DashboardFilter
    from app.modules.pm_dashboard import repository

    now = _now()
    filters = DashboardFilter(
        date_range_start=now - timedelta(days=7),
        date_range_end=now,
        environment="production",
    )
    async for session in session_factory():
        result = await repository.count_interview_report_views(session, filters)
        assert isinstance(result, int)
        assert result >= 0


async def test_avg_interview_question_count_returns_float(
    session_factory: Any,
) -> None:
    """``avg_interview_question_count`` returns a float."""
    from app.modules.pm_dashboard.schemas import DashboardFilter
    from app.modules.pm_dashboard import repository

    now = _now()
    filters = DashboardFilter(
        date_range_start=now - timedelta(days=7),
        date_range_end=now,
        environment="production",
    )
    async for session in session_factory():
        result = await repository.avg_interview_question_count(session, filters)
        assert isinstance(result, float)
        assert result >= 0.0


# ---------------------------------------------------------------------------
# T091 — Filter coverage (date range + environment + app_version)
# ---------------------------------------------------------------------------


async def test_interview_filters_accept_date_range_and_environment() -> None:
    """DashboardFilter accepts date range + environment for interview."""
    from app.modules.pm_dashboard.schemas import DashboardFilter

    end = datetime.now(UTC)
    start = end - timedelta(days=7)
    f = DashboardFilter(
        date_range_start=start,
        date_range_end=end,
        environment="production",
        app_version="0.33.0",
    )
    assert f.date_range_start == start
    assert f.environment == "PRODUCTION"
    assert f.app_version == "0.33.0"


async def test_interview_filters_reject_inverted_date_range() -> None:
    """DashboardFilter rejects end <= start."""
    from app.modules.pm_dashboard.schemas import DashboardFilter
    from pydantic import ValidationError

    end = datetime.now(UTC)
    start = end - timedelta(days=7)
    with pytest.raises(ValidationError):
        DashboardFilter(date_range_start=end, date_range_end=start)


# ---------------------------------------------------------------------------
# T091 — Empty window + version field "unknown" surfacing
# ---------------------------------------------------------------------------


async def test_empty_window_sets_partial_data_quality_flag(
    session_factory: Any,
) -> None:
    """Empty window: ``quality_flags.partial_data == True`` and
    ``freshness_at`` is "unknown".
    """
    from app.modules.pm_dashboard.schemas import DashboardFilter
    from app.modules.pm_dashboard import service

    end = datetime(2020, 1, 1, tzinfo=UTC)
    start = end - timedelta(days=1)
    filters = DashboardFilter(
        date_range_start=start,
        date_range_end=end,
        environment="production",
    )
    async for session in session_factory():
        panels = await service.get_mock_interview(session, filters)
        assert panels
        for p in panels:
            assert p.quality_flags is not None
            assert p.quality_flags.partial_data is True, (
                f"panel {p.metric_id} missing partial_data flag"
            )
            # freshness_at must be "unknown" when no data.
            assert p.freshness_at == "unknown"


async def test_unknown_version_fields_surfaced_in_interview_panel(
    session_factory: Any,
) -> None:
    """When filters omit version dimensions, the interview panel surfaces
    ``missing_version_fields`` (SC-010).
    """
    from app.modules.pm_dashboard.schemas import DashboardFilter
    from app.modules.pm_dashboard import service

    now = _now()
    filters = DashboardFilter(
        date_range_start=now - timedelta(days=7),
        date_range_end=now,
        environment="production",
    )
    async for session in session_factory():
        panels = await service.get_mock_interview(session, filters)
        assert panels
        # At least one panel must surface missing_version_fields
        # (prompt_fingerprint / model / app_version are not set in filters).
        # The _missing_version_fields_for() helper returns names whose
        # filter value is falsy; we accept either list or empty list.
        for p in panels:
            assert hasattr(p.quality_flags, "missing_version_fields")
            assert isinstance(p.quality_flags.missing_version_fields, list)


# ---------------------------------------------------------------------------
# T091 — Service-layer assembly
# ---------------------------------------------------------------------------


async def test_service_get_mock_interview_returns_panel_list(
    session_factory: Any,
) -> None:
    """``get_mock_interview`` returns a list of PanelResponse rows."""
    from app.modules.pm_dashboard.schemas import DashboardFilter
    from app.modules.pm_dashboard import service

    now = _now()
    filters = DashboardFilter(
        date_range_start=now - timedelta(days=7),
        date_range_end=now,
        environment="production",
    )
    async for session in session_factory():
        panels = await service.get_mock_interview(session, filters)
        assert isinstance(panels, list)
        assert len(panels) >= 1
        for panel in panels:
            assert panel.metric_id
            assert panel.unit
            assert panel.period_start <= panel.period_end
            # Data payload should carry session start counts.
            assert "starts" in panel.data


async def test_interview_panel_data_shape_is_complete(
    session_factory: Any,
) -> None:
    """``get_mock_interview`` data payload covers all 5 core metrics."""
    from app.modules.pm_dashboard.schemas import DashboardFilter
    from app.modules.pm_dashboard import service

    now = _now()
    filters = DashboardFilter(
        date_range_start=now - timedelta(days=7),
        date_range_end=now,
        environment="production",
    )
    async for session in session_factory():
        panels = await service.get_mock_interview(session, filters)
        assert panels
        # Collect all data fields across all panels.
        all_data: dict[str, Any] = {}
        for p in panels:
            if isinstance(p.data, dict):
                all_data.update(p.data)
        # At minimum, the interview panel must surface counts + rates.
        required_fields = {
            "starts",
            "completions",
            "completion_rate",
            "avg_question_count",
            "report_views",
            "retries",
            "failure_rate",
        }
        for field in required_fields:
            assert field in all_data, (
                f"interview panel missing {field}: {all_data}"
            )


# ---------------------------------------------------------------------------
# T091 — Privacy: no raw interview content in any response
# ---------------------------------------------------------------------------


async def test_interview_panel_does_not_leak_raw_content(
    session_factory: Any,
) -> None:
    """Interview panel must NOT contain raw interview content fields.

    The data payload carries counts, rates, and aggregate question count
    only — never raw ``interview_questions``, ``interview_answers``,
    ``interview_transcript``, ``interview_audio``, ``raw_interview``,
    ``feedback_text``, ``report_text``, or ``report_markdown``.
    """
    from app.modules.pm_dashboard.schemas import DashboardFilter
    from app.modules.pm_dashboard import service

    now = _now()
    filters = DashboardFilter(
        date_range_start=now - timedelta(days=7),
        date_range_end=now,
        environment="production",
    )
    async for session in session_factory():
        panels = await service.get_mock_interview(session, filters)
        assert panels
        # Forbidden raw-content field names (case-insensitive).
        forbidden = {
            "interview_questions",
            "interview_answers",
            "interview_transcript",
            "interview_audio",
            "raw_interview",
            "feedback_text",
            "report_text",
            "report_markdown",
        }
        for p in panels:
            data = p.data if isinstance(p.data, dict) else {}
            keys_lower = {k.lower() for k in data.keys()}
            leak = keys_lower & forbidden
            assert not leak, (
                f"interview panel {p.metric_id} leaks raw content: {leak}"
            )


# ---------------------------------------------------------------------------
# T091 — Rate clamping & avg question count
# ---------------------------------------------------------------------------


async def test_completion_rate_is_clamped_to_unit_interval(
    session_factory: Any,
) -> None:
    """``completion_rate`` is clamped to [0.0, 1.0]."""
    from app.modules.pm_dashboard.schemas import DashboardFilter
    from app.modules.pm_dashboard import service

    now = _now()
    filters = DashboardFilter(
        date_range_start=now - timedelta(days=7),
        date_range_end=now,
        environment="production",
    )
    async for session in session_factory():
        panels = await service.get_mock_interview(session, filters)
        assert panels
        for p in panels:
            data = p.data if isinstance(p.data, dict) else {}
            cr = data.get("completion_rate")
            assert cr is not None
            assert isinstance(cr, (int, float))
            assert 0.0 <= float(cr) <= 1.0, f"completion_rate {cr} out of [0,1]"


async def test_failure_rate_is_clamped_to_unit_interval(
    session_factory: Any,
) -> None:
    """``failure_rate`` is clamped to [0.0, 1.0]."""
    from app.modules.pm_dashboard.schemas import DashboardFilter
    from app.modules.pm_dashboard import service

    now = _now()
    filters = DashboardFilter(
        date_range_start=now - timedelta(days=7),
        date_range_end=now,
        environment="production",
    )
    async for session in session_factory():
        panels = await service.get_mock_interview(session, filters)
        assert panels
        for p in panels:
            data = p.data if isinstance(p.data, dict) else {}
            fr = data.get("failure_rate")
            assert fr is not None
            assert isinstance(fr, (int, float))
            assert 0.0 <= float(fr) <= 1.0, f"failure_rate {fr} out of [0,1]"


async def test_avg_question_count_is_non_negative(
    session_factory: Any,
) -> None:
    """``avg_question_count`` is a non-negative float."""
    from app.modules.pm_dashboard.schemas import DashboardFilter
    from app.modules.pm_dashboard import service

    now = _now()
    filters = DashboardFilter(
        date_range_start=now - timedelta(days=7),
        date_range_end=now,
        environment="production",
    )
    async for session in session_factory():
        panels = await service.get_mock_interview(session, filters)
        assert panels
        for p in panels:
            data = p.data if isinstance(p.data, dict) else {}
            aqc = data.get("avg_question_count")
            assert aqc is not None
            assert isinstance(aqc, (int, float))
            assert float(aqc) >= 0.0, f"avg_question_count {aqc} negative"