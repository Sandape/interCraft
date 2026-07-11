# ruff: noqa: RUF001
"""select_materials + draft_derived nodes (deterministic MVP path)."""
from __future__ import annotations

import copy
from typing import Any

from app.agents.nodes.resume_derive.validate_sources import collect_root_refs, validate_sources
from app.agents.state.resume_derive_state import ResumeDeriveState
from app.modules.resume_intelligence.claims import Claim, SourceDocument, validate_claim_ledger
from app.modules.resume_intelligence.llm import invoke_structured
from app.modules.resume_intelligence.schemas import DraftOutput


def select_materials(state: ResumeDeriveState) -> dict[str, Any]:
    jd = state.get("jd_parse") or {}
    high = set(jd.get("priority_high") or [])
    mapped_refs = {
        ref.get("source_id")
        for requirement in (state.get("evidence_map") or {}).get("requirements") or []
        if requirement.get("coverage") in {"covered", "weak", "evidence_not_shown"}
        for ref in requirement.get("evidence_refs") or []
        if isinstance(ref, dict)
    }
    root = state.get("root_data") or {}
    sections = root.get("sections") if isinstance(root.get("sections"), dict) else {}

    included: list[dict[str, Any]] = []
    compressed: list[dict[str, Any]] = []
    hidden: list[dict[str, Any]] = []

    metadata = root.get("metadata") or {}
    markdown_meta = metadata.get("markdown") if isinstance(metadata, dict) else {}
    source_markdown = (
        markdown_meta.get("sourceMarkdown") if isinstance(markdown_meta, dict) else None
    )
    if isinstance(source_markdown, str) and source_markdown.strip():
        # Markdown-backed resumes are a first-class editor format. Treat the
        # whole document as a traceable source so an empty structured sections
        # map cannot silently erase the candidate's resume.
        included.append(
            {
                "ref": "root:markdown",
                "section": "markdown",
                "score": len(high),
                "item": {"sourceMarkdown": source_markdown},
            }
        )

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
            if ref in mapped_refs or score > 0:
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


