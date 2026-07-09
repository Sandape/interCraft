"""REQ-033 US8 — golden-case candidate writer (T064).

Pure function :func:`promote_to_golden_candidate` writes a candidate
JSON file to the configured golden directory. The actual baseline
refresh lives in the US5 override-record flow; this module only
produces the candidate artifact that downstream tooling inspects
before approving a real baseline refresh.

Path resolution
---------------

1. ``BADCASES_GOLDEN_DIR`` environment variable (CLI override /
   test-friendly).
2. ``<repo>/specs/033-eval-pm-dashboard/golden/`` (canonical spec
   location, derived from this file's path).

File name
---------

``<badcase_id>.candidate.json`` — the ``.candidate.`` suffix keeps
the file out of any glob that filters by ``*.json`` (US5 baseline
loader).

File content
------------

A self-contained JSON document with the badcase content (camelCase,
matching the API response), the redaction audit id, the reviewer,
the reason, and a ``createdAt`` timestamp. The downstream
override-record tool reads this file and (after dual approval) writes
a sibling ``<badcase_id>.json`` to flip the candidate into the real
golden-case store.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Union

# Spec dir is the canonical default; this file lives at
# ``backend/app/modules/badcases/promotion.py`` so we go up 4 levels
# to find the repo root.
_REPO_ROOT = Path(__file__).resolve().parents[4]
_DEFAULT_GOLDEN_DIR = _REPO_ROOT / "specs" / "033-eval-pm-dashboard" / "golden"
_VALID_PROMOTION_LIFECYCLES = {"GOLDEN", "CANDIDATE", "REPORT_ONLY"}


def _resolve_golden_dir() -> Path:
    """Return the golden-candidate directory.

    Resolves ``$BADCASES_GOLDEN_DIR`` first; falls back to
    ``specs/033-eval-pm-dashboard/golden/`` under the repo root.
    The directory is created on demand.
    """
    override = os.environ.get("BADCASES_GOLDEN_DIR")
    if override:
        target = Path(override)
    else:
        target = _DEFAULT_GOLDEN_DIR
    target.mkdir(parents=True, exist_ok=True)
    return target


def promote_to_golden_candidate(
    badcase: Any,
    *,
    redaction_audit_id: str,
    reviewer: str,
    reason: str,
) -> Path:
    """Write a candidate JSON for ``badcase`` and return the file path.

    Parameters
    ----------
    badcase:
        Either an ORM row (with attribute access) or a Pydantic schema
        (with attribute access via alias). The function tolerates both
        so callers from the API and the CLI share the same code path.
    redaction_audit_id:
        The audit id that proves the candidate's privacy contract
        passed (FR-030).
    reviewer:
        Identity of the reviewer approving the promotion (FR-030).
    reason:
        Free-text justification for the promotion (FR-030).

    Returns
    -------
    pathlib.Path
        Absolute path of the candidate JSON file just written.
    """
    target_dir = _resolve_golden_dir()
    badcase_id = _badcase_id(badcase)
    target_path = target_dir / f"{badcase_id}.candidate.json"
    payload = _build_payload(
        badcase,
        redaction_audit_id=redaction_audit_id,
        reviewer=reviewer,
        reason=reason,
    )
    target_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    return target_path


def promote_badcase_to_eval_case(
    badcase: Any,
    *,
    lifecycle: str = "CANDIDATE",
    dataset_version: str = "candidate-v1",
    export_policy_decision_id: str | None = None,
    reviewer: str,
    reason: str,
) -> dict[str, Any]:
    """Build a REQ-045 eval-case payload from a governed badcase."""

    lifecycle_norm = lifecycle.strip().upper()
    if lifecycle_norm not in _VALID_PROMOTION_LIFECYCLES:
        raise ValueError(f"lifecycle must be one of {sorted(_VALID_PROMOTION_LIFECYCLES)}")
    if lifecycle_norm in {"GOLDEN", "CANDIDATE"}:
        redaction_status = str(_badcase_field(badcase, "redaction_status", "redactionStatus") or "")
        privacy_class = str(_badcase_field(badcase, "privacy_class", "privacyClass") or "")
        if redaction_status not in {"PASSED", "NOT_REQUIRED"}:
            raise ValueError("redaction must pass before candidate/golden promotion")
        if privacy_class == "SECRET":
            raise ValueError("secret badcases cannot be promoted to eval datasets")
    badcase_id = _badcase_id(badcase)
    return {
        "case_id": f"badcase-{badcase_id}",
        "node": "unknown.badcase",
        "label": f"Promoted badcase {badcase_id}",
        "source": "promoted",
        "input_state": {
            "badcase_id": badcase_id,
            "type": _badcase_field(badcase, "type"),
            "trace_id": _badcase_field(badcase, "trace_id", "traceId"),
            "run_id": str(_badcase_field(badcase, "run_id", "runId") or ""),
        },
        "llm_response": "",
        "expected_language": "zh-CN",
        "expected_contains": [],
        "expected_fidelity_pass": True,
        "status": "active",
        "lifecycle": lifecycle_norm,
        "dataset_version": dataset_version,
        "export_policy_decision_id": export_policy_decision_id,
        "reviewer": reviewer,
        "reason": reason,
        "blocks_merge": lifecycle_norm == "GOLDEN",
    }


def _badcase_id(badcase: Any) -> str:
    """Extract the ``badcaseId`` from either an ORM row or a Pydantic schema."""
    if isinstance(badcase, dict):
        value = badcase.get("badcase_id") or badcase.get("badcaseId")
        if value:
            return str(value)
    if hasattr(badcase, "badcase_id"):
        return str(badcase.badcase_id)
    if hasattr(badcase, "badcaseId"):
        return str(badcase.badcaseId)
    raise TypeError(f"cannot extract badcase_id from {type(badcase).__name__}")


def _badcase_field(badcase: Any, *names: str) -> Any:
    """Read a field by trying multiple attribute names (snake or camel)."""
    if isinstance(badcase, dict):
        for n in names:
            if n in badcase:
                return badcase[n]
    for n in names:
        if hasattr(badcase, n):
            return getattr(badcase, n)
    return None


def _build_payload(
    badcase: Any,
    *,
    redaction_audit_id: str,
    reviewer: str,
    reason: str,
) -> dict[str, Any]:
    """Build the candidate JSON payload.

    The shape mirrors the API ``/api/v1/badcases/{id}`` response so
    the candidate file is self-describing and can be diffed against
    the live API output.
    """
    closed_at = _badcase_field(badcase, "closed_at", "closedAt")
    return {
        "candidateId": _badcase_id(badcase),
        "badcaseId": _badcase_id(badcase),
        "badcase": {
            "badcaseId": _badcase_id(badcase),
            "type": _badcase_field(badcase, "type"),
            "severity": _badcase_field(badcase, "severity"),
            "status": _badcase_field(badcase, "status"),
            "source": _badcase_field(badcase, "source"),
            "reviewer": _badcase_field(badcase, "reviewer"),
            "privacyClass": _badcase_field(
                badcase, "privacy_class", "privacyClass"
            ),
            "redactionStatus": _badcase_field(
                badcase, "redaction_status", "redactionStatus"
            ),
            "runId": str(_badcase_field(badcase, "run_id", "runId"))
            if _badcase_field(badcase, "run_id", "runId")
            else None,
            "traceId": _badcase_field(badcase, "trace_id", "traceId"),
            "closureReason": _badcase_field(
                badcase, "closure_reason", "closureReason"
            ),
            "closedAt": closed_at.isoformat()
            if hasattr(closed_at, "isoformat")
            else closed_at,
        },
        "redactionAuditId": redaction_audit_id,
        "reviewer": reviewer,
        "reason": reason,
        "createdAt": datetime.now(timezone.utc).isoformat(),
    }


__all__ = ["promote_badcase_to_eval_case", "promote_to_golden_candidate"]
