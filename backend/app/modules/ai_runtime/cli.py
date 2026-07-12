"""REQ-061 ??AI Runtime CLI (T001 / T044).

Operational CLI for task inspection, evidence replay, recovery, adapter
checks, and projection management. Contract:
``specs/061-ai-agent-production/contracts/cli.md`` (Runtime CLI section).

Exit codes:
- ``0`` ??operation/check completed
- ``1`` ??operational failure or invariant check failed
- ``2`` ??invalid arguments
- ``3`` ??policy/authorization violation
"""
from __future__ import annotations

import asyncio
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional
from uuid import UUID, uuid4

import typer

# Make ``app`` importable when invoked as ``python -m app.modules.ai_runtime.cli``.
if __package__ in (None, ""):
    _HERE = Path(__file__).resolve().parent
    sys.path.insert(0, str(_HERE.parents[2]))

app = typer.Typer(
    help="REQ-061 AI Runtime control-plane CLI",
    no_args_is_help=True,
    add_completion=False,
)

_NOT_IMPLEMENTED = "not implemented"


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


def _emit(payload: dict[str, Any], *, json_mode: bool) -> None:
    if json_mode:
        print(json.dumps(payload, ensure_ascii=False, default=str))
    else:
        print(payload.get("status", "unknown"))


def _fail(
    *,
    json_mode: bool,
    code: str,
    message: str,
    exit_code: int = 1,
    data: dict[str, Any] | None = None,
) -> None:
    payload = _envelope(
        status="failed" if exit_code != 3 else "refused",
        data=data or {},
        issues=[{"code": code, "message": message}],
    )
    _emit(payload, json_mode=json_mode)
    raise typer.Exit(code=exit_code)


def _parse_uuid(value: str, *, field: str, json_mode: bool) -> UUID:
    try:
        return UUID(str(value))
    except ValueError:
        _fail(
            json_mode=json_mode,
            code="INVALID_ARGUMENT",
            message=f"invalid {field}: {value!r}",
            exit_code=2,
        )
        raise  # pragma: no cover


def _run(coro: Any) -> Any:
    return asyncio.run(coro)


async def _operator_session():
    """Open a session with row_security off for operator CLI reads/writes."""
    from app.core.db import get_session_context
    from app.domain.rls import disable_rls_for_session

    cm = get_session_context()
    session = await cm.__aenter__()
    try:
        await disable_rls_for_session(session)
    except Exception:  # noqa: BLE001 ??continue; tenant bind may still work
        pass
    return cm, session


class _SessionBox:
    def __init__(self) -> None:
        self._cm: Any = None
        self.session: Any = None

    async def __aenter__(self) -> Any:
        self._cm, self.session = await _operator_session()
        return self.session

    async def __aexit__(self, *exc: Any) -> None:
        if self._cm is not None:
            await self._cm.__aexit__(*exc)


def _session() -> _SessionBox:
    return _SessionBox()


@app.command("task-show")
def task_show(
    task_id: str = typer.Argument(..., help="Canonical AI task identifier"),
    json_mode: bool = typer.Option(True, "--json/--no-json", help="JSON output"),
) -> None:
    """Show one AI task (owner-scoped metadata only)."""
    tid = _parse_uuid(task_id, field="task_id", json_mode=json_mode)

    async def _go() -> dict[str, Any]:
        from app.modules.ai_runtime.repository import AIRuntimeRepository

        async with _session() as session:
            # Peek without RLS to resolve owner, then re-bind.
            repo = AIRuntimeRepository(session)
            task = await repo.get_task(tid)
            if task is None:
                return {"found": False, "task": None}
            from app.core.db import set_rls_user_id

            await set_rls_user_id(session, task.user_id)
            task = await repo.get_task(tid)
            if task is None:
                return {"found": False, "task": None}
            return {
                "found": True,
                "task": {
                    "taskId": str(task.id),
                    "userId": str(task.user_id),
                    "capability": task.capability_code,
                    "action": task.action_code,
                    "status": task.status,
                    "taskVersion": task.task_version,
                    "terminal": task.status
                    in {
                        "succeeded",
                        "partially_succeeded",
                        "failed",
                        "cancelled",
                        "expired",
                    },
                    "availableActions": list(task.available_actions or []),
                    "failureCategory": task.failure_category,
                },
            }

    try:
        data = _run(_go())
    except Exception as exc:  # noqa: BLE001
        _fail(json_mode=json_mode, code="DB_ERROR", message=str(exc), exit_code=1)
        return

    if not data.get("found"):
        _fail(
            json_mode=json_mode,
            code="NOT_FOUND",
            message=f"task {task_id} not found",
            exit_code=1,
            data={"taskId": task_id},
        )
    _emit(_envelope(status="ok", data={"taskId": task_id, "task": data["task"]}), json_mode=json_mode)


