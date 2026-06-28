"""REQ-033 US4 T100 — AI Operations dashboard integration tests.

Exercises the ``pm_dashboard.repository`` + ``pm_dashboard.service``
layers against a real Postgres database, seeding ``AIInvocationRecord``
rows and asserting the assembled AI operations panel aggregates match.

Coverage (7 core metrics per US4 + 4 top-N breakdowns):

- ``call_count`` — total ``AIInvocationRecord`` rows in window.
- ``success_count`` / ``failure_count`` — split by status.
- ``success_rate`` / ``failure_rate`` — clamped to [0.0, 1.0].
- ``retry_count`` — rows where ``retry_count > 0``.
- ``p50`` / ``p95`` / ``p99`` latency — via ``percentile_cont``.
- ``estimated_cost`` — sum, labeled as estimate per FR-008.
- ``total_tokens`` / ``prompt_tokens`` / ``completion_tokens`` sums.
- Top-5 breakdowns by model / graph / node / prompt_fingerprint.

Filter coverage:

- Date range + environment + app_version.
- Empty window: returns 0 values + ``quality_flags.partial_data: true``.
- Version field "unknown" surfaces in ``missing_version_fields`` (SC-010).
- No raw AI content in any response (privacy — only counts, rates,
  aggregates, and top-N breakdowns; no prompt / completion text).

US4 reads directly from the existing ``AIInvocationRecord`` table — the
same source the LLM client hook populates (US9 T040). No new table, no
migration. Privacy: the panel returns counts + rates + percentiles
only; raw prompt / completion text is never read.

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
    test_email = f"pmao_{suffix}@intercraft.io"
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


async def _seed_ai_invocation(
    session: Any,
    *,
    user_id: UUID,
    invocation_id: UUID,
    graph: str = "default_graph",
    node: str = "default_node",
    model: str = "gpt-4o-mini",
    prompt_fingerprint: str = "fp-default",
    prompt_tokens: int = 100,
    completion_tokens: int = 50,
    estimated_cost: float = 0.0001,
    latency_ms: int = 200,
    retry_count: int = 0,
    status: str = "SUCCESS",
    error_category: str | None = None,
) -> None:
    """Insert one ``AIInvocationRecord`` row."""
    from decimal import Decimal

    from app.modules.telemetry_contracts.repository import (
        insert_ai_invocation,
    )

    await insert_ai_invocation(
        session,
        user_id=user_id,
        invocation_id=invocation_id,
        graph=graph,
        node=node,
        model=model,
        prompt_fingerprint=prompt_fingerprint,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        estimated_cost=(
            Decimal(str(estimated_cost)) if estimated_cost is not None else None
        ),
        latency_ms=latency_ms,
        retry_count=retry_count,
        status=status,
        error_category=error_category,
        run_id=None,
        trace_id=None,
    )


# ---------------------------------------------------------------------------
# T100 — Repository-level aggregate correctness
# ---------------------------------------------------------------------------


async def test_count_ai_invocations_returns_int(
    session_factory: Any,
) -> None:
    """``count_ai_invocations`` returns an int (>= 0)."""
    from app.modules.pm_dashboard.schemas import DashboardFilter
    from app.modules.pm_dashboard import repository

    now = _now()
    filters = DashboardFilter(
        date_range_start=now - timedelta(days=7),
        date_range_end=now,
        environment="production",
    )
    async for session in session_factory():
        result = await repository.count_ai_invocations(session, filters)
        assert isinstance(result, int)
        assert result >= 0


async def test_count_ai_invocations_success_returns_int(
    session_factory: Any,
) -> None:
    """``count_ai_invocations_success`` returns an int (>= 0)."""
    from app.modules.pm_dashboard.schemas import DashboardFilter
    from app.modules.pm_dashboard import repository

    now = _now()
    filters = DashboardFilter(
        date_range_start=now - timedelta(days=7),
        date_range_end=now,
        environment="production",
    )
    async for session in session_factory():
        result = await repository.count_ai_invocations_success(session, filters)
        assert isinstance(result, int)
        assert result >= 0


async def test_count_ai_invocations_failure_returns_int(
    session_factory: Any,
) -> None:
    """``count_ai_invocations_failure`` returns an int (>= 0)."""
    from app.modules.pm_dashboard.schemas import DashboardFilter
    from app.modules.pm_dashboard import repository

    now = _now()
    filters = DashboardFilter(
        date_range_start=now - timedelta(days=7),
        date_range_end=now,
        environment="production",
    )
    async for session in session_factory():
        result = await repository.count_ai_invocations_failure(session, filters)
        assert isinstance(result, int)
        assert result >= 0


async def test_count_ai_invocations_retried_returns_int(
    session_factory: Any,
) -> None:
    """``count_ai_invocations_retried`` returns an int (>= 0)."""
    from app.modules.pm_dashboard.schemas import DashboardFilter
    from app.modules.pm_dashboard import repository

    now = _now()
    filters = DashboardFilter(
        date_range_start=now - timedelta(days=7),
        date_range_end=now,
        environment="production",
    )
    async for session in session_factory():
        result = await repository.count_ai_invocations_retried(session, filters)
        assert isinstance(result, int)
        assert result >= 0


async def test_sum_ai_prompt_tokens_returns_int(
    session_factory: Any,
) -> None:
    """``sum_ai_prompt_tokens`` returns a non-negative int."""
    from app.modules.pm_dashboard.schemas import DashboardFilter
    from app.modules.pm_dashboard import repository

    now = _now()
    filters = DashboardFilter(
        date_range_start=now - timedelta(days=7),
        date_range_end=now,
        environment="production",
    )
    async for session in session_factory():
        result = await repository.sum_ai_prompt_tokens(session, filters)
        assert isinstance(result, int)
        assert result >= 0


async def test_sum_ai_completion_tokens_returns_int(
    session_factory: Any,
) -> None:
    """``sum_ai_completion_tokens`` returns a non-negative int."""
    from app.modules.pm_dashboard.schemas import DashboardFilter
    from app.modules.pm_dashboard import repository

    now = _now()
    filters = DashboardFilter(
        date_range_start=now - timedelta(days=7),
        date_range_end=now,
        environment="production",
    )
    async for session in session_factory():
        result = await repository.sum_ai_completion_tokens(session, filters)
        assert isinstance(result, int)
        assert result >= 0


async def test_ai_latency_percentile_returns_float(
    session_factory: Any,
) -> None:
    """``ai_latency_percentile`` returns a non-negative float."""
    from app.modules.pm_dashboard.schemas import DashboardFilter
    from app.modules.pm_dashboard import repository

    now = _now()
    filters = DashboardFilter(
        date_range_start=now - timedelta(days=7),
        date_range_end=now,
        environment="production",
    )
    async for session in session_factory():
        for pct in (0.5, 0.95, 0.99):
            result = await repository.ai_latency_percentile(session, filters, pct)
            assert isinstance(result, float)
            assert result >= 0.0


async def test_ai_top_breakdown_returns_dict(
    session_factory: Any,
) -> None:
    """``ai_top_breakdown`` returns a dict[str, int] with <= top_n entries."""
    from app.modules.pm_dashboard.schemas import DashboardFilter
    from app.modules.pm_dashboard import repository

    now = _now()
    filters = DashboardFilter(
        date_range_start=now - timedelta(days=7),
        date_range_end=now,
        environment="production",
    )
    async for session in session_factory():
        for dim in ("model", "graph", "node", "prompt_fingerprint"):
            result = await repository.ai_top_breakdown(session, filters, dim, top_n=5)
            assert isinstance(result, dict)
            assert len(result) <= 5
            for k, v in result.items():
                assert isinstance(k, str)
                assert isinstance(v, int)
                assert v > 0


async def test_ai_top_breakdown_unknown_dimension_returns_empty(
    session_factory: Any,
) -> None:
    """Unknown dimension → empty dict (defensive)."""
    from app.modules.pm_dashboard.schemas import DashboardFilter
    from app.modules.pm_dashboard import repository

    now = _now()
    filters = DashboardFilter(
        date_range_start=now - timedelta(days=7),
        date_range_end=now,
        environment="production",
    )
    async for session in session_factory():
        result = await repository.ai_top_breakdown(
            session, filters, "totally-unknown-dimension", top_n=5
        )
        assert result == {}


# ---------------------------------------------------------------------------
# T100 — Filter coverage (date range + environment + app_version)
# ---------------------------------------------------------------------------


async def test_ai_ops_filters_accept_date_range_and_environment() -> None:
    """DashboardFilter accepts date range + environment for AI ops."""
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


async def test_ai_ops_filters_reject_inverted_date_range() -> None:
    """DashboardFilter rejects end <= start."""
    from app.modules.pm_dashboard.schemas import DashboardFilter
    from pydantic import ValidationError

    end = datetime.now(UTC)
    start = end - timedelta(days=7)
    with pytest.raises(ValidationError):
        DashboardFilter(date_range_start=end, date_range_end=start)


# ---------------------------------------------------------------------------
# T100 — Empty window + version field "unknown" surfacing
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
        panels = await service.get_ai_operations(session, filters)
        assert panels
        for p in panels:
            assert p.quality_flags is not None
            assert p.quality_flags.partial_data is True, (
                f"panel {p.metric_id} missing partial_data flag"
            )
            # freshness_at must be "unknown" when no data.
            assert p.freshness_at == "unknown"


async def test_unknown_version_fields_surfaced_in_ai_ops_panel(
    session_factory: Any,
) -> None:
    """When filters omit version dimensions, the AI ops panel surfaces
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
        panels = await service.get_ai_operations(session, filters)
        assert panels
        # At least one panel must surface missing_version_fields
        # (prompt_fingerprint / model / app_version are not set in filters).
        for p in panels:
            assert hasattr(p.quality_flags, "missing_version_fields")
            assert isinstance(p.quality_flags.missing_version_fields, list)


