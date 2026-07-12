"""REQ-061 usage/cost fact helpers and persistence service (T009/T020).

Pure helpers remain for unit invariants. ``UsageCostService`` persists
append-only attempt facts, rate/FX locks, adjustments, and allocations.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.ids import new_uuid_v7
from app.modules.ai_metering.usage_cost.models import (
    CostAdjustment,
    CostAllocation,
    CostRateVersion,
    FxRateVersion,
    UsageCostEvent,
)
from app.modules.ai_metering.usage_cost.repository import UsageCostRepository


ATTRIBUTION_CATEGORIES = frozenset(
    {
        "user_delivery",
        "automatic_retry",
        "failed_attempt",
        "online_evaluation",
        "safety_check",
        "background_proactive",
        "operator_replay",
        "compensation",
        "platform_shared",
    }
)


class CostFactError(ValueError):
    """Raised when cost/usage facts violate invariants."""


@dataclass(frozen=True, slots=True)
class AttemptUsage:
    attempt_id: UUID
    input_tokens: int
    output_tokens: int
    unit: str


@dataclass(frozen=True, slots=True)
class RateQuote:
    provider: str
    model_key: str
    input_per_1k: Decimal
    output_per_1k: Decimal
    currency: str
    version: str
    raw: dict[str, Any]


@dataclass(frozen=True, slots=True)
class EstimatedCost:
    amount: Decimal
    currency: str
    rate_version: str


@dataclass(frozen=True, slots=True)
class UsageCostFact:
    id: str
    attempt_id: UUID
    status: str
    amount: Decimal | None
    currency: str
    rate_version: str | None = None
    fx_version: str | None = None
    locked_rate: dict[str, Any] | None = None
    locked_fx: dict[str, Any] | None = None
    attribution: str | None = None
    source_fact_id: str | None = None
    adjustment_reason: str | None = None


@dataclass(frozen=True, slots=True)
class UsageCostCommandResult:
    event: UsageCostEvent
    adjustment: CostAdjustment | None = None
    allocations: list[CostAllocation] | None = None
    reused: bool = False


def record_attempt_usage(
    *,
    attempt_id: UUID,
    input_tokens: int,
    output_tokens: int,
    unit: str,
) -> AttemptUsage:
    if input_tokens < 0 or output_tokens < 0:
        raise CostFactError("usage must be non-negative")
    return AttemptUsage(
        attempt_id=attempt_id,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        unit=unit,
    )


def lookup_effective_rate(
    *,
    provider: str,
    model_key: str,
    as_of: str,
    rates: list[dict[str, Any]],
) -> RateQuote:
    matches = [
        r
        for r in rates
        if r.get("provider") == provider
        and r.get("model_key") == model_key
        and str(r.get("effective_from", "")) <= as_of
    ]
    if not matches:
        raise CostFactError("unknown_rate")
    matches.sort(key=lambda r: r.get("effective_from", ""), reverse=True)
    chosen = matches[0]
    return RateQuote(
        provider=provider,
        model_key=model_key,
        input_per_1k=Decimal(str(chosen["input_per_1k"])),
        output_per_1k=Decimal(str(chosen["output_per_1k"])),
        currency=str(chosen["currency"]),
        version=str(chosen["version"]),
        raw=chosen,
    )


def estimate_usage_cost(
    *,
    input_tokens: int,
    output_tokens: int,
    rate: RateQuote,
) -> EstimatedCost:
    amount = (Decimal(input_tokens) / Decimal(1000)) * rate.input_per_1k + (
        Decimal(output_tokens) / Decimal(1000)
    ) * rate.output_per_1k
    return EstimatedCost(
        amount=amount.quantize(Decimal("0.0001")),
        currency=rate.currency,
        rate_version=rate.version,
    )


def confirm_usage_cost(
    *,
    attempt_id: UUID,
    status: str,
    amount: Decimal | None,
    currency: str,
    rate_version: str | None = None,
    fx_version: str | None = None,
    locked_rate: dict[str, Any] | None = None,
    locked_fx: dict[str, Any] | None = None,
    attribution: str | None = None,
) -> UsageCostFact:
    if attribution is not None and attribution not in ATTRIBUTION_CATEGORIES:
        raise CostFactError(f"invalid attribution: {attribution}")
    if status == "unknown" and amount is not None:
        raise CostFactError("unknown status cannot carry a numeric amount")
    if status == "confirmed" and amount is None:
        raise CostFactError("confirmed status requires amount")
    return UsageCostFact(
        id=str(uuid4()),
        attempt_id=attempt_id,
        status=status,
        amount=amount,
        currency=currency,
        rate_version=rate_version,
        fx_version=fx_version,
        locked_rate=locked_rate,
        locked_fx=locked_fx,
        attribution=attribution,
    )


def apply_adjustment(
    original: UsageCostFact,
    *,
    delta: Decimal,
    reason: str,
    idempotency_key: str,
) -> UsageCostFact:
    if original.amount is None:
        raise CostFactError("cannot adjust unknown amount")
    _ = idempotency_key
    return UsageCostFact(
        id=str(uuid4()),
        attempt_id=original.attempt_id,
        status="adjusted",
        amount=original.amount + delta,
        currency=original.currency,
        rate_version=original.rate_version,
        fx_version=original.fx_version,
        locked_rate=original.locked_rate,
        locked_fx=original.locked_fx,
        attribution=original.attribution,
        source_fact_id=original.id,
        adjustment_reason=reason,
    )


def allocate_shared_cost(
    *,
    total: Decimal,
    shares: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    weight_sum = sum(int(s["weight"]) for s in shares)
    if weight_sum <= 0:
        raise CostFactError("weights must be positive")
    parts: list[dict[str, Any]] = []
    allocated = Decimal("0")
    for index, share in enumerate(shares):
        if index == len(shares) - 1:
            amount = total - allocated
        else:
            amount = (
                total * Decimal(int(share["weight"])) / Decimal(weight_sum)
            ).quantize(Decimal("0.01"))
            allocated += amount
        parts.append({"task_id": share["task_id"], "amount": amount})
    return parts


def convert_fx(
    *,
    amount: Decimal,
    rate: Decimal,
) -> Decimal:
    return (amount * rate).quantize(Decimal("0.0000000001"))


def _rate_snapshot(rate: CostRateVersion) -> dict[str, Any]:
    return {
        "version": rate.version,
        "provider_internal_key": rate.provider_internal_key,
        "model_or_tool_key": rate.model_or_tool_key,
        "unit": rate.unit,
        "input_per_1k": str(rate.input_per_1k) if rate.input_per_1k is not None else None,
        "output_per_1k": str(rate.output_per_1k) if rate.output_per_1k is not None else None,
        "currency": rate.currency,
        "effective_from": rate.effective_from.isoformat(),
    }


def _fx_snapshot(fx: FxRateVersion) -> dict[str, Any]:
    return {
        "version": fx.version,
        "base_currency": fx.base_currency,
        "quote_currency": fx.quote_currency,
        "rate": str(fx.rate),
        "effective_from": fx.effective_from.isoformat(),
    }


class UsageCostService:
    """Append-only usage/cost recording with rate/FX lock and allocations."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = UsageCostRepository(session)

    async def lookup_rate(
        self,
        *,
        provider_internal_key: str,
        model_or_tool_key: str,
        as_of: datetime | None = None,
    ) -> CostRateVersion:
        moment = as_of or datetime.now(timezone.utc)
        rows = await self.repo.list_active_rates(
            provider_internal_key=provider_internal_key,
            model_or_tool_key=model_or_tool_key,
            as_of=moment,
        )
        if not rows:
            raise CostFactError("unknown_rate")
        return rows[0]

    async def lookup_fx(
        self,
        *,
        base_currency: str,
        quote_currency: str = "CNY",
        as_of: datetime | None = None,
    ) -> FxRateVersion:
        moment = as_of or datetime.now(timezone.utc)
        rows = await self.repo.list_active_fx(
            base_currency=base_currency,
            quote_currency=quote_currency,
            as_of=moment,
        )
        if not rows:
            raise CostFactError("unknown_fx")
        return rows[0]

    async def record_attempt(
        self,
        *,
        idempotency_key: str,
        external_attempt_id: UUID,
        input_tokens: int,
        output_tokens: int,
        provider_internal_key: str,
        model_or_tool_key: str,
        attribution: str,
        task_id: UUID | None = None,
        root_task_id: UUID | None = None,
        execution_id: UUID | None = None,
        user_id: UUID | None = None,
        subject_id: str | None = None,
        provider_request_id: str | None = None,
        as_of: datetime | None = None,
        estimate: bool = True,
    ) -> UsageCostCommandResult:
        if attribution not in ATTRIBUTION_CATEGORIES:
            raise CostFactError(f"invalid attribution: {attribution}")
        if input_tokens < 0 or output_tokens < 0:
            raise CostFactError("usage must be non-negative")

        existing = await self.repo.find_by_idempotency(idempotency_key)
        if existing is not None:
            return UsageCostCommandResult(event=existing, reused=True)

        moment = as_of or datetime.now(timezone.utc)
        rate: CostRateVersion | None = None
        fx: FxRateVersion | None = None
        original_amount: Decimal | None = None
        rmb_amount: Decimal | None = None
        locked_rate: dict[str, Any] | None = None
        locked_fx: dict[str, Any] | None = None
        cost_status = "estimated"
        original_currency: str | None = None

        if estimate:
            try:
                rate = await self.lookup_rate(
                    provider_internal_key=provider_internal_key,
                    model_or_tool_key=model_or_tool_key,
                    as_of=moment,
                )
            except CostFactError:
                # Unknown rate is an explicit gate — record attempt with unknown cost.
                cost_status = "unknown"
                rate = None
            else:
                if rate.input_per_1k is None or rate.output_per_1k is None:
                    raise CostFactError("unknown_rate")
                quote = RateQuote(
                    provider=provider_internal_key,
                    model_key=model_or_tool_key,
                    input_per_1k=rate.input_per_1k,
                    output_per_1k=rate.output_per_1k,
                    currency=rate.currency,
                    version=rate.version,
                    raw=_rate_snapshot(rate),
                )
                estimated = estimate_usage_cost(
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    rate=quote,
                )
                original_amount = estimated.amount
                original_currency = estimated.currency
                locked_rate = _rate_snapshot(rate)
                try:
                    fx = await self.lookup_fx(
                        base_currency=rate.currency, as_of=moment
                    )
                except CostFactError:
                    fx = None
                else:
                    locked_fx = _fx_snapshot(fx)
                    rmb_amount = convert_fx(amount=original_amount, rate=fx.rate)

        event = UsageCostEvent(
            id=new_uuid_v7(),
            idempotency_key=idempotency_key,
            external_attempt_id=external_attempt_id,
            task_id=task_id,
            root_task_id=root_task_id,
            execution_id=execution_id,
            user_id=user_id,
            subject_id=subject_id,
            provider_request_id=provider_request_id,
            event_status="recorded",
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            original_amount=original_amount,
            original_currency=original_currency,
            rate_version_id=rate.id if rate is not None else None,
            fx_version_id=fx.id if fx is not None else None,
            locked_rate=locked_rate,
            locked_fx=locked_fx,
            rmb_amount=rmb_amount,
            evidence_source="provider_attempt",
            cost_status=cost_status,
            attribution=attribution,
            occurred_at=moment,
            payload={
                "provider_internal_key": provider_internal_key,
                "model_or_tool_key": model_or_tool_key,
            },
        )
        await self.repo.insert_usage_cost_event(event)
        return UsageCostCommandResult(event=event)

    async def confirm(
        self,
        *,
        event_id: UUID,
        amount: Decimal | None,
        currency: str,
        idempotency_key: str,
        provider_confirmed: bool = True,
        rate_version_id: UUID | None = None,
        fx_version_id: UUID | None = None,
        locked_rate: dict[str, Any] | None = None,
        locked_fx: dict[str, Any] | None = None,
        evidence_source: str = "provider_confirmation",
    ) -> UsageCostCommandResult:
        """Append a confirmation/correction without mutating the original estimate.

        Confirmation is modeled as a new event linked via payload, preserving the
        original estimate row. Unknown confirmation keeps amount=None.
        """
        existing = await self.repo.find_by_idempotency(idempotency_key)
        if existing is not None:
            return UsageCostCommandResult(event=existing, reused=True)

        base = await self.repo.get_event(event_id)
        if base is None:
            raise CostFactError("usage cost event not found")

        if amount is None:
            cost_status = "unknown"
        elif provider_confirmed:
            cost_status = "provider_confirmed"
        else:
            cost_status = "reconciled"

        rmb_amount: Decimal | None = None
        if amount is not None and locked_fx is not None and "rate" in locked_fx:
            rmb_amount = convert_fx(amount=amount, rate=Decimal(str(locked_fx["rate"])))

        event = UsageCostEvent(
            id=new_uuid_v7(),
            idempotency_key=idempotency_key,
            external_attempt_id=base.external_attempt_id,
            platform_cost_category=base.platform_cost_category,
            task_id=base.task_id,
            root_task_id=base.root_task_id,
            execution_id=base.execution_id,
            user_id=base.user_id,
            subject_id=base.subject_id,
            provider_request_id=base.provider_request_id,
            event_status="recorded",
            input_tokens=base.input_tokens,
            output_tokens=base.output_tokens,
            cache_creation_tokens=base.cache_creation_tokens,
            cache_read_tokens=base.cache_read_tokens,
            reasoning_tokens=base.reasoning_tokens,
            embedding_units=base.embedding_units,
            rerank_units=base.rerank_units,
            searches=base.searches,
            tool_units=base.tool_units,
            storage_units=base.storage_units,
            bandwidth_units=base.bandwidth_units,
            custom_unit_name=base.custom_unit_name,
            custom_unit_quantity=base.custom_unit_quantity,
            original_amount=amount,
            original_currency=currency,
            rate_version_id=rate_version_id or base.rate_version_id,
            fx_version_id=fx_version_id or base.fx_version_id,
            locked_rate=locked_rate or base.locked_rate,
            locked_fx=locked_fx or base.locked_fx,
            rmb_amount=rmb_amount if rmb_amount is not None else base.rmb_amount,
            evidence_source=evidence_source,
            cost_status=cost_status,
            attribution=base.attribution,
            payload={"confirms_event_id": str(base.id)},
        )
        await self.repo.insert_usage_cost_event(event)
        return UsageCostCommandResult(event=event)

    async def correct(
        self,
        *,
        base_event_id: UUID,
        delta_original: Decimal,
        reason: str,
        actor_type: str = "system",
        actor_id: str | None = None,
        delta_rmb: Decimal | None = None,
        old_evidence_ref: str | None = None,
        new_evidence_ref: str | None = None,
        prior_adjustment_id: UUID | None = None,
    ) -> UsageCostCommandResult:
        base = await self.repo.get_event(base_event_id)
        if base is None:
            raise CostFactError("usage cost event not found")
        if base.original_amount is None and base.cost_status == "unknown":
            raise CostFactError("cannot adjust unknown amount")

        adjustment = CostAdjustment(
            id=new_uuid_v7(),
            base_event_id=base_event_id,
            prior_adjustment_id=prior_adjustment_id,
            old_evidence_ref=old_evidence_ref,
            new_evidence_ref=new_evidence_ref,
            delta_original=delta_original,
            delta_rmb=delta_rmb,
            reason=reason,
            actor_type=actor_type,
            actor_id=actor_id,
            reversed=False,
        )
        await self.repo.insert_adjustment(adjustment)
        return UsageCostCommandResult(event=base, adjustment=adjustment)

    async def allocate(
        self,
        *,
        source_event_id: UUID,
        shares: list[dict[str, Any]],
        rule_version: str,
    ) -> UsageCostCommandResult:
        source = await self.repo.get_event(source_event_id)
        if source is None:
            raise CostFactError("usage cost event not found")
        if source.original_amount is None:
            raise CostFactError("cannot allocate unknown amount")
        if source.cost_status not in {"provider_confirmed", "reconciled", "estimated"}:
            raise CostFactError("source cost not allocatable")

        parts = allocate_shared_cost(total=source.original_amount, shares=shares)
        weight_sum = sum(int(s["weight"]) for s in shares)
        rows: list[CostAllocation] = []
        for share, part in zip(shares, parts, strict=True):
            task_raw = part["task_id"]
            task_id = task_raw if isinstance(task_raw, UUID) else UUID(str(task_raw))
            allocated = Decimal(str(part["amount"]))
            allocated_rmb = None
            if source.rmb_amount is not None and source.original_amount != 0:
                allocated_rmb = (
                    source.rmb_amount * allocated / source.original_amount
                ).quantize(Decimal("0.0000000001"))
            rows.append(
                CostAllocation(
                    id=new_uuid_v7(),
                    source_event_id=source_event_id,
                    task_id=task_id,
                    execution_id=share.get("execution_id"),
                    rule_version=rule_version,
                    numerator=Decimal(int(share["weight"])),
                    denominator=Decimal(weight_sum),
                    allocated_original=allocated,
                    allocated_rmb=allocated_rmb,
                )
            )
        await self.repo.insert_allocations(rows)
        total = await self.repo.sum_allocations(source_event_id)
        if total != source.original_amount:
            raise CostFactError(
                f"allocation conservation failed: {total} != {source.original_amount}"
            )
        return UsageCostCommandResult(event=source, allocations=rows)


__all__ = [
    "ATTRIBUTION_CATEGORIES",
    "AttemptUsage",
    "CostFactError",
    "EstimatedCost",
    "RateQuote",
    "UsageCostCommandResult",
    "UsageCostFact",
    "UsageCostService",
    "allocate_shared_cost",
    "apply_adjustment",
    "confirm_usage_cost",
    "convert_fx",
    "estimate_usage_cost",
    "lookup_effective_rate",
    "record_attempt_usage",
]
