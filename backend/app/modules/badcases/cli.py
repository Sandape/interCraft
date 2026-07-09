"""REQ-033 US8 — badcase CLI (T063).

Argparse CLI with subcommands:

- ``create``  — INSERT a new badcase row.
- ``classify`` — re-classify (type/severity), appends CLASSIFY action.
- ``close``   — set status=CLOSED, appends CLOSE action.
- ``reject``  — set status=REJECTED, appends REJECT action.
- ``promote`` — append PROMOTE_CANDIDATE + write candidate file.
- ``list``    — list badcases (filterable by status).
- ``get``     — read one badcase.

Exit codes (per ``app.eval.cli`` discipline):

- ``0`` success
- ``1`` operational failure (DB error, IO error, not-found)
- ``2`` invalid args
- ``3`` policy violation (FSM rejection, e.g. unknown type, redaction not passed)

``--json`` flag emits a machine-readable JSON envelope to stdout. The
``create`` / ``classify`` / ``close`` / ``reject`` / ``promote`` /
``get`` commands emit ``{"badcase": {...}, "reviewActions": [...]}``
(same as the API). The ``list`` command emits
``{"items": [...], "page": N, "pageSize": N}``.

Usage examples:

.. code-block:: bash

    # Create
    python -m app.modules.badcases.cli create \\
        --source eval_failure --type EVAL_REGRESSION \\
        --severity high --reviewer alice --json

    # Promote (writes specs/033-*/golden/<id>.candidate.json)
    python -m app.modules.badcases.cli promote \\
        --badcase-id badcase-... --reviewer alice \\
        --redaction-audit-id audit-001 \\
        --reason "protect regression" --json

    # Close
    python -m app.modules.badcases.cli close \\
        --badcase-id badcase-... --reviewer alice \\
        --closure-reason fixed --evidence-ref link --json
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

# Make ``app`` importable when invoked as ``python -m app.modules.badcases.cli``.
if __package__ in (None, ""):
    _HERE = Path(__file__).resolve().parent
    sys.path.insert(0, str(_HERE.parents[2]))

from app.core.db import get_db_session_no_rls, set_rls_user_id  # noqa: E402
from app.modules.auth import models as _auth_models  # noqa: E402,F401
from app.modules.avatars import models as _avatar_models  # noqa: E402,F401
from app.modules.badcases import repository as repo  # noqa: E402
from app.modules.badcases import service as badcase_service  # noqa: E402
from app.modules.badcases.promotion import (  # noqa: E402
    promote_badcase_to_eval_case,
    promote_to_golden_candidate,
)
from app.modules.badcases.schemas import (  # noqa: E402
    BADCASE_SEVERITIES,
    BADCASE_SOURCES,
    BADCASE_STATUSES,
    BADCASE_TYPES,
)


# ---------------------------------------------------------------------------
# CLI argument normalization
# ---------------------------------------------------------------------------

_CASE_MAP = {
    "open": "OPEN",
    "triaged": "TRIAGED",
    "in_progress": "IN_PROGRESS",
    "in-progress": "IN_PROGRESS",
    "inprogress": "IN_PROGRESS",
    "awaiting_validation": "AWAITING_VALIDATION",
    "awaiting-validation": "AWAITING_VALIDATION",
    "closed": "CLOSED",
    "rejected": "REJECTED",
    # Type aliases (matches the seed CLI examples in the spec).
    "eval_failure": "EVAL_FAILURE",
    "staging_trace": "STAGING_TRACE",
    "user_feedback": "USER_FEEDBACK",
    "pm_review": "PM_REVIEW",
    "manual_entry": "MANUAL_ENTRY",
    "manual": "MANUAL_ENTRY",
    "low": "LOW",
    "medium": "MEDIUM",
    "high": "HIGH",
    "critical": "CRITICAL",
    # Badcase type aliases
    "eval_regression": "EVAL_REGRESSION",
    "ai_reliability": "AI_RELIABILITY",
    "data_quality": "DATA_QUALITY",
    "resume_diagnosis_quality": "RESUME_DIAGNOSIS_QUALITY",
    "mock_interview_quality": "MOCK_INTERVIEW_QUALITY",
    "ai_cost_latency": "AI_COST_LATENCY",
    "product_funnel_ux": "PRODUCT_FUNNEL_UX",
    "privacy_redaction": "PRIVACY_REDACTION",
}


def _normalize(value: str | None, *, allowed: tuple[str, ...], field: str) -> str:
    """Normalize a CLI string value to its enum-canonical form."""
    if value is None:
        raise ValueError(f"{field} is required")
    raw = value.strip()
    if not raw:
        raise ValueError(f"{field} is required")
    upper = raw.upper()
    if upper in allowed:
        return upper
    # Lowercase alias?
    canon = _CASE_MAP.get(raw.lower())
    if canon and canon in allowed:
        return canon
    raise ValueError(f"{field} must be one of {sorted(allowed)}, got {value!r}")


# ---------------------------------------------------------------------------
# ORM row → JSON
# ---------------------------------------------------------------------------


def _row_to_dict(row: Any) -> dict[str, Any]:
    return {
        "badcaseId": row.badcase_id,
        "type": row.type,
        "severity": row.severity,
        "status": row.status,
        "source": row.source,
        "reviewer": row.reviewer,
        "privacyClass": row.privacy_class,
        "redactionStatus": row.redaction_status,
        "runId": str(row.run_id) if row.run_id else None,
        "traceId": row.trace_id,
        "closureReason": row.closure_reason,
        "closedAt": row.closed_at.isoformat() if row.closed_at else None,
        "createdAt": row.created_at.isoformat() if row.created_at else None,
        "updatedAt": row.updated_at.isoformat() if row.updated_at else None,
    }


def _action_to_dict(row: Any) -> dict[str, Any]:
    return {
        "actionType": row.action_type,
        "actorRole": row.actor_role,
        "reason": row.reason,
        "evidenceRef": row.evidence_ref,
        "createdAt": row.created_at.isoformat() if row.created_at else None,
    }


def _orm_to_schema(row: Any) -> Any:
    """Convert an ORM row to a Pydantic ``Badcase`` for the FSM."""
    from app.modules.badcases.schemas import Badcase as BadcaseSchema

    return BadcaseSchema(
        badcase_id=row.badcase_id,
        type=row.type,
        severity=row.severity,
        status=row.status,
        source=row.source,
        reviewer=row.reviewer,
        privacy_class=row.privacy_class,
        redaction_status=row.redaction_status,
        run_id=row.run_id,
        trace_id=row.trace_id,
        closure_reason=row.closure_reason,
        closed_at=row.closed_at,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


# ---------------------------------------------------------------------------
# Shared CLI helpers
# ---------------------------------------------------------------------------


def _emit_json(payload: dict[str, Any], json_flag: bool) -> None:
    """Emit the JSON envelope to stdout if ``--json`` is set."""
    if json_flag:
        print(json.dumps(payload, ensure_ascii=False, default=str))


def _err(msg: str) -> None:
    """Write a stderr error message."""
    print(f"[badcases] {msg}", file=sys.stderr)


# ---------------------------------------------------------------------------
# Subcommand implementations
# ---------------------------------------------------------------------------


async def _commit_or_rollback(db: Any, *, on_error_exit: int) -> bool:
    """Commit the current transaction. Returns True on success.

    On commit failure, writes a stderr error and returns False (caller
    should propagate the error exit). Each subcommand opens its own
    session via ``async for db in get_db_session_no_rls():``; without an
    explicit ``commit()`` the context-managed transaction rolls back on
    exit, so any writes are discarded. Call this right before
    ``return 0`` in every write subcommand.
    """
    try:
        await db.commit()
        return True
    except Exception as exc:
        await db.rollback()
        _err(f"db commit failed: {exc}")
        return False





async def cmd_create(args: argparse.Namespace) -> int:
    try:
        type_ = _normalize(args.type, allowed=BADCASE_TYPES, field="type")
        severity = _normalize(
            args.severity, allowed=BADCASE_SEVERITIES, field="severity"
        )
        source = _normalize(args.source, allowed=BADCASE_SOURCES, field="source")
    except ValueError as exc:
        _err(str(exc))
        return 3

    if not args.reviewer:
        _err("--reviewer is required")
        return 2

    user_id = _cli_user_id(args)
    badcase_id = f"badcase-{uuid4()}"
    try:
        async for db in get_db_session_no_rls():
            await set_rls_user_id(db, user_id)
            row = await repo.create(
                db,
                user_id=user_id,
                badcase_id=badcase_id,
                type=type_,
                source=source,
                privacy_class="PUBLIC_METADATA",
                severity=severity,
                reviewer=args.reviewer,
                redaction_status="NOT_REQUIRED",
                run_id=None,
                trace_id=None,
            )
            await repo.add_review_action(
                db,
                badcase_id=badcase_id,
                action_type="CREATE",
                actor_role="BADCASE_REVIEWER",
                reason=args.reviewer,
            )
            actions = await repo.list_review_actions(db, badcase_id=badcase_id)
            payload = {
                "badcase": _row_to_dict(row),
                "reviewActions": [_action_to_dict(a) for a in actions],
            }
            if not await _commit_or_rollback(db, on_error_exit=1):
                return 1
            _emit_json(payload, args.json)
            return 0
    except Exception as exc:
        _err(f"create failed: {exc}")
        return 1
    return 1  # async for emitted no session — defensive


async def cmd_classify(args: argparse.Namespace) -> int:
    try:
        type_ = _normalize(args.type, allowed=BADCASE_TYPES, field="type")
        severity = _normalize(
            args.severity, allowed=BADCASE_SEVERITIES, field="severity"
        )
    except ValueError as exc:
        _err(str(exc))
        return 3

    if not args.reviewer:
        _err("--reviewer is required")
        return 2

    user_id = _cli_user_id(args)
    try:
        async for db in get_db_session_no_rls():
            await set_rls_user_id(db, user_id)
            row = await repo.get(db, badcase_id=args.badcase_id, user_id=user_id)
            if row is None:
                _err(f"badcase {args.badcase_id!r} not found")
                return 1
            schema = _orm_to_schema(row)
            try:
                badcase_service.transition(
                    schema, new_status="TRIAGED", reviewer=args.reviewer
                )
            except badcase_service.BadcaseTransitionError as exc:
                _err(f"classify rejected: {exc}")
                return 3
            await repo.update_status(
                db,
                badcase_id=args.badcase_id,
                user_id=user_id,
                new_status="TRIAGED",
                reviewer=args.reviewer,
            )
            from sqlalchemy import update as _update
            from app.modules.badcases.models import Badcase as _BadcaseModel

            await db.execute(
                _update(_BadcaseModel)
                .where(_BadcaseModel.badcase_id == args.badcase_id)
                .values(type=type_, severity=severity)
            )
            await repo.add_review_action(
                db,
                badcase_id=args.badcase_id,
                action_type="CLASSIFY",
                actor_role="BADCASE_REVIEWER",
                reason=f"type={type_}, severity={severity}",
            )
            refreshed = await repo.get(
                db, badcase_id=args.badcase_id, user_id=user_id
            )
            actions = await repo.list_review_actions(
                db, badcase_id=args.badcase_id
            )
            payload = {
                "badcase": _row_to_dict(refreshed),
                "reviewActions": [_action_to_dict(a) for a in actions],
            }
            if not await _commit_or_rollback(db, on_error_exit=1):
                return 1
            _emit_json(payload, args.json)
            return 0
    except Exception as exc:
        _err(f"classify failed: {exc}")
        return 1
    return 1  # async for emitted no session — defensive


async def cmd_close(args: argparse.Namespace) -> int:
    if not args.reviewer:
        _err("--reviewer is required")
        return 2
    if not args.closure_reason:
        _err("--closure-reason is required")
        return 2
    if not args.evidence_ref:
        _err("--evidence-ref is required")
        return 2

    user_id = _cli_user_id(args)
    try:
        async for db in get_db_session_no_rls():
            await set_rls_user_id(db, user_id)
            row = await repo.get(db, badcase_id=args.badcase_id, user_id=user_id)
            if row is None:
                _err(f"badcase {args.badcase_id!r} not found")
                return 1
            schema = _orm_to_schema(row)
            closed_at = datetime.now(timezone.utc)
            try:
                badcase_service.transition(
                    schema,
                    new_status="CLOSED",
                    reviewer=args.reviewer,
                    closure_reason=args.closure_reason,
                    evidence_ref=args.evidence_ref,
                    closed_at=closed_at,
                )
            except badcase_service.BadcaseTransitionError as exc:
                _err(f"close rejected: {exc}")
                return 3
            await repo.update_status(
                db,
                badcase_id=args.badcase_id,
                user_id=user_id,
                new_status="CLOSED",
                reviewer=args.reviewer,
                closure_reason=args.closure_reason,
                closed_at=closed_at,
            )
            await repo.add_review_action(
                db,
                badcase_id=args.badcase_id,
                action_type="CLOSE",
                actor_role="BADCASE_REVIEWER",
                reason=args.closure_reason,
                evidence_ref=args.evidence_ref,
            )
            refreshed = await repo.get(
                db, badcase_id=args.badcase_id, user_id=user_id
            )
            actions = await repo.list_review_actions(
                db, badcase_id=args.badcase_id
            )
            payload = {
                "badcase": _row_to_dict(refreshed),
                "reviewActions": [_action_to_dict(a) for a in actions],
            }
            if not await _commit_or_rollback(db, on_error_exit=1):
                return 1
            _emit_json(payload, args.json)
            return 0
    except Exception as exc:
        _err(f"close failed: {exc}")
        return 1
    return 1  # async for emitted no session — defensive


async def cmd_reject(args: argparse.Namespace) -> int:
    if not args.reviewer:
        _err("--reviewer is required")
        return 2
    if not args.reason:
        _err("--reason is required")
        return 2

    user_id = _cli_user_id(args)
    try:
        async for db in get_db_session_no_rls():
            await set_rls_user_id(db, user_id)
            row = await repo.get(db, badcase_id=args.badcase_id, user_id=user_id)
            if row is None:
                _err(f"badcase {args.badcase_id!r} not found")
                return 1
            schema = _orm_to_schema(row)
            closed_at = datetime.now(timezone.utc)
            try:
                badcase_service.transition(
                    schema,
                    new_status="REJECTED",
                    reviewer=args.reviewer,
                    reason=args.reason,
                    closed_at=closed_at,
                )
            except badcase_service.BadcaseTransitionError as exc:
                _err(f"reject rejected: {exc}")
                return 3
            await repo.update_status(
                db,
                badcase_id=args.badcase_id,
                user_id=user_id,
                new_status="REJECTED",
                reviewer=args.reviewer,
                closure_reason=args.reason,
                closed_at=closed_at,
            )
            await repo.add_review_action(
                db,
                badcase_id=args.badcase_id,
                action_type="REJECT",
                actor_role="BADCASE_REVIEWER",
                reason=args.reason,
            )
            refreshed = await repo.get(
                db, badcase_id=args.badcase_id, user_id=user_id
            )
            actions = await repo.list_review_actions(
                db, badcase_id=args.badcase_id
            )
            payload = {
                "badcase": _row_to_dict(refreshed),
                "reviewActions": [_action_to_dict(a) for a in actions],
            }
            if not await _commit_or_rollback(db, on_error_exit=1):
                return 1
            _emit_json(payload, args.json)
            return 0
    except Exception as exc:
        _err(f"reject failed: {exc}")
        return 1
    return 1  # async for emitted no session — defensive


async def cmd_promote(args: argparse.Namespace) -> int:
    if not args.reviewer:
        _err("--reviewer is required")
        return 2
    if not args.redaction_audit_id and not getattr(args, "badcase_json", None):
        _err("--redaction-audit-id is required")
        return 2
    if not args.reason:
        _err("--reason is required")
        return 2
    if getattr(args, "badcase_json", None):
        try:
            raw = json.loads(Path(args.badcase_json).read_text(encoding="utf-8"))
            eval_case = promote_badcase_to_eval_case(
                raw,
                lifecycle=args.lifecycle,
                dataset_version=args.dataset_version,
                export_policy_decision_id=args.export_policy_decision_id,
                reviewer=args.reviewer,
                reason=args.reason,
            )
            candidate_path = promote_to_golden_candidate(
                raw,
                redaction_audit_id=args.redaction_audit_id or "not-required",
                reviewer=args.reviewer,
                reason=args.reason,
            )
        except Exception as exc:
            _err(f"promote failed: {exc}")
            return 3
        _emit_json(
            {
                "evalCase": eval_case,
                "candidatePath": str(candidate_path),
            },
            args.json,
        )
        return 0
    if not args.badcase_id:
        _err("--badcase-id is required unless --badcase-json is provided")
        return 2

    user_id = _cli_user_id(args)
    try:
        async for db in get_db_session_no_rls():
            await set_rls_user_id(db, user_id)
            row = await repo.get(db, badcase_id=args.badcase_id, user_id=user_id)
            if row is None:
                _err(f"badcase {args.badcase_id!r} not found")
                return 1
            candidate_path = promote_to_golden_candidate(
                row,
                redaction_audit_id=args.redaction_audit_id,
                reviewer=args.reviewer,
                reason=args.reason,
            )
            await repo.add_review_action(
                db,
                badcase_id=args.badcase_id,
                action_type="PROMOTE_CANDIDATE",
                actor_role="BADCASE_REVIEWER",
                reason=args.reason,
                evidence_ref=args.redaction_audit_id,
            )
            refreshed = await repo.get(
                db, badcase_id=args.badcase_id, user_id=user_id
            )
            actions = await repo.list_review_actions(
                db, badcase_id=args.badcase_id
            )
            payload = {
                "badcase": _row_to_dict(refreshed),
                "candidatePath": str(candidate_path),
                "reviewActions": [_action_to_dict(a) for a in actions],
            }
            if not await _commit_or_rollback(db, on_error_exit=1):
                return 1
            _emit_json(payload, args.json)
            return 0
    except Exception as exc:
        _err(f"promote failed: {exc}")
        return 1
    return 1  # async for emitted no session — defensive


async def cmd_list(args: argparse.Namespace) -> int:
    user_id = _cli_user_id(args)
    status_filter: str | None = None
    if args.status:
        try:
            status_filter = _normalize(
                args.status, allowed=BADCASE_STATUSES, field="status"
            )
        except ValueError as exc:
            _err(str(exc))
            return 3
    try:
        async for db in get_db_session_no_rls():
            await set_rls_user_id(db, user_id)
            rows = await repo.list_all(
                db,
                user_id=user_id,
                status=status_filter,
                page=args.page,
                page_size=args.page_size,
            )
            payload = {
                "items": [_row_to_dict(r) for r in rows],
                "page": args.page,
                "pageSize": args.page_size,
            }
            _emit_json(payload, args.json)
            return 0
    except Exception as exc:
        _err(f"list failed: {exc}")
        return 1
    return 1  # async for emitted no session — defensive


async def cmd_get(args: argparse.Namespace) -> int:
    if not args.badcase_id:
        _err("--badcase-id is required")
        return 2
    user_id = _cli_user_id(args)
    try:
        async for db in get_db_session_no_rls():
            await set_rls_user_id(db, user_id)
            row = await repo.get(db, badcase_id=args.badcase_id, user_id=user_id)
            if row is None:
                _err(f"badcase {args.badcase_id!r} not found")
                return 1
            actions = await repo.list_review_actions(
                db, badcase_id=args.badcase_id
            )
            payload = {
                "badcase": _row_to_dict(row),
                "reviewActions": [_action_to_dict(a) for a in actions],
            }
            _emit_json(payload, args.json)
            return 0
    except Exception as exc:
        _err(f"get failed: {exc}")
        return 1
    return 1  # async for emitted no session — defensive


# ---------------------------------------------------------------------------
# CLI plumbing
# ---------------------------------------------------------------------------


def _cli_user_id(args: argparse.Namespace) -> UUID:
    """Return the CLI user_id from ``--user-id`` or the env override.

    The CLI bypasses real auth (MVP convention): each invocation runs
    as the user specified via ``--user-id`` (UUID) or
    ``BADCASES_CLI_USER_ID`` env var. This mirrors how the eval CLI
    uses ``--reviewer`` for attribution without a real auth backend.
    """
    raw = getattr(args, "user_id", None) or _env_user_id()
    if not raw:
        # Last-resort fallback — generate a deterministic random UUID
        # so ad-hoc CLI usage doesn't fail. Real ops should set
        # ``--user-id`` explicitly.
        return uuid4()
    try:
        return UUID(str(raw))
    except (ValueError, AttributeError):
        _err(f"invalid --user-id: {raw!r}")
        sys.exit(2)


def _env_user_id() -> str | None:
    import os

    return os.environ.get("BADCASES_CLI_USER_ID")


def _add_user_id_arg(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--user-id",
        default=None,
        help="UUID of the user owning the badcase (RLS binding). "
        "Defaults to $BADCASES_CLI_USER_ID or a random UUID.",
    )


def _add_json_arg(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit a JSON envelope to stdout.",
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m app.modules.badcases.cli",
        description="REQ-033 US8 badcase lifecycle CLI.",
    )
    sub = parser.add_subparsers(dest="command", required=False)

    # create
    p_create = sub.add_parser("create", help="Create a new badcase")
    p_create.add_argument(
        "--source", required=True, help="Badcase source (EVAL_FAILURE, ...)"
    )
    p_create.add_argument("--type", required=True, help="Badcase type")
    p_create.add_argument("--severity", required=True, help="Severity")
    p_create.add_argument("--reviewer", help="Reviewer identity")
    _add_user_id_arg(p_create)
    _add_json_arg(p_create)
    p_create.set_defaults(func=cmd_create)

    # classify
    p_classify = sub.add_parser(
        "classify", help="Re-classify a badcase (type/severity)"
    )
    p_classify.add_argument("--badcase-id", required=True)
    p_classify.add_argument("--type", required=True)
    p_classify.add_argument("--severity", required=True)
    p_classify.add_argument("--reviewer", required=True)
    _add_user_id_arg(p_classify)
    _add_json_arg(p_classify)
    p_classify.set_defaults(func=cmd_classify)

    # close
    p_close = sub.add_parser("close", help="Close a badcase")
    p_close.add_argument("--badcase-id", required=True)
    p_close.add_argument("--reviewer", required=True)
    p_close.add_argument(
        "--closure-reason", required=True, dest="closure_reason"
    )
    p_close.add_argument("--evidence-ref", required=True, dest="evidence_ref")
    _add_user_id_arg(p_close)
    _add_json_arg(p_close)
    p_close.set_defaults(func=cmd_close)

    # reject
    p_reject = sub.add_parser("reject", help="Reject a badcase")
    p_reject.add_argument("--badcase-id", required=True)
    p_reject.add_argument("--reason", required=True)
    p_reject.add_argument("--reviewer", required=True)
    _add_user_id_arg(p_reject)
    _add_json_arg(p_reject)
    p_reject.set_defaults(func=cmd_reject)

    # promote
    p_promote = sub.add_parser(
        "promote", help="Promote a badcase to a golden-case candidate"
    )
    p_promote.add_argument("--badcase-id", required=False)
    p_promote.add_argument("--badcase-json", required=False, dest="badcase_json")
    p_promote.add_argument("--reviewer", required=True)
    p_promote.add_argument(
        "--redaction-audit-id", required=False, dest="redaction_audit_id"
    )
    p_promote.add_argument("--reason", required=True)
    p_promote.add_argument("--lifecycle", default="CANDIDATE")
    p_promote.add_argument("--dataset-version", default="candidate-v1", dest="dataset_version")
    p_promote.add_argument("--export-policy-decision-id", default=None, dest="export_policy_decision_id")
    _add_user_id_arg(p_promote)
    _add_json_arg(p_promote)
    p_promote.set_defaults(func=cmd_promote)

    # list
    p_list = sub.add_parser("list", help="List badcases")
    p_list.add_argument("--status", help="Filter by status")
    p_list.add_argument(
        "--page", type=int, default=1, help="Page number (1-indexed)"
    )
    p_list.add_argument(
        "--page-size",
        type=int,
        default=50,
        dest="page_size",
        help="Page size (1-200)",
    )
    _add_user_id_arg(p_list)
    _add_json_arg(p_list)
    p_list.set_defaults(func=cmd_list)

    # get
    p_get = sub.add_parser("get", help="Read one badcase")
    p_get.add_argument("--badcase-id", required=True)
    _add_user_id_arg(p_get)
    _add_json_arg(p_get)
    p_get.set_defaults(func=cmd_get)

    return parser


def main(argv: list[str] | None = None) -> int:
    # Route structlog to stderr before any subcommand runs — otherwise
    # the default PrintLoggerFactory writes log lines to stdout and
    # contaminates the JSON envelope that ``--json`` emits. The
    # function is idempotent so a second call (e.g. from the web app)
    # is a no-op.
    from app.core.logging import configure_logging

    configure_logging()
    parser = _build_parser()
    args = parser.parse_args(argv)
    if not getattr(args, "command", None):
        parser.print_help()
        return 2
    result = asyncio.run(args.func(args))
    return int(result) if result is not None else 1


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())


__all__ = ["main"]
