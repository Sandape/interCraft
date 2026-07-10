"""Page calibrate node — budget heuristics + guidance (REQ-055 US3)."""
from __future__ import annotations

from typing import Any

from app.agents.state.resume_derive_state import ResumeDeriveState

MAX_ROUNDS = 5


def _estimate_pages(markdown: str, *, line_height_factor: float = 1.0) -> int:
    """Rough page estimate from markdown length (A4 ~ 3200 chars/page at default)."""
    text = markdown or ""
    chars = max(1, len(text))
    per_page = int(3200 * line_height_factor)
    pages = (chars + per_page - 1) // per_page
    return max(1, pages)


def calibrate_pages(state: ResumeDeriveState) -> dict[str, Any]:
    target = int(state.get("target_page_count") or 1)
    derived = state.get("derived_data") or {}
    md = (
        ((derived.get("metadata") or {}).get("markdown") or {}).get("sourceMarkdown")
        if isinstance(derived.get("metadata"), dict)
        else ""
    ) or ""

    round_no = int(state.get("calibrate_round") or 0)
    strategies: list[str] = []
    measured = _estimate_pages(md)
    factor = 1.0

    while measured != target and round_no < MAX_ROUNDS:
        round_no += 1
        if measured > target:
            # Compress: trim markdown by dropping trailing sections content
            strategies.append("compress_weak_content")
            lines = md.splitlines()
            keep = max(20, int(len(lines) * (target / measured) * 0.9))
            md = "\n".join(lines[:keep])
            factor = max(0.85, factor - 0.05)
            strategies.append("tighten_line_height")
        else:
            strategies.append("expand_from_included")
            # Expand: append unused material blurbs if any
            unused = state.get("unused_materials") or []
            extra = []
            for u in unused[:3]:
                extra.append(f"\n### 补充素材\n- {u.get('ref')}")
            md = md + "\n".join(extra)
            factor = min(1.2, factor + 0.05)
            strategies.append("relax_spacing")
        measured = _estimate_pages(md, line_height_factor=factor)

    # Persist markdown back
    if isinstance(derived.get("metadata"), dict):
        md_meta = derived["metadata"].setdefault("markdown", {})
        if isinstance(md_meta, dict):
            md_meta["sourceMarkdown"] = md
            md_meta["pageCount"] = measured
            md_meta["paginationState"] = "ready"

    page_report = {
        "target": target,
        "measured": measured,
        "rounds": round_no,
        "strategies": strategies,
    }

    if measured == target:
        return {
            "derived_data": derived,
            "page_report": page_report,
            "calibrate_round": round_no,
            "status": "succeeded",
            "phase": "done",
        }

    guidance = [
        "建议切换为更紧凑的模板",
        "建议隐藏低相关模块或减少项目数量",
        "建议改选其他目标页数，或补充/精简根简历素材",
    ]
    return {
        "derived_data": derived,
        "page_report": page_report,
        "calibrate_round": round_no,
        "status": "needs_guidance",
        "phase": "needs_guidance",
        "error_code": "DERIVE_INFEASIBLE",
        "error_message": "自动校准后仍无法严格满足目标页数",
        "suggestions": (state.get("suggestions") or [])
        + [
            {
                "id": f"guidance-{i}",
                "priority": "high",
                "type": "page",
                "location": "page",
                "problem": g,
                "apply_mode": "do_not_write",
                "status": "open",
            }
            for i, g in enumerate(guidance)
        ],
    }