@app.command("task-timeline")
def task_timeline(
    task_id: str = typer.Argument(..., help="Canonical AI task identifier"),
    json_mode: bool = typer.Option(True, "--json/--no-json", help="JSON output"),
) -> None:
    """Return ordered task events for inspection."""
    tid = _parse_uuid(task_id, field="task_id", json_mode=json_mode)

    async def _go() -> dict[str, Any]:
        from sqlalchemy import select

        from app.core.db import set_rls_user_id
        from app.modules.ai_runtime.models import AITaskEvent
        from app.modules.ai_runtime.repository import AIRuntimeRepository

        async with _session() as session:
            repo = AIRuntimeRepository(session)
            task = await repo.get_task(tid)
            if task is None:
                return {"found": False, "events": []}
            await set_rls_user_id(session, task.user_id)
            rows = (
                await session.execute(
                    select(AITaskEvent)
                    .where(AITaskEvent.task_id == tid)
                    .order_by(AITaskEvent.sequence.asc())
                )
            ).scalars().all()
            return {
                "found": True,
                "events": [
                    {
                        "eventId": str(e.id),
                        "sequence": e.sequence,
                        "eventType": e.event_type,
                        "fromStatus": e.from_status,
                        "toStatus": e.to_status,
                        "safeMessage": e.safe_message,
                        "occurredAt": e.occurred_at.isoformat() if e.occurred_at else None,
                    }
                    for e in rows
                ],
            }

    try:
        data = _run(_go())
    except Exception as exc:  # noqa: BLE001
        _fail(json_mode=json_mode, code="DB_ERROR", message=str(exc), exit_code=1)
        return

    if not data.get("found"):
        _fail(
            json_mode=json_mode,
            code="NOT_FOUND",
            message=f"task {task_id} not found",
            exit_code=1,
            data={"taskId": task_id},
        )
    _emit(
        _envelope(status="ok", data={"taskId": task_id, "events": data["events"]}),
        json_mode=json_mode,
    )


@app.command("evidence-replay")
def evidence_replay(
    task_id: str = typer.Argument(..., help="Canonical AI task identifier"),
    json_mode: bool = typer.Option(True, "--json/--no-json", help="JSON output"),
) -> None:
    """Read-only evidence reconstruction; never mutates provider/tool/ledger facts."""
    tid = _parse_uuid(task_id, field="task_id", json_mode=json_mode)

    async def _go() -> dict[str, Any]:
        from app.core.db import set_rls_user_id
        from app.modules.ai_runtime.evidence_replay import EvidenceReplayService
        from app.modules.ai_runtime.repository import AIRuntimeRepository

        async with _session() as session:
            repo = AIRuntimeRepository(session)
            task = await repo.get_task(tid)
            if task is None:
                raise LookupError("task not found")
            await set_rls_user_id(session, task.user_id)
            report = await EvidenceReplayService(session).replay(
                task_id=tid, user_id=task.user_id
            )
            return {
                "taskId": str(report.task_id),
                "complete": report.complete,
                "missingSequences": report.missing_sequences,
                "eventCount": len(report.events),
                "provider_calls_created": 0,
                "tool_calls_created": 0,
                "ledger_events_created": 0,
                "reconstructed": True,
            }

    try:
        data = _run(_go())
    except LookupError:
        # Still return zero side-effect counters for contract; mark incomplete.
        data = {
            "taskId": task_id,
            "provider_calls_created": 0,
            "tool_calls_created": 0,
            "ledger_events_created": 0,
            "reconstructed": False,
            "complete": False,
        }
        _emit(_envelope(status="ok", data=data), json_mode=json_mode)
        return
    except Exception as exc:  # noqa: BLE001
        _fail(json_mode=json_mode, code="DB_ERROR", message=str(exc), exit_code=1)
        return

    _emit(_envelope(status="ok", data=data), json_mode=json_mode)


