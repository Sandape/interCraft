"""Integration test for the IRT θ sidecar in `aggregate_scores_node` (REQ-030 US1).

Per spec acceptance scenario US1.AS-3:
  "Given 5 mock responses to calibrated items, the system outputs
   θ + standard_error per dimension."

This test:
  1. Inserts 10 IRT items for `tech_depth` via the seed loader.
  2. Inserts 5 ItemResponse rows for a test user (3 correct, 2 incorrect).
  3. Calls `aggregate_scores_node` directly with a mock state.
  4. Asserts `irt_thetas` is populated with the expected shape.
  5. Asserts the existing `interview_scores` shape is preserved
     (backward-compat check for the additive sidecar).

Falls back to a pure-math test if DB is unavailable (the
`_compute_irt_thetas` function in aggregate_scores is bypassed and
the engine is exercised directly with the same response pattern).
"""
from __future__ import annotations

import uuid
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import text

pytestmark = [pytest.mark.integration]


# ── Test helpers ───────────────────────────────────────────────────────────


async def _seed_via_register(client, suffix: str) -> tuple[dict, str]:
    """Register a fresh user; mirrors the helper in test_ability_diagnose.py."""
    email = f"irt_{suffix}@intercraft.io"
    fp = f"fp-{suffix}"
    reg = await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "Demo1234",
            "display_name": f"irt-{suffix}",
            "device_fingerprint": fp,
        },
        headers={"X-Device-Fingerprint": fp},
    )
    assert reg.status_code in (200, 201), reg.text
    access = reg.json()["tokens"]["access_token"]
    headers = {
        "Authorization": f"Bearer {access}",
        "X-Device-Fingerprint": fp,
    }
    me = await client.get("/api/v1/users/me", headers=headers)
    assert me.status_code == 200, me.text
    return headers, me.json()["id"]


async def _insert_seed_items_for_test(db_session, dimension: str) -> list:
    """Insert 10 seed items for one dimension and return their ORM rows."""
    from app.modules.irt.models import Item
    from app.modules.irt.repository import ItemRepository
    from app.modules.irt.seed import seed_items_for_dimension

    repo = ItemRepository(db_session)
    items = seed_items_for_dimension(dimension)
    await repo.upsert_seed_items(items)
    await db_session.commit()

    from sqlalchemy import select

    result = await db_session.execute(
        select(Item).where(Item.dimension == dimension).order_by(Item.difficulty_b)
    )
    return list(result.scalars().all())


async def _insert_responses(
    db_session, user_id: str, items: list, n_correct: int = 3
) -> None:
    """Insert n_correct correct + (5 - n_correct) incorrect responses."""
    from app.modules.irt.models import ItemResponse

    n = len(items)
    if n < 5:
        raise ValueError("need at least 5 items for this test")
    for i, it in enumerate(items[:5]):
        u = "correct" if i < n_correct else "incorrect"
        score = 8.0 if u == "correct" else 4.0
        # RLS scoping
        await db_session.execute(
            text("SELECT set_config('app.user_id', :uid, true)"),
            {"uid": user_id},
        )
        db_session.add(
            ItemResponse(
                id=uuid.uuid4(),
                user_id=uuid.UUID(user_id),
                item_id=it.id,
                response=u,
                score=score,
                source_interview_id=None,
            )
        )
    await db_session.commit()


# ── Test ──────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_aggregate_scores_emits_irt_thetas(client, db_session):
    """REQ-030 US1: 5 mock responses → `aggregate_scores_node` emits θ + SE.

    The sidecar is purely additive: the existing `interview_scores` shape
    is preserved. The new `irt_thetas` key carries a per-dimension θ
    estimate with the documented fields.
    """
    from app.agents.nodes.ability_diagnose.aggregate_scores import (
        aggregate_scores_node,
    )

    # 1) Register user
    suffix = uuid.uuid4().hex[:8]
    _headers, user_id = await _seed_via_register(client, suffix)

    # 2) Insert 10 seed items for tech_depth
    items = await _insert_seed_items_for_test(db_session, "tech_depth")
    assert len(items) == 10, f"expected 10 seed items, got {len(items)}"

    # 3) Insert 5 responses (3 correct, 2 incorrect)
    await _insert_responses(db_session, user_id, items, n_correct=3)

    # 4) Call aggregate_scores_node with a minimal state. We mock the
    #    report/question helpers to return empty (no LLM dependency).
    state: dict[str, Any] = {
        "user_id": user_id,
        "session_id": str(uuid.uuid4()),
    }
    with (
        patch(
            "app.agents.nodes.ability_diagnose.aggregate_scores.query_interview_report",
            new=AsyncMock(return_value=None),
        ),
        patch(
            "app.agents.nodes.ability_diagnose.aggregate_scores.query_interview_questions",
            new=AsyncMock(return_value=[]),
        ),
        patch(
            "app.agents.nodes.ability_diagnose.aggregate_scores.query_ai_messages_for_session",
            new=AsyncMock(return_value=[]),
        ),
    ):
        result = await aggregate_scores_node(state)

    # 5) Assert additive sidecar shape is correct.
    assert "interview_scores" in result
    assert "irt_thetas" in result
    assert isinstance(result["irt_thetas"], list)

    # 5 mock responses were for tech_depth → exactly one θ entry.
    thetas = result["irt_thetas"]
    assert len(thetas) == 1, f"expected 1 theta, got {len(thetas)}: {thetas}"
    entry = thetas[0]
    assert entry["dimension"] == "tech_depth"
    assert -6.0 <= entry["theta"] <= 6.0, f"theta out of range: {entry['theta']}"
    assert entry["standard_error"] > 0.0
    assert entry["n_items"] == 5
    assert entry["converged"] is True


