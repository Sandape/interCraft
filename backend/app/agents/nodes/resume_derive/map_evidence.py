"""Map parsed requirements to root-resume evidence through structured LLM."""
from __future__ import annotations

import json
from typing import Any

from app.agents.state.resume_derive_state import ResumeDeriveState
from app.modules.resume_intelligence.llm import invoke_structured
from app.modules.resume_intelligence.schemas import EvidenceMapOutput
from app.modules.resume_intelligence.snapshots import canonical_hash


def build_source_inventory(
    root: dict[str, Any], *, prefix: str = "root"
) -> list[dict[str, str]]:
    inventory: list[dict[str, str]] = []
    metadata = root.get("metadata") or {}
    markdown_meta = metadata.get("markdown") if isinstance(metadata, dict) else {}
    source_markdown = (
        markdown_meta.get("sourceMarkdown") if isinstance(markdown_meta, dict) else None
    )
    if isinstance(source_markdown, str) and source_markdown.strip():
        inventory.append(
            {
                "source_id": f"{prefix}:markdown",
                "source_type": "current_resume" if prefix == "current" else "root_resume",
                "anchor": "metadata.markdown.sourceMarkdown",
                "content_hash": canonical_hash(source_markdown),
                "text": source_markdown,
            }
        )
    summary = root.get("summary")
    if summary:
        text = json.dumps(summary, ensure_ascii=False)
        inventory.append(
            {
                "source_id": f"{prefix}:summary",
                "source_type": "current_resume" if prefix == "current" else "root_resume",
                "anchor": "summary",
                "content_hash": canonical_hash(text),
                "text": text,
            }
        )
    sections = root.get("sections") or {}
    if not isinstance(sections, dict):
        return inventory
    for key, section in sections.items():
        items = section.get("items") if isinstance(section, dict) else section
        for index, item in enumerate(items or []):
            if not isinstance(item, dict):
                continue
            item_id = item.get("id") or index
            text = json.dumps(item, ensure_ascii=False)
            inventory.append(
                {
                    "source_id": f"{prefix}:{key}:{item_id}",
                    "source_type": "current_resume" if prefix == "current" else "root_resume",
                    "anchor": f"sections.{key}.{item_id}",
                    "content_hash": canonical_hash(text),
                    "text": text,
                }
            )
    return inventory


async def map_evidence_ai(state: ResumeDeriveState) -> dict[str, Any]:
    inventory = build_source_inventory(state.get("root_data") or {})
    result = await invoke_structured(
        user_id=str(state.get("user_id")),
        run_id=str(state.get("run_id")),
        node_name="resume_intelligence_map_evidence",
        contract="evidence_map.v1",
        output_model=EvidenceMapOutput,
        system_prompt=(
            "你是候选人证据映射器。对每项岗位要求仅引用提供的source_id。"
            "区分已覆盖、偏弱、根简历有但当前稿未展示、缺少证据、真实能力缺口和无法判断。"
            "JD本身绝不是候选人证据。"
        ),
        payload={
            "requirements": (state.get("jd_parse") or {}).get("requirements") or [],
            "candidate_sources": inventory,
        },
    )
    return {
        "source_inventory": inventory,
        "evidence_map": result.model_dump(mode="json"),
        "phase": "select",
    }