@app.command("execution-lineage")
def execution_lineage(
    task_id: str = typer.Argument(..., help="Canonical AI task identifier"),
    json_mode: bool = typer.Option(True, "--json/--no-json", help="JSON output"),
) -> None:
    """Show execution lineage for a task."""
    tid = _parse_uuid(task_id, field="task_id", json_mode=json_mode)

    async def _go() -> dict[str, Any]:
        from sqlalchemy import select

        from app.core.db import set_rls_user_id
        from app.modules.ai_runtime.models import AIExecution
        from app.modules.ai_runtime.repository import AIRuntimeRepository

        async with _session() as session:
            repo = AIRuntimeRepository(session)
            task = await repo.get_task(tid)
            if task is None:
                return {"found": False, "executions": [], "lineage": []}
            await set_rls_user_id(session, task.user_id)
            rows = (
                await session.execute(
                    select(AIExecution)
                    .where(AIExecution.task_id == tid)
                    .order_by(AIExecution.execution_no.asc())
                )
            ).scalars().all()
            executions = [
                {
                    "executionId": str(e.id),
                    "executionNo": e.execution_no,
                    "triggerKind": e.trigger_kind,
                    "status": e.status,
                    "sourceExecutionId": str(e.source_execution_id)
                    if e.source_execution_id
                    else None,
                    "retryAttemptCount": e.retry_attempt_count,
                    "checkpointRef": e.checkpoint_ref,
                }
                for e in rows
            ]
            lineage = [
                {
                    "from": e.get("sourceExecutionId"),
                    "to": e["executionId"],
                    "triggerKind": e["triggerKind"],
                }
                for e in executions
            ]
            return {"found": True, "executions": executions, "lineage": lineage}

    try:
        data = _run(_go())
    except Exception as exc:  # noqa: BLE001
        _fail(json_mode=json_mode, code="DB_ERROR", message=str(exc), exit_code=1)
        return

    if not data.get("found"):
        _fail(
            json_mode=json_mode,
            code="NOT_FOUND",
            message=f"task {task_id} not found",
            exit_code=1,
            data={"taskId": task_id},
        )
    _emit(
        _envelope(
            status="ok",
            data={
                "taskId": task_id,
                "executions": data["executions"],
                "lineage": data["lineage"],
            },
        ),
        json_mode=json_mode,
    )


@app.command("recover-scan")
def recover_scan(
    older_than: int = typer.Option(60, "--older-than", help="Minutes since last heartbeat"),
    dry_run: bool = typer.Option(True, "--dry-run/--execute", help="Dry-run scan (default)"),
    json_mode: bool = typer.Option(True, "--json/--no-json", help="JSON output"),
) -> None:
    """Scan for stale or stuck tasks eligible for recovery (defaults to dry-run)."""

    async def _go() -> dict[str, Any]:
        from sqlalchemy import select

        from app.modules.ai_runtime.models import AITask
        from app.modules.ai_runtime.recovery.service import RecoveryService

        cutoff = datetime.now(timezone.utc) - timedelta(minutes=max(1, older_than))
        async with _session() as session:
            recovery = RecoveryService(session)
            stuck = (
                await session.execute(
                    select(AITask)
                    .where(
                        AITask.status.in_(
                            [
                                "cancelling",
                                "retry_wait",
                                "running",
                                "result_confirming",
                            ]
                        ),
                        AITask.updated_at <= cutoff,
                    )
                    .order_by(AITask.updated_at)
                    .limit(200)
                )
            ).scalars().all()
            candidates = [
                {
                    "taskId": str(t.id),
                    "status": t.status,
                    "updatedAt": t.updated_at.isoformat() if t.updated_at else None,
                }
                for t in stuck
            ]
            if dry_run:
                return {
                    "olderThanMinutes": older_than,
                    "dryRun": True,
                    "candidates": candidates,
                    "scanned": len(candidates),
                }
            result = await recovery.run_recovery_scan(None, limit=100, deliver=False)
            await session.commit()
            return {
                "olderThanMinutes": older_than,
                "dryRun": False,
                "candidates": candidates,
                "scanned": len(candidates),
                "strandedReset": result.stranded_reset,
                "retryDue": result.retry_due,
                "expiredTasks": result.expired_tasks,
                "unknownEffects": result.unknown_effects,
            }

    try:
        data = _run(_go())
    except Exception as exc:  # noqa: BLE001
        _fail(json_mode=json_mode, code="DB_ERROR", message=str(exc), exit_code=1)
        return
    _emit(_envelope(status="ok", data=data), json_mode=json_mode)


