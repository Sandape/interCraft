"""REQ-061 provider gateway — fenced attempts, circuit breaker, fallback (T021).

All model/search/tool SDK calls must go through this gateway. Graph nodes and
routers never call provider SDKs directly.
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable, Generic, TypeVar
from uuid import UUID

from pydantic import BaseModel, ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.ids import new_uuid_v7
from app.modules.ai_runtime.execution_context import ExecutionContext
from app.modules.ai_runtime.models import AIExternalAttempt, AIExternalEffectIntent
from app.modules.ai_runtime.repository import AIRuntimeRepository, ClaimGenerationConflict

T = TypeVar("T")


class ProviderGatewayError(RuntimeError):
    """Base gateway failure."""


class CircuitOpenError(ProviderGatewayError):
    """Raised when the circuit breaker rejects a call."""


class StructuredOutputBoundaryError(ProviderGatewayError):
    """Raised when provider output fails the structured-output schema boundary."""


@dataclass
class CircuitBreaker:
    failure_threshold: int = 5
    cooldown_seconds: float = 30.0
    failures: int = 0
    opened_at: float | None = None

    def allow(self) -> bool:
        if self.opened_at is None:
            return True
        if time.monotonic() - self.opened_at >= self.cooldown_seconds:
            self.opened_at = None
            self.failures = 0
            return True
        return False

    def record_success(self) -> None:
        self.failures = 0
        self.opened_at = None

    def record_failure(self) -> None:
        self.failures += 1
        if self.failures >= self.failure_threshold:
            self.opened_at = time.monotonic()


@dataclass
class FallbackRoute:
    provider_internal_code: str
    route_internal_code: str
    reason: str = "primary_unavailable"


@dataclass
class GatewayCallResult(Generic[T]):
    value: T | None
    attempt: AIExternalAttempt | None
    effect_intent: AIExternalEffectIntent | None
    status: str
    failure_category: str | None = None
    used_fallback: bool = False
    rejected_stale: bool = False


def canonical_request_hash(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    digest = hashlib.sha256(encoded.encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


def enforce_structured_output(model: type[BaseModel], payload: Any) -> BaseModel:
    try:
        if isinstance(payload, model):
            return payload
        if isinstance(payload, dict):
            return model.model_validate(payload)
        if isinstance(payload, str):
            return model.model_validate_json(payload)
        return model.model_validate(payload)
    except (ValidationError, TypeError, ValueError) as exc:
        raise StructuredOutputBoundaryError(str(exc)) from exc


@dataclass
class ProviderGateway:
    """Issues fenced effect intents and records external attempts."""

    session: AsyncSession
    circuit_breakers: dict[str, CircuitBreaker] = field(default_factory=dict)
    fallback_routes: dict[str, list[FallbackRoute]] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.repo = AIRuntimeRepository(self.session)

    def _breaker(self, route_key: str) -> CircuitBreaker:
        if route_key not in self.circuit_breakers:
            self.circuit_breakers[route_key] = CircuitBreaker()
        return self.circuit_breakers[route_key]

    async def issue_effect_intent(
        self,
        *,
        ctx: ExecutionContext,
        operation_name: str,
        request_payload: dict[str, Any],
        risk_class: str = "R0",
        provider_route_version: str | None = None,
        provider_idempotency_key: str | None = None,
        authorization_receipt_id: UUID | None = None,
    ) -> AIExternalEffectIntent:
        if ctx.session is None:
            # Allow callers that already bound self.session.
            pass
        intent = AIExternalEffectIntent(
            id=new_uuid_v7(),
            root_task_id=ctx.root_task_id,
            task_id=ctx.task_id,
            execution_id=ctx.execution_id,
            stage_attempt_id=ctx.stage_attempt_id,
            user_id=ctx.user_id,
            authorization_receipt_id=authorization_receipt_id
            or ctx.authorization_receipt_id,
            operation_name=operation_name,
            risk_class=risk_class,
            provider_route_version=provider_route_version,
            canonical_request_hash=canonical_request_hash(request_payload),
            provider_idempotency_key=provider_idempotency_key,
            claim_generation=ctx.claim_generation,
            status="prepared",
        )
        self.session.add(intent)
        await self.session.flush()
        return intent

    async def record_attempt(
        self,
        *,
        ctx: ExecutionContext,
        operation_name: str,
        attempt_kind: str,
        attempt_no: int = 1,
        provider_internal_code: str | None = None,
        route_internal_code: str | None = None,
        effect_intent_id: UUID | None = None,
        authorization_receipt_id: UUID | None = None,
        request_hash: str | None = None,
        status: str = "created",
    ) -> AIExternalAttempt:
        attempt = AIExternalAttempt(
            id=new_uuid_v7(),
            task_id=ctx.task_id,
            execution_id=ctx.execution_id,
            root_task_id=ctx.root_task_id,
            user_id=ctx.user_id,
            stage_attempt_id=ctx.stage_attempt_id,
            external_effect_intent_id=effect_intent_id,
            authorization_receipt_id=authorization_receipt_id
            or ctx.authorization_receipt_id,
            claim_generation_at_send=ctx.claim_generation,
            attempt_kind=attempt_kind,
            provider_internal_code=provider_internal_code,
            route_internal_code=route_internal_code,
            operation_name=operation_name,
            attempt_no=attempt_no,
            status=status,
            request_hash=request_hash,
            trace_id=ctx.trace_id,
        )
        self.session.add(attempt)
        await self.session.flush()
        return attempt

    async def mark_sent(
        self,
        *,
        intent: AIExternalEffectIntent,
        attempt: AIExternalAttempt,
        provider_request_id: str | None = None,
    ) -> None:
        intent.status = "sent"
        intent.sent_at = datetime.now(timezone.utc)
        intent.attempt_id = attempt.id
        intent.provider_request_id = provider_request_id
        attempt.status = "sent"
        attempt.provider_request_id = provider_request_id
        await self.session.flush()

    async def adopt_result(
        self,
        *,
        ctx: ExecutionContext,
        intent: AIExternalEffectIntent,
        attempt: AIExternalAttempt,
        status: str,
        response_structure_hash: str | None = None,
        failure_category: str | None = None,
        evidence_ref: str | None = None,
        latency_ms: int | None = None,
    ) -> GatewayCallResult[None]:
        try:
            await self.repo.cas_execution_claim(
                execution_id=ctx.execution_id,
                expected_claim_generation=ctx.claim_generation,
                values={"updated_at": datetime.now(timezone.utc)},
            )
        except ClaimGenerationConflict:
            attempt.status = "rejected_stale"
            attempt.failure_category = "stale_claim"
            attempt.finished_at = datetime.now(timezone.utc)
            intent.status = "unknown"
            await self.session.flush()
            return GatewayCallResult(
                value=None,
                attempt=attempt,
                effect_intent=intent,
                status="rejected_stale",
                failure_category="stale_claim",
                rejected_stale=True,
            )

        attempt.status = status
        attempt.claim_generation_at_adoption = ctx.claim_generation
        attempt.response_structure_hash = response_structure_hash
        attempt.failure_category = failure_category
        attempt.latency_ms = latency_ms
        attempt.finished_at = datetime.now(timezone.utc)
        intent.status = "adopted" if status in {"succeeded", "failed"} else status
        intent.adopted_at = datetime.now(timezone.utc)
        intent.result_evidence_ref = evidence_ref
        await self.session.flush()
        return GatewayCallResult(
            value=None,
            attempt=attempt,
            effect_intent=intent,
            status=status,
            failure_category=failure_category,
        )

    def select_route(
        self,
        *,
        primary_provider: str,
        primary_route: str,
    ) -> tuple[str, str, bool]:
        key = f"{primary_provider}:{primary_route}"
        breaker = self._breaker(key)
        if breaker.allow():
            return primary_provider, primary_route, False
        for fallback in self.fallback_routes.get(key, []):
            fb_key = f"{fallback.provider_internal_code}:{fallback.route_internal_code}"
            if self._breaker(fb_key).allow():
                return (
                    fallback.provider_internal_code,
                    fallback.route_internal_code,
                    True,
                )
        raise CircuitOpenError(f"circuit open for {key} and no fallback available")

    async def invoke(
        self,
        *,
        ctx: ExecutionContext,
        operation_name: str,
        request_payload: dict[str, Any],
        call: Callable[[], Awaitable[Any]],
        attempt_kind: str = "model",
        primary_provider: str = "default",
        primary_route: str = "default",
        risk_class: str = "R0",
        structured_model: type[BaseModel] | None = None,
        attempt_no: int = 1,
    ) -> GatewayCallResult[Any]:
        provider, route, used_fallback = self.select_route(
            primary_provider=primary_provider,
            primary_route=primary_route,
        )
        route_key = f"{provider}:{route}"
        breaker = self._breaker(route_key)

        intent = await self.issue_effect_intent(
            ctx=ctx,
            operation_name=operation_name,
            request_payload=request_payload,
            risk_class=risk_class,
            provider_route_version=route,
        )
        attempt = await self.record_attempt(
            ctx=ctx,
            operation_name=operation_name,
            attempt_kind=attempt_kind,
            attempt_no=attempt_no,
            provider_internal_code=provider,
            route_internal_code=route,
            effect_intent_id=intent.id,
            request_hash=intent.canonical_request_hash,
            status="created",
        )
        started = time.perf_counter()
        await self.mark_sent(intent=intent, attempt=attempt)

        try:
            raw = await call()
            value: Any = raw
            structure_hash = None
            if structured_model is not None:
                parsed = enforce_structured_output(structured_model, raw)
                value = parsed
                structure_hash = canonical_request_hash(parsed.model_dump(mode="json"))
            latency_ms = int((time.perf_counter() - started) * 1000)
            breaker.record_success()
            adopted = await self.adopt_result(
                ctx=ctx,
                intent=intent,
                attempt=attempt,
                status="succeeded",
                response_structure_hash=structure_hash,
                latency_ms=latency_ms,
            )
            return GatewayCallResult(
                value=value,
                attempt=adopted.attempt,
                effect_intent=adopted.effect_intent,
                status=adopted.status,
                used_fallback=used_fallback,
                rejected_stale=adopted.rejected_stale,
                failure_category=adopted.failure_category,
            )
        except StructuredOutputBoundaryError as exc:
            breaker.record_failure()
            latency_ms = int((time.perf_counter() - started) * 1000)
            adopted = await self.adopt_result(
                ctx=ctx,
                intent=intent,
                attempt=attempt,
                status="failed",
                failure_category="structured_output_invalid",
                latency_ms=latency_ms,
                evidence_ref=str(exc),
            )
            raise
        except Exception as exc:
            breaker.record_failure()
            latency_ms = int((time.perf_counter() - started) * 1000)
            category = "provider_error"
            if isinstance(exc, TimeoutError):
                category = "timeout"
            adopted = await self.adopt_result(
                ctx=ctx,
                intent=intent,
                attempt=attempt,
                status="failed",
                failure_category=category,
                latency_ms=latency_ms,
                evidence_ref=str(exc),
            )
            if adopted.rejected_stale:
                return GatewayCallResult(
                    value=None,
                    attempt=adopted.attempt,
                    effect_intent=adopted.effect_intent,
                    status="rejected_stale",
                    failure_category="stale_claim",
                    used_fallback=used_fallback,
                    rejected_stale=True,
                )
            raise


def create_provider_gateway(session: AsyncSession) -> ProviderGateway:
    return ProviderGateway(session=session)


__all__ = [
    "CircuitBreaker",
    "CircuitOpenError",
    "FallbackRoute",
    "GatewayCallResult",
    "ProviderGateway",
    "ProviderGatewayError",
    "StructuredOutputBoundaryError",
    "canonical_request_hash",
    "create_provider_gateway",
    "enforce_structured_output",
]
