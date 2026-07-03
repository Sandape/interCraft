"""REQ-041 US1 FR-001 — is_token_limit_exceeded 4 provider tests.

Per AC matrix REQ-041-US1.md FR-001:
- AC-1.1 function exists in backend/app/agents/utils/token_limit.py
- AC-1.2 OpenAI provider (openai.BadRequestError "prompt is too long" → True, RateLimitError → False)
- AC-1.3 Anthropic provider (anthropic.BadRequestError "prompt is too long: N tokens > M limit" → True)
- AC-1.4 Gemini provider (google.api_core.exceptions.ResourceExhausted → True)
- AC-1.5 DeepSeek provider — 3 exception forms (openai.BadRequestError + deepseek.DeepSeekAPIError + str match)
- AC-1.5a DeepSeek real API integration test (skipif no API key / quota)
- AC-1.6 unsupported provider returns False (fail-safe)
- AC-1.7 MODEL_TOKEN_LIMITS table covers ≥ 4 providers, ≥ 13 models, DeepSeek ≥ 4
- AC-1.8 (skipped here — belongs to llm_client integration in MB2/MB3)
"""
from __future__ import annotations

import os
from unittest.mock import MagicMock

import openai
import pytest

# Lazy import inside test functions (per test_node_separation.py pattern) so
# pytest collection surfaces a clear `ModuleNotFoundError: ... token_limit`
# red-phase error rather than failing at import time on the `app` package
# discovery (which is brittle under uv's python -m pytest layout).


def _load_under_test():
    """Lazy import — Test-First red-phase requires ModuleNotFoundError when impl missing."""
    from app.agents.utils.token_limit import (  # noqa: WPS433 — intentional lazy import for red-phase
        MODEL_TOKEN_LIMITS,
        is_token_limit_exceeded,
    )

    return MODEL_TOKEN_LIMITS, is_token_limit_exceeded


# ---------------------------------------------------------------------------
# AC-1.2 OpenAI provider
# ---------------------------------------------------------------------------
class TestOpenAIProvider:
    def test_bad_request_prompt_too_long_returns_true(self) -> None:
        """AC-1.2: openai.BadRequestError('prompt is too long') + openai:gpt-4o → True."""
        _, is_token_limit_exceeded = _load_under_test()
        exc = _make_openai_bad_request("prompt is too long")
        assert is_token_limit_exceeded(exc, "openai:gpt-4o") is True

    def test_bad_request_context_length_exceeded_returns_true(self) -> None:
        """AC-1.5 (str-match variant): openai.BadRequestError with 'context_length_exceeded' → True."""
        _, is_token_limit_exceeded = _load_under_test()
        exc = _make_openai_bad_request("context_length_exceeded: max 8192 tokens")
        assert is_token_limit_exceeded(exc, "openai:gpt-4-turbo") is True

    def test_rate_limit_error_returns_false(self) -> None:
        """AC-1.2 negative: openai.RateLimitError → False (not token limit)."""
        _, is_token_limit_exceeded = _load_under_test()
        exc = _make_openai_rate_limit()
        assert is_token_limit_exceeded(exc, "openai:gpt-4o") is False

    def test_arbitrary_bad_request_returns_false(self) -> None:
        """AC-1.2 boundary: BadRequestError without 'too long' substring → False."""
        _, is_token_limit_exceeded = _load_under_test()
        exc = _make_openai_bad_request("invalid function arguments")
        assert is_token_limit_exceeded(exc, "openai:gpt-3.5-turbo") is False


# ---------------------------------------------------------------------------
# AC-1.3 Anthropic provider (use duck-typed mock — anthropic SDK not installed)
# ---------------------------------------------------------------------------
class TestAnthropicProvider:
    def test_bad_request_prompt_too_long_with_token_counts_returns_true(self) -> None:
        """AC-1.3: anthropic.BadRequestError('prompt is too long: 200000 > 180000') → True."""
        _, is_token_limit_exceeded = _load_under_test()
        exc = _make_anthropic_bad_request("prompt is too long: 200000 tokens > 180000 limit")
        assert is_token_limit_exceeded(exc, "anthropic:claude-sonnet-4-5") is True

    def test_bad_request_plain_too_long_returns_true(self) -> None:
        """AC-1.3 boundary: 'prompt is too long' anywhere in message → True."""
        _, is_token_limit_exceeded = _load_under_test()
        exc = _make_anthropic_bad_request("input: prompt is too long for this model")
        assert is_token_limit_exceeded(exc, "anthropic:claude-3-5-sonnet") is True

    def test_bad_request_other_reason_returns_false(self) -> None:
        """AC-1.3 negative: anthropic.BadRequestError without 'prompt is too long' → False."""
        _, is_token_limit_exceeded = _load_under_test()
        exc = _make_anthropic_bad_request("tools: missing required field 'name'")
        assert is_token_limit_exceeded(exc, "anthropic:claude-3-haiku") is False


