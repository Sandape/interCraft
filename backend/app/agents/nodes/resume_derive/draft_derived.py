"""select_materials + draft_derived nodes (deterministic MVP path)."""
from __future__ import annotations

import copy
from typing import Any

from app.agents.nodes.resume_derive.validate_sources import collect_root_refs, validate_sources
from app.agents.state.resume_derive_state import ResumeDeriveState


def select_materials(state: ResumeDeriveState) -> dict[str, Any]:
    jd = state.get("jd_parse") or {}
    high = set(jd.get("priority_high") or [])
    root = state.get("root_data") or {}
    sections = root.get("sections") if isinstance(root.get("sections"), dict) else {}

    included: list[dict[str, Any]] = []
    compressed: list[dict[str, Any]] = []
    hidden: list[dict[str, Any]] = []

    for key, section in (sections or {}).items():
        items = []
        if isinstance(section, dict):
            items = section.get("items") or []
        elif isinstance(section, list):
            items = section
        for idx, item in enumerate(items if isinstance(items, list) else []):
            blob = str(item).lower()
            score = sum(1 for k in high if k in blob)
            ref = f"root:{key}:{item.get('id') if isinstance(item, dict) and item.get('id') else idx}"
            entry = {"ref": ref, "section": key, "score": score, "item": item}
            if score > 0:
                included.append(entry)
            elif key in ("projects", "experience", "work"):
                compressed.append(entry)
            else:
                hidden.append(entry)

    # Always keep basics
    plan = {
        "included": included,
        "compressed": compressed[:3],
        "hidden": hidden,
        "must_show": ["basics", "summary"],
    }
    return {"selection_plan": plan, "phase": "draft"}


def draft_derived(state: ResumeDeriveState) -> dict[str, Any]:
    root = copy.deepcopy(state.get("root_data") or {})
    plan = state.get("selection_plan") or {}
    jd = state.get("jd_parse") or {}
    allowed = collect_root_refs(root)

    # Build a slimmed sections map from included + compressed
    keep_refs = {e["ref"] for e in (plan.get("included") or [])} | {
        e["ref"] for e in (plan.get("compressed") or [])
    }
    sections_in = root.get("sections") if isinstance(root.get("sections"), dict) else {}
    new_sections: dict[str, Any] = {}
    unused: list[dict[str, Any]] = []

    for key, section in (sections_in or {}).items():
        items = []
        if isinstance(section, dict):
            items = list(section.get("items") or [])
            base = {k: v for k, v in section.items() if k != "items"}
        elif isinstance(section, list):
            items = list(section)
            base = {}
        else:
            continue

        kept_items = []
        for idx, item in enumerate(items):
            ref = f"root:{key}:{item.get('id') if isinstance(item, dict) and item.get('id') else idx}"
            if ref in keep_refs or key in ("education",):
                if isinstance(item, dict):
                    item = dict(item)
                    item["source_refs"] = [ref]
                    item.setdefault("id", f"{key}-{idx}")
                kept_items.append(item)
            else:
                unused.append({"ref": ref, "reason": "low_relevance", "section": key})

        if isinstance(section, dict):
            new_sections[key] = {**base, "items": kept_items}
        else:
            new_sections[key] = kept_items

    # Rewrite summary toward JD keywords (expression only)
    summary = root.get("summary")
    keywords = jd.get("priority_high") or []
    takeaways = [
        f"优先展示与 JD 高优先级能力相关的素材：{', '.join(keywords) or '（未识别到关键词）'}",
        f"纳入 {len(plan.get('included') or [])} 项强相关素材，压缩 {len(plan.get('compressed') or [])} 项。",
    ]
    missing = jd.get("evidence_missing") or []
    questions = []
    for m in missing[:5]:
        questions.append(
            {
                "question_id": f"gap-{m}",
                "text": f"JD 强调「{m}」，根简历暂无明确证据。你是否有相关经历？请补充具体职责、指标与结果。",
                "apply_mode": "needs_supplement",
            }
        )
        takeaways.append(f"未将「{m}」写入正文（根简历无依据），已生成补充问题。")

    derived = {
        "picture": root.get("picture") or {},
        "basics": root.get("basics") or {},
        "summary": summary
        if summary
        else {
            "content": f"面向 {state.get('job_position') or '目标岗位'} 的定向简历摘要。",
            "source_refs": ["root:summary"],
            "require_source": False,
        },
        "sections": new_sections,
        "customSections": root.get("customSections") or [],
        "metadata": {
            **(root.get("metadata") if isinstance(root.get("metadata"), dict) else {}),
            "derive": {
                "unusedMaterials": unused,
                "sourceMap": {},
                "pendingClaims": [
                    {"question_id": q["question_id"], "reason": "evidence_missing"} for q in questions
                ],
                "jd_keywords": keywords,
            },
            "markdown": (root.get("metadata") or {}).get("markdown")
            if isinstance(root.get("metadata"), dict)
            else {},
        },
    }

    # Ensure markdown source exists for editor
    md_meta = derived["metadata"].setdefault("markdown", {})
    if isinstance(md_meta, dict) and not str(md_meta.get("sourceMarkdown") or "").strip():
        md_meta["sourceMarkdown"] = _to_markdown(derived, keywords)

    derived = validate_sources(derived, allowed_refs=allowed)

    suggestions = []
    for q in questions:
        suggestions.append(
            {
                "id": q["question_id"],
                "priority": "high",
                "type": "data_gap",
                "location": "root",
                "problem": q["text"],
                "apply_mode": "needs_supplement",
                "status": "open",
            }
        )
    if keywords:
        suggestions.append(
            {
                "id": "kw-order",
                "priority": "mid",
                "type": "reorder",
                "location": "skills",
                "problem": "建议按 JD 相关度排序技能模块",
                "apply_mode": "direct",
                "status": "open",
            }
        )

    return {
        "derived_data": derived,
        "unused_materials": unused,
        "takeaway_notes": takeaways,
        "suggestions": suggestions,
        "supplement_questions": questions,
        "allowed_refs": sorted(allowed),
        "phase": "calibrate",
    }


def _to_markdown(derived: dict[str, Any], keywords: list[str]) -> str:
    lines: list[str] = []
    basics = derived.get("basics") or {}
    if isinstance(basics, dict):
        name = basics.get("name") or basics.get("fullName") or "候选人"
        lines.append(f"# {name}")
    if keywords:
        lines.append("")
        lines.append(f"> 目标关键词：{', '.join(keywords)}")
    summary = derived.get("summary")
    if isinstance(summary, dict) and summary.get("content"):
        lines.append("")
        lines.append("## 个人总结")
        lines.append(str(summary["content"]))
    sections = derived.get("sections") or {}
    if isinstance(sections, dict):
        for key, section in sections.items():
            lines.append("")
            lines.append(f"## {key}")
            items = section.get("items") if isinstance(section, dict) else section
            for item in items or []:
                if not isinstance(item, dict):
                    continue
                title = item.get("name") or item.get("title") or item.get("company") or "条目"
                lines.append(f"### {title}")
                for b in item.get("bullets") or item.get("highlights") or []:
                    lines.append(f"- {b}")
                if item.get("summary"):
                    lines.append(f"- {item['summary']}")
    lines.append("")
    return "\n".join(lines)
