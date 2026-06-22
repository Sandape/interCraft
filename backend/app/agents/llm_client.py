"""M14 — Unified LLM client (T010).

OpenAI-compatible protocol to DeepSeek V4 Pro.
Pre-deduct + actual adjust token quota, auto-retry, structured logging.

Per contracts/llm-client.md.
"""
from __future__ import annotations

import os
import time
import uuid

import openai
import structlog
from openai import (
    APIConnectionError,
    APITimeoutError,
    AuthenticationError,
    BadRequestError,
    InternalServerError,
    PermissionDeniedError,
    RateLimitError,
    UnprocessableEntityError,
)
from typing_extensions import TypedDict

from app.agents.token_estimator import TokenEstimator
from app.core.config import get_settings

logger = structlog.get_logger("agents.llm_client")

# ---------------------------------------------------------------------------
# Prometheus metrics
# ---------------------------------------------------------------------------
try:
    from prometheus_client import Counter, Histogram

    LLM_INVOKE_TOTAL = Counter(
        "llm_invoke_total",
        "LLM invoke count by model, node, result",
        ["model", "node", "result"],
    )
    LLM_TOKEN_CONSUMED_TOTAL = Counter(
        "llm_token_consumed_total",
        "LLM token consumption by model, type",
        ["model", "type"],
    )
    LLM_INVOKE_DURATION = Histogram(
        "llm_invoke_duration_seconds",
        "LLM invoke duration in seconds",
        ["model", "node"],
        buckets=(0.5, 1.0, 2.0, 5.0, 10.0, 20.0, 30.0, 60.0),
    )
except ImportError:  # pragma: no cover
    LLM_INVOKE_TOTAL = None
    LLM_TOKEN_CONSUMED_TOTAL = None
    LLM_INVOKE_DURATION = None


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------
class QuotaExceededError(Exception):
    """Raised when monthly token quota is insufficient for the requested call."""

    def __init__(self, used: int, quota: int, estimated: int) -> None:
        self.used = used
        self.quota = quota
        self.estimated = estimated
        super().__init__(
            f"Token quota exceeded: used={used}, quota={quota}, needed={estimated}"
        )


class LLMInvokeError(Exception):
    """Raised when LLM invocation fails after exhausting retries."""

    def __init__(self, message: str, *, node_name: str = "", retry_count: int = 0) -> None:
        self.node_name = node_name
        self.retry_count = retry_count
        super().__init__(message)


# ---------------------------------------------------------------------------
# Response type
# ---------------------------------------------------------------------------
class LLMResponse(TypedDict):
    content: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    duration_ms: int
    checkpoint_id: str | None


# ---------------------------------------------------------------------------
# LLM Client
# ---------------------------------------------------------------------------
_llm_client_singleton: LLMClient | None = None
# 021: mock client is cached per scenario-file mtime so the score sequence
# inside MockLLMClient persists across invokes within a session. When the
# E2E test overwrites the scenario file, the mtime changes and the cache
# is invalidated.
_mock_client_singleton: object | None = None
_mock_client_scenario_mtime: float | None = None


def get_llm_client() -> LLMClient:
    global _llm_client_singleton, _mock_client_singleton, _mock_client_scenario_mtime
    if os.environ.get("LLM_MOCK_MODE") == "1":
        path = os.environ.get("LLM_MOCK_SCENARIO_PATH", "")
        try:
            mtime = os.path.getmtime(path) if path and os.path.exists(path) else 0.0
        except OSError:
            mtime = 0.0
        if _mock_client_singleton is None or mtime != _mock_client_scenario_mtime:
            from app.agents.llm_client_mock import MockLLMClient

            _mock_client_singleton = MockLLMClient.from_scenario_file(path)
            _mock_client_scenario_mtime = mtime
        return _mock_client_singleton  # type: ignore[return-value]
    if _llm_client_singleton is None:
        _llm_client_singleton = LLMClient()
    return _llm_client_singleton


