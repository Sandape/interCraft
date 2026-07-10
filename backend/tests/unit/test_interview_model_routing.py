"""Interview LLM model routing: plan = pro, everything else = flash."""
from __future__ import annotations

import pytest

from app.agents.token_estimator import (
    TokenEstimator,
    _get_per_node_model,
    thinking_enabled_for_model,
)
from app.core.config import get_settings

# Stale process env from older backend launches must not mask .env / defaults.
_STALE_ENV_KEYS = (
    "DEEPSEEK_MODEL",
    "DEEPSEEK_MODEL_PLANNER",
    "DEEPSEEK_MODEL_PLANNER_GENERATE",
    "DEEPSEEK_MODEL_INTAKE",
    "DEEPSEEK_MODEL_QUESTION_GEN",
    "DEEPSEEK_MODEL_SCORE",
    "DEEPSEEK_MODEL_SCORE_LLM",
    "DEEPSEEK_MODEL_REPORT",
    "DEEPSEEK_MODEL_COMPRESS_HISTORY",
    "DEEPSEEK_MODEL_VARIANT_GENERATOR",
    "AGENT_MODEL_PLANNER",
    "AGENT_MODEL_PLANNER_GENERATE",
    "AGENT_MODEL_INTAKE",
    "AGENT_MODEL_QUESTION_GEN",
    "AGENT_MODEL_SCORE",
    "AGENT_MODEL_SCORE_LLM",
    "AGENT_MODEL_REPORT",
    "AGENT_MODEL_COMPRESS_HISTORY",
    "AGENT_MODEL_VARIANT_GENERATOR",
)


@pytest.fixture(autouse=True)
def _clear_stale_model_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in _STALE_ENV_KEYS:
        monkeypatch.delenv(key, raising=False)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.mark.parametrize(
    "node_name,expected",
    [
        ("planner", "deepseek-v4-pro"),
        ("planner_generate", "deepseek-v4-pro"),
        ("intake", "deepseek-v4-flash"),
        ("question_gen", "deepseek-v4-flash"),
        ("score", "deepseek-v4-flash"),
        ("score_llm", "deepseek-v4-flash"),
        ("report", "deepseek-v4-flash"),
        ("compress_history", "deepseek-v4-flash"),
        ("variant_generator", "deepseek-v4-flash"),
    ],
)
def test_per_node_model_policy(node_name: str, expected: str) -> None:
    assert _get_per_node_model(node_name) == expected
    assert TokenEstimator().get_model(node_name) == expected


def test_thinking_only_on_pro() -> None:
    assert thinking_enabled_for_model("deepseek-v4-pro") is True
    assert thinking_enabled_for_model("deepseek-v4-flash") is False


def test_score_llm_aliases_to_score_settings() -> None:
    """score_llm must not fall through to a stale global pro default."""
    assert _get_per_node_model("score_llm") == "deepseek-v4-flash"
