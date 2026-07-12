"""Atomic-claim ledger and deterministic high-risk source checks."""
from __future__ import annotations

import re
from dataclasses import dataclass, field, replace
from typing import Literal

AllowedSourceType = Literal["root_resume", "current_resume", "confirmed_supplement"]


class ClaimLedgerError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(message)


@dataclass(frozen=True)
class SourceDocument:
    source_id: str
    source_type: str
    text: str


@dataclass(frozen=True)
class Claim:
    claim_id: str
    claim_type: str
    text: str
    source_refs: list[str]
    verdict: Literal["pending", "accepted", "rejected"] = "pending"
    reason: str | None = None


@dataclass(frozen=True)
class ClaimLedgerResult:
    accepted: list[Claim] = field(default_factory=list)
    rejected: list[Claim] = field(default_factory=list)


_HIGH_RISK_TYPES = {"metric", "date", "duration", "employer", "project", "role", "scale"}
_VALUE_RE = re.compile(r"(?:\d+(?:\.\d+)?\s*%?|\d{4}[年/-]?\d{0,2})")


def _normalized(text: str) -> str:
    return re.sub(r"\s+", "", text).casefold()


def _source_supports(claim: Claim, source_text: str) -> bool:
    claim_text = _normalized(claim.text)
    source = _normalized(source_text)
    if claim_text and claim_text in source:
        return True
    if claim.claim_type in _HIGH_RISK_TYPES:
        values = _VALUE_RE.findall(claim.text)
        return bool(values) and all(_normalized(value) in source for value in values)
    # Non-high-risk paraphrases require meaningful token overlap; semantic
    # mapping may propose them, but an empty/irrelevant source is not enough.
    words = {token.casefold() for token in re.findall(r"[A-Za-z0-9_+#.-]{2,}", claim.text)}
    han = "".join(re.findall(r"[\u4e00-\u9fff]", claim.text))
    bigrams = {han[index : index + 2] for index in range(max(0, len(han) - 1))}
    tokens = words | bigrams
    return bool(tokens) and any(_normalized(token) in source for token in tokens)


def validate_claim_ledger(
    claims: list[Claim],
    sources: dict[str, SourceDocument],
    *,
    strict: bool = False,
) -> ClaimLedgerResult:
    accepted: list[Claim] = []
    rejected: list[Claim] = []
    for claim in claims:
        resolved: list[SourceDocument] = []
        for ref in claim.source_refs:
            source = sources.get(ref)
            if source is None:
                if strict:
                    raise ClaimLedgerError("UNKNOWN_SOURCE_REF", f"Unknown source: {ref}")
                rejected.append(replace(claim, verdict="rejected", reason="unknown_source_ref"))
                break
            if source.source_type not in {
                "root_resume",
                "current_resume",
                "confirmed_supplement",
            }:
                rejected.append(replace(claim, verdict="rejected", reason="source_not_confirmed"))
                break
            resolved.append(source)
        else:
            if not resolved:
                rejected.append(replace(claim, verdict="rejected", reason="missing_source_ref"))
            elif any(_source_supports(claim, source.text) for source in resolved):
                accepted.append(replace(claim, verdict="accepted", reason=None))
            else:
                reason = (
                    "unsupported_high_risk_value"
                    if claim.claim_type in _HIGH_RISK_TYPES
                    else "unsupported_claim"
                )
                rejected.append(replace(claim, verdict="rejected", reason=reason))
    return ClaimLedgerResult(accepted=accepted, rejected=rejected)
