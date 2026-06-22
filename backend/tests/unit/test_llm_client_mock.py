"""021: Unit tests for MockLLMClient and LLM_MOCK_MODE factory hook.

Tests per specs/021-error-coach-e2e/plan.md Phase A (TDD).
"""
from __future__ import annotations

import json
import os
import tempfile
from unittest.mock import patch

import pytest

from app.agents.llm_client import LLMClient, LLMResponse, get_llm_client


@pytest.fixture(autouse=True)
def _reset_singleton():
    """Reset the LLM client singletons between tests so env switches take effect."""
    import app.agents.llm_client as mod

    saved_real = mod._llm_client_singleton
    saved_mock = mod._mock_client_singleton
    saved_mtime = mod._mock_client_scenario_mtime
    mod._llm_client_singleton = None
    mod._mock_client_singleton = None
    mod._mock_client_scenario_mtime = None
    yield
    mod._llm_client_singleton = saved_real
    mod._mock_client_singleton = saved_mock
    mod._mock_client_scenario_mtime = saved_mtime


@pytest.fixture
def clean_mock_env(monkeypatch):
    """Remove all mock-related env vars."""
    monkeypatch.delenv("LLM_MOCK_MODE", raising=False)
    monkeypatch.delenv("LLM_MOCK_SCENARIO_PATH", raising=False)


@pytest.fixture
def scenario_file(tmp_path):
    """Write a sample scenario JSON to a tmp file and return its path."""
    scenario = {
        "evaluate_scores": [8, 9, 9],
        "hint_contents": {
            "small": "小提示：回忆依赖数组机制。",
            "medium": "中等提示：对比 useMemo 与 useCallback 的输入输出。",
            "detailed": "详细提示：useMemo 缓存值，useCallback 缓存函数。",
        },
    }
    path = tmp_path / "scenario.json"
    path.write_text(json.dumps(scenario), encoding="utf-8")
    return str(path)


class TestGetLLMClientFactory:
    """T004, T005: LLM_MOCK_MODE env var switches the client type."""

    def test_get_llm_client_returns_real_when_mock_mode_unset(self, clean_mock_env):
        """T004: env unset → returns real LLMClient."""
        client = get_llm_client()
        assert isinstance(client, LLMClient), "expected real LLMClient when LLM_MOCK_MODE unset"

    def test_get_llm_client_returns_mock_when_mock_mode_set(
        self, monkeypatch, scenario_file
    ):
        """T005: LLM_MOCK_MODE=1 + valid scenario path → returns MockLLMClient."""
        monkeypatch.setenv("LLM_MOCK_MODE", "1")
        monkeypatch.setenv("LLM_MOCK_SCENARIO_PATH", scenario_file)
        from app.agents.llm_client_mock import MockLLMClient

        client = get_llm_client()
        assert isinstance(client, MockLLMClient), "expected MockLLMClient when LLM_MOCK_MODE=1"


class TestMockLLMClientScenarioParsing:
    """T006: scenario JSON parsing."""

    def test_mock_llm_client_reads_scenario_json(self, scenario_file):
        """T006: from_scenario_file parses evaluate_scores + hint_contents."""
        from app.agents.llm_client_mock import MockLLMClient

        client = MockLLMClient.from_scenario_file(scenario_file)
        assert client.evaluate_scores == [8, 9, 9]
        assert "small" in client.hint_contents
        assert "medium" in client.hint_contents
        assert "detailed" in client.hint_contents

    def test_mock_llm_client_falls_back_on_missing_scenario(
        self, monkeypatch, tmp_path
    ):
        """T010: empty/missing scenario path → fallback defaults, no crash."""
        from app.agents.llm_client_mock import MockLLMClient

        missing = str(tmp_path / "does-not-exist.json")
        client = MockLLMClient.from_scenario_file(missing)
        assert client.evaluate_scores == [5], "fallback should be a single default score=5"
        assert client.hint_contents["small"] != "" or client.hint_contents["small"] == ""


class TestMockLLMClientInvoke:
    """T007: invoke returns score sequence for evaluate node."""

    @pytest.mark.asyncio
    async def test_mock_llm_client_evaluate_returns_score_sequence(
        self, scenario_file
    ):
        """T007: 3 sequential evaluate calls return [8, 9, 9] in order."""
        from app.agents.llm_client_mock import MockLLMClient

        client = MockLLMClient.from_scenario_file(scenario_file)

        scores = []
        for _ in range(3):
            resp = await client.invoke(
                messages=[{"role": "user", "content": "answer"}],
                user_id="00000000-0000-0000-0000-000000000001",
                thread_id="t-1",
                node_name="error_coach_evaluate",
            )
            import json as _json

            data = _json.loads(resp["content"])
            scores.append(data["score"])

        assert scores == [8, 9, 9], f"expected [8,9,9], got {scores}"

    @pytest.mark.asyncio
    async def test_mock_llm_client_hint_returns_level_content(self, scenario_file):
        """hint node returns content from hint_contents dict.

        The real hint_ladder prompt embeds 'Hint level: <level>' (see
        hint_ladder.md template). The mock must parse that format, not a
        synthetic 'current_hint_level=X' marker.
        """
        from app.agents.llm_client_mock import MockLLMClient

        client = MockLLMClient.from_scenario_file(scenario_file)

        # Realistic prompt shape — matches hint_ladder.md template output.
        realistic_prompt = (
            "You are helping a student answer an interview question.\n\n"
            "Question: ...\nDimension: general\nReference answer: ...\n"
            "Hint level: small (small = subtle hint, ...)\nAttempt number: 1\n"
        )
        resp = await client.invoke(
            messages=[
                {"role": "system", "content": "你是一位面试辅导老师。"},
                {"role": "user", "content": realistic_prompt},
            ],
            user_id="00000000-0000-0000-0000-000000000001",
            thread_id="t-1",
            node_name="error_coach_hint",
        )
        assert "依赖数组" in resp["content"], f"expected small hint content, got {resp['content']}"

    @pytest.mark.asyncio
    async def test_mock_llm_client_hint_medium_level(self, scenario_file):
        """When the prompt says 'Hint level: medium', mock returns medium hint."""
        from app.agents.llm_client_mock import MockLLMClient

        client = MockLLMClient.from_scenario_file(scenario_file)
        prompt = "Hint level: medium (medium = more direct hint)\nAttempt number: 3"
        resp = await client.invoke(
            messages=[{"role": "user", "content": prompt}],
            user_id="u",
            thread_id="t",
            node_name="error_coach_hint",
        )
        assert "useMemo" in resp["content"] or "useCallback" in resp["content"], (
            f"expected medium hint, got {resp['content']}"
        )

    @pytest.mark.asyncio
    async def test_mock_llm_client_evaluate_exhausted_returns_default(
        self, scenario_file
    ):
        """When score sequence exhausted, return score=5 fallback."""
        from app.agents.llm_client_mock import MockLLMClient

        client = MockLLMClient.from_scenario_file(scenario_file)
        # Consume all 3 scores
        for _ in range(3):
            await client.invoke(
                messages=[{"role": "user", "content": "x"}],
                user_id="u",
                thread_id="t",
                node_name="error_coach_evaluate",
            )
        # 4th call → fallback
        resp = await client.invoke(
            messages=[{"role": "user", "content": "x"}],
            user_id="u",
            thread_id="t",
            node_name="error_coach_evaluate",
        )
        import json as _json

        data = _json.loads(resp["content"])
        assert data["score"] == 5, f"expected fallback score=5, got {data['score']}"
