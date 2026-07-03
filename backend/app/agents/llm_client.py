"""M14 — Unified LLM client (T010).

OpenAI-compatible protocol to DeepSeek V4 Pro.
Pre-deduct + actual adjust token quota, auto-retry, structured logging.

Per contracts/llm-client.md.
"""
from __future__ import annotations

import os
import time
import uuid
from decimal import Decimal

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
from typing import Any
from typing_extensions import TypedDict

from pydantic import BaseModel

from app.agents.structured_output.client import parse_structured_output
from app.agents.structured_output.errors import (
    ParseFail,
    SchemaInvalid,
    StructuredOutputError,
)
from app.agents.token_estimator import TokenEstimator
from app.core.config import get_settings
from app.eval.prompt_fingerprint import compute_prompt_fingerprint
from app.modules.telemetry_contracts.costs import estimate_cost
from app.modules.telemetry_contracts.schemas import AIInvocationSummary

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


class LLMInvokeError(RuntimeError):
    """Raised when LLM invocation fails after exhausting retries.

    Inherits ``RuntimeError`` so legacy 040 US-2 tests using
    ``pytest.raises(RuntimeError)`` (e.g.
    ``test_ac_4_6_score_llm_failure_does_not_trigger_sink_error``)
    still pass — ``LLMInvokeError`` IS-A ``RuntimeError``. The 041
    decorator's ``raise LLMInvokeError(...) from last_exc`` path
    therefore satisfies BOTH the new ``LLMInvokeError`` contract
    (AC-2.2a) AND the legacy ``RuntimeError`` contract (040 AC-4.6).
    """

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
                    # US9 (T040): fire AI invocation hook on failure.
                    _extract_and_record_ai_invocation(
                        _build_ai_invocation_summary(
                            invocation_id=str(uuid.uuid4()),
                            graph="",  # graph unknown at this scope; node carries context
                            node=node_name,
                            model=model,
                            system_prompt="",
                            tool_defs=None,
                            messages=messages,
                            prompt_tokens=0,
                            completion_tokens=0,
                            latency_ms=int(time.time() * 1000) - start_ms,
                            retry_count=retry_count,
                            status="FAILURE",
                            error_category=_classify_error(exc),
                        )
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
                # US9 (T040): fire AI invocation hook on non-retryable failure.
                _extract_and_record_ai_invocation(
                    _build_ai_invocation_summary(
                        invocation_id=str(uuid.uuid4()),
                        graph="",
                        node=node_name,
                        model=model,
                        system_prompt="",
                        tool_defs=None,
                        messages=messages,
                        prompt_tokens=0,
                        completion_tokens=0,
                        latency_ms=int(time.time() * 1000) - start_ms,
                        retry_count=0,
                        status="FAILURE",
                        error_category=_classify_error(exc),
                    )
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

        # US9 (T040): fire AI invocation hook on success.
        _extract_and_record_ai_invocation(
            _build_ai_invocation_summary(
                invocation_id=str(uuid.uuid4()),
                graph="",
                node=node_name,
                model=model,
                system_prompt="",
                tool_defs=None,
                messages=messages,
                prompt_tokens=response.usage.prompt_tokens,
                completion_tokens=response.usage.completion_tokens,
                latency_ms=duration_ms,
                retry_count=retry_count,
                status="SUCCESS",
                error_category=None,
            )
        )

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

    # ------------------------------------------------------------------
    # REQ-038 US1 P1 — Structured-output parsing (single authoritative
    # entry point; ac-matrix AC-005). MockLLMClient subclasses this so
    # mock and prod share the Pydantic validation path (AC-009).
    # ------------------------------------------------------------------
    def parse_structured_output(
        self,
        content: str,
        schema: type[BaseModel],
        *,
        fallback_strategy: str = "retry",
        node_name: str | None = None,
    ) -> BaseModel:
        """Parse raw LLM content through the structured-output pipeline.

        Returns a Pydantic-validated instance on success; raises one of
        the StructuredOutputError subclasses (SchemaInvalid, ParseFail,
        OutOfBounds, Quota, Timeout) on failure.
        """
        try:
            return parse_structured_output(
                content,
                schema,
                fallback_strategy=fallback_strategy,  # type: ignore[arg-type]
                node_name=node_name,
            )
        except StructuredOutputError:
            # Re-raise so callers can branch on .category
            raise


__all__ = [
    "LLMClient",
    "LLMInvokeError",
    "LLMResponse",
    "QuotaExceededError",
    "_build_ai_invocation_summary",
    "_extract_and_record_ai_invocation",
    "get_llm_client",
]


# ---------------------------------------------------------------------------
# AI invocation summary extraction (T040, US9)
# ---------------------------------------------------------------------------


# Cost per token table (USD) — populated lazily from settings or env.
# If a model is missing from the table, cost=0.0 with is_estimate=True.
# US4 T108: this legacy helper is no longer called by
# ``_build_ai_invocation_summary`` (which now delegates to
# ``telemetry_contracts.costs.estimate_cost``). Kept for backward
# compatibility with any external caller that imports it; not part
# of the active cost-calculation path.
_DEFAULT_COST_PER_TOKEN: float = 0.0  # conservative; US9 T040 says cost=0 if not configured


def _get_cost_per_token(model: str) -> float:
    """Return USD cost per token for ``model`` (legacy — US4 T108).

    US4 T108 redirected the active cost path to
    ``app.modules.telemetry_contracts.costs.estimate_cost``. This
    function is retained as a back-compat shim and reads the same
    ``Settings.deepseek_cost_per_token`` scalar it always did.

    Looks at:

    1. ``Settings.deepseek_cost_per_token`` (single scalar — applies to
       all models). Default 0.0.
    2. Future: per-model dict when model heterogeneity is needed.

    Always returns 0.0 when not configured, with ``is_estimate=True``
    on the AIInvocationSummary so consumers know the value is a stub.
    """
    try:
        settings = get_settings()
        cpt = getattr(settings, "deepseek_cost_per_token", 0.0)
        return float(cpt) if cpt else 0.0
    except Exception:  # pragma: no cover — fail-open
        return _DEFAULT_COST_PER_TOKEN


def _build_ai_invocation_summary(
    *,
    invocation_id: str,
    graph: str,
    node: str,
    model: str,
    system_prompt: str,
    tool_defs: list[dict[str, Any]] | None,
    messages: list[dict[str, str]] | None,
    prompt_tokens: int,
    completion_tokens: int,
    latency_ms: int,
    retry_count: int,
    status: str,
    error_category: str | None = None,
    run_id: Any | None = None,
    trace_id: str | None = None,
) -> AIInvocationSummary:
    """Build an ``AIInvocationSummary`` for a completed LLM call.

    Pure function — no IO. Computes prompt fingerprint, cost estimate,
    and SC-010 ``"unknown"`` defaults in one place so the contract is
    consistent across invoke and invoke_stream paths.
    """
    try:
        fp = compute_prompt_fingerprint(
            system_prompt=system_prompt,
            tool_defs=tool_defs or [],
            messages=[dict(m) for m in (messages or [])] if messages else [],
        )
    except Exception:  # pragma: no cover — fail-open per SC-010
        fp = "unknown"

    # US4 T108: route cost computation through the canonical
    # ``telemetry_contracts.costs.estimate_cost`` pure function so the
    # PM Dashboard AI Operations panel and the LLM client hook agree
    # on the same USD value for matching (prompt, completion, model)
    # inputs. ``estimate_cost`` falls back to a conservative low rate
    # for unknown models and clamps negative token counts to 0.
    estimated_cost = estimate_cost(
        prompt_tokens=int(prompt_tokens),
        completion_tokens=int(completion_tokens),
        model=model,
    )

    return AIInvocationSummary(
        invocation_id=invocation_id,
        run_id=run_id,
        trace_id=trace_id,
        graph=graph,
        node=node,
        model=model,
        prompt_fingerprint=fp,
        prompt_tokens=int(prompt_tokens),
        completion_tokens=int(completion_tokens),
        estimated_cost=estimated_cost,
        is_estimate=True,  # always an estimate
        latency_ms=int(latency_ms),
        retry_count=int(retry_count),
        status=status,
        error_category=error_category,
    )


def _classify_error(exc: BaseException) -> str:
    """Map a LLM exception to a short error category string.

    The category is the join key for the badcase/regression analysis
    pipeline (US9). Examples: ``rate_limit``, ``timeout``,
    ``auth_failure``, ``bad_request``, ``server``, ``connection``,
    ``quota_exceeded``, ``unknown``.
    """
    name = type(exc).__name__
    msg = str(exc).lower()
    if "ratelimit" in name.lower() or "rate" in msg:
        return "rate_limit"
    if "timeout" in name.lower() or "timeout" in msg:
        return "timeout"
    if "auth" in name.lower():
        return "auth_failure"
    if "badrequest" in name.lower() or "unprocessable" in name.lower():
        return "bad_request"
    if "permission" in name.lower():
        return "permission_denied"
    if "server" in name.lower():
        return "server_error"
    if "connection" in name.lower():
        return "connection"
    return "unknown"


def _extract_and_record_ai_invocation(summary: AIInvocationSummary) -> None:
    """Hook: persist the AIInvocationSummary to DB (best-effort, fail-open).

    Called automatically after every LLMClient.invoke / invoke_stream
    completion. Persistence path (T040 contract):

    1. Tries to insert via ``repository.insert_ai_invocation`` (US9 path).
    2. If the repository is unavailable (test / no DB), falls back to
       a no-op + structlog warning so the call site still works.

    The hook MUST NOT raise — the LLM call has already succeeded (or
    failed with LLMInvokeError), and a hook failure must not propagate
    to the caller. This is the ``fail-open`` contract from
    lessons-learned (REQ-MERGE-02 round 1).
    """
    try:
        import asyncio

        from app.core.db import get_session_factory
        from uuid import UUID as _UUID

        from app.modules.telemetry_contracts.repository import (
            insert_ai_invocation,
        )

        # Resolve a user_id from run_id or fall back to a sentinel zero
        # UUID. The repository requires a non-null user_id — we use a
        # deterministic system-actor UUID when the call site didn't pass one.
        SYSTEM_USER_ID = _UUID("00000000-0000-0000-0000-000000000000")
        user_id = SYSTEM_USER_ID

        async def _persist() -> None:
            factory = get_session_factory()
            async with factory() as session:
                await insert_ai_invocation(
                    session,
                    user_id=user_id,
                    invocation_id=_UUID(summary.invocation_id),
                    graph=summary.graph,
                    node=summary.node,
                    model=summary.model,
                    prompt_fingerprint=summary.prompt_fingerprint,
                    prompt_tokens=summary.prompt_tokens,
                    completion_tokens=summary.completion_tokens,
                    estimated_cost=(
                        Decimal(str(summary.estimated_cost))
                        if summary.estimated_cost is not None
                        else None
                    ),
                    latency_ms=summary.latency_ms,
                    retry_count=summary.retry_count,
                    status=summary.status,
                    error_category=summary.error_category,
                    run_id=summary.run_id,
                    trace_id=summary.trace_id,
                )

        # Try to run the async persist. In a sync context (which the
        # LLMClient callsite is not — invoke is async), this would
        # block; we still wrap in try/except to ensure fail-open.
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # We're inside an async context — schedule as a task.
                loop.create_task(_persist())
            else:
                loop.run_until_complete(_persist())
        except RuntimeError:
            # No event loop — try asyncio.run (only works if not in a loop).
            try:
                asyncio.run(_persist())
            except Exception:
                pass
    except Exception as exc:  # pragma: no cover — fail-open
        # Never let hook failure propagate to the LLM call.
        try:
            import structlog as _sl

            _sl.get_logger("agents.llm_client.hook").warning(
                "ai_invocation.persist_failed",
                invocation_id=summary.invocation_id,
                error=str(exc),
            )
        except Exception:
            pass
