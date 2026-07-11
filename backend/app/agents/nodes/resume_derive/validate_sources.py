"""Deterministic source validator — drop claims without provenance (REQ-055)."""
from __future__ import annotations

from typing import Any

from app.modules.resume_intelligence.claims import Claim, SourceDocument, validate_claim_ledger


def validate_sources(derived_data: dict[str, Any], *, allowed_refs: set[str]) -> dict[str, Any]:
    """Strip bullets/sections that lack source_refs intersecting allowed_refs.

    Also moves illegal claims into metadata.derive.pendingClaims when marked
    as needing confirmation.
    """
    data = derived_data
    meta = data.setdefault("metadata", {})
    derive = meta.setdefault("derive", {}) if isinstance(meta, dict) else {}
    source_map = derive.setdefault("sourceMap", {})
    pending = list(derive.get("pendingClaims") or [])
    rejected: list[dict[str, Any]] = []

    sections = data.get("sections")
    if isinstance(sections, dict):
        for _key, section in sections.items():
            items = []
            if isinstance(section, dict):
                items = section.get("items") or []
            elif isinstance(section, list):
                items = section
            if not isinstance(items, list):
                continue
            kept = []
            for item in items:
                if not isinstance(item, dict):
                    kept.append(item)
                    continue
                refs = item.get("source_refs") or source_map.get(str(item.get("id") or "")) or []
                if not refs:
                    # Allow items that are structural (name/contact) without refs
                    if item.get("require_source") is False:
                        kept.append(item)
                        continue
                    rejected.append({"item": item, "reason": "missing_source_refs"})
                    continue
                if not set(map(str, refs)) & allowed_refs:
                    rejected.append({"item": item, "reason": "unknown_source_refs", "refs": refs})
                    continue
                kept.append(item)
            if isinstance(section, dict):
                section["items"] = kept

    if rejected:
        derive.setdefault("rejectedClaims", []).extend(rejected)
    claim_ledger = derive.get("claimLedger") or []
    source_texts = derive.get("sourceTexts") or {}
    if isinstance(claim_ledger, list) and isinstance(source_texts, dict) and claim_ledger:
        entailment = validate_claim_entailment(claim_ledger, source_texts=source_texts)
        if entailment["rejected"]:
            derive.setdefault("rejectedClaims", []).extend(entailment["rejected"])
    derive["pendingClaims"] = pending
    return data


def collect_root_refs(root_data: dict[str, Any]) -> set[str]:
    """Build allowed source ref ids from root resume structure."""
    refs: set[str] = {"root:basics", "root:summary"}
    metadata = (root_data or {}).get("metadata") or {}
    markdown = metadata.get("markdown") if isinstance(metadata, dict) else {}
    if isinstance(markdown, dict) and str(markdown.get("sourceMarkdown") or "").strip():
        refs.add("root:markdown")
    sections = (root_data or {}).get("sections") or {}
    if not isinstance(sections, dict):
        return refs
    for key, section in sections.items():
        refs.add(f"root:section:{key}")
        items = []
        if isinstance(section, dict):
            items = section.get("items") or []
        elif isinstance(section, list):
            items = section
        for idx, item in enumerate(items if isinstance(items, list) else []):
            if isinstance(item, dict) and item.get("id"):
                refs.add(f"root:{key}:{item['id']}")
            else:
                refs.add(f"root:{key}:{idx}")
    return refs


def validate_claim_entailment(
    claims: list[dict[str, Any]],
    *,
    source_texts: dict[str, str],
) -> dict[str, Any]:
    """Validate claim entailment using the shared REQ-059 claim ledger."""
    ledger_claims = [
        Claim(
            claim_id=str(item.get("claim_id") or index),
            claim_type=str(item.get("claim_type") or "description"),
            text=str(item.get("text") or item.get("normalized_text") or ""),
            source_refs=[str(ref) for ref in item.get("source_refs") or []],
        )
        for index, item in enumerate(claims)
    ]
    sources = {
        source_id: SourceDocument(
            source_id=source_id,
            source_type=(
                "root_resume"
                if source_id.startswith("root:")
                else "confirmed_supplement"
                if source_id.startswith("supplement:")
                else "current_resume"
            ),
            text=text,
        )
        for source_id, text in source_texts.items()
    }
    result = validate_claim_ledger(ledger_claims, sources)
    return {
        "accepted": [claim.__dict__ for claim in result.accepted],
        "rejected": [claim.__dict__ for claim in result.rejected],
    }
