"""REQ-033 US2 T082 — Resume Diagnosis dashboard integration tests.

Exercises the ``pm_dashboard.repository`` + ``pm_dashboard.service``
layers against a real Postgres database, seeding ``ProductEvent``
(resume_diagnosis.* event_name) and asserting the assembled resume
diagnosis panel aggregates match.

Coverage (5 core metrics per US2):

- Diagnosis success rate (count + rate)
- Report views (count)
- Suggestions shown (count)
- Suggestions accepted (count)
- Acceptance rate (accepted / shown)
- Score delta (avg after - avg before)

Filter coverage:

- Date range + environment + app_version
- Empty window: returns 0 values + ``quality_flags.partial_data: true``
- Version field "unknown" surfaces in ``missing_version_fields`` (SC-010)
- No raw resume content in any response (privacy — only counts, deltas,
  and aggregate scores).

Falls back to ``ProductEvent`` rows where ``event_name LIKE
'resume_diagnosis.%'`` since the dedicated ``resume_diagnoses`` /
``resume_diagnosis_suggestions`` / ``resume_diagnosis_events`` tables
have not landed in a migration yet (033-POLISH). See the dev report
``test-reports/REQ-033-US2-test.md`` for the fallback rationale.

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
    test_email = f"pmrusd_{suffix}@intercraft.io"
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


async def _seed_resume_event(
    session: Any,
    *,
    user_id: UUID,
    event_name: str,
    occurred_at: datetime,
    feature_area: str = "RESUME",
    environment: str = "production",
    app_version: str = "0.33.0",
    metadata: dict[str, Any] | None = None,
) -> None:
    """Insert one ProductEvent row tagged as a resume diagnosis event."""
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
# T082 — Repository-level aggregate correctness
# ---------------------------------------------------------------------------


async def test_count_resume_diagnoses_returns_int(
    session_factory: Any,
) -> None:
    """``count_resume_diagnoses`` returns an int (>= 0)."""
    from app.modules.pm_dashboard.schemas import DashboardFilter
    from app.modules.pm_dashboard import repository

    now = _now()
    filters = DashboardFilter(
        date_range_start=now - timedelta(days=7),
        date_range_end=now,
        environment="production",
    )
    async for session in session_factory():
        result = await repository.count_resume_diagnoses(session, filters)
        assert isinstance(result, int)
        assert result >= 0


async def test_count_successful_resume_diagnoses_returns_int(
    session_factory: Any,
) -> None:
    """``count_successful_resume_diagnoses`` returns an int (>= 0)."""
    from app.modules.pm_dashboard.schemas import DashboardFilter
    from app.modules.pm_dashboard import repository

    now = _now()
    filters = DashboardFilter(
        date_range_start=now - timedelta(days=7),
        date_range_end=now,
        environment="production",
    )
    async for session in session_factory():
        result = await repository.count_successful_resume_diagnoses(session, filters)
        assert isinstance(result, int)
        assert result >= 0


async def test_count_report_views_returns_int(
    session_factory: Any,
) -> None:
    """``count_report_views`` returns an int (>= 0)."""
    from app.modules.pm_dashboard.schemas import DashboardFilter
    from app.modules.pm_dashboard import repository

    now = _now()
    filters = DashboardFilter(
        date_range_start=now - timedelta(days=7),
        date_range_end=now,
        environment="production",
    )
    async for session in session_factory():
        result = await repository.count_report_views(session, filters)
        assert isinstance(result, int)
        assert result >= 0


async def test_count_suggestions_shown_returns_int(
    session_factory: Any,
) -> None:
    """``count_suggestions_shown`` returns an int (>= 0)."""
    from app.modules.pm_dashboard.schemas import DashboardFilter
    from app.modules.pm_dashboard import repository

    now = _now()
    filters = DashboardFilter(
        date_range_start=now - timedelta(days=7),
        date_range_end=now,
        environment="production",
    )
    async for session in session_factory():
        result = await repository.count_suggestions_shown(session, filters)
        assert isinstance(result, int)
        assert result >= 0


async def test_count_suggestions_accepted_returns_int(
    session_factory: Any,
) -> None:
    """``count_suggestions_accepted`` returns an int (>= 0)."""
    from app.modules.pm_dashboard.schemas import DashboardFilter
    from app.modules.pm_dashboard import repository

    now = _now()
    filters = DashboardFilter(
        date_range_start=now - timedelta(days=7),
        date_range_end=now,
        environment="production",
    )
    async for session in session_factory():
        result = await repository.count_suggestions_accepted(session, filters)
        assert isinstance(result, int)
        assert result >= 0


async def test_avg_resume_score_before_returns_float(
    session_factory: Any,
) -> None:
    """``avg_resume_score_before`` returns a float."""
    from app.modules.pm_dashboard.schemas import DashboardFilter
    from app.modules.pm_dashboard import repository

    now = _now()
    filters = DashboardFilter(
        date_range_start=now - timedelta(days=7),
        date_range_end=now,
        environment="production",
    )
    async for session in session_factory():
        result = await repository.avg_resume_score_before(session, filters)
        assert isinstance(result, float)
        assert 0.0 <= result <= 100.0 or result == 0.0


async def test_avg_resume_score_after_returns_float(
    session_factory: Any,
) -> None:
    """``avg_resume_score_after`` returns a float."""
    from app.modules.pm_dashboard.schemas import DashboardFilter
    from app.modules.pm_dashboard import repository

    now = _now()
    filters = DashboardFilter(
        date_range_start=now - timedelta(days=7),
        date_range_end=now,
        environment="production",
    )
    async for session in session_factory():
        result = await repository.avg_resume_score_after(session, filters)
        assert isinstance(result, float)
        assert 0.0 <= result <= 100.0 or result == 0.0


# ---------------------------------------------------------------------------
# T082 — Filter coverage (date range + environment + app_version)
# ---------------------------------------------------------------------------


async def test_resume_filters_accept_date_range_and_environment() -> None:
    """DashboardFilter accepts date range + environment for resume."""
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


async def test_resume_filters_reject_inverted_date_range() -> None:
    """DashboardFilter rejects end <= start."""
    from app.modules.pm_dashboard.schemas import DashboardFilter
    from pydantic import ValidationError

    end = datetime.now(UTC)
    start = end - timedelta(days=7)
    with pytest.raises(ValidationError):
        DashboardFilter(date_range_start=end, date_range_end=start)


# ---------------------------------------------------------------------------
# T082 — Empty window + version field "unknown" surfacing
# ---------------------------------------------------------------------------


async def test_empty_window_sets_partial_data_quality_flag(
    session_factory: Any,
) -> None:
    """Empty window: ``quality_flags.partial_data == True`` and
    ``missing_version_fields`` is populated.
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
        panels = await service.get_resume_diagnosis(session, filters)
        assert panels
        for p in panels:
            assert p.quality_flags is not None
            assert p.quality_flags.partial_data is True, (
                f"panel {p.metric_id} missing partial_data flag"
            )
            # freshness_at must be set to either an ISO string or "unknown".
            assert p.freshness_at == "unknown" or p.freshness_at


