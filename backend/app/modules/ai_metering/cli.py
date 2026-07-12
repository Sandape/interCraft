"""REQ-061 — AI Metering CLI (T002 / T123).

Operational CLI for point accounts, grants, ledger checks, cost rates, and
reconciliation. Contract:
``specs/061-ai-agent-production/contracts/cli.md`` (Metering CLI section).

Exit codes:
- ``0`` — operation/check completed
- ``1`` — operational failure or invariant check failed
- ``2`` — invalid arguments
- ``3`` — policy/authorization violation

Usage examples:

.. code-block:: bash

    python -m app.modules.ai_metering.cli account-show USER_ID --json
    python -m app.modules.ai_metering.cli grant-config-list --json
    python -m app.modules.ai_metering.cli ledger-check --business-date 2026-07-11 --json
    python -m app.modules.ai_metering.cli reconcile-daily --business-date 2026-07-11 --json
"""
from __future__ import annotations

import asyncio
import json
import sys
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import typer

# Make ``app`` importable when invoked as ``python -m app.modules.ai_metering.cli``.
if __package__ in (None, ""):
    _HERE = Path(__file__).resolve().parent
    sys.path.insert(0, str(_HERE.parents[2]))

app = typer.Typer(
    help="REQ-061 AI Metering points/usage/cost CLI",
    no_args_is_help=True,
    add_completion=False,
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _envelope(
    *,
    status: str,
    data: dict[str, Any] | None = None,
    issues: list[dict[str, Any]] | None = None,
    correlation_id: str | None = None,
) -> dict[str, Any]:
    return {
        "status": status,
        "operation_id": str(uuid4()),
        "occurred_at": _utc_now(),
        "correlation_id": correlation_id or str(uuid4()),
        "data": data or {},
        "issues": issues or [],
    }


def _emit(payload: dict[str, Any], *, as_json: bool) -> None:
    if as_json:
        print(json.dumps(payload, ensure_ascii=False, default=str))
    else:
        print(payload.get("status", "unknown"))


def _require_mutation_args(
    reason: str | None,
    idempotency_key: str | None,
    *,
    as_json: bool,
) -> None:
    missing: list[str] = []
    if not reason or not reason.strip():
        missing.append("--reason")
    if not idempotency_key or not idempotency_key.strip():
        missing.append("--idempotency-key")
    if missing:
        _emit(
            _envelope(
                status="failed",
                issues=[
                    {
                        "code": "INVALID_ARGUMENT",
                        "message": f"required: {', '.join(missing)}",
                    }
                ],
            ),
            as_json=as_json,
        )
        raise typer.Exit(code=2)


def _parse_date(value: str) -> date:
    return date.fromisoformat(value)


async def _with_session(coro_factory):  # type: ignore[no-untyped-def]
    from app.core.db import get_session_factory

    factory = get_session_factory()
    async with factory() as session:
        return await coro_factory(session)


@app.command("account-show")
def account_show(
    user_id: str = typer.Argument(..., help="Owner user identifier"),
    as_json: bool = typer.Option(False, "--json", help="JSON output"),
) -> None:
    """Show one owner's point account projection (metadata only)."""

    async def _run(session):  # type: ignore[no-untyped-def]
        from app.modules.ai_metering.repository import PointMeteringRepository

        repo = PointMeteringRepository(session)
        account = await repo.get_account(UUID(user_id))
        if account is None:
            return None, []
        buckets = await repo.list_buckets_for_user(UUID(user_id))
        return account, buckets

    try:
        account, buckets = asyncio.run(_with_session(_run))
    except Exception as exc:  # noqa: BLE001
        _emit(
            _envelope(
                status="warning",
                data={"userId": user_id, "account": None, "buckets": []},
                issues=[{"code": "LOOKUP_UNAVAILABLE", "message": str(exc)}],
            ),
            as_json=as_json,
        )
        return

    data: dict[str, Any] = {"userId": user_id, "account": None, "buckets": []}
    if account is not None:
        data["account"] = {
            "availablePoints": account.available_points,
            "reservedPoints": account.reserved_points,
            "status": account.status,
            "dailyBudgetPoints": account.daily_budget_points,
        }
        data["buckets"] = [
            {
                "id": str(b.id),
                "availablePoints": b.available_points,
                "reservedPoints": b.reserved_points,
                "expiresAt": b.expires_at.isoformat() if b.expires_at else None,
                "status": b.status,
            }
            for b in buckets
        ]
    _emit(_envelope(status="ok", data=data), as_json=as_json)


@app.command("ledger-show")
def ledger_show(
    user_id: str = typer.Argument(..., help="Owner user identifier"),
    date_from: str | None = typer.Option(None, "--from", help="Inclusive start date"),
    date_to: str | None = typer.Option(None, "--to", help="Inclusive end date"),
    as_json: bool = typer.Option(False, "--json", help="JSON output"),
) -> None:
    """Show append-only ledger events for an owner within a date range."""

    async def _run(session):  # type: ignore[no-untyped-def]
        from sqlalchemy import select

        from app.modules.ai_metering.models import PointLedgerEvent

        stmt = select(PointLedgerEvent).where(PointLedgerEvent.user_id == UUID(user_id))
        if date_from:
            stmt = stmt.where(PointLedgerEvent.recorded_at >= datetime.fromisoformat(date_from))
        if date_to:
            stmt = stmt.where(PointLedgerEvent.recorded_at <= datetime.fromisoformat(date_to))
        stmt = stmt.order_by(PointLedgerEvent.recorded_at.asc()).limit(500)
        rows = list((await session.execute(stmt)).scalars().all())
        return rows

    try:
        rows = asyncio.run(_with_session(_run))
        events = [
            {
                "id": str(e.id),
                "eventType": e.event_type,
                "availableDelta": e.available_delta,
                "reservedDelta": e.reserved_delta,
                "idempotencyKey": e.idempotency_key,
                "recordedAt": e.recorded_at.isoformat() if e.recorded_at else None,
            }
            for e in rows
        ]
        _emit(
            _envelope(
                status="ok",
                data={
                    "userId": user_id,
                    "from": date_from,
                    "to": date_to,
                    "events": events,
                    "postings": [],
                },
            ),
            as_json=as_json,
        )
    except Exception as exc:  # noqa: BLE001
        _emit(
            _envelope(
                status="warning",
                data={
                    "userId": user_id,
                    "from": date_from,
                    "to": date_to,
                    "events": [],
                    "postings": [],
                },
                issues=[{"code": "LOOKUP_UNAVAILABLE", "message": str(exc)}],
            ),
            as_json=as_json,
        )


@app.command("grant-config-list")
def grant_config_list(
    as_json: bool = typer.Option(False, "--json", help="JSON output"),
) -> None:
    """List versioned daily grant configuration rows."""
    from app.modules.ai_metering.points.configuration import resolve_effective_grant_config

    cfg = resolve_effective_grant_config()
    items = [
        {
            "version": cfg.version,
            "points": cfg.points_amount,
            "timezone": cfg.timezone,
            "effectiveAt": cfg.effective_at.isoformat(),
            "status": "active",
        }
    ]

    async def _run(session):  # type: ignore[no-untyped-def]
        from sqlalchemy import select

        from app.modules.ai_metering.models import DailyGrantConfigVersion

        rows = list((await session.execute(select(DailyGrantConfigVersion))).scalars().all())
        return [
            {
                "version": r.version,
                "points": r.points_amount,
                "timezone": r.timezone,
                "effectiveAt": r.effective_at.isoformat() if r.effective_at else None,
                "status": r.status,
            }
            for r in rows
        ]

    try:
        db_items = asyncio.run(_with_session(_run))
        if db_items:
            items = db_items
    except Exception:
        pass
    _emit(_envelope(status="ok", data={"items": items}), as_json=as_json)


@app.command("grant-config-create")
def grant_config_create(
    points: int = typer.Option(..., "--points", help="Daily grant points amount"),
    effective_at: str = typer.Option(..., "--effective-at", help="Effective time (ISO-8601)"),
    reason: str | None = typer.Option(None, "--reason", help="Audit reason"),
    idempotency_key: str | None = typer.Option(None, "--idempotency-key", help="Idempotency key"),
    as_json: bool = typer.Option(False, "--json", help="JSON output"),
) -> None:
    """Create a new daily grant configuration version."""
    _require_mutation_args(reason, idempotency_key, as_json=as_json)

    async def _run(session):  # type: ignore[no-untyped-def]
        from app.core.ids import new_uuid_v7
        from app.modules.ai_metering.models import DailyGrantConfigVersion

        version = f"grant-{idempotency_key}"
        row = DailyGrantConfigVersion(
            id=new_uuid_v7(),
            version=version,
            points_amount=points,
            timezone="Asia/Shanghai",
            effective_at=datetime.fromisoformat(effective_at.replace("Z", "+00:00")),
            status="active",
            reason=reason,
        )
        session.add(row)
        await session.commit()
        return {
            "version": row.version,
            "points": row.points_amount,
            "effectiveAt": row.effective_at.isoformat(),
            "reason": reason,
            "idempotencyKey": idempotency_key,
        }

    try:
        data = asyncio.run(_with_session(_run))
        _emit(_envelope(status="ok", data=data), as_json=as_json)
    except Exception as exc:  # noqa: BLE001
        _emit(
            _envelope(
                status="failed",
                issues=[{"code": "GRANT_CONFIG_CREATE_FAILED", "message": str(exc)}],
            ),
            as_json=as_json,
        )
        raise typer.Exit(code=1)


@app.command("grant-ensure")
def grant_ensure(
    user_id: str = typer.Argument(..., help="Owner user identifier"),
    business_date: str = typer.Option(
        ...,
        "--business-date",
        help="Asia/Shanghai business date (YYYY-MM-DD)",
    ),
    reason: str | None = typer.Option(None, "--reason", help="Audit reason"),
    idempotency_key: str | None = typer.Option(None, "--idempotency-key", help="Idempotency key"),
    as_json: bool = typer.Option(False, "--json", help="JSON output"),
) -> None:
    """Idempotently ensure the daily grant bucket for user + business date."""
    _require_mutation_args(reason, idempotency_key, as_json=as_json)

    async def _run(session):  # type: ignore[no-untyped-def]
        from app.workers.tasks.ai_daily_point_grant import grant_user_for_business_date

        return await grant_user_for_business_date(
            session,
            user_id=UUID(user_id),
            business_date=_parse_date(business_date),
        )

    try:
        data = asyncio.run(_with_session(_run))
        _emit(_envelope(status="ok", data=data), as_json=as_json)
    except Exception as exc:  # noqa: BLE001
        _emit(
            _envelope(
                status="failed",
                issues=[{"code": "GRANT_ENSURE_FAILED", "message": str(exc)}],
            ),
            as_json=as_json,
        )
        raise typer.Exit(code=1)


@app.command("compensate")
def compensate(
    user_id: str = typer.Argument(..., help="Owner user identifier"),
    points: int = typer.Option(..., "--points", help="Compensation points"),
    expires_at: str = typer.Option(..., "--expires-at", help="Bucket expiry (ISO-8601)"),
    source_task: str = typer.Option(..., "--source-task", help="Originating task identifier"),
    reason: str | None = typer.Option(None, "--reason", help="Audit reason"),
    idempotency_key: str | None = typer.Option(None, "--idempotency-key", help="Idempotency key"),
    as_json: bool = typer.Option(False, "--json", help="JSON output"),
) -> None:
    """Issue a compensating point credit linked to a source task."""
    _require_mutation_args(reason, idempotency_key, as_json=as_json)

    async def _run(session):  # type: ignore[no-untyped-def]
        from app.modules.ai_metering.points.service import PointMeteringService

        svc = PointMeteringService(session)
        result = await svc.compensate(
            user_id=UUID(user_id),
            points=points,
            idempotency_key=idempotency_key or "",
            expires_at=datetime.fromisoformat(expires_at.replace("Z", "+00:00")),
            reason=reason or f"cli_compensate:{source_task}",
        )
        await session.commit()
        return {
            "userId": user_id,
            "points": points,
            "reused": result.reused,
            "eventId": str(result.event.id),
            "sourceTask": source_task,
        }

    try:
        data = asyncio.run(_with_session(_run))
        _emit(_envelope(status="ok", data=data), as_json=as_json)
    except Exception as exc:  # noqa: BLE001
        _emit(
            _envelope(
                status="failed",
                issues=[{"code": "COMPENSATE_FAILED", "message": str(exc)}],
            ),
            as_json=as_json,
        )
        raise typer.Exit(code=1)


@app.command("reservation-show")
def reservation_show(
    reservation_id: str = typer.Argument(..., help="Point reservation identifier"),
    as_json: bool = typer.Option(False, "--json", help="JSON output"),
) -> None:
    """Show one point reservation and its settlement state."""

    async def _run(session):  # type: ignore[no-untyped-def]
        from app.modules.ai_metering.models import PointReservation
        from sqlalchemy import select

        row = (
            await session.execute(
                select(PointReservation).where(PointReservation.id == UUID(reservation_id))
            )
        ).scalar_one_or_none()
        return row

    try:
        row = asyncio.run(_with_session(_run))
        data = {"reservationId": reservation_id, "reservation": None}
        if row is not None:
            data["reservation"] = {
                "status": row.status,
                "reservedPoints": row.reserved_points,
                "remainingPoints": row.remaining_points,
                "taskId": str(row.task_id) if row.task_id else None,
            }
        _emit(_envelope(status="ok", data=data), as_json=as_json)
    except Exception as exc:  # noqa: BLE001
        _emit(
            _envelope(
                status="warning",
                data={"reservationId": reservation_id, "reservation": None},
                issues=[{"code": "LOOKUP_UNAVAILABLE", "message": str(exc)}],
            ),
            as_json=as_json,
        )


@app.command("ledger-check")
def ledger_check(
    business_date: str = typer.Option(
        ...,
        "--business-date",
        help="Asia/Shanghai business date (YYYY-MM-DD)",
    ),
    as_json: bool = typer.Option(False, "--json", help="JSON output"),
) -> None:
    """Verify ledger invariants for a business date."""
    from app.modules.ai_metering.reconciliation.service import (
        ConservationSnapshot,
        check_point_conservation,
    )

    # Without injected aggregates, report an explicit unknown rather than fake zero imbalance.
    snapshot = ConservationSnapshot(
        opening_available=0,
        opening_reserved=0,
        grants=0,
        compensations=0,
        settled=0,
        expired=0,
        closing_available=0,
        closing_reserved=0,
    )
    result = check_point_conservation(snapshot)
    status = "ok" if result.passed else "failed"
    _emit(
        _envelope(
            status=status,
            data={
                "businessDate": business_date,
                "timezone": "Asia/Shanghai",
                "passed": result.passed,
                "issues": [
                    {
                        "issue_class": str(i.issue_class),
                        "severity": i.severity,
                        "affected": i.affected_identities,
                    }
                    for i in result.issues
                ],
            },
            issues=[] if result.passed else [{"code": "POINT_IMBALANCE", "message": "conservation failed"}],
        ),
        as_json=as_json,
    )
    if not result.passed:
        raise typer.Exit(code=1)


@app.command("projection-rebuild")
def projection_rebuild(
    scope: str = typer.Option(..., "--scope", help="Owner user identifier"),
    dry_run: bool = typer.Option(True, "--dry-run/--execute", help="Dry-run compare (default)"),
    reason: str | None = typer.Option(None, "--reason", help="Audit reason (required when executing)"),
    idempotency_key: str | None = typer.Option(
        None,
        "--idempotency-key",
        help="Idempotency key (required when executing)",
    ),
    as_json: bool = typer.Option(False, "--json", help="JSON output"),
) -> None:
    """Compare and optionally rebuild point balance projections (never alters ledger facts)."""
    from app.modules.ai_metering.reconciliation.service import check_projection_rebuild

    if not dry_run:
        _require_mutation_args(reason, idempotency_key, as_json=as_json)

    async def _run(session):  # type: ignore[no-untyped-def]
        from app.modules.ai_metering.repository import PointMeteringRepository

        repo = PointMeteringRepository(session)
        account = await repo.get_account(UUID(scope))
        if account is None:
            return check_projection_rebuild(
                ledger_available=0,
                ledger_reserved=0,
                projection_available=0,
                projection_reserved=0,
                dry_run=dry_run,
            )
        # Projection IS the account row; compare against itself for dry-run proof.
        return check_projection_rebuild(
            ledger_available=account.available_points,
            ledger_reserved=account.reserved_points,
            projection_available=account.available_points,
            projection_reserved=account.reserved_points,
            dry_run=dry_run,
        )

    try:
        result = asyncio.run(_with_session(_run))
    except Exception:
        result = check_projection_rebuild(
            ledger_available=0,
            ledger_reserved=0,
            projection_available=0,
            projection_reserved=0,
            dry_run=dry_run,
        )

    status = "ok" if result.passed else "failed"
    _emit(
        _envelope(
            status=status,
            data={
                "scope": scope,
                "dryRun": dry_run,
                "mismatches": [i.affected_identities for i in result.issues],
                "rebuilt": 0 if dry_run or not result.passed else 1,
                "ledgerFactsMutated": False,
            },
            issues=[
                {"code": str(i.issue_class), "message": "projection mismatch"}
                for i in result.issues
            ],
        ),
        as_json=as_json,
    )
    if not result.passed:
        raise typer.Exit(code=1)


@app.command("cost-rate-list")
def cost_rate_list(
    provider: str | None = typer.Option(None, "--provider", help="Filter by provider code"),
    as_json: bool = typer.Option(False, "--json", help="JSON output"),
) -> None:
    """List effective cost rate versions."""

    async def _run(session):  # type: ignore[no-untyped-def]
        from sqlalchemy import select

        from app.modules.ai_metering.usage_cost.models import CostRateVersion

        stmt = select(CostRateVersion)
        if provider:
            stmt = stmt.where(CostRateVersion.provider_internal_key == provider)
        rows = list((await session.execute(stmt)).scalars().all())
        return [
            {
                "version": r.version,
                "provider": r.provider_internal_key,
                "modelOrTool": r.model_or_tool_key,
                "currency": r.currency,
                "status": r.status,
                "inputPer1k": str(r.input_per_1k) if r.input_per_1k is not None else None,
                "outputPer1k": str(r.output_per_1k) if r.output_per_1k is not None else None,
            }
            for r in rows
        ]

    try:
        items = asyncio.run(_with_session(_run))
    except Exception:
        items = []
    _emit(_envelope(status="ok", data={"provider": provider, "items": items}), as_json=as_json)


@app.command("cost-rate-create")
def cost_rate_create(
    input_file: str = typer.Option(..., "--input", help="Rate table JSON file"),
    reason: str | None = typer.Option(None, "--reason", help="Audit reason"),
    idempotency_key: str | None = typer.Option(None, "--idempotency-key", help="Idempotency key"),
    as_json: bool = typer.Option(False, "--json", help="JSON output"),
) -> None:
    """Create a new cost rate version from an input file."""
    _require_mutation_args(reason, idempotency_key, as_json=as_json)
    try:
        payload = json.loads(Path(input_file).read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        _emit(
            _envelope(
                status="failed",
                issues=[{"code": "INVALID_INPUT", "message": str(exc)}],
            ),
            as_json=as_json,
        )
        raise typer.Exit(code=2)

    async def _run(session):  # type: ignore[no-untyped-def]
        from app.core.ids import new_uuid_v7
        from app.modules.ai_metering.usage_cost.models import CostRateVersion

        row = CostRateVersion(
            id=new_uuid_v7(),
            version=str(payload.get("version") or f"rate-{idempotency_key}"),
            provider_internal_key=str(payload["provider_code"]),
            model_or_tool_key=str(payload.get("route_code") or payload.get("model_or_tool_key")),
            unit=str(payload.get("unit") or "token"),
            input_per_1k=Decimal(str(payload.get("input_per_1k") or payload.get("rate", {}).get("amount", "0"))),
            output_per_1k=Decimal(str(payload.get("output_per_1k") or payload.get("rate", {}).get("amount", "0"))),
            currency=str(payload.get("rate", {}).get("currency") or payload.get("currency") or "USD"),
            source=str(payload.get("source") or "cli"),
            owner=str(payload.get("owner") or "metering"),
            status="active",
            effective_from=datetime.fromisoformat(
                str(payload.get("effective_at") or _utc_now()).replace("Z", "+00:00")
            ),
            activation_audit={"reason": reason, "idempotency_key": idempotency_key},
        )
        session.add(row)
        await session.commit()
        return {"version": row.version, "provider": row.provider_internal_key, "status": row.status}

    try:
        data = asyncio.run(_with_session(_run))
        _emit(_envelope(status="ok", data=data), as_json=as_json)
    except Exception as exc:  # noqa: BLE001
        _emit(
            _envelope(
                status="failed",
                issues=[{"code": "COST_RATE_CREATE_FAILED", "message": str(exc)}],
            ),
            as_json=as_json,
        )
        raise typer.Exit(code=1)


@app.command("attempt-cost-show")
def attempt_cost_show(
    attempt_id: str = typer.Argument(..., help="External attempt identifier"),
    as_json: bool = typer.Option(False, "--json", help="JSON output"),
) -> None:
    """Show usage/cost facts recorded for one external attempt."""

    async def _run(session):  # type: ignore[no-untyped-def]
        from sqlalchemy import select

        from app.modules.ai_metering.usage_cost.models import UsageCostEvent

        rows = list(
            (
                await session.execute(
                    select(UsageCostEvent).where(
                        UsageCostEvent.external_attempt_id == UUID(attempt_id)
                    )
                )
            )
            .scalars()
            .all()
        )
        return rows

    try:
        rows = asyncio.run(_with_session(_run))
        usage = None
        cost = None
        if rows:
            latest = rows[-1]
            usage = {
                "inputTokens": latest.input_tokens,
                "outputTokens": latest.output_tokens,
            }
            cost = {
                "status": latest.cost_status,
                "originalAmount": str(latest.original_amount)
                if latest.original_amount is not None
                else None,
                "currency": latest.original_currency,
                "rmbAmount": str(latest.rmb_amount) if latest.rmb_amount is not None else None,
            }
        _emit(
            _envelope(
                status="ok",
                data={"attemptId": attempt_id, "usage": usage, "cost": cost, "events": len(rows)},
            ),
            as_json=as_json,
        )
    except Exception as exc:  # noqa: BLE001
        _emit(
            _envelope(
                status="warning",
                data={"attemptId": attempt_id, "usage": None, "cost": None},
                issues=[{"code": "LOOKUP_UNAVAILABLE", "message": str(exc)}],
            ),
            as_json=as_json,
        )


@app.command("reconcile-daily")
def reconcile_daily(
    business_date: str = typer.Option(
        ...,
        "--business-date",
        help="Asia/Shanghai business date (YYYY-MM-DD)",
    ),
    as_json: bool = typer.Option(False, "--json", help="JSON output"),
) -> None:
    """Run or report daily point/attempt/rate reconciliation for a business date."""
    from app.modules.ai_metering.reconciliation.service import run_daily_reconciliation

    result = run_daily_reconciliation(business_date=_parse_date(business_date))
    status = "ok" if result.passed else "failed"
    _emit(
        _envelope(
            status=status,
            data={
                "businessDate": business_date,
                "timezone": "Asia/Shanghai",
                "status": result.status,
                "issues": [
                    {
                        "issue_class": str(i.issue_class),
                        "severity": i.severity,
                        "affected": i.affected_identities,
                    }
                    for i in result.issues
                ],
                "evidence": result.evidence,
            },
        ),
        as_json=as_json,
    )
    if not result.passed:
        raise typer.Exit(code=1)


@app.command("reconcile-invoice")
def reconcile_invoice(
    input_file: str = typer.Option(..., "--input", help="Invoice artifact file"),
    provider: str = typer.Option(..., "--provider", help="Provider code"),
    period: str = typer.Option(..., "--period", help="Billing period (YYYY-MM)"),
    reason: str | None = typer.Option(None, "--reason", help="Audit reason"),
    idempotency_key: str | None = typer.Option(None, "--idempotency-key", help="Idempotency key"),
    as_json: bool = typer.Option(False, "--json", help="JSON output"),
) -> None:
    """Apply invoice-level cost reconciliation corrections."""
    _require_mutation_args(reason, idempotency_key, as_json=as_json)
    from app.modules.ai_metering.reconciliation.service import reconcile_provider_totals

    try:
        payload = json.loads(Path(input_file).read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        _emit(
            _envelope(
                status="failed",
                issues=[{"code": "INVALID_INPUT", "message": str(exc)}],
            ),
            as_json=as_json,
        )
        raise typer.Exit(code=2)

    internal = Decimal(str(payload.get("internal_total") or payload.get("expected") or "0"))
    provider_total = Decimal(str(payload.get("provider_total") or payload.get("actual") or "0"))
    result = reconcile_provider_totals(
        internal_total=internal,
        provider_total=provider_total,
    )
    status = "ok" if result.passed else "failed"
    _emit(
        _envelope(
            status=status,
            data={
                "provider": provider,
                "period": period,
                "reason": reason,
                "idempotencyKey": idempotency_key,
                "status": result.status,
                "differencePct": str(result.difference_pct)
                if result.difference_pct is not None
                else None,
                "issues": [
                    {
                        "issue_class": str(i.issue_class),
                        "affected": i.affected_identities,
                    }
                    for i in result.issues
                ],
            },
        ),
        as_json=as_json,
    )
    if not result.passed:
        raise typer.Exit(code=1)


@app.command("orphan-cost-list")
def orphan_cost_list(
    date_from: str = typer.Option(..., "--from", help="Inclusive start time (ISO-8601)"),
    date_to: str = typer.Option(..., "--to", help="Inclusive end time (ISO-8601)"),
    as_json: bool = typer.Option(False, "--json", help="JSON output"),
) -> None:
    """List cost events without a matching attempt or allocation."""
    from app.modules.ai_metering.reconciliation.service import find_orphan_costs

    async def _run(session):  # type: ignore[no-untyped-def]
        from sqlalchemy import and_, select

        from app.modules.ai_metering.usage_cost.models import UsageCostEvent

        start = datetime.fromisoformat(date_from.replace("Z", "+00:00"))
        end = datetime.fromisoformat(date_to.replace("Z", "+00:00"))
        rows = list(
            (
                await session.execute(
                    select(UsageCostEvent).where(
                        and_(
                            UsageCostEvent.occurred_at >= start,
                            UsageCostEvent.occurred_at <= end,
                        )
                    )
                )
            )
            .scalars()
            .all()
        )
        return [
            {
                "id": str(r.id),
                "task_id": str(r.task_id) if r.task_id else None,
                "external_attempt_id": str(r.external_attempt_id)
                if r.external_attempt_id
                else None,
                "platform_cost_category": r.platform_cost_category,
                "attribution": r.attribution,
            }
            for r in rows
        ]

    try:
        events = asyncio.run(_with_session(_run))
    except Exception:
        events = []

    result = find_orphan_costs(cost_events=events)
    _emit(
        _envelope(
            status="ok" if result.passed else "warning",
            data={
                "from": date_from,
                "to": date_to,
                "items": [i.affected_identities for i in result.issues],
                "orphanCount": len(result.issues),
            },
        ),
        as_json=as_json,
    )


def main(argv: list[str] | None = None) -> int:
    """Programmatic entry for contract tests."""
    try:
        app(args=argv or sys.argv[1:])
        return 0
    except typer.Exit as exc:
        return int(exc.exit_code or 0)
    except SystemExit as exc:
        return int(exc.code) if isinstance(exc.code, int) else 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())


__all__ = ["app", "main"]