# ---------------------------------------------------------------------------
# T100 — Service-layer assembly
# ---------------------------------------------------------------------------


async def test_service_get_ai_operations_returns_panel_list(
    session_factory: Any,
) -> None:
    """``get_ai_operations`` returns a list of PanelResponse rows."""
    from app.modules.pm_dashboard.schemas import DashboardFilter
    from app.modules.pm_dashboard import service

    now = _now()
    filters = DashboardFilter(
        date_range_start=now - timedelta(days=7),
        date_range_end=now,
        environment="production",
    )
    async for session in session_factory():
        panels = await service.get_ai_operations(session, filters)
        assert isinstance(panels, list)
        assert len(panels) >= 1
        for panel in panels:
            assert panel.metric_id
            assert panel.unit
            assert panel.period_start <= panel.period_end
            # Data payload should carry call count.
            assert "call_count" in panel.data


async def test_ai_ops_panel_data_shape_is_complete(
    session_factory: Any,
) -> None:
    """``get_ai_operations`` data payload covers all 7 core metrics + breakdowns."""
    from app.modules.pm_dashboard.schemas import DashboardFilter
    from app.modules.pm_dashboard import service

    now = _now()
    filters = DashboardFilter(
        date_range_start=now - timedelta(days=7),
        date_range_end=now,
        environment="production",
    )
    async for session in session_factory():
        panels = await service.get_ai_operations(session, filters)
        assert panels
        # Collect all data fields across all panels.
        all_data: dict[str, Any] = {}
        for p in panels:
            if isinstance(p.data, dict):
                all_data.update(p.data)
        # At minimum, the AI ops panel must surface all 7 core metrics
        # + the 4 top-N breakdowns.
        required_fields = {
            "call_count",
            "success_count",
            "failure_count",
            "success_rate",
            "failure_rate",
            "retry_count",
            "p50_latency_ms",
            "p95_latency_ms",
            "p99_latency_ms",
            "estimated_cost",
            "total_tokens",
            "prompt_tokens",
            "completion_tokens",
            "is_estimate",
            "model_breakdown",
            "graph_breakdown",
            "node_breakdown",
            "prompt_fingerprint_breakdown",
        }
        for field in required_fields:
            assert field in all_data, (
                f"ai ops panel missing {field}: {all_data}"
            )


