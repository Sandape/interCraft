"""Root completeness hints (non-blocking) — REQ-055 FR-005."""
from __future__ import annotations

from typing import Any


_PROJECT_DIMS = ("background", "responsibility", "tech", "result", "metrics")


def compute_root_completeness(data: dict[str, Any]) -> dict[str, Any]:
    """Return a soft completeness report for root resume metadata.

    Never blocks save/derive; product shows as hints only.
    """
    sections = (data or {}).get("sections") or {}
    projects = []
    if isinstance(sections, dict):
        raw = sections.get("projects") or sections.get("project") or []
        if isinstance(raw, dict):
            projects = raw.get("items") or []
        elif isinstance(raw, list):
            projects = raw

    project_gaps: list[dict[str, Any]] = []
    for idx, proj in enumerate(projects):
        if not isinstance(proj, dict):
            continue
        missing = []
        text_blob = " ".join(
            str(proj.get(k) or "") for k in ("summary", "description", "bullets", "name", "title")
        ).lower()
        bullets = proj.get("bullets") or proj.get("highlights") or []
        if isinstance(bullets, list):
            text_blob += " " + " ".join(str(b) for b in bullets).lower()

        checks = {
            "background": any(w in text_blob for w in ("背景", "background", "context")),
            "responsibility": any(w in text_blob for w in ("负责", "responsibility", "owned", "lead")),
            "tech": any(w in text_blob for w in ("技术", "stack", "架构", "react", "python", "llm")),
            "result": any(w in text_blob for w in ("结果", "result", "outcome", "上线")),
            "metrics": any(ch.isdigit() for ch in text_blob) and any(
                w in text_blob for w in ("%", "提升", "降低", "用户", "qps", "ms")
            ),
        }
        for dim in _PROJECT_DIMS:
            if not checks.get(dim):
                missing.append(dim)
        if missing:
            project_gaps.append(
                {
                    "index": idx,
                    "name": proj.get("name") or proj.get("title") or f"project-{idx}",
                    "missing": missing,
                }
            )

    return {
        "project_gaps": project_gaps,
        "hint_only": True,
        "score_forced": False,
    }