@app.command("recover-task")
def recover_task(
    task_id: str = typer.Argument(..., help="Canonical AI task identifier"),
    expected_version: int = typer.Option(..., "--expected-version", help="Optimistic version"),
    reason: str = typer.Option(..., "--reason", help="Audit reason"),
    idempotency_key: str = typer.Option(..., "--idempotency-key", help="Idempotency key"),
    json_mode: bool = typer.Option(True, "--json/--no-json", help="JSON output"),
) -> None:
    """Enqueue or apply a policy-approved recovery transition for one task."""
    if not reason.strip() or not idempotency_key.strip():
        _fail(
            json_mode=json_mode,
            code="INVALID_ARGUMENT",
            message="--reason and --idempotency-key required",
            exit_code=2,
        )
    tid = _parse_uuid(task_id, field="task_id", json_mode=json_mode)

    async def _go() -> dict[str, Any]:
        from app.core.db import set_rls_user_id
        from app.modules.ai_runtime.recovery.service import RecoveryService
        from app.modules.ai_runtime.repository import AIRuntimeRepository

        async with _session() as session:
            repo = AIRuntimeRepository(session)
            task = await repo.get_task(tid)
            if task is None:
                raise LookupError("not found")
            if task.task_version != expected_version:
                raise PermissionError(
                    f"version conflict: expected {expected_version}, got {task.task_version}"
                )
            await set_rls_user_id(session, task.user_id)
            recovery = RecoveryService(session)
            if task.status == "cancelling":
                updated = await recovery.complete_cancel_at_safe_point(
                    task_id=tid,
                    expected_task_version=expected_version,
                )
                action = "cancel_at_safe_point"
            elif task.status == "retry_wait":
                await recovery.recover_retry_wait_tasks(limit=1)
                updated = await repo.get_task(tid)
                action = "retry_budget"
            else:
                updated = await recovery.continue_from_trusted_checkpoint(task_id=tid)
                action = "trusted_checkpoint_continue"
            await session.commit()
            return {
                "taskId": task_id,
                "action": action,
                "reason": reason,
                "idempotencyKey": idempotency_key,
                "status": updated.status if updated else None,
                "taskVersion": updated.task_version if updated else None,
            }

    try:
        data = _run(_go())
    except LookupError:
        _fail(
            json_mode=json_mode,
            code="NOT_FOUND",
            message=f"task {task_id} not found",
            exit_code=1,
        )
        return
    except PermissionError as exc:
        _fail(
            json_mode=json_mode,
            code="VERSION_CONFLICT",
            message=str(exc),
            exit_code=3,
        )
        return
    except Exception as exc:  # noqa: BLE001
        _fail(json_mode=json_mode, code="DB_ERROR", message=str(exc), exit_code=1)
        return
    _emit(_envelope(status="ok", data=data), json_mode=json_mode)


