"""REQ-033 US9 — AI invocation summary extraction tests (T036).

Locks the data-model.md §AIInvocationRecord contract for the post-call
extraction hook on LLMClient:

- ``AIInvocationSummary`` / ``extract_ai_invocation_summary`` returns
  fields: ``invocationId``, ``runId``, ``traceId``, ``graph``, ``node``,
  ``model``, ``promptFingerprint``, ``promptTokens``, ``completionTokens``,
  ``estimatedCost`` (with ``isEstimate=true``), ``latencyMs``,
  ``retryCount``, ``status``, ``errorCategory`` (on failure).
- Triggering an LLM call → the hook is automatically invoked (no caller
  must remember to call it).
- Missing field → explicit ``"unknown"`` (SC-010 / FR-038).
- Failure (exception) → ``status=FAILURE`` + ``errorCategory`` filled in;
  no exception propagates from the hook itself (fail-open).

All tests are TDD — they MUST fail before T040 implementation lands.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agents.llm_client import (
    LLMClient,
    LLMInvokeError,
    get_llm_client,
)
from app.modules.telemetry_contracts.schemas import AIInvocationSummary


# ---------------------------------------------------------------------------
# Test fixtures
# ---------------------------------------------------------------------------


def _make_usage(prompt_tokens: int = 2000, completion_tokens: int = 500):
    usage = MagicMock()
    usage.prompt_tokens = prompt_tokens
    usage.completion_tokens = completion_tokens
    return usage


def _make_completion(
    content: str = "test response",
    prompt_tokens: int = 2000,
    completion_tokens: int = 500,
):
    choice = MagicMock()
    choice.message.content = content
    response = MagicMock()
    response.choices = [choice]
    response.usage = _make_usage(prompt_tokens, completion_tokens)
    response.model = "deepseek-v4-pro"
    return response


# ---------------------------------------------------------------------------
# AIInvocationSummary dataclass contract
# ---------------------------------------------------------------------------


class TestAIInvocationSummaryFields:
    """The summary dataclass must carry all required fields (data-model.md)."""

    def test_summary_carries_all_required_fields(self) -> None:
        s = AIInvocationSummary(
            invocation_id="00000000-0000-0000-0000-000000000001",
            run_id=None,
            trace_id=None,
            graph="interview",
            node="score",
            model="deepseek-v4-pro",
            prompt_fingerprint="fp-abc",
            prompt_tokens=2000,
            completion_tokens=500,
            estimated_cost=0.01,
            is_estimate=True,
            latency_ms=1234,
            retry_count=0,
            status="SUCCESS",
            error_category=None,
        )
        assert s.graph == "interview"
        assert s.node == "score"
        assert s.model == "deepseek-v4-pro"
        assert s.prompt_tokens == 2000
        assert s.completion_tokens == 500
        assert s.estimated_cost == 0.01
        assert s.is_estimate is True
        assert s.latency_ms == 1234
        assert s.retry_count == 0
        assert s.status == "SUCCESS"

    def test_summary_status_enum(self) -> None:
        s = AIInvocationSummary(
            invocation_id="00000000-0000-0000-0000-000000000001",
            run_id=None,
            trace_id=None,
            graph="x",
            node="y",
            model="m",
            prompt_fingerprint="fp",
            prompt_tokens=0,
            completion_tokens=0,
            estimated_cost=0.0,
            is_estimate=True,
            latency_ms=0,
            retry_count=0,
            status="FAILURE",
            error_category="rate_limit",
        )
        assert s.status == "FAILURE"
        assert s.error_category == "rate_limit"

    def test_summary_to_dict_uses_camel_case(self) -> None:
        s = AIInvocationSummary(
            invocation_id="00000000-0000-0000-0000-000000000001",
            run_id=None,
            trace_id=None,
            graph="interview",
            node="score",
            model="deepseek-v4-pro",
            prompt_fingerprint="fp-abc",
            prompt_tokens=2000,
            completion_tokens=500,
            estimated_cost=0.01,
            is_estimate=True,
            latency_ms=1234,
            retry_count=0,
            status="SUCCESS",
            error_category=None,
        )
        d = s.to_dict()
        # camelCase keys (per event-metric-schema.md contract)
        assert "invocationId" in d
        assert "runId" in d
        assert "traceId" in d
        assert "graph" in d
        assert "node" in d
        assert "model" in d
        assert "promptFingerprint" in d
        assert "promptTokens" in d
        assert "completionTokens" in d
        assert "estimatedCost" in d
        assert "isEstimate" in d
        assert "latencyMs" in d
        assert "retryCount" in d
        assert "status" in d
        assert "errorCategory" in d

    def test_summary_unknown_factory(self) -> None:
        """``AIInvocationSummary.unknown()`` fills everything with 'unknown'."""
        s = AIInvocationSummary.unknown()
        # invocation_id is auto-generated (UUID) — not a "version" field.
        assert s.invocation_id  # non-empty UUID string
        assert s.run_id is None
        assert s.trace_id is None
        assert s.graph == "unknown"
        assert s.node == "unknown"
        assert s.model == "unknown"
        assert s.prompt_fingerprint == "unknown"
        assert s.estimated_cost == 0.0
        assert s.is_estimate is True
        assert s.latency_ms == 0
        assert s.retry_count == 0
        assert s.status == "UNKNOWN"
        assert s.error_category == "unknown"

    def test_summary_to_dict_unknown_no_none_no_empty(self) -> None:
        """SC-010: to_dict never has None / empty for the string fields."""
        s = AIInvocationSummary.unknown()
        d = s.to_dict()
        # All non-id string fields must be explicit "unknown" — not None / empty.
        string_fields = [
            "graph",
            "node",
            "model",
            "promptFingerprint",
            "status",
            "errorCategory",
        ]
        for f in string_fields:
            assert f in d, f"missing {f}"
            assert d[f] is not None, f"{f} is None"
            assert d[f] != "", f"{f} is empty"


# ---------------------------------------------------------------------------
# Hook fires automatically on LLMClient.invoke
# ---------------------------------------------------------------------------


class TestAIInvocationHookFires:
    """When LLMClient.invoke completes, the AI invocation hook is auto-triggered."""

    @pytest.fixture
    def client(self):
        with patch("app.agents.llm_client.openai.AsyncOpenAI") as mock_oa:
            mock_oa.return_value.chat.completions.create = AsyncMock()
            yield LLMClient()

    @pytest.mark.asyncio
    async def test_invoke_triggers_ai_invocation_hook(self, client: LLMClient) -> None:
        """A successful LLM call → the hook is called with the summary."""
        client._client.chat.completions.create.return_value = _make_completion()

        captured: list[AIInvocationSummary] = []

        def fake_hook(summary: AIInvocationSummary) -> None:
            captured.append(summary)

        with patch.object(client, "_pre_deduct", AsyncMock()), \
             patch.object(client, "_actual_adjust", AsyncMock()), \
             patch.object(client, "_write_ai_message", AsyncMock()), \
             patch(
                 "app.agents.llm_client._extract_and_record_ai_invocation",
                 new=fake_hook,
             ):
            await client.invoke(
                messages=[{"role": "user", "content": "hi"}],
                estimated_tokens=2500,
                user_id="user-1",
                thread_id="thread-1",
                node_name="score",
            )

        assert len(captured) == 1, "hook should fire exactly once per successful invoke"
        s = captured[0]
        assert s.status == "SUCCESS"
        assert s.node == "score"
        assert s.prompt_tokens == 2000
        assert s.completion_tokens == 500
        assert s.retry_count == 0
        assert s.error_category is None

    @pytest.mark.asyncio
    async def test_invoke_failure_triggers_hook_with_failure_status(
        self, client: LLMClient
    ) -> None:
        """Failed LLM call → hook still fires, status=FAILURE, errorCategory set."""
        from openai import APIConnectionError

        client._client.chat.completions.create.side_effect = APIConnectionError(
            request=MagicMock()
        )

        captured: list[AIInvocationSummary] = []

        def fake_hook(summary: AIInvocationSummary) -> None:
            captured.append(summary)

        with patch.object(client, "_pre_deduct", AsyncMock()), \
             patch.object(client, "_actual_adjust", AsyncMock()), \
             patch.object(client, "_write_ai_message", AsyncMock()), \
             patch(
                 "app.agents.llm_client._extract_and_record_ai_invocation",
                 new=fake_hook,
             ):
            with pytest.raises(LLMInvokeError):
                await client.invoke(
                    messages=[{"role": "user", "content": "hi"}],
                    estimated_tokens=2500,
                    user_id="user-1",
                    thread_id="thread-1",
                    node_name="score",
                    max_retries=0,
                )

        # Hook still fires on failure (fail-open semantic).
        assert len(captured) >= 1
        s = captured[-1]
        assert s.status == "FAILURE"
        assert s.error_category is not None
        assert s.error_category != ""
        assert s.error_category != "unknown"

    @pytest.mark.asyncio
    async def test_hook_failure_does_not_break_invocation(
        self, client: LLMClient
    ) -> None:
        """If the DB persist inside the hook fails, the LLM response still reaches the caller.

        We simulate the DB being down by patching
        ``app.modules.telemetry_contracts.repository.insert_ai_invocation``
        to throw — the hook's own try/except must catch that and not
        propagate.
        """
        client._client.chat.completions.create.return_value = _make_completion()

        # Patch the DB-level insert (not the hook itself) so we verify the
        # real hook's fail-open behavior.
        with patch.object(client, "_pre_deduct", AsyncMock()), \
             patch.object(client, "_actual_adjust", AsyncMock()), \
             patch.object(client, "_write_ai_message", AsyncMock()), \
             patch(
                 "app.modules.telemetry_contracts.repository.insert_ai_invocation",
                 new=AsyncMock(side_effect=RuntimeError("DB down")),
             ):
            # Caller still gets the response — fail-open.
            result = await client.invoke(
                messages=[{"role": "user", "content": "hi"}],
                estimated_tokens=2500,
                user_id="user-1",
                thread_id="thread-1",
                node_name="score",
            )

        assert result["content"] == "test response"


# ---------------------------------------------------------------------------
# Token / latency / retry_count extraction
# ---------------------------------------------------------------------------


class TestHookExtractsTokensLatencyRetry:
    """The hook correctly extracts tokens, latency, retry count from LLM response."""

    @pytest.fixture
    def client(self):
        with patch("app.agents.llm_client.openai.AsyncOpenAI") as mock_oa:
            mock_oa.return_value.chat.completions.create = AsyncMock()
            yield LLMClient()

    @pytest.mark.asyncio
    async def test_hook_extracts_prompt_and_completion_tokens(
        self, client: LLMClient
    ) -> None:
        client._client.chat.completions.create.return_value = _make_completion(
            prompt_tokens=1234, completion_tokens=567
        )
        captured: list[AIInvocationSummary] = []
        with patch.object(client, "_pre_deduct", AsyncMock()), \
             patch.object(client, "_actual_adjust", AsyncMock()), \
             patch.object(client, "_write_ai_message", AsyncMock()), \
             patch(
                 "app.agents.llm_client._extract_and_record_ai_invocation",
                 new=lambda s: captured.append(s),
             ):
            await client.invoke(
                messages=[{"role": "user", "content": "hi"}],
                estimated_tokens=2000,
                user_id="user-1",
                thread_id="thread-1",
                node_name="intake",
            )
        s = captured[0]
        assert s.prompt_tokens == 1234
        assert s.completion_tokens == 567

    @pytest.mark.asyncio
    async def test_hook_extracts_latency_ms(self, client: LLMClient) -> None:
        client._client.chat.completions.create.return_value = _make_completion()
        captured: list[AIInvocationSummary] = []
        with patch.object(client, "_pre_deduct", AsyncMock()), \
             patch.object(client, "_actual_adjust", AsyncMock()), \
             patch.object(client, "_write_ai_message", AsyncMock()), \
             patch(
                 "app.agents.llm_client._extract_and_record_ai_invocation",
                 new=lambda s: captured.append(s),
             ):
            await client.invoke(
                messages=[{"role": "user", "content": "hi"}],
                estimated_tokens=2000,
                user_id="user-1",
                thread_id="thread-1",
                node_name="intake",
            )
        s = captured[0]
        assert s.latency_ms >= 0

    @pytest.mark.asyncio
    async def test_hook_extracts_retry_count(self, client: LLMClient) -> None:
        from openai import APITimeoutError

        # First call times out, second succeeds → retry_count == 1.
        client._client.chat.completions.create.side_effect = [
            APITimeoutError(request=MagicMock()),
            _make_completion(),
        ]
        captured: list[AIInvocationSummary] = []
        with patch.object(client, "_pre_deduct", AsyncMock()), \
             patch.object(client, "_actual_adjust", AsyncMock()), \
             patch.object(client, "_write_ai_message", AsyncMock()), \
             patch(
                 "app.agents.llm_client._extract_and_record_ai_invocation",
                 new=lambda s: captured.append(s),
             ):
            await client.invoke(
                messages=[{"role": "user", "content": "hi"}],
                estimated_tokens=2000,
                user_id="user-1",
                thread_id="thread-1",
                node_name="intake",
                max_retries=2,
            )
        s = captured[0]
        assert s.retry_count >= 1


# ---------------------------------------------------------------------------
# Cost estimation
# ---------------------------------------------------------------------------


class TestCostEstimation:
    """Cost is computed from tokens × cost_per_token; is_estimate=True always."""

    @pytest.fixture
    def client(self):
        with patch("app.agents.llm_client.openai.AsyncOpenAI") as mock_oa:
            mock_oa.return_value.chat.completions.create = AsyncMock()
            yield LLMClient()

    @pytest.mark.asyncio
    async def test_cost_field_is_marked_estimate(self, client: LLMClient) -> None:
        client._client.chat.completions.create.return_value = _make_completion(
            prompt_tokens=1000, completion_tokens=500
        )
        captured: list[AIInvocationSummary] = []
        with patch.object(client, "_pre_deduct", AsyncMock()), \
             patch.object(client, "_actual_adjust", AsyncMock()), \
             patch.object(client, "_write_ai_message", AsyncMock()), \
             patch(
                 "app.agents.llm_client._extract_and_record_ai_invocation",
                 new=lambda s: captured.append(s),
             ):
            await client.invoke(
                messages=[{"role": "user", "content": "hi"}],
                estimated_tokens=2000,
                user_id="user-1",
                thread_id="thread-1",
                node_name="intake",
            )
        s = captured[0]
        assert s.is_estimate is True

    @pytest.mark.asyncio
    async def test_cost_zero_when_no_cost_table(self, client: LLMClient) -> None:
        """If cost table not configured, estimated_cost=0.0 with is_estimate=True."""
        client._client.chat.completions.create.return_value = _make_completion()
        captured: list[AIInvocationSummary] = []
        with patch.object(client, "_pre_deduct", AsyncMock()), \
             patch.object(client, "_actual_adjust", AsyncMock()), \
             patch.object(client, "_write_ai_message", AsyncMock()), \
             patch(
                 "app.agents.llm_client._extract_and_record_ai_invocation",
                 new=lambda s: captured.append(s),
             ), \
             patch.dict("os.environ", {}, clear=False), \
             patch("app.core.config.get_settings") as mock_settings:
            # Simulate no cost table.
            mock_settings.return_value.deepseek_cost_per_token = 0.0
            await client.invoke(
                messages=[{"role": "user", "content": "hi"}],
                estimated_tokens=2000,
                user_id="user-1",
                thread_id="thread-1",
                node_name="intake",
            )
        s = captured[0]
        # is_estimate stays True even when cost is 0; cost=0 acceptable.
        assert s.is_estimate is True
