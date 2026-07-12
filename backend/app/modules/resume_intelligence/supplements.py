"""Confirmed supplement facts and source identity helpers."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Literal
from uuid import UUID

from app.modules.resume_intelligence.snapshots import canonical_hash

SupplementScope = Literal["derived_only", "root", "discard"]
SupplementStatus = Literal["pending", "confirmed", "discarded"]


class SupplementError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(message)


@dataclass(frozen=True)
class SupplementFact:
    fact_id: str
    user_id: str
    resume_id: str
    question_id: str
    text: str
    scope: SupplementScope
    status: SupplementStatus
    confirmed_at: str | None

    @property
    def source_id(self) -> str:
        return f"supplement:{self.fact_id}"

    @property
    def content_hash(self) -> str:
        return canonical_hash({"question_id": self.question_id, "text": self.text, "scope": self.scope})

    def source_ref(self) -> dict[str, Any]:
        if self.status != "confirmed" or self.scope == "discard":
            raise SupplementError("UNCONFIRMED_SUPPLEMENT", "Only confirmed supplement facts may become sources.")
        return {
            "source_id": self.source_id,
            "source_type": "confirmed_supplement",
            "anchor": self.question_id,
            "content_hash": self.content_hash,
            "excerpt": self.text[:240],
        }

    def to_payload(self) -> dict[str, Any]:
        return {
            "fact_id": self.fact_id,
            "user_id": self.user_id,
            "resume_id": self.resume_id,
            "question_id": self.question_id,
            "text": self.text,
            "scope": self.scope,
            "status": self.status,
            "confirmed_at": self.confirmed_at,
            "source_id": self.source_id,
            "content_hash": self.content_hash,
        }


def build_supplement_fact(
    *,
    user_id: UUID | str,
    resume_id: UUID | str,
    question_id: str,
    text: str,
    scope: SupplementScope,
    confirmed: bool,
    fact_id: str | None = None,
) -> SupplementFact:
    clean_text = str(text or "").strip()
    if not clean_text and scope != "discard":
        raise SupplementError("INVALID_SUPPLEMENT", "Supplement text is required unless discarded.")
    status: SupplementStatus = "discarded" if scope == "discard" else "confirmed" if confirmed else "pending"
    identity = fact_id or canonical_hash(
        {
            "user_id": str(user_id),
            "resume_id": str(resume_id),
            "question_id": question_id,
            "text": clean_text,
        }
    )[:16]
    return SupplementFact(
        fact_id=identity,
        user_id=str(user_id),
        resume_id=str(resume_id),
        question_id=question_id,
        text=clean_text,
        scope=scope,
        status=status,
        confirmed_at=datetime.now(UTC).isoformat() if status == "confirmed" else None,
    )


def persist_confirmed_supplement(
    resume_data: dict[str, Any],
    *,
    user_id: UUID | str,
    resume_id: UUID | str,
    question_id: str,
    text: str,
    scope: SupplementScope,
    confirmed: bool,
) -> SupplementFact:
    fact = build_supplement_fact(
        user_id=user_id,
        resume_id=resume_id,
        question_id=question_id,
        text=text,
        scope=scope,
        confirmed=confirmed,
    )
    meta = resume_data.setdefault("metadata", {})
    derive = meta.setdefault("derive", {}) if isinstance(meta, dict) else {}
    supplements = derive.setdefault("confirmedSupplements", [])
    if fact.status == "confirmed":
        supplements.append(fact.to_payload())
    elif fact.status == "discarded":
        derive.setdefault("discardedSupplements", []).append(fact.to_payload())
    else:
        derive.setdefault("pendingSupplements", []).append(fact.to_payload())
    return fact


def confirmed_supplement_sources(resume_data: dict[str, Any]) -> list[dict[str, Any]]:
    supplements = (
        ((resume_data.get("metadata") or {}).get("derive") or {}).get("confirmedSupplements")
        or []
    )
    sources: list[dict[str, Any]] = []
    for raw in supplements:
        fact = SupplementFact(
            fact_id=str(raw["fact_id"]),
            user_id=str(raw.get("user_id") or ""),
            resume_id=str(raw.get("resume_id") or ""),
            question_id=str(raw["question_id"]),
            text=str(raw["text"]),
            scope=str(raw.get("scope") or "derived_only"),  # type: ignore[arg-type]
            status=str(raw.get("status") or "confirmed"),  # type: ignore[arg-type]
            confirmed_at=raw.get("confirmed_at"),
        )
        sources.append(fact.source_ref())
    return sources


def reject_unconfirmed_supplements(resume_data: dict[str, Any]) -> None:
    derive = ((resume_data.get("metadata") or {}).get("derive") or {})
    blocked = list(derive.get("pendingSupplements") or []) + list(derive.get("discardedSupplements") or [])
    if blocked:
        raise SupplementError(
            "UNCONFIRMED_SUPPLEMENT",
            "Pending or discarded supplement facts cannot be used for draft, apply, or export.",
        )


__all__ = [
    "SupplementError",
    "SupplementFact",
    "confirmed_supplement_sources",
    "persist_confirmed_supplement",
    "reject_unconfirmed_supplements",
]
