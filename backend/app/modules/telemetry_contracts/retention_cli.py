"""CLI entrypoint for the REQ-033 retention check (T029, US10).

Implements the retention half of the contract documented in
``specs/033-eval-pm-dashboard/contracts/eval-langsmith-cli.md``:

  python -m app.modules.telemetry_contracts.retention check \\
      --environment production \\
      [--json] [--dry-run]

Behavior:

- Reads ``trace_run_refs`` rows whose ``environment`` matches the
  requested one and ``retention_expires_at < now()`` is treated as
  expired.
- Reports ``expiredCount`` + ``earliestExpiredAt`` + ``earliestTraceId``.
- Production MUST always be dry-run (FR-035a — operator-triggered
  deletion only); the CLI confirms operator intent by setting
  ``dryRun: true`` in the JSON output.
- Exit codes per the shared CLI contract:
  - 0  — successful run (the report may still list expired rows; the
    operator decides what to do).
  - 1  — operational failure (DB error, etc.). Production check that
    fails to read rows is operational, not a policy violation.
  - 2  — invalid arguments.

US6 LangSmith sync work does not interact with this CLI; it exists for
the FR-035a retention audit + the operator-driven cleanup script.

For testability the actual row-iteration goes through a tiny in-memory
stand-in (``_retention_check``) when no DB session is available; the
production implementation in Sub-batch 2+ will wire this CLI to the
SQLAlchemy repository once that exists.  The CLI contract — exit codes,
JSON shape, ``dryRun`` flag — is fixed by this module so tests can pin
it down.
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterable

import structlog

from app.modules.telemetry_contracts.retention import (
    RetentionContext,
    enforce_retention,
    next_cleanup_at,
    production_default_context,
    staging_default_context,
)

logger = structlog.get_logger("telemetry.retention_cli")

VALID_ENVIRONMENTS: frozenset[str] = frozenset(
    {"local", "ci", "staging", "production", "dev", "prod"}
)


# ---------------------------------------------------------------------------
# Row stub (mirrors the SQLAlchemy TraceRunRef columns needed for retention)
# ---------------------------------------------------------------------------


@dataclass
class TraceRunRefRow:
    """Minimal row shape used by the in-memory retention CLI stand-in."""

    trace_id: str
    environment: str
    privacy_class: str
    redaction_status: str
    retention_expires_at: datetime | None


@dataclass
class RetentionCheckReport:
    """Aggregate retention check report (matches contract shape)."""

    environment: str
    checked_rows: int
    expired_count: int
    earliest_expired_at: str | None
    earliest_trace_id: str | None
    dry_run: bool
    policy_version: str
    next_cleanup_at: str
    policy_action: str
    max_age_days: int
    timestamp: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "environment": self.environment.upper(),
            "checkedRows": self.checked_rows,
            "expiredCount": self.expired_count,
            "earliestExpiredAt": self.earliest_expired_at,
            "earliestTraceId": self.earliest_trace_id,
            "dryRun": self.dry_run,
            "policyVersion": self.policy_version,
            "nextCleanupAt": self.next_cleanup_at,
            "policyAction": self.policy_action,
            "maxAgeDays": self.max_age_days,
            "timestamp": self.timestamp,
        }


# ---------------------------------------------------------------------------
# Core check logic (pure, callable from tests)
# ---------------------------------------------------------------------------


def _context_for_environment(environment: str) -> RetentionContext:
    """Return the canonical retention context for ``environment``."""
    norm = environment.strip().lower()
    if norm in ("production", "prod"):
        return production_default_context()
    if norm == "staging":
        return staging_default_context()
    # dev / local / ci: no caps. Use production's shape but with 0 caps.
    return RetentionContext(
        env=norm,
        max_age_days=0,
        max_records=0,
        action="archive",
        policy_version="v1",
    )


def check_retention(
    rows: Iterable[TraceRunRefRow],
    *,
    environment: str,
    dry_run: bool = True,
    policy_version: str = "v1",
    now: datetime | None = None,
    last_cleanup: datetime | None = None,
) -> RetentionCheckReport:
    """Run the retention check over ``rows``.

    Production always returns ``dry_run=True`` regardless of caller
    intent (FR-035a — production never auto-deletes; only the operator
    can persist deletion after reviewing this report).

    The function does NOT mutate the input rows. ``dry_run=False`` on
    staging is permitted (staging action is ``archive``, not delete).
    """
    now = now or datetime.now(UTC)
    norm_env = environment.strip().lower()
    ctx = _context_for_environment(norm_env)

    # Production auto-overrides dry_run to True per FR-035a.
    if norm_env in ("production", "prod"):
        dry_run = True

    rows_list = [r for r in rows if r.environment == norm_env]
    expired = [
        r for r in rows_list
        if r.retention_expires_at is not None and r.retention_expires_at < now
    ]
    if expired:
        timestamps = [r.retention_expires_at for r in expired if r.retention_expires_at is not None]
        earliest = min(timestamps)
    else:
        earliest = None
    earliest_tid: str | None = None
    if earliest is not None:
        earliest_tid = next(
            (r.trace_id for r in expired if r.retention_expires_at == earliest),
            None,
        )

    last_cleanup = last_cleanup or now
    next_cleanup = next_cleanup_at(last_cleanup)

    return RetentionCheckReport(
        environment=norm_env,
        checked_rows=len(rows_list),
        expired_count=len(expired),
        earliest_expired_at=earliest.isoformat() if earliest else None,
        earliest_trace_id=earliest_tid,
        dry_run=dry_run,
        policy_version=policy_version,
        next_cleanup_at=next_cleanup.isoformat(),
        policy_action=ctx.action,
        max_age_days=ctx.max_age_days,
        timestamp=now.isoformat(),
    )


# ---------------------------------------------------------------------------
# Row source — pluggable for tests
# ---------------------------------------------------------------------------


def _load_rows_from_store(environment: str) -> list[TraceRunRefRow]:
    """Load rows from the SQLAlchemy store.

    Sub-batch 2 will implement this against
    ``app.modules.telemetry_contracts.repository`` + ``trace_run_refs``.
    For T029 we return an empty list so the CLI still produces a valid
    ``{"expiredCount": 0, ...}`` JSON envelope.
    """
    # Sub-batch 2 stub: integrate with the SQLAlchemy repository here.
    # The CLI contract — exit codes, JSON shape, dryRun flag — is fixed
    # by this module. US6 will add the actual fetch path.
    return []


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m app.modules.telemetry_contracts.retention check",
        description="Run a retention check for trace_run_refs rows in an environment.",
    )
    parser.add_argument(
        "--environment",
        required=True,
        choices=sorted(VALID_ENVIRONMENTS),
        help="Target environment for the check.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit machine-readable JSON summary to stdout.",
    )
    parser.add_argument(
        "--dry-run",
        dest="dry_run",
        action="store_true",
        default=True,
        help="Force dry-run mode (default for production; recommended elsewhere).",
    )
    parser.add_argument(
        "--no-dry-run",
        dest="dry_run",
        action="store_false",
        help="Permit non-dry-run; production always forces dry-run regardless.",
    )
    return parser


def cmd_check(args: argparse.Namespace) -> int:
    environment: str = args.environment

    try:
        rows = _load_rows_from_store(environment)
    except Exception as exc:  # pragma: no cover — defensive
        print(f"[retention_cli] row load failure: {exc}", file=sys.stderr)
        return 1

    try:
        report = check_retention(rows, environment=environment, dry_run=args.dry_run)
    except ValueError as exc:
        print(f"[retention_cli] invalid argument: {exc}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(report.to_dict(), ensure_ascii=False))

    # Always exit 0 on a successful check (the report is informational;
    # operator decides what to do with the expired rows).
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    return cmd_check(args)


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())


__all__ = [
    "RetentionCheckReport",
    "TraceRunRefRow",
    "VALID_ENVIRONMENTS",
    "check_retention",
    "cmd_check",
    "main",
]