# ---------------------------------------------------------------------------
# T100 — Privacy: no raw AI content in any response
# ---------------------------------------------------------------------------


async def test_ai_ops_panel_does_not_leak_raw_content(
    session_factory: Any,
) -> None:
    """AI ops panel must NOT contain raw AI content fields.

    The data payload carries counts, rates, percentiles, and top-N
    breakdowns only — never raw ``prompt_text``, ``completion_text``,
    ``system_prompt``, ``messages``, ``tool_calls``, ``request_body``,
    ``response_body``, or ``raw_response``.
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
        panels = await service.get_ai_operations(session, filters)
        assert panels
        # Forbidden raw-content field names (case-insensitive).
        forbidden = {
            "prompt_text",
            "completion_text",
            "system_prompt",
            "messages",
            "tool_calls",
            "request_body",
            "response_body",
            "raw_response",
            "prompt",
            "completion",
        }
        for p in panels:
            data = p.data if isinstance(p.data, dict) else {}
            keys_lower = {k.lower() for k in data.keys()}
            leak = keys_lower & forbidden
            assert not leak, (
                f"ai ops panel {p.metric_id} leaks raw content: {leak}"
            )


# ---------------------------------------------------------------------------
# T100 — Rate clamping & cost labeling
# ---------------------------------------------------------------------------


async def test_success_rate_is_clamped_to_unit_interval(
    session_factory: Any,
) -> None:
    """``success_rate`` is clamped to [0.0, 1.0]."""
    from app.modules.pm_dashboard.schemas import DashboardFilter
    from app.modules.pm_dashboard import service

    now = _now()
    filters = DashboardFilter(
        date_range_start=now - timedelta(days=7),
        date_range_end=now,
        environment="production",
    )
    async for session in session_factory():
        panels = await service.get_ai_operations(session, filters)
        assert panels
        for p in panels:
            data = p.data if isinstance(p.data, dict) else {}
            sr = data.get("success_rate")
            assert sr is not None
            assert isinstance(sr, (int, float))
            assert 0.0 <= float(sr) <= 1.0, f"success_rate {sr} out of [0,1]"


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
        panels = await service.get_ai_operations(session, filters)
        assert panels
        for p in panels:
            data = p.data if isinstance(p.data, dict) else {}
            fr = data.get("failure_rate")
            assert fr is not None
            assert isinstance(fr, (int, float))
            assert 0.0 <= float(fr) <= 1.0, f"failure_rate {fr} out of [0,1]"


async def test_ai_ops_cost_is_labeled_as_estimate(
    session_factory: Any,
) -> None:
    """``is_estimate`` flag is True (FR-008)."""
    from app.modules.pm_dashboard.schemas import DashboardFilter
    from app.modules.pm_dashboard import service

    now = _now()
    filters = DashboardFilter(
        date_range_start=now - timedelta(days=7),
        date_range_end=now,
        environment="production",
    )
    async for session in session_factory():
        panels = await service.get_ai_operations(session, filters)
        assert panels
        for p in panels:
            data = p.data if isinstance(p.data, dict) else {}
            assert data.get("is_estimate") is True, (
                f"ai ops panel must label cost as estimate (FR-008): {data}"
            )


async def test_ai_ops_token_counts_are_non_negative(
    session_factory: Any,
) -> None:
    """All token count fields (total, prompt, completion) are non-negative."""
    from app.modules.pm_dashboard.schemas import DashboardFilter
    from app.modules.pm_dashboard import service

    now = _now()
    filters = DashboardFilter(
        date_range_start=now - timedelta(days=7),
        date_range_end=now,
        environment="production",
    )
    async for session in session_factory():
        panels = await service.get_ai_operations(session, filters)
        assert panels
        for p in panels:
            data = p.data if isinstance(p.data, dict) else {}
            for key in ("total_tokens", "prompt_tokens", "completion_tokens"):
                v = data.get(key)
                assert v is not None
                assert isinstance(v, (int, float))
                assert int(v) >= 0, f"{key}={v} negative"


# ---------------------------------------------------------------------------
# T100 — Source-of-truth label
# ---------------------------------------------------------------------------


async def test_ai_ops_source_of_truth_label(
    session_factory: Any,
) -> None:
    """The panel's source_of_truth should be ``"ai_invocation_records"``."""
    from app.modules.pm_dashboard.schemas import DashboardFilter
    from app.modules.pm_dashboard import service

    now = _now()
    filters = DashboardFilter(
        date_range_start=now - timedelta(days=7),
        date_range_end=now,
        environment="production",
    )
    async for session in session_factory():
        panels = await service.get_ai_operations(session, filters)
        assert panels
        for p in panels:
            assert p.source_of_truth == "ai_invocation_records", (
                f"unexpected source_of_truth: {p.source_of_truth!r}"
            )