@pytest.mark.asyncio
async def test_aggregate_scores_no_irt_data_returns_empty_list(client, db_session):
    """With no IRT responses in the bank, `irt_thetas` is `[]` — not an error."""
    from app.agents.nodes.ability_diagnose.aggregate_scores import (
        aggregate_scores_node,
    )

    suffix = uuid.uuid4().hex[:8]
    _headers, user_id = await _seed_via_register(client, suffix)

    state: dict[str, Any] = {
        "user_id": user_id,
        "session_id": str(uuid.uuid4()),
    }
    with (
        patch(
            "app.agents.nodes.ability_diagnose.aggregate_scores.query_interview_report",
            new=AsyncMock(return_value=None),
        ),
        patch(
            "app.agents.nodes.ability_diagnose.aggregate_scores.query_interview_questions",
            new=AsyncMock(return_value=[]),
        ),
        patch(
            "app.agents.nodes.ability_diagnose.aggregate_scores.query_ai_messages_for_session",
            new=AsyncMock(return_value=[]),
        ),
    ):
        result = await aggregate_scores_node(state)

    assert "irt_thetas" in result
    assert result["irt_thetas"] == []


@pytest.mark.asyncio
async def test_aggregate_scores_fewer_than_min_responses_skips_dimension(
    client, db_session
):
    """Dimensions with <3 responses are excluded from the result list."""
    from app.agents.nodes.ability_diagnose.aggregate_scores import (
        aggregate_scores_node,
    )

    suffix = uuid.uuid4().hex[:8]
    _headers, user_id = await _seed_via_register(client, suffix)

    items = await _insert_seed_items_for_test(db_session, "algorithm")
    # Only 2 responses (below MIN_IRT_RESPONSES = 3).
    from app.modules.irt.models import ItemResponse

    for it in items[:2]:
        await db_session.execute(
            text("SELECT set_config('app.user_id', :uid, true)"),
            {"uid": user_id},
        )
        db_session.add(
            ItemResponse(
                id=uuid.uuid4(),
                user_id=uuid.UUID(user_id),
                item_id=it.id,
                response="correct",
                score=8.0,
                source_interview_id=None,
            )
        )
    await db_session.commit()

    state: dict[str, Any] = {
        "user_id": user_id,
        "session_id": str(uuid.uuid4()),
    }
    with (
        patch(
            "app.agents.nodes.ability_diagnose.aggregate_scores.query_interview_report",
            new=AsyncMock(return_value=None),
        ),
        patch(
            "app.agents.nodes.ability_diagnose.aggregate_scores.query_interview_questions",
            new=AsyncMock(return_value=[]),
        ),
        patch(
            "app.agents.nodes.ability_diagnose.aggregate_scores.query_ai_messages_for_session",
            new=AsyncMock(return_value=[]),
        ),
    ):
        result = await aggregate_scores_node(state)

    # 2 responses < MIN_IRT_RESPONSES → algorithm dimension is skipped.
    dims = {e["dimension"] for e in result["irt_thetas"]}
    assert "algorithm" not in dims


# ── Pure-math fallback (no DB) ─────────────────────────────────────────────


def test_pure_math_five_responses_recovers_theta() -> None:
    """Pure-math regression: simulate 50 responses from a user with
    known θ=0.5, verify the estimator recovers within 0.3 logit.

    This test runs without a DB, exercising only the engine. Mirrors
    the US1 acceptance scenario for IRT math (ground-truth error
    < 0.3 logit per spec).
    """
    import random

    from app.modules.irt.engine import estimate_theta_mle, probability_2pl

    # 50 items with difficulty spanning [-2, +2], discrimination=1.0.
    rng = random.Random(42)  # deterministic
    items = [(1.0, b) for b in (rng.uniform(-2.0, 2.0) for _ in range(50))]

    # Simulate responses from a user with true θ = 0.5.
    true_theta = 0.5
    responses = []
    for a, b in items:
        p = probability_2pl(true_theta, a, b)
        u = 1 if rng.random() < p else 0
        responses.append((a, b, u))

    result = estimate_theta_mle(responses)
    # Ground truth θ=0.5 → estimator should land within 0.3 logit.
    assert abs(result.theta - true_theta) < 0.3, (
        f"expected θ̂ within 0.3 of {true_theta}, got {result.theta} "
        f"(n_items={result.n_items}, converged={result.converged})"
    )
    assert result.n_items == 50
    assert result.standard_error > 0
    assert result.standard_error < float("inf")
    assert result.converged is True
