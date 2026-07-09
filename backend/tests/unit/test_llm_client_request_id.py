"""022 US1 — Unit tests: LLM client reads request_id from ContextVar.

Tests per contracts/request-id.md FR-002: every llm.invoke / llm.retry /
llm.mock_invoke log event carries request_id field.
"""
from __future__ import annotations

from contextvars import ContextVar
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agents.llm_client import LLMClient, LLMInvokeError


def _make_usage(prompt_tokens=100, completion_tokens=50):
    usage = MagicMock()
    usage.prompt_tokens = prompt_tokens
    usage.completion_tokens = completion_tokens
    return usage


def _make_completion(content="ok", prompt_tokens=100, completion_tokens=50):
    choice = MagicMock()
    choice.message.content = content
    response = MagicMock()
    response.choices = [choice]
    response.usage = _make_usage(prompt_tokens, completion_tokens)
    response.model = "deepseek-v4-pro"
    return response


@pytest.fixture
def client():
    with patch("app.agents.llm_client.openai.AsyncOpenAI") as mock_oa:
        mock_oa.return_value.chat.completions.create = AsyncMock()
        yield LLMClient()


@pytest.mark.asyncio
async def test_invoke_logs_contain_request_id(client: LLMClient):
    """Log entries from invoke carry request_id when ContextVar is set."""
    client._client.chat.completions.create.return_value = _make_completion()

    with patch.object(client, "_pre_deduct", AsyncMock()), \
         patch.object(client, "_actual_adjust", AsyncMock()), \
         patch.object(client, "_write_ai_message", AsyncMock()), \
         patch("app.agents.llm_client._request_id_var") as mock_var:
        # Simulate ContextVar with value set
        mock_var.get.return_value = "req-abc123"
        with patch("app.agents.llm_client.logger") as mock_logger:
            await client.invoke(
                messages=[{"role": "user", "content": "hi"}],
                estimated_tokens=100,
                user_id="user-1",
                thread_id="thread-1",
                node_name="intake",
            )

            # Verify logger.info called with request_id
            mock_logger.info.assert_called()
            _call_kwargs = mock_logger.info.call_args.kwargs
            assert _call_kwargs.get("request_id") == "req-abc123", (
                f"expected request_id=req-abc123, got {_call_kwargs.get('request_id')}"
            )


@pytest.mark.asyncio
async def test_invoke_logs_request_id_on_retry(client: LLMClient):
    """Retry log events also carry request_id."""
    from openai import RateLimitError

    client._client.chat.completions.create.side_effect = [
        RateLimitError("too fast", response=MagicMock(), body=None),
        _make_completion(),
    ]

    with patch.object(client, "_pre_deduct", AsyncMock()), \
         patch.object(client, "_actual_adjust", AsyncMock()), \
         patch.object(client, "_write_ai_message", AsyncMock()), \
         patch("app.agents.llm_client._request_id_var") as mock_var:
        mock_var.get.return_value = "req-retry-test"
        with patch("app.agents.llm_client.logger") as mock_logger:
            await client.invoke(
                messages=[{"role": "user", "content": "hi"}],
                estimated_tokens=100,
                user_id="user-1",
                thread_id="thread-1",
                node_name="intake",
            )

            # logger.warning is called for retries
            warning_calls = [c for c in mock_logger.warning.call_args_list]
            if warning_calls:
                for c in warning_calls:
                    assert c.kwargs.get("request_id") == "req-retry-test", (
                        f"retry log missing request_id: {c.kwargs}"
                    )


@pytest.mark.asyncio
async def test_invoke_logs_request_id_on_failure(client: LLMClient):
    """Error log events on exhausted retries carry request_id."""
    from openai import InternalServerError

    client._client.chat.completions.create.side_effect = InternalServerError(
        "overloaded", response=MagicMock(), body=None
    )

    with patch.object(client, "_pre_deduct", AsyncMock()), \
         patch.object(client, "_actual_adjust", AsyncMock()), \
         patch.object(client, "_write_ai_message", AsyncMock()), \
         patch("app.agents.llm_client._request_id_var") as mock_var:
        mock_var.get.return_value = "req-fail"
        with patch("app.agents.llm_client.logger") as mock_logger:
            try:
                await client.invoke(
                    messages=[{"role": "user", "content": "hi"}],
                    estimated_tokens=100,
                    user_id="user-1",
                    thread_id="thread-1",
                    node_name="intake",
                )
            except LLMInvokeError:
                pass

            mock_logger.error.assert_called()
            error_kwargs = mock_logger.error.call_args.kwargs
            assert error_kwargs.get("request_id") == "req-fail", (
                f"error log missing request_id: {error_kwargs}"
            )


@pytest.mark.asyncio
async def test_invoke_fallback_request_id_when_contextvar_empty(client: LLMClient):
    """When ContextVar is empty, request_id falls back to a UUID string."""
    client._client.chat.completions.create.return_value = _make_completion()

    with patch.object(client, "_pre_deduct", AsyncMock()), \
         patch.object(client, "_actual_adjust", AsyncMock()), \
         patch.object(client, "_write_ai_message", AsyncMock()), \
         patch("app.agents.llm_client._request_id_var") as mock_var:
        mock_var.get.return_value = None  # Not set
        with patch("app.agents.llm_client.logger") as mock_logger:
            await client.invoke(
                messages=[{"role": "user", "content": "hi"}],
                estimated_tokens=100,
                user_id="user-1",
                thread_id="thread-1",
                node_name="intake",
            )

            mock_logger.info.assert_called()
            rid = mock_logger.info.call_args.kwargs.get("request_id", "")
            # Should be a fallback UUID (not the test value)
            assert rid and len(rid) > 10