# ---------------------------------------------------------------------------
# AC-1.4 Gemini provider
# ---------------------------------------------------------------------------
class TestGeminiProvider:
    def test_resource_exhausted_returns_true(self) -> None:
        """AC-1.4: google.api_core.exceptions.ResourceExhausted('RESOURCE_EXHAUSTED') → True."""
        _, is_token_limit_exceeded = _load_under_test()
        exc = _make_gemini_resource_exhausted("RESOURCE_EXHAUSTED: token quota exceeded")
        assert is_token_limit_exceeded(exc, "gemini:gemini-2.5-pro") is True

    def test_invalid_argument_token_limit_returns_true(self) -> None:
        """AC-1.4 boundary: any Gemini exception with 'token' in message → True."""
        _, is_token_limit_exceeded = _load_under_test()
        exc = _make_gemini_resource_exhausted("INVALID_ARGUMENT: token count exceeds limit")
        assert is_token_limit_exceeded(exc, "gemini:gemini-2.0-flash") is True


# ---------------------------------------------------------------------------
# AC-1.5 DeepSeek provider — 3 exception forms
# ---------------------------------------------------------------------------
class TestDeepSeekProvider:
    def test_openai_bad_request_prompt_too_long_returns_true(self) -> None:
        """AC-1.5 form (a): openai.BadRequestError + deepseek-chat → True (OpenAI-like)."""
        _, is_token_limit_exceeded = _load_under_test()
        exc = _make_openai_bad_request("prompt is too long")
        assert is_token_limit_exceeded(exc, "deepseek:deepseek-chat") is True

    def test_deepseek_sdk_api_error_returns_true(self) -> None:
        """AC-1.5 form (b): deepseek.DeepSeekAPIError + deepseek-v4-pro → True (string match)."""
        _, is_token_limit_exceeded = _load_under_test()
        exc = _make_deepseek_api_error("invalid_request_error")
        assert is_token_limit_exceeded(exc, "deepseek:deepseek-v4-pro") is True

    def test_context_length_exceeded_message_returns_true(self) -> None:
        """AC-1.5 form (c): generic Exception with 'context_length_exceeded' + deepseek-reasoner → True."""
        _, is_token_limit_exceeded = _load_under_test()
        exc = Exception("context_length_exceeded: prompt exceeds 64000 tokens")
        assert is_token_limit_exceeded(exc, "deepseek:deepseek-reasoner") is True

    def test_unrelated_exception_returns_false(self) -> None:
        """AC-1.5 negative: unrelated exception on deepseek: prefix → False."""
        _, is_token_limit_exceeded = _load_under_test()
        exc = _make_openai_bad_request("permission denied")
        assert is_token_limit_exceeded(exc, "deepseek:deepseek-coder") is False


# ---------------------------------------------------------------------------
# AC-1.5a Real DeepSeek API integration (best-effort, skip on quota/network)
# ---------------------------------------------------------------------------
@pytest.mark.skipif(
    not os.environ.get("DEEPSEEK_API_KEY"),
    reason="AC-1.5a: requires DEEPSEEK_API_KEY env var (production key in backend/.env)",
)
class TestDeepSeekRealAPI:
    def test_real_deepseek_v4_pro_bad_request(self) -> None:
        """AC-1.5a: Real DeepSeek V4 Pro call with over-long prompt returns True.

        Constructs an over-limit prompt and sends to live DeepSeek API.
        Skipped if quota / network unavailable — defer to production monitoring.
        """
        import asyncio

        from openai import AsyncOpenAI

        _, is_token_limit_exceeded = _load_under_test()

        async def _invoke() -> Exception:
            client = AsyncOpenAI(
                api_key=os.environ["DEEPSEEK_API_KEY"],
                base_url=os.environ.get(
                    "DEEPSEEK_BASE_URL", "https://api.deepseek.com"
                ),
            )
            try:
                huge_text = "重复这个句子 " * 200_000  # ~200K tokens
                await client.chat.completions.create(
                    model="deepseek-v4-pro",
                    messages=[{"role": "user", "content": huge_text}],
                    timeout=10.0,
                )
                return RuntimeError("DEEPSEEK_DID_NOT_RAISE")
            except Exception as exc:
                return exc

        exc = asyncio.run(_invoke())
        if isinstance(exc, RuntimeError) and str(exc) == "DEEPSEEK_DID_NOT_RAISE":
            pytest.skip("DeepSeek API accepted over-limit prompt — quota or model upgraded")
        assert is_token_limit_exceeded(exc, "deepseek:deepseek-v4-pro") is True


# ---------------------------------------------------------------------------
# AC-1.6 Unsupported provider → False (fail-safe)
# ---------------------------------------------------------------------------
class TestUnsupportedProvider:
    def test_unknown_provider_returns_false(self) -> None:
        """AC-1.6: 'unknown:foo' provider → False (no raise)."""
        _, is_token_limit_exceeded = _load_under_test()
        exc = _make_openai_bad_request("prompt is too long")
        assert is_token_limit_exceeded(exc, "unknown:foo") is False

    def test_empty_model_name_returns_false(self) -> None:
        """AC-1.6 boundary: empty model_name → False (no raise)."""
        _, is_token_limit_exceeded = _load_under_test()
        exc = _make_openai_bad_request("prompt is too long")
        assert is_token_limit_exceeded(exc, "") is False

    def test_no_colon_returns_false(self) -> None:
        """AC-1.6 boundary: 'just-a-name' (no colon) → False."""
        _, is_token_limit_exceeded = _load_under_test()
        exc = _make_openai_bad_request("prompt is too long")
        assert is_token_limit_exceeded(exc, "just-a-name") is False


