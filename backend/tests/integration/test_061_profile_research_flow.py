"""REQ-061 T092 integration tests — profile dashboard/API/service contract.

Covers:
- No score and no task → verified_score_status=unavailable, ai_insight=None
- Manual-only dimensions → verified_score_status=unavailable
- Score 0 from interview/coach → verified_score_status=ready
- Score present but no task → verified_score_status=ready, ai_insight=None
- Failed latest insight task → ai_insight with failure_category, score unchanged
- Latest task ordering (accepted_at DESC, id DESC — equal-timestamp tie-break)
- User isolation (never expose another user's task)
- Response serialization against typed schemas
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient

from app.core.db import _session_cm


def _user_id_from_headers(headers: dict[str, str]) -> UUID:
    """Decode the user_id from auth headers by hitting a protected endpoint."""
    import base64
    import json

    token = headers.get("Authorization", "").removeprefix("Bearer ")
    if not token:
        raise ValueError("No bearer token in headers")
    parts = token.split(".")
    if len(parts) < 2:
        raise ValueError("Not a JWT")
    payload = parts[1]
    payload += "=" * (4 - len(payload) % 4)
    decoded = json.loads(base64.urlsafe_b64decode(payload).decode())
    return UUID(decoded["sub"])


@pytest.mark.integration
class TestVerifiedScoreStatus:
    """verified_score_status is derived only from active deterministic dimensions."""

    async def test_no_score_no_task_returns_unavailable(
        self, client: AsyncClient, fresh_user_headers: dict[str, str]
    ):
        """New user with no scores → unavailable, no insight task."""
        resp = await client.get(
            "/api/v1/ability-profile/dashboard",
            headers=fresh_user_headers,
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["verified_score_status"] == "unavailable"
        assert data["ai_insight"] is None

    async def test_manual_only_dimensions_returns_unavailable(
        self, client: AsyncClient, fresh_user_headers: dict[str, str]
    ):
        """Dimensions with source=manual only → unavailable."""
        uid = _user_id_from_headers(fresh_user_headers)
        async with _session_cm() as session:
            from sqlalchemy import text

            await session.execute(
                text("SELECT set_config('app.user_id', :u, true)"),
                {"u": str(uid)},
            )
            await session.execute(
                text(
                    """
                    INSERT INTO ability_dimensions
                        (user_id, dimension_key, actual_score, ideal_score,
                         source, is_active, self_assessed_score)
                    VALUES (:uid, 'communication', 5.0, 10, 'manual', true, NULL)
                    ON CONFLICT (user_id, dimension_key) DO UPDATE
                        SET actual_score = 5.0, source = 'manual', is_active = true
                    """
                ),
                {"uid": uid},
            )
            await session.commit()

        resp = await client.get(
            "/api/v1/ability-profile/dashboard",
            headers=fresh_user_headers,
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["verified_score_status"] == "unavailable"

    async def test_score_zero_from_interview_returns_ready(
        self, client: AsyncClient, user_a_headers: dict[str, str]
    ):
        """Score 0 from interview → ready (not gated on >0)."""
        uid = _user_id_from_headers(user_a_headers)
        async with _session_cm() as session:
            from sqlalchemy import text

            await session.execute(
                text("SELECT set_config('app.user_id', :u, true)"),
                {"u": str(uid)},
            )
            await session.execute(
                text(
                    """
                    INSERT INTO ability_dimensions
                        (user_id, dimension_key, actual_score, ideal_score,
                         source, is_active, self_assessed_score)
                    VALUES (:uid, 'algorithm', 0, 10, 'interview', true, NULL)
                    ON CONFLICT (user_id, dimension_key) DO UPDATE
                        SET actual_score = 0, source = 'interview', is_active = true
                    """
                ),
                {"uid": uid},
            )
            await session.commit()

        resp = await client.get(
            "/api/v1/ability-profile/dashboard",
            headers=user_a_headers,
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["verified_score_status"] == "ready"

    async def test_score_zero_from_coach_returns_ready(
        self, client: AsyncClient, user_a_headers: dict[str, str]
    ):
        """Score 0 from coach → ready."""
        uid = _user_id_from_headers(user_a_headers)
        async with _session_cm() as session:
            from sqlalchemy import text

            await session.execute(
                text("SELECT set_config('app.user_id', :u, true)"),
                {"u": str(uid)},
            )
            await session.execute(
                text(
                    """
                    INSERT INTO ability_dimensions
                        (user_id, dimension_key, actual_score, ideal_score,
                         source, is_active, self_assessed_score)
                    VALUES (:uid, 'business', 0, 10, 'coach', true, NULL)
                    ON CONFLICT (user_id, dimension_key) DO UPDATE
                        SET actual_score = 0, source = 'coach', is_active = true
                    """
                ),
                {"uid": uid},
            )
            await session.commit()

        resp = await client.get(
            "/api/v1/ability-profile/dashboard",
            headers=user_a_headers,
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["verified_score_status"] == "ready"

    async def test_score_present_no_task_returns_ready(
        self, client: AsyncClient, user_a_headers: dict[str, str]
    ):
        """User with deterministic score → ready even without insight task."""
        uid = _user_id_from_headers(user_a_headers)
        async with _session_cm() as session:
            from sqlalchemy import text

            await session.execute(
                text("SELECT set_config('app.user_id', :u, true)"),
                {"u": str(uid)},
            )
            await session.execute(
                text(
                    """
                    INSERT INTO ability_dimensions
                        (user_id, dimension_key, actual_score, ideal_score,
                         source, is_active, self_assessed_score)
                    VALUES (:uid, 'tech_depth', 7.5, 10, 'interview', true, NULL)
                    ON CONFLICT (user_id, dimension_key) DO UPDATE
                        SET actual_score = 7.5, source = 'interview', is_active = true
                    """
                ),
                {"uid": uid},
            )
            await session.commit()

        resp = await client.get(
            "/api/v1/ability-profile/dashboard",
            headers=user_a_headers,
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["verified_score_status"] == "ready"
        assert data["ai_insight"] is None

    async def test_insight_failure_never_downgrades_score(
        self, client: AsyncClient, user_a_headers: dict[str, str]
    ):
        """Insight task failure must not change verified_score_status to unavailable."""
        uid = _user_id_from_headers(user_a_headers)
        now = datetime.now(timezone.utc)
        task_id = uuid4()

        async with _session_cm() as session:
            from sqlalchemy import text

            # Seed a deterministic score
            await session.execute(
                text("SELECT set_config('app.user_id', :u, true)"),
                {"u": str(uid)},
            )
            await session.execute(
                text(
                    """
                    INSERT INTO ability_dimensions
                        (user_id, dimension_key, actual_score, ideal_score,
                         source, is_active, self_assessed_score)
                    VALUES (:uid, 'tech_depth', 8.0, 10, 'interview', true, NULL)
                    ON CONFLICT (user_id, dimension_key) DO UPDATE
                        SET actual_score = 8.0, source = 'interview', is_active = true
                    """
                ),
                {"uid": uid},
            )

            # Seed a failed insight task
            await session.execute(text("SELECT set_config('app.user_id', '', true)"))
            await session.execute(
                text(
                    """
                    INSERT INTO ai_tasks
                        (id, user_id, capability_code, action_code,
                         idempotency_key, acceptance_request_hash,
                         service_tier, status, user_summary,
                         available_actions, failure_category,
                         accepted_at, task_version)
                    VALUES
                        (:tid, :uid, 'ability_insight', 'diagnose',
                         'diagnose:test-fail:session-1', 'sha256:deadbeef',
                         'standard', 'failed',
                         '洞察生成失败，已验证评分不受影响。',
                         '["cancel"]'::jsonb, 'insight_generation_failed',
                         :accepted, 1)
                    """
                ),
                {
                    "tid": task_id,
                    "uid": uid,
                    "accepted": now - timedelta(minutes=5),
                },
            )
            await session.commit()

        resp = await client.get(
            "/api/v1/ability-profile/dashboard",
            headers=user_a_headers,
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["verified_score_status"] == "ready"
        assert data["ai_insight"] is not None
        assert data["ai_insight"]["status"] == "failed"
        assert data["ai_insight"]["failure_category"] == "insight_generation_failed"
        assert data["ai_insight"]["task_id"] == str(task_id)


@pytest.mark.integration
class TestInsightTaskOrdering:
    """Latest task selection respects accepted_at DESC, id DESC."""

    async def test_latest_by_accepted_at_desc(
        self, client: AsyncClient, user_a_headers: dict[str, str]
    ):
        """Multiple tasks → the latest by accepted_at is projected."""
        uid = _user_id_from_headers(user_a_headers)
        now = datetime.now(timezone.utc)

        older_id = uuid4()
        newer_id = uuid4()

        async with _session_cm() as session:
            from sqlalchemy import text

            await session.execute(text("SELECT set_config('app.user_id', '', true)"))
            await session.execute(
                text(
                    """
                    INSERT INTO ai_tasks
                        (id, user_id, capability_code, action_code,
                         idempotency_key, acceptance_request_hash,
                         service_tier, status, user_summary,
                         available_actions, failure_category,
                         accepted_at, task_version)
                    VALUES
                        (:tid1, :uid, 'ability_insight', 'diagnose',
                         'diagnose:test-ordering:old', 'sha256:aaa',
                         'standard', 'succeeded', '洞察完成',
                         '[]'::jsonb, NULL,
                         :older, 1),
                        (:tid2, :uid, 'ability_insight', 'diagnose',
                         'diagnose:test-ordering:new', 'sha256:bbb',
                         'standard', 'succeeded', '最新洞察',
                         '[]'::jsonb, NULL,
                         :newer, 1)
                    """
                ),
                {
                    "tid1": older_id,
                    "tid2": newer_id,
                    "uid": uid,
                    "older": now - timedelta(hours=1),
                    "newer": now,
                },
            )
            await session.commit()

        resp = await client.get(
            "/api/v1/ability-profile/dashboard",
            headers=user_a_headers,
        )
        assert resp.status_code == 200
        insight = resp.json()["data"]["ai_insight"]
        assert insight is not None
        assert insight["task_id"] == str(newer_id)
        assert insight["status"] == "succeeded"
        assert insight["user_summary"] == "最新洞察"

    async def test_tie_break_accepted_at_equal_id_desc(
        self, client: AsyncClient, user_a_headers: dict[str, str]
    ):
        """When accepted_at is equal, id DESC tie-breaks to the higher UUID."""
        uid = _user_id_from_headers(user_a_headers)
        same_ts = datetime.now(timezone.utc)

        # Generate two random UUIDs and sort by integer value for deterministic ordering
        raw = [uuid4(), uuid4()]
        raw.sort(key=lambda u: u.int)
        lower_id, higher_id = raw[0], raw[1]

        async with _session_cm() as session:
            from sqlalchemy import text

            await session.execute(text("SELECT set_config('app.user_id', '', true)"))
            await session.execute(
                text(
                    """
                    INSERT INTO ai_tasks
                        (id, user_id, capability_code, action_code,
                         idempotency_key, acceptance_request_hash,
                         service_tier, status, user_summary,
                         available_actions, failure_category,
                         accepted_at, task_version)
                    VALUES
                        (:tid1, :uid, 'ability_insight', 'diagnose',
                         'diagnose:tie-lower', 'sha256:tie-a',
                         'standard', 'succeeded', 'older-by-id',
                         '[]'::jsonb, NULL,
                         :ts, 1),
                        (:tid2, :uid, 'ability_insight', 'diagnose',
                         'diagnose:tie-higher', 'sha256:tie-b',
                         'standard', 'succeeded', 'newer-by-id',
                         '[]'::jsonb, NULL,
                         :ts, 1)
                    """
                ),
                {
                    "tid1": lower_id,
                    "tid2": higher_id,
                    "uid": uid,
                    "ts": same_ts,
                },
            )
            await session.commit()

        resp = await client.get(
            "/api/v1/ability-profile/dashboard",
            headers=user_a_headers,
        )
        assert resp.status_code == 200
        insight = resp.json()["data"]["ai_insight"]
        assert insight is not None
        # id DESC → higher_id returned
        assert insight["task_id"] == str(higher_id)
        assert insight["user_summary"] == "newer-by-id"


@pytest.mark.integration
class TestUserIsolation:
    """Never expose another user's ability_insight task."""

    async def test_user_a_cannot_see_user_b_insight_task(
        self, client: AsyncClient, user_a_headers: dict[str, str], user_b_headers: dict[str, str]
    ):
        """User A's dashboard must NOT include User B's insight task."""
        uid_a = _user_id_from_headers(user_a_headers)
        uid_b = _user_id_from_headers(user_b_headers)
        now = datetime.now(timezone.utc)
        task_b = uuid4()

        async with _session_cm() as session:
            from sqlalchemy import text

            await session.execute(text("SELECT set_config('app.user_id', '', true)"))
            await session.execute(
                text(
                    """
                    INSERT INTO ai_tasks
                        (id, user_id, capability_code, action_code,
                         idempotency_key, acceptance_request_hash,
                         service_tier, status, user_summary,
                         available_actions, failure_category,
                         accepted_at, task_version)
                    VALUES
                        (:tid, :uid, 'ability_insight', 'diagnose',
                         'diagnose:isolate:b', 'sha256:ccc',
                         'standard', 'succeeded', 'User B insight',
                         '[]'::jsonb, NULL,
                         :ts, 1)
                    """
                ),
                {"tid": task_b, "uid": uid_b, "ts": now},
            )
            await session.commit()

        resp_a = await client.get(
            "/api/v1/ability-profile/dashboard",
            headers=user_a_headers,
        )
        assert resp_a.status_code == 200
        insight_a = resp_a.json()["data"]["ai_insight"]
        assert insight_a is None


