from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.agents.llm_client import LLMClient
from app.modules.telemetry_contracts.schemas import AIInvocationSummary


class _FakeUsage:
    prompt_tokens = 321
    completion_tokens = 123


def _content_chunk(text: str) -> SimpleNamespace:
    return SimpleNamespace(
        choices=[SimpleNamespace(delta=SimpleNamespace(content=text))],
        usage=None,
    )


def _usage_chunk() -> SimpleNamespace:
    return SimpleNamespace(choices=[], usage=_FakeUsage())


async def _fake_stream():
    yield _content_chunk("he")
    yield _content_chunk("llo")
    yield _usage_chunk()


@pytest.mark.asyncio
async def test_invoke_stream_records_req035_ai_invocation_summary() -> None:
    with patch("app.agents.llm_client.openai.AsyncOpenAI") as mock_openai:
        mock_openai.return_value.chat.completions.create = AsyncMock(return_value=_fake_stream())
        client = LLMClient()

    captured: list[AIInvocationSummary] = []
    with (
        patch.object(client, "_pre_deduct", AsyncMock()),
        patch.object(client, "_actual_adjust", AsyncMock()),
        patch.object(client, "_write_ai_message", AsyncMock()),
        patch(
            "app.agents.llm_client._extract_and_record_ai_invocation",
            new=lambda summary: captured.append(summary),
        ),
    ):
        chunks = [
            chunk
            async for chunk in client.invoke_stream(
                messages=[{"role": "user", "content": "hi"}],
                estimated_tokens=500,
                user_id="user-1",
                thread_id="thread-1",
                node_name="intake",
            )
        ]

    assert chunks == ["he", "llo"]
    assert len(captured) == 1
    summary = captured[0]
    assert summary.prompt_tokens == 321
    assert summary.completion_tokens == 123
    assert summary.status == "SUCCESS"
    assert summary.retry_count == 0
    assert summary.latency_ms >= 0
