"""T009: Unit tests for LLMClient (OpenAI SDK mocked).

Tests per contracts/llm-client.md.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agents.llm_client import (
    LLMClient,
    LLMInvokeError,
    LLMResponse,
    QuotaExceededError,
    get_llm_client,
)


def _make_usage(prompt_tokens=2000, completion_tokens=500):
    usage = MagicMock()
    usage.prompt_tokens = prompt_tokens
    usage.completion_tokens = completion_tokens
    return usage


def _make_completion(content="test response", prompt_tokens=2000, completion_tokens=500):
    choice = MagicMock()
    choice.message.content = content
    response = MagicMock()
    response.choices = [choice]
    response.usage = _make_usage(prompt_tokens, completion_tokens)
    response.model = "deepseek-v4-pro"
    return response


class TestLLMClientInvoke:
    """Tests for LLMClient.invoke with mocked internal helpers."""

    @pytest.fixture
    def client(self):
        with patch("app.agents.llm_client.openai.AsyncOpenAI") as mock_oa:
            mock_oa.return_value.chat.completions.create = AsyncMock()
            yield LLMClient()

    @pytest.mark.asyncio
    async def test_invoke_success_returns_LLMResponse(self, client: LLMClient):
        client._client.chat.completions.create.return_value = _make_completion("hello")

        with patch.object(client, "_pre_deduct", AsyncMock()), \
             patch.object(client, "_actual_adjust", AsyncMock()), \
             patch.object(client, "_write_ai_message", AsyncMock()):
            result = await client.invoke(
                messages=[{"role": "user", "content": "hi"}],
                estimated_tokens=700,
                user_id="user-1",
                thread_id="thread-1",
                node_name="intake",
            )

        assert isinstance(result, dict)
        assert result["content"] == "hello"
        assert result["model"] == "deepseek-v4-flash"  # intake uses flash
        assert result["prompt_tokens"] == 2000
        assert result["completion_tokens"] == 500
        assert result["duration_ms"] >= 0

    @pytest.mark.asyncio
    async def test_invoke_pre_deducts_quota_atomically(self, client: LLMClient):
        client._client.chat.completions.create.return_value = _make_completion()

        pre_deduct = AsyncMock()
        with patch.object(client, "_pre_deduct", pre_deduct), \
             patch.object(client, "_actual_adjust", AsyncMock()), \
             patch.object(client, "_write_ai_message", AsyncMock()):
            await client.invoke(
                messages=[{"role": "user", "content": "hi"}],
                estimated_tokens=2500,
                user_id="user-1",
                thread_id="thread-1",
                node_name="question_gen",
            )

        pre_deduct.assert_called_once_with("user-1", 2500)

    @pytest.mark.asyncio
    async def test_invoke_adjusts_quota_on_actual_usage(self, client: LLMClient):
        client._client.chat.completions.create.return_value = _make_completion(
            prompt_tokens=2000, completion_tokens=500
        )

        actual_adjust = AsyncMock()
        with patch.object(client, "_pre_deduct", AsyncMock()), \
             patch.object(client, "_actual_adjust", actual_adjust), \
             patch.object(client, "_write_ai_message", AsyncMock()):
            await client.invoke(
                messages=[{"role": "user", "content": "hi"}],
                estimated_tokens=2500,
                user_id="user-1",
                thread_id="thread-1",
                node_name="question_gen",
            )

        # actual=2500, estimated=2500 → delta=0 → _actual_adjust still called
        actual_adjust.assert_called_once_with("user-1", 2500, 2500)

    @pytest.mark.asyncio
    async def test_invoke_raises_QuotaExceededError_when_quota_depleted(self, client: LLMClient):
        pre_deduct = AsyncMock(side_effect=QuotaExceededError(499900, 500000, 2500))

        with patch.object(client, "_pre_deduct", pre_deduct), \
             patch.object(client, "_actual_adjust", AsyncMock()), \
             patch.object(client, "_write_ai_message", AsyncMock()):
            with pytest.raises(QuotaExceededError):
                await client.invoke(
                    messages=[{"role": "user", "content": "hi"}],
                    estimated_tokens=2500,
                    user_id="user-1",
                    thread_id="thread-1",
                    node_name="question_gen",
                )

    @pytest.mark.asyncio
    async def test_invoke_retries_on_rate_limited(self, client: LLMClient):
        from openai import RateLimitError

        client._client.chat.completions.create.side_effect = [
            RateLimitError("rate limited", response=MagicMock(), body=None),
            _make_completion("retry success"),
        ]

        with patch.object(client, "_pre_deduct", AsyncMock()), \
             patch.object(client, "_actual_adjust", AsyncMock()), \
             patch.object(client, "_write_ai_message", AsyncMock()):
            result = await client.invoke(
                messages=[{"role": "user", "content": "hi"}],
                estimated_tokens=700,
                user_id="user-1",
                thread_id="thread-1",
                node_name="intake",
            )

        assert result["content"] == "retry success"
        assert client._client.chat.completions.create.call_count == 2

    @pytest.mark.asyncio
    async def test_invoke_retries_on_overloaded_then_exhausts(self, client: LLMClient):
        from openai import InternalServerError

        client._client.chat.completions.create.side_effect = InternalServerError(
            "overloaded", response=MagicMock(), body=None
        )

        with patch.object(client, "_pre_deduct", AsyncMock()), \
             patch.object(client, "_actual_adjust", AsyncMock()), \
             patch.object(client, "_write_ai_message", AsyncMock()):
            with pytest.raises(LLMInvokeError):
                await client.invoke(
                    messages=[{"role": "user", "content": "hi"}],
                    estimated_tokens=700,
                    user_id="user-1",
                    thread_id="thread-1",
                    node_name="intake",
                )

        # 1 initial + 3 retries = 4
        assert client._client.chat.completions.create.call_count == 4

    @pytest.mark.asyncio
    async def test_invoke_does_not_retry_on_auth_error(self, client: LLMClient):
        from openai import AuthenticationError

        client._client.chat.completions.create.side_effect = AuthenticationError(
            "invalid key", response=MagicMock(), body=None
        )

        with patch.object(client, "_pre_deduct", AsyncMock()), \
             patch.object(client, "_actual_adjust", AsyncMock()), \
             patch.object(client, "_write_ai_message", AsyncMock()):
            with pytest.raises(LLMInvokeError):
                await client.invoke(
                    messages=[{"role": "user", "content": "hi"}],
                    estimated_tokens=700,
                    user_id="user-1",
                    thread_id="thread-1",
                    node_name="intake",
                )

        # Should NOT retry on 401
        assert client._client.chat.completions.create.call_count == 1

    @pytest.mark.asyncio
    async def test_invoke_logs_structured_on_success(self, client: LLMClient):
        client._client.chat.completions.create.return_value = _make_completion()

        with patch.object(client, "_pre_deduct", AsyncMock()), \
             patch.object(client, "_actual_adjust", AsyncMock()), \
             patch.object(client, "_write_ai_message", AsyncMock()), \
             patch("app.agents.llm_client.logger") as mock_logger:
            await client.invoke(
                messages=[{"role": "user", "content": "hi"}],
                estimated_tokens=700,
                user_id="user-1",
                thread_id="thread-1",
                node_name="intake",
            )

            mock_logger.info.assert_called()

    @pytest.mark.asyncio
    async def test_invoke_logs_structured_on_failure(self, client: LLMClient):
        from openai import APITimeoutError

        client._client.chat.completions.create.side_effect = APITimeoutError("timeout")

        with patch.object(client, "_pre_deduct", AsyncMock()), \
             patch.object(client, "_actual_adjust", AsyncMock()), \
             patch.object(client, "_write_ai_message", AsyncMock()), \
             patch("app.agents.llm_client.logger") as mock_logger:
            try:
                await client.invoke(
                    messages=[{"role": "user", "content": "hi"}],
                    estimated_tokens=700,
                    user_id="user-1",
                    thread_id="thread-1",
                    node_name="intake",
                )
            except LLMInvokeError:
                pass

            mock_logger.error.assert_called()

    @pytest.mark.asyncio
    async def test_invoke_writes_ai_message_on_each_call(self, client: LLMClient):
        client._client.chat.completions.create.return_value = _make_completion()

        write_mock = AsyncMock()
        with patch.object(client, "_pre_deduct", AsyncMock()), \
             patch.object(client, "_actual_adjust", AsyncMock()), \
             patch.object(client, "_write_ai_message", write_mock):
            await client.invoke(
                messages=[{"role": "user", "content": "hi"}],
                estimated_tokens=700,
                user_id="user-1",
                thread_id="thread-1",
                node_name="intake",
            )

        write_mock.assert_called_once()


class TestLLMClientSingleton:
    def test_get_llm_client_returns_same_instance(self):
        # Reset singleton for test isolation
        import app.agents.llm_client as mod
        old = mod._llm_client_singleton
        mod._llm_client_singleton = None
        try:
            with patch("app.agents.llm_client.openai.AsyncOpenAI"):
                a = get_llm_client()
                b = get_llm_client()
                assert a is b
        finally:
            mod._llm_client_singleton = old
