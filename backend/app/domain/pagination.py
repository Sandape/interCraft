"""Cursor-based pagination helpers — DEC-P2-1."""
from __future__ import annotations

import base64
import binascii
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Generic, TypeVar
from uuid import UUID

T = TypeVar("T")


@dataclass
class Page(Generic[T]):
    """Legacy alias for simple offset/limit pages (Phase 1)."""

    data: list[T]
    next_cursor: str | None
    has_more: bool


@dataclass
class CursorPage(Generic[T]):
    """Cursor-based page for time-ordered, append-only feeds (Phase 2).

    DEC-P2-1: forward-only, base64url(JSON({ts, id})), DESC order.
    """

    items: list[T]
    next_cursor: str | None
    has_more: bool


def encode_cursor(value: object) -> str:
    raw = json.dumps(value, separators=(",", ":"), sort_keys=True).encode("utf-8")
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def decode_cursor(token: str) -> object:
    try:
        pad = "=" * (-len(token) % 4)
        raw = base64.urlsafe_b64decode(token + pad)
        return json.loads(raw)
    except (ValueError, TypeError, binascii.Error) as exc:
        raise ValueError(f"Invalid cursor: {exc}") from exc


def encode_activity_cursor(occurred_at: datetime, id: UUID) -> str:
    """Encode (occurred_at, id) tuple into opaque base64url cursor."""
    payload = {"ts": occurred_at.isoformat(), "id": str(id)}
    return encode_cursor(payload)


def decode_activity_cursor(opaque: str) -> tuple[datetime, UUID]:
    """Decode opaque cursor back to (occurred_at, id)."""
    payload = decode_cursor(opaque)
    ts = datetime.fromisoformat(payload["ts"])
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return ts, UUID(payload["id"])


__all__ = [
    "CursorPage",
    "Page",
    "decode_activity_cursor",
    "decode_cursor",
    "encode_activity_cursor",
    "encode_cursor",
]
