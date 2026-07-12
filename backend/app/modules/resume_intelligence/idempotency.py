"""Redis/DB idempotency helpers for resume intelligence runs."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.modules.resume_intelligence.snapshots import canonical_hash


class IdempotencyMismatchError(ValueError):
    code = "IDEMPOTENCY_MISMATCH"


@dataclass(frozen=True)
class IdempotencyRecord:
    key: str
    fingerprint: str
    run_id: str
    status: str


def build_request_fingerprint(payload: dict[str, Any]) -> str:
    return canonical_hash(payload)


def assert_fingerprint_match(existing: str | None, candidate: str) -> None:
    if existing and existing != candidate:
        raise IdempotencyMismatchError("Idempotency key was already used with different inputs.")


def arq_job_id_for_run(run_id: str) -> str:
    return str(run_id)


def arq_kwargs_for_run(run_id: str, **kwargs: Any) -> dict[str, Any]:
    return {**kwargs, "_job_id": arq_job_id_for_run(run_id)}


class MemoryIdempotencyStore:
    """Small test double with Redis-like set-if-absent semantics."""

    def __init__(self) -> None:
        self._records: dict[str, IdempotencyRecord] = {}

    def reserve(self, *, key: str, fingerprint: str, run_id: str) -> IdempotencyRecord:
        existing = self._records.get(key)
        if existing:
            assert_fingerprint_match(existing.fingerprint, fingerprint)
            return existing
        record = IdempotencyRecord(
            key=key,
            fingerprint=fingerprint,
            run_id=run_id,
            status="reserved",
        )
        self._records[key] = record
        return record


__all__ = [
    "IdempotencyMismatchError",
    "IdempotencyRecord",
    "MemoryIdempotencyStore",
    "arq_job_id_for_run",
    "arq_kwargs_for_run",
    "assert_fingerprint_match",
    "build_request_fingerprint",
]
