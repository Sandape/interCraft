from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from app.modules.pm_dashboard import repository
from app.modules.pm_dashboard.schemas import DashboardFilter


class FakeResult:
    def __init__(self, rows: list[dict[str, object]] | None = None) -> None:
        self._rows = rows or []

    def mappings(self) -> "FakeResult":
        return self

    def all(self) -> list[dict[str, object]]:
        return self._rows


class FakeSession:
    def __init__(self, rows: list[dict[str, object]] | None = None) -> None:
        self.rows = rows or []
        self.statements: list[object] = []

    async def execute(self, statement: object) -> FakeResult:
        self.statements.append(statement)
        return FakeResult(self.rows)


@pytest.mark.asyncio
async def test_create_metric_snapshot_persists_freshness_and_quality_flags() -> None:
    now = datetime(2026, 6, 29, 12, 0, tzinfo=UTC)
    session = FakeSession()
    user_id = uuid4()

    row = await repository.create_metric_snapshot(
        session,
        user_id=user_id,
        metric_id="pm.active_users",
        period_start=now - timedelta(days=1),
        period_end=now,
        value=128,
        unit="COUNT",
        source_of_truth="product_events",
        freshness_at=now - timedelta(minutes=5),
        quality_flags={"quality_state": "complete", "missing_sources": []},
        dimensions={"environment": "local"},
        numerator=128,
        denominator=None,
    )

    assert row["metric_id"] == "pm.active_users"
    assert row["freshness_at"] == now - timedelta(minutes=5)
    assert row["quality_flags"]["quality_state"] == "complete"
    assert row["dimensions"] == {"environment": "local"}
    assert session.statements
    assert "pm_metric_snapshots" in str(session.statements[0])


@pytest.mark.asyncio
async def test_list_metric_snapshots_uses_180_day_window_and_returns_quality_metadata() -> None:
    now = datetime(2026, 6, 29, 12, 0, tzinfo=UTC)
    snapshot_id = uuid4()
    session = FakeSession(
        rows=[
            {
                "id": snapshot_id,
                "metric_id": "pm.active_users",
                "period_start": now - timedelta(days=1),
                "period_end": now,
                "grain": "DAY",
                "dimensions": {"environment": "local"},
                "numerator": 128,
                "denominator": None,
                "value": 128,
                "unit": "COUNT",
                "source_of_truth": "product_events",
                "freshness_at": now - timedelta(minutes=5),
                "quality_flags": {"quality_state": "complete"},
                "user_id": uuid4(),
                "created_at": now,
            }
        ]
    )
    filters = DashboardFilter(
        date_range_start=now - timedelta(days=365),
        date_range_end=now,
        environment="local",
    )

    rows = await repository.list_metric_snapshots(
        session,
        filters=filters,
        metric_ids=["pm.active_users"],
        now=now,
    )

    assert len(rows) == 1
    assert rows[0]["snapshot_id"] == snapshot_id
    assert rows[0]["metric_id"] == "pm.active_users"
    assert rows[0]["quality_state"] == "complete"
    assert rows[0]["freshness_at"] == now - timedelta(minutes=5)

    compiled = str(session.statements[0])
    assert "pm_metric_snapshots" in compiled
    assert "period_start" in compiled
    assert "metric_id" in compiled
