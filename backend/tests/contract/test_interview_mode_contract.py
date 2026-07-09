"""REQ-048 US1 - POST /api/v1/interview-sessions mode contract tests."""
from __future__ import annotations

import pytest


pytestmark = pytest.mark.contract


def _error(body: dict) -> dict | None:
    """Support the project-wide envelope and older nested HTTPException detail."""
    if isinstance(body.get("error"), dict):
        return body["error"]
    detail = body.get("detail")
    if isinstance(detail, dict) and isinstance(detail.get("error"), dict):
        return detail["error"]
    return None


def _details(error: dict) -> dict:
    return error.get("details") or error.get("ctx") or {}


@pytest.mark.asyncio
async def test_insufficient_error_pool_returns_422(client, user_a_headers) -> None:
    """AC-02: quick_drill mode with <5 active errors returns 422 + details.available."""
    r = await client.post(
        "/api/v1/interview-sessions",
        json={
            "position": "Backend Engineer",
            "company": "Acme",
            "mode": "quick_drill",
        },
        headers=user_a_headers,
    )
    assert r.status_code == 422, r.text
    error = _error(r.json())
    assert error is not None
    assert error["code"] == "INSUFFICIENT_ERROR_POOL"
    details = _details(error)
    assert details.get("available", 99) < 5
    assert details.get("required") == 5


@pytest.mark.asyncio
async def test_invalid_max_questions_returns_422(client, user_a_headers) -> None:
    """full mode + max_questions not in [10, 15] returns INVALID_MAX_QUESTIONS."""
    r = await client.post(
        "/api/v1/interview-sessions",
        json={
            "position": "Backend Engineer",
            "company": "Acme",
            "mode": "full",
            "max_questions": 5,
        },
        headers=user_a_headers,
    )
    assert r.status_code == 422, r.text
    error = _error(r.json())
    assert error is not None
    assert error["code"] == "INVALID_MAX_QUESTIONS"
    assert _details(error).get("allowed") == [10, 15]


@pytest.mark.asyncio
async def test_full_mode_rejects_non_choice_that_passes_schema(client, user_a_headers) -> None:
    """12 is an integer but not an allowed REQ-048 full-interview choice."""
    r = await client.post(
        "/api/v1/interview-sessions",
        json={
            "position": "Backend Engineer",
            "company": "Acme",
            "mode": "full",
            "max_questions": 12,
        },
        headers=user_a_headers,
    )
    assert r.status_code == 422, r.text
    error = _error(r.json())
    assert error is not None
    assert error["code"] == "INVALID_MAX_QUESTIONS"


@pytest.mark.asyncio
async def test_doubao_use_variants_returns_422(client, user_a_headers) -> None:
    """mode='doubao' + use_variants=true returns INVALID_COMBINATION."""
    r = await client.post(
        "/api/v1/interview-sessions",
        json={
            "position": "Backend Engineer",
            "company": "Acme",
            "mode": "doubao",
            "use_variants": True,
        },
        headers=user_a_headers,
    )
    assert r.status_code == 422, r.text
    error = _error(r.json())
    assert error is not None
    assert error["code"] == "INVALID_COMBINATION"
    assert _details(error).get("field") == "use_variants"


@pytest.mark.asyncio
async def test_invalid_mode_returns_422(client, user_a_headers) -> None:
    """Mode Literal rejects non-enum values at the Pydantic layer."""
    r = await client.post(
        "/api/v1/interview-sessions",
        json={
            "position": "Backend Engineer",
            "company": "Acme",
            "mode": "garbage",
        },
        headers=user_a_headers,
    )
    assert r.status_code == 422, r.text
    error = _error(r.json())
    assert error is not None
    assert error["code"] == "validation.failed"