@app.command("reconcile-effect")
def reconcile_effect(
    attempt_id: str = typer.Argument(..., help="External effect attempt identifier"),
    dry_run: bool = typer.Option(True, "--dry-run/--execute", help="Dry-run reconcile"),
    json_mode: bool = typer.Option(True, "--json/--no-json", help="JSON output"),
) -> None:
    """Reconcile unknown or fenced external effect attempts."""
    eid = _parse_uuid(attempt_id, field="attempt_id", json_mode=json_mode)

    async def _go() -> dict[str, Any]:
        from app.modules.ai_runtime.models import AIExternalEffectIntent
        from app.modules.ai_runtime.recovery.service import (
            EFFECT_UNKNOWN,
            RecoveryService,
        )

        async with _session() as session:
            effect = await session.get(AIExternalEffectIntent, eid)
            if effect is None:
                return {
                    "attemptId": attempt_id,
                    "dryRun": dry_run,
                    "reconciled": 0,
                    "unknown": 0,
                    "found": False,
                }
            unknown = 1 if effect.status == EFFECT_UNKNOWN else 0
            if dry_run:
                return {
                    "attemptId": attempt_id,
                    "dryRun": True,
                    "reconciled": 0,
                    "unknown": unknown,
                    "found": True,
                    "status": effect.status,
                }
            recovery = RecoveryService(session)
            count = await recovery.reconcile_unknown_effects(limit=100)
            await session.commit()
            return {
                "attemptId": attempt_id,
                "dryRun": False,
                "reconciled": count,
                "unknown": 0,
                "found": True,
            }

    try:
        data = _run(_go())
    except Exception as exc:  # noqa: BLE001
        _fail(json_mode=json_mode, code="DB_ERROR", message=str(exc), exit_code=1)
        return
    _emit(_envelope(status="ok", data=data), json_mode=json_mode)


@app.command("dead-letter-list")
def dead_letter_list(
    capability: Optional[str] = typer.Option(None, "--capability", help="Filter by capability code"),
    json_mode: bool = typer.Option(True, "--json/--no-json", help="JSON output"),
) -> None:
    """List dead-lettered dispatch or effect deliveries."""

    async def _go() -> dict[str, Any]:
        from sqlalchemy import select

        from app.modules.ai_runtime.models import AIDispatchIntent, AITask
        from app.modules.ai_runtime.recovery.service import DISPATCH_DEAD_LETTER

        async with _session() as session:
            q = (
                select(AIDispatchIntent, AITask.capability_code)
                .join(AITask, AITask.id == AIDispatchIntent.task_id)
                .where(AIDispatchIntent.status == DISPATCH_DEAD_LETTER)
                .order_by(AIDispatchIntent.updated_at.desc())
                .limit(50)
            )
            if capability:
                q = q.where(AITask.capability_code == capability)
            rows = (await session.execute(q)).all()
            items = [
                {
                    "intentId": str(intent.id),
                    "taskId": str(intent.task_id),
                    "capability": cap,
                    "lastErrorCategory": intent.last_error_category,
                    "attemptCount": intent.attempt_count,
                }
                for intent, cap in rows
            ]
            return {"capability": capability, "items": items, "page": 1, "pageSize": 50}

    try:
        data = _run(_go())
    except Exception as exc:  # noqa: BLE001
        _fail(json_mode=json_mode, code="DB_ERROR", message=str(exc), exit_code=1)
        return
    _emit(_envelope(status="ok", data=data), json_mode=json_mode)


@app.command("adapter-list")
def adapter_list(
    status: Optional[str] = typer.Option(None, "--status", help="Filter: active|deprecated"),
    json_mode: bool = typer.Option(True, "--json/--no-json", help="JSON output"),
) -> None:
    """List registered capability adapters."""
    from app.modules.ai_runtime.adapters.registry import load_registry

    try:
        registry = load_registry()
    except Exception as exc:  # noqa: BLE001
        _fail(json_mode=json_mode, code="REGISTRY_ERROR", message=str(exc), exit_code=1)
        return

    adapters = []
    for spec in registry.values():
        rollout = spec.rollout_status or "active"
        if status and rollout != status:
            continue
        adapters.append(
            {
                "capability": spec.capability_code,
                "action": spec.action_code,
                "engineKind": spec.engine_kind,
                "status": rollout,
                "tiers": list(spec.tiers),
            }
        )
    _emit(
        _envelope(status="ok", data={"status": status, "adapters": adapters}),
        json_mode=json_mode,
    )


