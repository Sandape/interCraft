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


def _badcase_id(badcase: Any) -> str:
    """Extract the ``badcaseId`` from either an ORM row or a Pydantic schema."""
    if hasattr(badcase, "badcase_id"):
        return str(badcase.badcase_id)
    if hasattr(badcase, "badcaseId"):
        return str(badcase.badcaseId)
    raise TypeError(f"cannot extract badcase_id from {type(badcase).__name__}")


def _badcase_field(badcase: Any, *names: str) -> Any:
    """Read a field by trying multiple attribute names (snake or camel)."""
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


__all__ = ["promote_to_golden_candidate"]