@pytest.mark.integration
class TestResponseSerialization:
    """DashboardResponse serializes with typed fields matching Pydantic schema."""

    async def test_dashboard_response_matches_schema(
        self, client: AsyncClient, user_a_headers: dict[str, str]
    ):
        """Response passes response_model validation and has all typed fields."""
        uid = _user_id_from_headers(user_a_headers)
        now = datetime.now(timezone.utc)
        task_id = uuid4()

        async with _session_cm() as session:
            from sqlalchemy import text

            await session.execute(
                text("SELECT set_config('app.user_id', :u, true)"),
                {"u": str(uid)},
            )
            await session.execute(
                text(
                    """
                    INSERT INTO ability_dimensions
                        (user_id, dimension_key, actual_score, ideal_score,
                         source, is_active, self_assessed_score)
                    VALUES (:uid, 'architecture', 6.0, 10, 'interview', true, NULL)
                    ON CONFLICT (user_id, dimension_key) DO UPDATE
                        SET actual_score = 6.0, source = 'interview', is_active = true
                    """
                ),
                {"uid": uid},
            )

            await session.execute(text("SELECT set_config('app.user_id', '', true)"))
            await session.execute(
                text(
                    """
                    INSERT INTO ai_tasks
                        (id, user_id, capability_code, action_code,
                         idempotency_key, acceptance_request_hash,
                         service_tier, status, user_summary,
                         available_actions, failure_category,
                         accepted_at, task_version)
                    VALUES
                        (:tid, :uid, 'ability_insight', 'diagnose',
                         'diagnose:serial:1', 'sha256:ddd',
                         'standard', 'succeeded', '洞察完成',
                         '["cancel"]'::jsonb, NULL,
                         :ts, 1)
                    """
                ),
                {"tid": task_id, "uid": uid, "ts": now},
            )
            await session.commit()

        resp = await client.get(
            "/api/v1/ability-profile/dashboard",
            headers=user_a_headers,
        )
        assert resp.status_code == 200
        data = resp.json()["data"]

        assert "verified_score_status" in data
        assert data["verified_score_status"] in ("ready", "unavailable")
        assert "ai_insight" in data

        insight = data["ai_insight"]
        assert insight is not None
        assert insight["task_id"] == str(task_id)
        assert insight["status"] == "succeeded"
        assert isinstance(insight["available_actions"], list)
        assert "dimensions" in data
        assert "generated_at" in data

        for dim in data["dimensions"]:
            assert "key" in dim
            assert "actual_score" in dim
            assert "history" in dim