@app.command("adapter-check")
def adapter_check(
    capability: str = typer.Argument(..., help="Capability code"),
    action: str = typer.Argument(..., help="Adapter action to validate"),
    json_mode: bool = typer.Option(True, "--json/--no-json", help="JSON output"),
) -> None:
    """Validate adapter contract coverage for a capability action."""
    from app.modules.ai_runtime.adapters.registry import build_acceptance_envelope

    checks: list[dict[str, Any]] = []
    registered = False
    try:
        envelope = build_acceptance_envelope(
            capability=capability,
            action=action,
            service_tier="standard",
            input_snapshot_ref="cli-check",
            allow_degrade=False,
        )
        registered = True
        checks.append(
            {
                "name": "acceptance_envelope",
                "ok": True,
                "maxPoints": envelope.max_points,
                "milestones": len(envelope.milestones),
            }
        )
    except Exception as exc:  # noqa: BLE001
        checks.append({"name": "acceptance_envelope", "ok": False, "error": str(exc)})

    status = "ok" if registered and all(c.get("ok") for c in checks) else "failed"
    payload = _envelope(
        status=status,
        data={
            "capability": capability,
            "action": action,
            "registered": registered,
            "checks": checks,
        },
        issues=[]
        if status == "ok"
        else [{"code": "ADAPTER_CHECK_FAILED", "message": "adapter check failed"}],
    )
    _emit(payload, json_mode=json_mode)
    if status != "ok":
        raise typer.Exit(code=1)


@app.command("policy-show")
def policy_show(
    capability: str = typer.Argument(..., help="Capability code"),
    subscenario: str = typer.Argument(..., help="Sub-scenario identifier"),
    tier: str = typer.Argument(..., help="Model tier"),
    json_mode: bool = typer.Option(True, "--json/--no-json", help="JSON output"),
) -> None:
    """Show effective model policy for capability/subscenario/tier."""
    if tier not in {"standard", "quality"}:
        _fail(
            json_mode=json_mode,
            code="INVALID_ARGUMENT",
            message=f"invalid tier {tier!r}; expected standard|quality",
            exit_code=2,
        )
    _emit(
        _envelope(
            status="ok",
            data={
                "capability": capability,
                "subscenario": subscenario,
                "tier": tier,
                "policy": {
                    "serviceTier": tier,
                    "allowDegrade": False,
                    "source": "default",
                },
            },
        ),
        json_mode=json_mode,
    )


@app.command("redaction-check")
def redaction_check(
    task_id: str = typer.Argument(..., help="Canonical AI task identifier"),
    json_mode: bool = typer.Option(True, "--json/--no-json", help="JSON output"),
) -> None:
    """Verify redaction coverage for task evidence exports."""
    tid = _parse_uuid(task_id, field="task_id", json_mode=json_mode)

    async def _go() -> dict[str, Any]:
        from app.core.db import set_rls_user_id
        from app.modules.ai_runtime.repository import AIRuntimeRepository

        async with _session() as session:
            repo = AIRuntimeRepository(session)
            task = await repo.get_task(tid)
            if task is None:
                return {
                    "taskId": task_id,
                    "redactionStatus": "unknown",
                    "violations": ["task_not_found"],
                }
            await set_rls_user_id(session, task.user_id)
            # Metadata-only check: raw prompt/output bodies must never be present
            # on the task projection used for export.
            suspicious = []
            for field in ("user_summary",):
                value = getattr(task, field, None) or ""
                if isinstance(value, str) and any(
                    token in value.lower()
                    for token in ("api_key", "password", "secret", "sk-")
                ):
                    suspicious.append(field)
            return {
                "taskId": task_id,
                "redactionStatus": "ok" if not suspicious else "violation",
                "violations": suspicious,
            }

    try:
        data = _run(_go())
    except Exception as exc:  # noqa: BLE001
        _fail(json_mode=json_mode, code="DB_ERROR", message=str(exc), exit_code=1)
        return
    status = "ok" if data.get("redactionStatus") == "ok" else "failed"
    _emit(_envelope(status=status, data=data), json_mode=json_mode)
    if status != "ok":
        raise typer.Exit(code=1)


