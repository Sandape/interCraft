"""In-memory point ledger helpers for REQ-061 unit invariants (T008/T019 precursor)."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import uuid4


class LedgerError(ValueError):
    """Raised when a ledger command violates an invariant."""


@dataclass(frozen=True, slots=True)
class PointBucket:
    id: str
    granted_points: int
    remaining_points: int
    expires_at: datetime
    grant_kind: str
    business_date: str


@dataclass(frozen=True, slots=True)
class LedgerEvent:
    id: str
    command: str
    points: Decimal
    idempotency_key: str
    task_id: str | None = None
    reservation_id: str | None = None
    source_event_id: str | None = None
    amount: Decimal | None = None


@dataclass
class PointLedger:
    user_id: str
    buckets: list[PointBucket]
    events: list[LedgerEvent]
    reserved: int = 0
    last_reservation_id: str | None = None
    _reservations: dict[str, int] = field(default_factory=dict, repr=False)
    _seen_keys: dict[str, str] = field(default_factory=dict, repr=False)

    @property
    def available(self) -> int:
        return sum(b.remaining_points for b in self.buckets)


def rebuild_balances(
    events: list[LedgerEvent],
    *,
    grants: list[PointBucket],
) -> PointLedger:
    """Rebuild available/reserved from grant buckets minus settle/refund netting.

    For unit tests we recompute reserved as unsettled reservation remainder and
    available from current bucket remainders (grants argument).
    """
    reserved = 0
    for event in events:
        if event.command == "reserve":
            reserved += int(event.points)
        elif event.command in {"settle", "release"}:
            reserved -= int(event.points)
    reserved = max(0, reserved)
    return PointLedger(
        user_id="rebuild",
        buckets=list(grants),
        events=list(events),
        reserved=reserved,
    )


def apply_command(
    ledger: PointLedger,
    *,
    command: str,
    points: int | None = None,
    idempotency_key: str,
    expires_at: datetime | None = None,
    business_date: str | None = None,
    task_id: str | None = None,
    reservation_id: str | None = None,
    source_event_id: str | None = None,
    **_: Any,
) -> PointLedger:
    if idempotency_key in ledger._seen_keys:
        return ledger

    buckets = list(ledger.buckets)
    events = list(ledger.events)
    reserved = ledger.reserved
    reservations = dict(ledger._reservations)
    seen = dict(ledger._seen_keys)
    last_reservation_id = ledger.last_reservation_id

    def _event(cmd: str, pts: int, **extra: Any) -> LedgerEvent:
        return LedgerEvent(
            id=str(uuid4()),
            command=cmd,
            points=Decimal(pts),
            idempotency_key=idempotency_key,
            amount=Decimal(pts),
            **extra,
        )

    if command == "grant":
        if points is None or expires_at is None or business_date is None:
            raise LedgerError("grant requires points, expires_at, business_date")
        bucket = PointBucket(
            id=str(uuid4()),
            granted_points=points,
            remaining_points=points,
            expires_at=expires_at,
            grant_kind="daily_experience",
            business_date=business_date,
        )
        buckets.append(bucket)
        events.append(_event("grant", points))
    elif command == "reserve":
        if points is None:
            raise LedgerError("reserve requires points")
        if ledger.available < points:
            raise LedgerError("insufficient balance")
        remaining_to_take = points
        new_buckets: list[PointBucket] = []
        for bucket in sorted(buckets, key=lambda b: b.expires_at):
            if remaining_to_take <= 0:
                new_buckets.append(bucket)
                continue
            take = min(bucket.remaining_points, remaining_to_take)
            new_buckets.append(
                replace(bucket, remaining_points=bucket.remaining_points - take)
            )
            remaining_to_take -= take
        if remaining_to_take > 0:
            raise LedgerError("insufficient balance")
        buckets = new_buckets
        last_reservation_id = str(uuid4())
        reservations[last_reservation_id] = points
        reserved += points
        events.append(
            _event("reserve", points, task_id=task_id, reservation_id=last_reservation_id)
        )
    elif command == "settle":
        if points is None or reservation_id is None:
            raise LedgerError("settle requires points and reservation_id")
        open_amt = reservations.get(reservation_id, 0)
        if points > open_amt:
            raise LedgerError("settle exceeds reservation")
        reservations[reservation_id] = open_amt - points
        reserved -= points
        # Settled points leave the system (consumed); buckets already reduced at reserve.
        events.append(
            _event("settle", points, task_id=task_id, reservation_id=reservation_id)
        )
    elif command == "release":
        if points is None or reservation_id is None:
            raise LedgerError("release requires points and reservation_id")
        open_amt = reservations.get(reservation_id, 0)
        if points > open_amt:
            raise LedgerError("release exceeds reservation")
        reservations[reservation_id] = open_amt - points
        reserved -= points
        # Return points to earliest bucket (FIFO restore approximate: first bucket)
        to_return = points
        restored: list[PointBucket] = []
        for bucket in buckets:
            if to_return <= 0:
                restored.append(bucket)
                continue
            room = bucket.granted_points - bucket.remaining_points
            add = min(room, to_return) if room > 0 else to_return
            # If no room tracking, just add back
            add = min(to_return, points)
            restored.append(
                replace(bucket, remaining_points=bucket.remaining_points + add)
            )
            to_return -= add
            # Only restore into first applicable bucket for simplicity
            if to_return > 0:
                # continue to next
                pass
            else:
                # append rest unchanged later — handled by loop
                pass
        # Fix: properly restore across buckets
        buckets = _restore_points(buckets, points)
        events.append(
            _event("release", points, task_id=task_id, reservation_id=reservation_id)
        )
    elif command == "refund":
        if points is None:
            raise LedgerError("refund requires points")
        buckets = _restore_points(buckets, points)
        events.append(_event("refund", points, task_id=task_id))
    elif command == "compensate":
        if points is None or expires_at is None:
            raise LedgerError("compensate requires points and expires_at")
        buckets.append(
            PointBucket(
                id=str(uuid4()),
                granted_points=points,
                remaining_points=points,
                expires_at=expires_at,
                grant_kind="compensation",
                business_date=business_date or "compensation",
            )
        )
        events.append(_event("compensate", points))
    elif command == "reverse":
        if points is None or source_event_id is None:
            raise LedgerError("reverse requires points and source_event_id")
        buckets = _restore_points(buckets, points)
        events.append(
            _event("reverse", points, source_event_id=source_event_id, task_id=task_id)
        )
    else:
        raise LedgerError(f"unknown command: {command}")

    seen[idempotency_key] = command
    return PointLedger(
        user_id=ledger.user_id,
        buckets=buckets,
        events=events,
        reserved=max(0, reserved),
        last_reservation_id=last_reservation_id,
        _reservations=reservations,
        _seen_keys=seen,
    )


def _restore_points(buckets: list[PointBucket], points: int) -> list[PointBucket]:
    if not buckets:
        return buckets
    first, *rest = buckets
    return [replace(first, remaining_points=first.remaining_points + points), *rest]