async def draft_derived_ai(state: ResumeDeriveState) -> dict[str, Any]:
    """Use the real provider for evidence-bound rewriting, then validate claims."""
    baseline = draft_derived(state)
    inventory = list(state.get("source_inventory") or [])
    selected = {
        entry.get("ref")
        for bucket in ("included", "compressed")
        for entry in (state.get("selection_plan") or {}).get(bucket) or []
    }
    selected_sources = [item for item in inventory if item.get("source_id") in selected]
    result = await invoke_structured(
        user_id=str(state.get("user_id")),
        run_id=str(state.get("run_id")),
        node_name="resume_intelligence_draft",
        contract="draft.v1",
        output_model=DraftOutput,
        system_prompt=(
            "你是岗位定制简历编辑器。只能压缩、重组或改写给出的候选人来源，"
            "禁止新增数字、公司、项目、技能熟练度、职责、时间或成果。"
            "每条改写必须引用支持它的source_id；无证据要求只能省略。"
            "If root:markdown is present, it is the editor-authoritative resume. Return one rewrite "
            "whose source_ref is root:markdown and whose text is the complete tailored Markdown "
            "document. Preserve supported facts; reorder and compress them toward the job."
        ),
        payload={
            "job": {
                "position": state.get("job_position") or "",
                "requirements": (state.get("jd_parse") or {}).get("requirements") or [],
            },
            "selected_candidate_sources": selected_sources,
        },
    )
    output = result.model_dump(mode="json")
    markdown_is_authoritative = any(
        item.get("source_id") == "root:markdown" for item in selected_sources
    )
    has_markdown_rewrite = any(
        rewrite.get("source_ref") == "root:markdown" for rewrite in output["rewrites"]
    )
    if markdown_is_authoritative and not has_markdown_rewrite:
        # A schema-valid response can still be unusable for a Markdown-backed
        # editor (for example summary-only output). Perform one bounded semantic
        # repair call; never publish a fabricated deterministic rewrite.
        result = await invoke_structured(
            user_id=str(state.get("user_id")),
            run_id=str(state.get("run_id")),
            node_name="resume_intelligence_draft_markdown_repair",
            contract="draft.v1",
            output_model=DraftOutput,
            system_prompt=(
                "Return a complete job-tailored Markdown resume as exactly one rewrite with "
                "source_ref root:markdown and source_refs containing root:markdown. Keep every "
                "fact grounded in the supplied candidate source; do not add metrics, dates, roles, "
                "skills, employers, projects, or outcomes."
            ),
            payload={
                "job": {
                    "position": state.get("job_position") or "",
                    "requirements": (state.get("jd_parse") or {}).get("requirements") or [],
                },
                "selected_candidate_sources": selected_sources,
                "previous_schema_valid_but_incomplete_output": output,
            },
        )
        output = result.model_dump(mode="json")
    source_docs = {
        item["source_id"]: SourceDocument(
            source_id=item["source_id"], source_type="root_resume", text=item["text"]
        )
        for item in inventory
        if item.get("source_id") and item.get("text")
    }
    claims = [
        Claim(
            claim_id=f"rewrite:{index}",
            claim_type="metric" if any(char.isdigit() for char in rewrite["text"]) else "description",
            text=rewrite["text"],
            source_refs=list(rewrite["source_refs"]),
        )
        for index, rewrite in enumerate(output["rewrites"])
    ]
    ledger = validate_claim_ledger(claims, source_docs, strict=True)
    rejected_ids = {claim.claim_id for claim in ledger.rejected}
    accepted_rewrites = [
        rewrite
        for index, rewrite in enumerate(output["rewrites"])
        if f"rewrite:{index}" not in rejected_ids
    ]

    derived = copy.deepcopy(baseline["derived_data"])
    rewrite_by_ref = {rewrite["source_ref"]: rewrite for rewrite in accepted_rewrites}
    markdown_rewrite = rewrite_by_ref.get("root:markdown")
    sections = derived.get("sections") or {}
    if isinstance(sections, dict):
        for section_key, section in sections.items():
            items = section.get("items") if isinstance(section, dict) else section
            for index, item in enumerate(items or []):
                if not isinstance(item, dict):
                    continue
                ref = f"root:{section_key}:{item.get('id') or index}"
                rewrite = rewrite_by_ref.get(ref)
                if rewrite:
                    item["summary"] = rewrite["text"]
                    item["source_refs"] = rewrite["source_refs"]

    if output["summary"] and output["summary_source_refs"]:
        summary_claim = Claim(
            claim_id="summary",
            claim_type="metric" if any(c.isdigit() for c in output["summary"]) else "description",
            text=output["summary"],
            source_refs=list(output["summary_source_refs"]),
        )
        summary_ledger = validate_claim_ledger([summary_claim], source_docs, strict=True)
        if summary_ledger.accepted:
            derived["summary"] = {
                "content": output["summary"],
                "source_refs": output["summary_source_refs"],
            }

    metadata = derived.setdefault("metadata", {})
    derive_meta = metadata.setdefault("derive", {}) if isinstance(metadata, dict) else {}
    derive_meta["claimLedger"] = [
        {
            "claim_id": claim.claim_id,
            "verdict": claim.verdict,
            "reason": claim.reason,
            "source_refs": claim.source_refs,
        }
        for claim in [*ledger.accepted, *ledger.rejected]
    ]
    derive_meta["rejectedAIRewrites"] = [claim.claim_id for claim in ledger.rejected]
    md_meta = metadata.setdefault("markdown", {})
    if isinstance(md_meta, dict):
        if markdown_rewrite:
            md_meta["sourceMarkdown"] = markdown_rewrite["text"]
            md_meta["sourceRefs"] = markdown_rewrite["source_refs"]
        elif not str(md_meta.get("sourceMarkdown") or "").strip():
            md_meta["sourceMarkdown"] = _to_markdown(
                derived, list((state.get("jd_parse") or {}).get("keywords") or [])
            )
    derived = validate_sources(derived, allowed_refs=set(source_docs))
    return {
        **baseline,
        "derived_data": derived,
        "phase": "calibrate",
        "ai_draft": {
            "accepted_rewrites": len(accepted_rewrites),
            "rejected_rewrites": len(ledger.rejected),
            "schema_version": "draft.v1",
        },
    }


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