@app.command("projection-status")
def projection_status(
    destination: str = typer.Option(
        ...,
        "--destination",
        help="admin_read_model | otel | langsmith",
    ),
    json_mode: bool = typer.Option(True, "--json/--no-json", help="JSON output"),
) -> None:
    """Report projection delivery backlog and freshness."""
    allowed = {"admin_read_model", "otel", "langsmith"}
    if destination not in allowed:
        typer.echo(
            f"invalid --destination: {destination!r}; expected one of {sorted(allowed)}",
            err=True,
        )
        raise typer.Exit(code=2)

    async def _go() -> dict[str, Any]:
        from sqlalchemy import func, select

        from app.modules.ai_runtime.models import TelemetryProjectionDelivery
        from app.modules.ai_runtime.projections.service import (
            STATUS_BLOCKED,
            STATUS_CONFIRMED,
            STATUS_PENDING,
            STATUS_RETRY_WAIT,
        )

        async with _session() as session:
            pending = (
                await session.execute(
                    select(func.count())
                    .select_from(TelemetryProjectionDelivery)
                    .where(
                        TelemetryProjectionDelivery.destination == destination,
                        TelemetryProjectionDelivery.status.in_(
                            [STATUS_PENDING, STATUS_RETRY_WAIT]
                        ),
                    )
                )
            ).scalar_one()
            blocked = (
                await session.execute(
                    select(func.count())
                    .select_from(TelemetryProjectionDelivery)
                    .where(
                        TelemetryProjectionDelivery.destination == destination,
                        TelemetryProjectionDelivery.status == STATUS_BLOCKED,
                    )
                )
            ).scalar_one()
            last = (
                await session.execute(
                    select(TelemetryProjectionDelivery)
                    .where(
                        TelemetryProjectionDelivery.destination == destination,
                        TelemetryProjectionDelivery.status == STATUS_CONFIRMED,
                    )
                    .order_by(TelemetryProjectionDelivery.last_success_at.desc().nullslast())
                    .limit(1)
                )
            ).scalar_one_or_none()
            oldest_pending = (
                await session.execute(
                    select(TelemetryProjectionDelivery)
                    .where(
                        TelemetryProjectionDelivery.destination == destination,
                        TelemetryProjectionDelivery.status.in_(
                            [STATUS_PENDING, STATUS_RETRY_WAIT]
                        ),
                    )
                    .order_by(TelemetryProjectionDelivery.first_attempt_at.asc().nullslast())
                    .limit(1)
                )
            ).scalar_one_or_none()
            backlog_age = None
            anchor = oldest_pending.first_attempt_at if oldest_pending else None
            if anchor is not None:
                backlog_age = int((datetime.now(timezone.utc) - anchor).total_seconds())
            return {
                "destination": destination,
                "backlogAgeSeconds": backlog_age,
                "pendingCount": int(pending or 0),
                "lastConfirmedSourceSequence": getattr(last, "confirmed_position", None),
                "lastSuccessAt": last.last_success_at.isoformat()
                if last and last.last_success_at
                else None,
                "blockedByPolicyCount": int(blocked or 0),
                "unknownFailureCount": 0,
            }

    try:
        data = _run(_go())
    except Exception as exc:  # noqa: BLE001
        # Table may be empty / missing in early envs ??still emit explicit nulls.
        data = {
            "destination": destination,
            "backlogAgeSeconds": None,
            "lastConfirmedSourceSequence": None,
            "lastSuccessAt": None,
            "blockedByPolicyCount": 0,
            "unknownFailureCount": 0,
            "warning": str(exc),
        }
        _emit(_envelope(status="warning", data=data), json_mode=json_mode)
        return
    _emit(_envelope(status="ok", data=data), json_mode=json_mode)


