"""REQ-041 US1 FR-001 — is_token_limit_exceeded + MODEL_TOKEN_LIMITS.

Reference: openDeepResearch ``src/open_deep_research/utils.py:665-785``.

This module is the single authoritative source for token-limit detection
across all four LLM providers used by InterCraft agents (OpenAI / Anthropic /
Gemini / DeepSeek). It is consumed by:

- ``@node_error_handler`` (MB2) — branches into ``retry_with_shorter_prompt``
  instead of normal retry when the cause is a context-length error.
- ``llm_client.invoke`` (MB3, AC-1.8) — distinguishes retryable quota / timeout
  from non-retryable token-limit errors.

Design rules (locked 260703, AC-1.5 / AC-1.5a / AC-1.6):
- Always import provider SDK exception classes for ``isinstance`` checks; do
  NOT re-implement exception classification.
- Duck-typed fallback when the provider SDK is not installed in the
  runtime environment (Anthropic / Gemini / DeepSeek SDKs are optional).
  Detection keys off class name + message substring so we still match
  upstream exception types when the SDK lands.
- ``model_name`` argument follows ``<provider>:<model>`` convention, e.g.
  ``"openai:gpt-4o"`` / ``"anthropic:claude-sonnet-4-5"`` /
  ``"deepseek:deepseek-v4-pro"``. Anything else returns False (fail-safe).
"""
from __future__ import annotations

from typing import Any

import openai

# ---------------------------------------------------------------------------
# Optional SDK imports (duck-typed fallback if SDK absent)
# ---------------------------------------------------------------------------
try:
    import anthropic  # type: ignore[import-untyped]
except ImportError:  # pragma: no cover — Anthropic SDK optional
    anthropic = None  # type: ignore[assignment]

try:
    from google.api_core import exceptions as _google_exceptions  # type: ignore[import-untyped]
except ImportError:  # pragma: no cover — google-api-core optional
    _google_exceptions = None  # type: ignore[assignment]