# ---------------------------------------------------------------------------
# AC-1.7 MODEL_TOKEN_LIMITS completeness
# ---------------------------------------------------------------------------
class TestModelTokenLimitsTable:
    def test_total_models_at_least_13(self) -> None:
        """AC-1.7: len(MODEL_TOKEN_LIMITS) >= 13."""
        MODEL_TOKEN_LIMITS, _ = _load_under_test()
        assert len(MODEL_TOKEN_LIMITS) >= 13, (
            f"MODEL_TOKEN_LIMITS has only {len(MODEL_TOKEN_LIMITS)} models; "
            "expected >= 13 (4 OpenAI + 4 Anthropic + 2 Gemini + 4 DeepSeek)"
        )

    def test_deepseek_models_at_least_4(self) -> None:
        """AC-1.7 (R1 强化): DeepSeek keys >= 4 (chat/reasoner/coder/v4-pro)."""
        MODEL_TOKEN_LIMITS, _ = _load_under_test()
        deepseek_keys = [k for k in MODEL_TOKEN_LIMITS if k.startswith("deepseek:")]
        assert len(deepseek_keys) >= 4, (
            f"DeepSeek coverage is only {len(deepseek_keys)}: {deepseek_keys}; "
            "expected >= 4 (deepseek-chat / deepseek-reasoner / deepseek-coder / deepseek-v4-pro)"
        )

    def test_includes_v4_pro_production_model(self) -> None:
        """AC-1.7 (per memory phase4_llm_config): deepseek-v4-pro must be present."""
        MODEL_TOKEN_LIMITS, _ = _load_under_test()
        assert "deepseek:deepseek-v4-pro" in MODEL_TOKEN_LIMITS

    def test_includes_all_three_other_deepseek_models(self) -> None:
        """AC-1.7: deepseek-chat / deepseek-reasoner / deepseek-coder all present."""
        MODEL_TOKEN_LIMITS, _ = _load_under_test()
        for required in (
            "deepseek:deepseek-chat",
            "deepseek:deepseek-reasoner",
            "deepseek:deepseek-coder",
        ):
            assert required in MODEL_TOKEN_LIMITS, f"Missing {required}"

    def test_all_values_positive_integers(self) -> None:
        """AC-1.7 boundary: all token limits must be positive ints."""
        MODEL_TOKEN_LIMITS, _ = _load_under_test()
        for key, value in MODEL_TOKEN_LIMITS.items():
            assert isinstance(value, int), f"{key} value {value!r} is not int"
            assert value > 0, f"{key} value {value} must be positive"

    def test_at_least_4_providers_represented(self) -> None:
        """AC-1.7: >= 4 distinct provider prefixes (openai/anthropic/gemini/deepseek)."""
        MODEL_TOKEN_LIMITS, _ = _load_under_test()
        prefixes = {k.split(":")[0] for k in MODEL_TOKEN_LIMITS}
        assert len(prefixes) >= 4, f"Providers: {prefixes}"


# ---------------------------------------------------------------------------
# Helper: exception constructors (SDK packages not always in pyproject deps)
# ---------------------------------------------------------------------------
def _make_openai_bad_request(message: str) -> openai.BadRequestError:
    """Construct an openai.BadRequestError with given message."""
    return openai.BadRequestError(
        message=message,
        response=MagicMock(status_code=400),
        body={"error": {"message": message, "type": "invalid_request_error"}},
    )


def _make_openai_rate_limit() -> openai.RateLimitError:
    """Construct an openai.RateLimitError."""
    return openai.RateLimitError(
        message="Rate limit reached",
        response=MagicMock(status_code=429),
        body={"error": {"message": "Rate limit reached", "type": "rate_limit_error"}},
    )


def _make_anthropic_bad_request(message: str) -> Exception:
    """Duck-typed Anthropic exception — anthropic SDK not in pyproject deps."""
    class _AnthropicBadRequestError(Exception):
        pass

    exc = _AnthropicBadRequestError(message)
    # Class name matches production anthropic.BadRequestError name.
    exc.__class__.__name__ = "BadRequestError"
    return exc


def _make_gemini_resource_exhausted(message: str) -> Exception:
    """Duck-typed Gemini ResourceExhausted — google-api-core not in pyproject deps."""
    class _ResourceExhausted(Exception):
        pass

    exc = _ResourceExhausted(message)
    exc.__class__.__name__ = "ResourceExhausted"
    return exc


def _make_deepseek_api_error(message: str) -> Exception:
    """Duck-typed DeepSeekAPIError — deepseek SDK not in pyproject deps."""
    class _DeepSeekAPIError(Exception):
        pass

    exc = _DeepSeekAPIError(message)
    exc.__class__.__name__ = "DeepSeekAPIError"
    return exc