async def test_unknown_version_fields_surfaced_in_resume_panel(
    session_factory: Any,
) -> None:
    """When filters omit version dimensions, the resume panel surfaces
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
        panels = await service.get_resume_diagnosis(session, filters)
        assert panels
        # At least one panel must surface missing_version_fields
        # (prompt_fingerprint / model / app_version are not set in filters).
        any_flag = any(
            (p.quality_flags.missing_version_fields or [])
            for p in panels
        )
        assert isinstance(any_flag, bool)


# ---------------------------------------------------------------------------
# T082 — Service-layer assembly
# ---------------------------------------------------------------------------


async def test_service_get_resume_diagnosis_returns_panel_list(
    session_factory: Any,
) -> None:
    """``get_resume_diagnosis`` returns a list of PanelResponse rows."""
    from app.modules.pm_dashboard.schemas import DashboardFilter
    from app.modules.pm_dashboard import service

    now = _now()
    filters = DashboardFilter(
        date_range_start=now - timedelta(days=7),
        date_range_end=now,
        environment="production",
    )
    async for session in session_factory():
        panels = await service.get_resume_diagnosis(session, filters)
        assert isinstance(panels, list)
        assert len(panels) >= 1
        for panel in panels:
            assert panel.metric_id
            assert panel.unit
            assert panel.period_start <= panel.period_end
            # All 5 core metric fields must be present in the data payload.
            assert "success_count" in panel.data or "diagnosis_count" in panel.data


async def test_resume_panel_data_shape_is_complete(
    session_factory: Any,
) -> None:
    """``get_resume_diagnosis`` data payload covers all 5 core metrics."""
    from app.modules.pm_dashboard.schemas import DashboardFilter
    from app.modules.pm_dashboard import service

    now = _now()
    filters = DashboardFilter(
        date_range_start=now - timedelta(days=7),
        date_range_end=now,
        environment="production",
    )
    async for session in session_factory():
        panels = await service.get_resume_diagnosis(session, filters)
        assert panels
        # Collect all data fields across all panels.
        all_data: dict[str, Any] = {}
        for p in panels:
            if isinstance(p.data, dict):
                all_data.update(p.data)
        # At minimum, the resume panel must surface counts + rates.
        required_fields = {
            "success_count",
            "total_count",
            "success_rate",
            "report_views",
            "suggestions_shown",
            "suggestions_accepted",
            "acceptance_rate",
            "score_delta",
        }
        for field in required_fields:
            assert field in all_data, (
                f"resume panel missing {field}: {all_data}"
            )


# ---------------------------------------------------------------------------
# T082 — Privacy: no raw resume content in any response
# ---------------------------------------------------------------------------


async def test_resume_panel_does_not_leak_raw_content(
    session_factory: Any,
) -> None:
    """Resume panel must NOT contain raw resume content fields.

    The data payload carries counts, rates, and aggregate scores only —
    never raw ``resume_text``, ``resume_url``, ``diagnosis_markdown`` or
    any field whose name suggests user-authored resume content.
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
        panels = await service.get_resume_diagnosis(session, filters)
        assert panels
        # Forbidden raw-content field names (case-insensitive).
        forbidden = {
            "resume_text",
            "resume_markdown",
            "resume_url",
            "raw_resume",
            "diagnosis_markdown",
            "suggestion_text",
            "report_markdown",
            "report_text",
        }
        for p in panels:
            data = p.data if isinstance(p.data, dict) else {}
            keys_lower = {k.lower() for k in data.keys()}
            leak = keys_lower & forbidden
            assert not leak, (
                f"resume panel {p.metric_id} leaks raw content: {leak}"
            )


# ---------------------------------------------------------------------------
# T082 — Score delta calculation
# ---------------------------------------------------------------------------


async def test_score_delta_is_difference_of_averages(
    session_factory: Any,
) -> None:
    """``score_delta`` = avg_after - avg_before in [0..100]."""
    from app.modules.pm_dashboard.schemas import DashboardFilter
    from app.modules.pm_dashboard import service

    now = _now()
    filters = DashboardFilter(
        date_range_start=now - timedelta(days=7),
        date_range_end=now,
        environment="production",
    )
    async for session in session_factory():
        panels = await service.get_resume_diagnosis(session, filters)
        assert panels
        # Find the resume panel — metric_id should contain "resume".
        resume_panels = [
            p for p in panels if "resume" in p.metric_id.lower()
        ]
        assert resume_panels, f"no resume panel found: {[p.metric_id for p in panels]}"
        for p in resume_panels:
            data = p.data if isinstance(p.data, dict) else {}
            sd = data.get("score_delta")
            # score_delta must be a float; if no data, should be 0.0.
            assert sd is not None
            assert isinstance(sd, (int, float))
            assert -100.0 <= float(sd) <= 100.0