# ---------------------------------------------------------------------------
# MODEL_TOKEN_LIMITS — covers 14 models across 4 providers (AC-1.7: >= 13)
#
# Per memory `phase4_llm_config`: production DeepSeek model is
# `deepseek-v4-pro` (128K token context window as of 2026-Q3).
# ---------------------------------------------------------------------------
MODEL_TOKEN_LIMITS: dict[str, int] = {
    # --- OpenAI (4 models) ---
    "openai:gpt-4o": 128_000,
    "openai:gpt-4-turbo": 128_000,
    "openai:gpt-3.5-turbo": 16_385,
    "openai:o1-preview": 128_000,
    # --- Anthropic (4 models) ---
    "anthropic:claude-sonnet-4-5": 200_000,
    "anthropic:claude-3-5-sonnet": 200_000,
    "anthropic:claude-3-opus": 200_000,
    "anthropic:claude-3-haiku": 200_000,
    # --- Gemini (2 models) ---
    "gemini:gemini-2.5-pro": 2_000_000,
    "gemini:gemini-2.0-flash": 1_000_000,
    # --- DeepSeek (4 models — per AC-1.7 R1 强化: >= 4 incl. production) ---
    "deepseek:deepseek-chat": 64_000,
    "deepseek:deepseek-reasoner": 64_000,
    "deepseek:deepseek-coder": 64_000,
    "deepseek:deepseek-v4-pro": 128_000,  # current production per `phase4_llm_config`
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def is_token_limit_exceeded(exception: BaseException, model_name: str) -> bool:
    """Return True iff ``exception`` indicates the model's token limit was hit.

    Supports 4 providers via ``model_name`` prefix:

    - ``openai:<model>``   — ``openai.BadRequestError`` with
      ``"prompt is too long"`` or ``"context_length_exceeded"`` in message.
    - ``anthropic:<model>`` — ``anthropic.BadRequestError`` (or duck-typed
      ``BadRequestError``) with ``"prompt is too long"`` in message.
    - ``gemini:<model>``    — ``google.api_core.exceptions.ResourceExhausted``
      (or duck-typed ``ResourceExhausted``) with quota/token message.
    - ``deepseek:<model>``  — OpenAI-like branch (``openai.BadRequestError``)
      plus string match against ``"context_length_exceeded"`` /
      ``"DeepSeekAPIError"`` (covers all three DeepSeek SDK shapes).

    Fail-safe: unknown / malformed ``model_name`` returns False rather than
    raising, so callers can use this helper in generic error-classification
    pipelines (AC-1.6).
    """
    if not model_name or ":" not in model_name:
        return False
    provider = model_name.split(":", 1)[0]
    msg = str(exception).lower()
    exc_name = type(exception).__name__

    if provider == "openai":
        return _check_openai_like(exception, exc_name, msg)
    if provider == "deepseek":
        return _check_openai_like(exception, exc_name, msg)
    if provider == "anthropic":
        return _check_anthropic(exception, exc_name, msg)
    if provider == "gemini":
        return _check_gemini(exception, exc_name, msg)

    # Unknown provider — fail-safe
    return False


# ---------------------------------------------------------------------------
# Provider-specific checks
# ---------------------------------------------------------------------------
def _check_openai_like(exception: BaseException, exc_name: str, msg: str) -> bool:
    """OpenAI / DeepSeek: BadRequestError + prompt-too-long / context_length_exceeded.

    Per AC-1.5, DeepSeek's runtime exception surface spans three shapes:
    (a) ``openai.BadRequestError`` with prompt-too-long message (OpenAI-compat);
    (b) ``DeepSeekAPIError`` carrying ``invalid_request_error`` type —
        DeepSeek SDK maps context-window overflows to ``invalid_request_error``
        type within ``DeepSeekAPIError``;
    (c) any exception whose message contains ``context_length_exceeded``
        (DeepSeek SDK sometimes wraps as a plain ``Exception`` or
        ``APIError`` — string match is the broadest reliable signal).
    """
    # (c) generic substring match — covers DeepSeek's plain-Exception wrapper
    # and acts as a safety net for any future SDK shape change.
    if "context_length_exceeded" in msg:
        return True
    is_bad_request = isinstance(exception, openai.BadRequestError) or exc_name == "BadRequestError"
    is_deepseek_api_err = exc_name == "DeepSeekAPIError"
    if not (is_bad_request or is_deepseek_api_err):
        return False
    if "prompt is too long" in msg or "context_length_exceeded" in msg:
        return True
    # (b) DeepSeekAPIError + invalid_request_error type → context window overflow
    if is_deepseek_api_err and "invalid_request_error" in msg:
        return True
    return False


def _check_anthropic(exception: BaseException, exc_name: str, msg: str) -> bool:
    """Anthropic: BadRequestError (SDK or duck-typed) + 'prompt is too long' substring."""
    is_bad_request = (
        (anthropic is not None and isinstance(exception, anthropic.BadRequestError))
        or exc_name == "BadRequestError"
    )
    if not is_bad_request:
        return False
    return "prompt is too long" in msg


def _check_gemini(exception: BaseException, exc_name: str, msg: str) -> bool:
    """Gemini: ResourceExhausted (SDK or duck-typed) with quota/token message."""
    is_resource_exhausted = (
        (
            _google_exceptions is not None
            and isinstance(exception, _google_exceptions.ResourceExhausted)
        )
        or exc_name == "ResourceExhausted"
    )
    if not is_resource_exhausted:
        return False
    # Gemini sometimes returns ResourceExhausted for both quota AND token
    # overage — narrow to token-overage messages.
    return "token" in msg or "RESOURCE_EXHAUSTED" in msg


__all__ = [
    "MODEL_TOKEN_LIMITS",
    "is_token_limit_exceeded",
]