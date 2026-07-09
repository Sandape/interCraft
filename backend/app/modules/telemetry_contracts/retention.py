"""Production trace retention policy for REQ-033 US10 (FR-035a).

The contract:

- **production**: keep ``MetricSnapshot`` rows for **30 days**, then
  ``delete`` (or "archive" — caller decides, defaults to delete per spec).
- **staging**: keep **7 days**, action ``archive``.
- **dev / local / ci**: **no limit** (synthetic data).

``enforce_retention(snapshots, ctx) -> list[MetricSnapshot]`` is a pure
filter: returns the subset that is still within retention. The caller
(Sub-batch 2 retention worker) decides what to do with the dropped rows
(persist the deletion audit row, etc).

``next_cleanup_at(last_cleanup, interval_hours=24)`` is the canonical
"when does the next cleanup run" calculation — defaults to 24h cadence,
caller can override for tests.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

from app.modules.telemetry_contracts.events import MetricSnapshot

RetentionAction = Literal["archive", "delete"]


@dataclass(frozen=True)
class RetentionContext:
    """Environment-specific retention configuration."""

    env: str
    max_age_days: int
    max_records: int
    action: RetentionAction
    policy_version: str = "v1"

    def __post_init__(self) -> None:
        env_norm = self.env.strip().lower()
        if env_norm not in {"dev", "local", "ci", "staging", "production"}:
            raise ValueError(
                f"invalid env={self.env!r}; expected dev/local/ci/staging/production"
            )
        # ``frozen=True`` blocks normal assignment; use object.__setattr__
        # to canonicalize env casing once at construction.
        object.__setattr__(self, "env", env_norm)
        if self.max_age_days < 0:
            raise ValueError("max_age_days must be >= 0")
        if self.max_records < 0:
            raise ValueError("max_records must be >= 0")


@dataclass(frozen=True)
class Req035RetentionContext:
    """REQ-035 debug-heavy retention and freshness windows.

    Production policy:
    - PM metric snapshots: 180 days.
    - Redacted traces/spans: 60 days.
    - Masked raw payloads: 14 days.
    - Dashboard freshness target: 15 minutes.
    """

    env: str
    pm_metrics_days: int
    redacted_trace_days: int
    masked_raw_days: int
    dashboard_freshness_minutes: int
    policy_version: str = "req035-v1"

    def __post_init__(self) -> None:
        env_norm = self.env.strip().lower()
        if env_norm not in {"dev", "local", "ci", "staging", "production"}:
            raise ValueError(
                f"invalid env={self.env!r}; expected dev/local/ci/staging/production"
            )
        object.__setattr__(self, "env", env_norm)


@dataclass(frozen=True)
class DestinationRetentionMetadata:
    destination: str
    environment: str
    retention_days: int | None
    access_scope: str | None
    owner: str | None
    policy_version: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "destination": self.destination,
            "environment": self.environment,
            "retentionDays": self.retention_days,
            "accessScope": self.access_scope,
            "owner": self.owner,
            "policyVersion": self.policy_version,
        }


def production_default_context(policy_version: str = "v1") -> RetentionContext:
    """Spec FR-035a: 30-day production retention, delete action."""
    return RetentionContext(
        env="production",
        max_age_days=30,
        max_records=1_000_000,
        action="delete",
        policy_version=policy_version,
    )


def req035_default_context(
    env: str = "production",
    policy_version: str = "req035-v1",
) -> Req035RetentionContext:
    """Return the REQ-035 debug-heavy retention context for an environment."""

    env_norm = env.strip().lower()
    if env_norm == "production":
        return Req035RetentionContext(
            env=env_norm,
            pm_metrics_days=180,
            redacted_trace_days=60,
            masked_raw_days=14,
            dashboard_freshness_minutes=15,
            policy_version=policy_version,
        )
    if env_norm == "staging":
        return Req035RetentionContext(
            env=env_norm,
            pm_metrics_days=90,
            redacted_trace_days=30,
            masked_raw_days=7,
            dashboard_freshness_minutes=15,
            policy_version=policy_version,
        )
    return Req035RetentionContext(
        env=env_norm,
        pm_metrics_days=0,
        redacted_trace_days=0,
        masked_raw_days=0,
        dashboard_freshness_minutes=15,
        policy_version=policy_version,
    )


def req035_is_expired(
    record_kind: str,
    *,
    captured_at: datetime,
    now: datetime | None = None,
    ctx: Req035RetentionContext | None = None,
) -> bool:
    """Return whether a REQ-035 record has passed its retention window."""

    ctx = ctx or req035_default_context("production")
    now = now or datetime.now(UTC)
    kind = record_kind.strip().lower()
    if kind in {"pm_metric", "dashboard_metric", "dashboard_snapshot"}:
        days = ctx.pm_metrics_days
    elif kind in {"redacted_trace", "trace", "span"}:
        days = ctx.redacted_trace_days
    elif kind in {"masked_raw_payload", "payload", "masked_raw"}:
        days = ctx.masked_raw_days
    else:
        raise ValueError(f"unknown REQ-035 retention record kind: {record_kind}")
    if days <= 0:
        return False
    return captured_at < now - timedelta(days=days)


def staging_default_context(policy_version: str = "v1") -> RetentionContext:
    """Staging: 7-day archive retention."""
    return RetentionContext(
        env="staging",
        max_age_days=7,
        max_records=500_000,
        action="archive",
        policy_version=policy_version,
    )


def dev_default_context(policy_version: str = "v1") -> RetentionContext:
    """Dev / local / CI: no retention cap (synthetic data)."""
    return RetentionContext(
        env="dev",
        max_age_days=0,  # 0 = no age cap
        max_records=0,  # 0 = no record cap
        action="archive",
        policy_version=policy_version,
    )


def _default_context_for_env(env: str) -> RetentionContext:
    env_norm = env.strip().lower()
    if env_norm == "production":
        return production_default_context()
    if env_norm == "staging":
        return staging_default_context()
    return dev_default_context()


def enforce_retention(
    snapshots: list[MetricSnapshot],
    ctx: RetentionContext | None = None,
    *,
    now: datetime | None = None,
) -> list[MetricSnapshot]:
    """Return the subset of ``snapshots`` that is still within retention.

    A snapshot is dropped if either:

    - ``ctx.max_age_days > 0`` and ``snapshot.captured_at`` is older than
      ``now - max_age_days``.
    - ``ctx.max_records > 0`` and the snapshot's chronological rank
      exceeds ``max_records`` (only the *newest* ``max_records`` rows
      survive — older rows are dropped first).

    ``ALLOW_ALL`` semantics: dev/local/ci default context has both caps
    set to ``0``, so all rows pass through unchanged.
    """
    if ctx is None:
        # default behavior: choose context by the *first* snapshot's env?
        # No — snapshots themselves don't carry env. Caller is expected to
        # pass an explicit ctx. Fall back to dev (no-op) if none given.
        ctx = dev_default_context()

    if ctx.max_age_days == 0 and ctx.max_records == 0:
        return list(snapshots)

    now = now or datetime.now(UTC)
    cutoff = now - timedelta(days=ctx.max_age_days) if ctx.max_age_days > 0 else None

    # Age filter
    kept = [s for s in snapshots if cutoff is None or s.captured_at >= cutoff]

    # Record-count cap (drop oldest first)
    if ctx.max_records > 0 and len(kept) > ctx.max_records:
        kept = sorted(kept, key=lambda s: s.captured_at, reverse=True)[
            : ctx.max_records
        ]
        # re-sort chronologically (oldest first) to match caller expectation
        kept = sorted(kept, key=lambda s: s.captured_at)

    return kept


def next_cleanup_at(last_cleanup: datetime, interval_hours: int = 24) -> datetime:
    """Return the wall-clock time of the next cleanup run.

    Default cadence is 24h. ``last_cleanup`` is taken as UTC-naive if it
    has no tzinfo (legacy datetime from old call sites). The returned
    value carries tzinfo matching the input.
    """
    if interval_hours <= 0:
        raise ValueError("interval_hours must be > 0")
    base = last_cleanup if last_cleanup.tzinfo else last_cleanup.replace(tzinfo=UTC)
    return base + timedelta(hours=interval_hours)


def destination_retention_metadata(decision: Any) -> DestinationRetentionMetadata:
    """Extract destination retention/access metadata from a policy decision."""

    def value(name: str) -> Any:
        if isinstance(decision, dict):
            return decision.get(name) or decision.get(_camel(name))
        return getattr(decision, name, None)

    return DestinationRetentionMetadata(
        destination=str(getattr(value("destination"), "value", value("destination"))),
        environment=str(getattr(value("environment"), "value", value("environment"))),
        retention_days=value("retention_days"),
        access_scope=value("access_scope"),
        owner=value("owner"),
        policy_version=str(value("policy_version") or "unknown"),
    )


def _camel(name: str) -> str:
    head, *tail = name.split("_")
    return head + "".join(part[:1].upper() + part[1:] for part in tail)


__all__ = [
    "DestinationRetentionMetadata",
    "Req035RetentionContext",
    "RetentionAction",
    "RetentionContext",
    "destination_retention_metadata",
    "dev_default_context",
    "enforce_retention",
    "next_cleanup_at",
    "production_default_context",
    "req035_default_context",
    "req035_is_expired",
    "staging_default_context",
]
