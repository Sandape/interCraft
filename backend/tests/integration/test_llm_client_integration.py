"""T015: Integration tests for LLMClient with real DeepSeek API.

These tests require a valid DEEPSEEK_API_KEY in the environment.
Skipped if the key is not set or is the placeholder value.
"""
from __future__ import annotations

import os

import pytest

from app.agents.llm_client import LLMClient, get_llm_client


def _has_api_key() -> bool:
    key = os.environ.get("DEEPSEEK_API_KEY", "")
    return bool(key) and key not in ("", "sk-...")


pytestmark = pytest.mark.skipif(
    not _has_api_key(),
    reason="DEEPSEEK_API_KEY not configured",
)


@pytest.mark.integration
class TestLLMClientIntegration:
    @pytest.fixture
    async def client(self):
        return get_llm_client()

    @pytest.mark.asyncio
    async def test_invoke_intake_with_deepseek(self, client: LLMClient):
        result = await client.invoke(
            messages=[
                {"role": "system", "content": "Extract structured data from user input."},
                {"role": "user", "content": "I want to interview for Senior Frontend Engineer at ByteDance."},
            ],
            estimated_tokens=700,
            user_id="00000000-0000-0000-0000-000000000001",
            thread_id="test-thread-intake",
            node_name="intake",
        )
        assert result["content"]
        assert result["model"] == "deepseek-v4-flash"  # intake uses flash
        assert result["prompt_tokens"] > 0
        assert result["completion_tokens"] > 0
        assert result["duration_ms"] > 0

    @pytest.mark.asyncio
    async def test_invoke_question_gen_with_deepseek(self, client: LLMClient):
        result = await client.invoke(
            messages=[
                {"role": "system", "content": "You are a technical interviewer. Generate one interview question."},
                {"role": "user", "content": "Position: Senior Frontend Engineer. Dimension: tech_depth. Round 1."},
            ],
            estimated_tokens=2500,
            user_id="00000000-0000-0000-0000-000000000001",
            thread_id="test-thread-qgen",
            node_name="question_gen",
        )
        assert result["content"]
        assert len(result["content"]) > 10

    @pytest.mark.asyncio
    async def test_invoke_score_with_deepseek(self, client: LLMClient):
        result = await client.invoke(
            messages=[
                {"role": "system", "content": "Score the candidate's answer 0-10 and provide brief feedback."},
                {"role": "user", "content": "Question: What is React Fiber? Answer: It's a reconciliation algorithm..."},
            ],
            estimated_tokens=1800,
            user_id="00000000-0000-0000-0000-000000000001",
            thread_id="test-thread-score",
            node_name="score",
        )
        assert result["content"]

    @pytest.mark.asyncio
    async def test_invoke_report_with_deepseek(self, client: LLMClient):
        result = await client.invoke(
            messages=[
                {"role": "system", "content": "Generate an interview summary report with overall_score, per_question_score, strengths, improvements."},
                {"role": "user", "content": "Here are 5 rounds of interview data: Q1: React Fiber (score 7), Q2: Architecture (score 6), Q3: Engineering Practice (score 8), Q4: Communication (score 7), Q5: Algorithms (score 7)."},
            ],
            estimated_tokens=5500,
            user_id="00000000-0000-0000-0000-000000000001",
            thread_id="test-thread-report",
            node_name="report",
        )
        assert result["content"]
