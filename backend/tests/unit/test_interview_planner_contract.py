"""Regression tests for the interview planner graph contract."""
from __future__ import annotations

import inspect

import pytest


def test_planner_subgraph_factory_returns_runnable_not_coroutine() -> None:
    """LangGraph add_node must receive a Runnable/callable, not a coroutine."""
    from app.agents.interview.planner_graph import get_planner_subgraph

    planner_subgraph = get_planner_subgraph()

    assert not inspect.isawaitable(planner_subgraph)
    assert hasattr(planner_subgraph, "ainvoke")


def test_error_question_model_matches_archived_at_drop_migration() -> None:
    """The ORM must not select archived_at after migration 0014 drops it."""
    from app.modules.errors.models import ErrorQuestion

    assert "archived_at" not in ErrorQuestion.__table__.columns


def test_error_question_out_accepts_rows_without_archived_at() -> None:
    """Older API shape keeps archived_at nullable without requiring a DB column."""
    from datetime import UTC, datetime
    from types import SimpleNamespace
    from uuid import uuid4

    from app.modules.errors.schemas import ErrorQuestionOut

    row = SimpleNamespace(
        id=uuid4(),
        source_session_id=None,
        source_question_id=None,
        dimension="tech_depth",
        question_text="请解释 Redis 缓存雪崩。",
        answer_text=None,
        reference_answer_md=None,
        score=5,
        status="fresh",
        frequency=3,
        tags=None,
        last_practiced_at=None,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )

    parsed = ErrorQuestionOut.model_validate(row)

    assert parsed.archived_at is None


def test_settings_exposes_tavily_real_and_mock_fields() -> None:
    """Tavily search reads these Settings fields in production."""
    from app.core.config import Settings

    settings = Settings(
        database_url="sqlite+aiosqlite://",
        deepseek_api_key="sk-dummy",
        tavily_api_key="tvly-test",
        tavily_mock_mode=False,
    )

    assert settings.tavily_api_key == "tvly-test"
    assert settings.tavily_mock_mode is False