class LLMClient:
    """Unified LLM client via OpenAI-compatible protocol for DeepSeek V4 Pro."""

    def __init__(self) -> None:
        settings = get_settings()
        api_key = settings.deepseek_api_key or os.environ.get("DEEPSEEK_API_KEY", "")
        base_url = settings.deepseek_base_url or os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
        self._model = settings.deepseek_model or os.environ.get("DEEPSEEK_MODEL", "deepseek-v4-pro")
        self._quota = settings.monthly_token_quota

        self._client = openai.AsyncOpenAI(
            base_url=base_url,
            api_key=api_key,
            max_retries=0,  # We handle retries ourselves for observability
            timeout=30.0,
        )
        self._estimator = TokenEstimator()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    async def invoke(
        self,
        *,
        messages: list[dict[str, str]],
        estimated_tokens: int | None = None,
        user_id: str,
        thread_id: str,
        node_name: str,
        checkpoint_id: str | None = None,
        max_retries: int = 3,
        timeout_ms: int = 30_000,
        stream: bool = False,
    ) -> LLMResponse:
        """Invoke DeepSeek V4 Pro with pre-deduct, call, adjust, log.

        Raises:
            QuotaExceededError: insufficient quota
            LLMInvokeError: exhausted retries
        """
        if estimated_tokens is None:
            estimated_tokens = self._estimator.estimate(node_name)

        model = self._estimator.get_model(node_name)

        # 1. Pre-deduct quota
        await self._pre_deduct(user_id, estimated_tokens)

        # 2. Call with retries
        start_ms = int(time.time() * 1000)
        retry_count = 0

        for attempt in range(max_retries + 1):
            try:
                response = await self._call_deepseek(
                    messages=messages,
                    model=model,
                    stream=stream,
                    timeout_ms=timeout_ms,
                )
                break
            except (RateLimitError, APITimeoutError, APIConnectionError, InternalServerError) as exc:
                retry_count = attempt + 1
                if attempt >= max_retries:
                    self._record_metrics(model, node_name, "error")
                    logger.error(
                        "llm.invoke",
                        request_id=str(uuid.uuid4()),
                        user_id=user_id,
                        thread_id=thread_id,
                        node_name=node_name,
                        model=model,
                        result="error",
                        retry_count=retry_count,
                        error=str(exc),
                    )
                    raise LLMInvokeError(
                        f"LLM invoke failed after {retry_count} retries: {exc}",
                        node_name=node_name,
                        retry_count=retry_count,
                    ) from exc
                wait_s = 2 ** attempt  # 1s, 2s, 4s
                logger.warning(
                    "llm.retry",
                    node_name=node_name,
                    attempt=retry_count,
                    wait_s=wait_s,
                    error=str(exc),
                )
                import asyncio

                await asyncio.sleep(wait_s)
            except (AuthenticationError, PermissionDeniedError, BadRequestError, UnprocessableEntityError) as exc:
                self._record_metrics(model, node_name, "error")
                logger.error(
                    "llm.invoke",
                    request_id=str(uuid.uuid4()),
                    user_id=user_id,
                    thread_id=thread_id,
                    node_name=node_name,
                    model=model,
                    result="error",
                    error=str(exc),
                )
                raise LLMInvokeError(
                    f"LLM invoke non-retryable error: {exc}",
                    node_name=node_name,
                ) from exc

        duration_ms = int(time.time() * 1000) - start_ms
        actual_tokens = response.usage.prompt_tokens + response.usage.completion_tokens

        # 3. Actual adjust
        await self._actual_adjust(user_id, estimated_tokens, actual_tokens)

        # 4. Write ai_messages
        await self._write_ai_message(
            user_id=user_id,
            thread_id=thread_id,
            checkpoint_id=checkpoint_id,
            node_name=node_name,
            role="assistant",
            model=model,
            prompt_tokens=response.usage.prompt_tokens,
            completion_tokens=response.usage.completion_tokens,
            duration_ms=duration_ms,
        )

        # 5. Structured log
        self._record_metrics(model, node_name, "success")
        self._record_tokens(model, response.usage.prompt_tokens, response.usage.completion_tokens)
        if LLM_INVOKE_DURATION:
            LLM_INVOKE_DURATION.labels(model=model, node=node_name).observe(duration_ms / 1000.0)

        logger.info(
            "llm.invoke",
            request_id=str(uuid.uuid4()),
            user_id=user_id,
            thread_id=thread_id,
            node_name=node_name,
            model=model,
            estimated_tokens=estimated_tokens,
            actual_tokens=actual_tokens,
            prompt_tokens=response.usage.prompt_tokens,
            completion_tokens=response.usage.completion_tokens,
            duration_ms=duration_ms,
            retry_count=retry_count,
            result="success",
        )

        content = response.choices[0].message.content or ""

        return LLMResponse(
            content=content,
            model=model,
            prompt_tokens=response.usage.prompt_tokens,
            completion_tokens=response.usage.completion_tokens,
            duration_ms=duration_ms,
            checkpoint_id=checkpoint_id,
        )

    async def invoke_stream(
        self,
        *,
        messages: list[dict[str, str]],
        estimated_tokens: int | None = None,
        user_id: str,
        thread_id: str,
        node_name: str,
        checkpoint_id: str | None = None,
        max_retries: int = 3,
        timeout_ms: int = 30_000,
    ):
        """Streaming version — yields content chunks.

        Usage:
            async for chunk in client.invoke_stream(...):
                yield chunk  # each chunk is a str fragment
        """
        if estimated_tokens is None:
            estimated_tokens = self._estimator.estimate(node_name)

        model = self._estimator.get_model(node_name)

        await self._pre_deduct(user_id, estimated_tokens)

        start_ms = int(time.time() * 1000)
        retry_count = 0
        total_prompt_tokens = 0
        total_completion_tokens = 0

        for attempt in range(max_retries + 1):
            try:
                stream = await self._client.chat.completions.create(
                    model=model,
                    messages=messages,
                    stream=True,
                    timeout=timeout_ms / 1000.0,
                )
                async for chunk in stream:
                    if chunk.choices and chunk.choices[0].delta.content:
                        yield chunk.choices[0].delta.content
                    if chunk.usage:
                        total_prompt_tokens = chunk.usage.prompt_tokens or 0
                        total_completion_tokens = chunk.usage.completion_tokens or 0
                break
            except (RateLimitError, APITimeoutError, APIConnectionError, InternalServerError) as exc:
                retry_count = attempt + 1
                if attempt >= max_retries:
                    raise LLMInvokeError(
                        f"LLM stream failed after {retry_count} retries: {exc}",
                        node_name=node_name,
                        retry_count=retry_count,
                    ) from exc
                wait_s = 2 ** attempt
                logger.warning("llm.stream_retry", node_name=node_name, attempt=retry_count, wait_s=wait_s)
                import asyncio

                await asyncio.sleep(wait_s)
            except (AuthenticationError, PermissionDeniedError, BadRequestError) as exc:
                raise LLMInvokeError(
                    f"LLM stream non-retryable error: {exc}",
                    node_name=node_name,
                ) from exc

        duration_ms = int(time.time() * 1000) - start_ms
        actual_tokens = total_prompt_tokens + total_completion_tokens
        if actual_tokens > 0:
            await self._actual_adjust(user_id, estimated_tokens, actual_tokens)

        if total_prompt_tokens > 0:
            await self._write_ai_message(
                user_id=user_id,
                thread_id=thread_id,
                checkpoint_id=checkpoint_id,
                node_name=node_name,
                role="assistant",
                model=model,
                prompt_tokens=total_prompt_tokens,
                completion_tokens=total_completion_tokens,
                duration_ms=duration_ms,
            )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    async def _call_deepseek(
        self,
        messages: list[dict[str, str]],
        model: str,
        stream: bool,
        timeout_ms: int,
    ):
        settings = get_settings()
        return await self._client.chat.completions.create(
            model=model,
            messages=messages,
            stream=stream,
            timeout=timeout_ms / 1000.0,
            reasoning_effort=settings.deepseek_reasoning_effort,
            extra_body={"thinking": {"type": "enabled"}}
            if settings.deepseek_thinking_enabled
            else None,
        )

    async def _pre_deduct(self, user_id: str, estimated_tokens: int) -> None:
        """Atomically check and pre-deduct quota via SELECT...FOR UPDATE."""
        from uuid import UUID as _UUID

        from sqlalchemy import text

        from app.core.db import get_session_factory

        # Non-fatal: if user_id is not a valid UUID (e.g. "unknown"), skip quota check
        try:
            uid = _UUID(user_id)
        except ValueError:
            logger.warning("llm.pre_deduct_skip", user_id=user_id, reason="invalid_uuid")
            return

        factory = get_session_factory()
        async with factory() as session:
            result = await session.execute(
                text(
                    "SELECT monthly_token_used, monthly_token_quota "
                    "FROM users WHERE id = :uid FOR UPDATE"
                ),
                {"uid": uid},
            )
            row = result.fetchone()
            if row is None:
                return  # User not found, let it proceed

            used = row[0] or 0
            quota = row[1] or self._quota

            if used + estimated_tokens > quota:
                raise QuotaExceededError(used=used, quota=quota, estimated=estimated_tokens)

            await session.execute(
                text(
                    "UPDATE users SET monthly_token_used = monthly_token_used + :est "
                    "WHERE id = :uid"
                ),
                {"est": estimated_tokens, "uid": _UUID(user_id)},
            )
            await session.commit()

    async def _actual_adjust(self, user_id: str, estimated: int, actual: int) -> None:
        """Adjust quota: subtract estimate, add actual."""
        from uuid import UUID as _UUID

        from sqlalchemy import text

        from app.core.db import get_session_factory

        delta = actual - estimated
        if delta == 0:
            return

        factory = get_session_factory()
        async with factory() as session:
            await session.execute(
                text(
                    "UPDATE users SET monthly_token_used = monthly_token_used + :delta "
                    "WHERE id = :uid"
                ),
                {"delta": delta, "uid": _UUID(user_id)},
            )
            await session.commit()

    async def _write_ai_message(
        self,
        *,
        user_id: str,
        thread_id: str,
        checkpoint_id: str | None,
        node_name: str,
        role: str,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
        duration_ms: int,
    ) -> None:
        """Insert an ai_messages audit row."""
        from uuid import UUID as _UUID
        from uuid import uuid4

        from sqlalchemy import text

        from app.core.db import get_session_factory

        factory = get_session_factory()
        async with factory() as session:
            await session.execute(
                text(
                    """INSERT INTO ai_messages
                    (id, user_id, thread_id, checkpoint_ns, checkpoint_id, node_name,
                     role, model, prompt_tokens, completion_tokens, cache_hit, duration_ms)
                    VALUES
                    (:id, :uid, :tid, :cns, :cid, :nn,
                     :role, :model, :pt, :ct, :ch, :dur)
                    """
                ),
                {
                    "id": uuid4(),
                    "uid": _UUID(user_id),
                    "tid": thread_id,
                    "cns": "",
                    "cid": checkpoint_id,
                    "nn": node_name,
                    "role": role,
                    "model": model,
                    "pt": prompt_tokens,
                    "ct": completion_tokens,
                    "ch": False,
                    "dur": duration_ms,
                },
            )
            await session.commit()

    @staticmethod
    def _record_metrics(model: str, node: str, result: str) -> None:
        if LLM_INVOKE_TOTAL:
            LLM_INVOKE_TOTAL.labels(model=model, node=node, result=result).inc()

    @staticmethod
    def _record_tokens(model: str, prompt_tokens: int, completion_tokens: int) -> None:
        if LLM_TOKEN_CONSUMED_TOTAL:
            LLM_TOKEN_CONSUMED_TOTAL.labels(model=model, type="input").inc(prompt_tokens)
            LLM_TOKEN_CONSUMED_TOTAL.labels(model=model, type="output").inc(completion_tokens)


__all__ = [
    "LLMClient",
    "LLMInvokeError",
    "LLMResponse",
    "QuotaExceededError",
    "get_llm_client",
]