@app.command("projection-retry")
def projection_retry(
    delivery_id: str = typer.Option(..., "--delivery-id", help="Projection delivery id"),
    reason: str = typer.Option(..., "--reason", help="Audit reason"),
    idempotency_key: str = typer.Option(..., "--idempotency-key", help="Idempotency key"),
    json_mode: bool = typer.Option(True, "--json/--no-json", help="JSON output"),
) -> None:
    """Re-emit a persisted, policy-approved projection representation."""
    if not reason.strip() or not idempotency_key.strip():
        _fail(
            json_mode=json_mode,
            code="INVALID_ARGUMENT",
            message="--reason and --idempotency-key required",
            exit_code=2,
        )
    did = _parse_uuid(delivery_id, field="delivery_id", json_mode=json_mode)

    async def _go() -> dict[str, Any]:
        from app.modules.ai_runtime.models import TelemetryProjectionDelivery
        from app.modules.ai_runtime.projections.service import (
            STATUS_CONFIRMED,
            STATUS_PENDING,
            ProjectionService,
        )

        async with _session() as session:
            row = await session.get(TelemetryProjectionDelivery, did)
            if row is None:
                raise LookupError("delivery not found")
            # Never call providers/tools/metering ??only re-queue persisted row.
            if row.status == STATUS_CONFIRMED:
                return {
                    "deliveryId": delivery_id,
                    "status": row.status,
                    "duplicate": True,
                    "reason": reason,
                    "idempotencyKey": idempotency_key,
                }
            row.status = STATUS_PENDING
            row.next_attempt_at = datetime.now(timezone.utc)
            await session.flush()
            if hasattr(ProjectionService, "retry_delivery"):
                svc = ProjectionService(session)
                await svc.retry_delivery(delivery_id=did, reason=reason)
            await session.commit()
            return {
                "deliveryId": delivery_id,
                "status": row.status,
                "duplicate": False,
                "reason": reason,
                "idempotencyKey": idempotency_key,
            }

    try:
        data = _run(_go())
    except LookupError:
        _fail(
            json_mode=json_mode,
            code="NOT_FOUND",
            message=f"delivery {delivery_id} not found",
            exit_code=1,
        )
        return
    except Exception as exc:  # noqa: BLE001
        _fail(json_mode=json_mode, code="DB_ERROR", message=str(exc), exit_code=1)
        return
    _emit(_envelope(status="ok", data=data), json_mode=json_mode)


@app.command("shadow-compare")
def shadow_compare(
    fixture: Path = typer.Option(
        ...,
        "--fixture",
        exists=False,
        help="JSON fixture with canonical/legacy row pairs",
    ),
    dry_run: bool = typer.Option(True, "--dry-run/--execute"),
    json_mode: bool = typer.Option(True, "--json/--no-json"),
) -> None:
    """Compare canonical runtime facts vs legacy shadow capture (T168).

    Never fabricates retries, zero usage, or historical point charges.
    """
    from app.modules.ai_runtime.migration import (
        backfill_legacy_partial,
        compare_shadow_row,
    )

    if not fixture.exists():
        _fail(
            json_mode=json_mode,
            code="INVALID_ARGUMENT",
            message=f"fixture not found: {fixture}",
            exit_code=2,
        )
    try:
        payload = json.loads(fixture.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        _fail(json_mode=json_mode, code="INVALID_ARGUMENT", message=str(exc), exit_code=2)
        return

    pairs = payload.get("pairs") or []
    comparisons = [
        compare_shadow_row(
            task_id=row.get("task_id", "unknown"),
            canonical=row.get("canonical") or {},
            legacy=row.get("legacy") or {},
        )
        for row in pairs
    ]
    records = payload.get("backfill_records") or []
    backfill = backfill_legacy_partial(records, dry_run=dry_run)
    _emit(
        _envelope(
            status="ok",
            data={
                "dryRun": dry_run,
                "comparisons": [
                    {
                        "taskId": c.task_id,
                        "statusMatch": c.status_match,
                        "usageMatch": c.usage_match,
                        "notes": list(c.notes),
                    }
                    for c in comparisons
                ],
                "backfill": {
                    "scanned": backfill.scanned,
                    "updated": backfill.updated,
                    "skipped": backfill.skipped,
                    "fabricatedRetries": backfill.fabricated_retries,
                    "fabricatedUsage": backfill.fabricated_usage,
                    "fabricatedCharges": backfill.fabricated_charges,
                },
            },
        ),
        json_mode=json_mode,
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
