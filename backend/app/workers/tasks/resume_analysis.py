# ruff: noqa: RUF001
"""ARQ worker for real-LLM general/job-fit resume analysis."""
from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.nodes.resume_derive.map_evidence import build_source_inventory
from app.agents.nodes.resume_derive.parse_jd import parse_jd_ai
from app.core.db import get_session_factory
from app.core.ids import new_uuid_v7
from app.core.logging import get_logger
from app.modules.resume_intelligence.gaps import gap_payloads
from app.modules.resume_intelligence.llm import invoke_structured
from app.modules.resume_intelligence.models import ResumeAISuggestion, ResumeFitAnalysis
from app.modules.resume_intelligence.schemas import EvidenceMapOutput, SuggestionListOutput
from app.modules.resume_intelligence.scoring import (
    Coverage,
    RequirementScoreInput,
    ScoringInput,
    calculate_job_fit,
)

log = get_logger("resume_intelligence.worker")


async def _bind_tenant(session: AsyncSession, user_id: UUID | str) -> None:
    await session.execute(
        text("SELECT set_config('app.user_id', :uid, true)"), {"uid": str(user_id)}
    )


def _patch_for_suggestion(
    *, source_ref: str | None, replacement_text: str | None, current: dict
) -> list[dict[str, object]]:
    if not source_ref or not replacement_text or not source_ref.startswith("current:"):
        return []
    parts = source_ref.split(":", 2)
    if source_ref == "current:markdown":
        markdown = ((current.get("metadata") or {}).get("markdown") or {}).get(
            "sourceMarkdown"
        )
        if not isinstance(markdown, str):
            return []
        original_headings = [
            line.strip() for line in markdown.splitlines() if line.lstrip().startswith("#")
        ]
        replacement_headings = [
            line.strip()
            for line in replacement_text.splitlines()
            if line.lstrip().startswith("#")
        ]
        if (
            not original_headings
            or not replacement_headings
            or replacement_headings[0] != original_headings[0]
            or any(heading not in replacement_headings for heading in original_headings[1:])
            or len(replacement_text.strip()) < max(20, int(len(markdown.strip()) * 0.6))
        ):
            return []
        return [
            {
                "op": "replace",
                "path": "/metadata/markdown/sourceMarkdown",
                "value": replacement_text,
            }
        ]
    if source_ref == "current:summary":
        return [{"op": "replace", "path": "/summary/content", "value": replacement_text}]
    if len(parts) != 3:
        return []
    section_key, item_id = parts[1], parts[2]
    section = (current.get("sections") or {}).get(section_key)
    items = section.get("items") if isinstance(section, dict) else section
    for index, item in enumerate(items or []):
        if isinstance(item, dict) and str(item.get("id") or index) == item_id:
            return [
                {
                    "op": "add" if "summary" not in item else "replace",
                    "path": f"/sections/{section_key}/items/{index}/summary",
                    "value": replacement_text,
                }
            ]
    return []


async def execute_resume_analysis(
    ctx: dict, *, analysis_id: str, user_id: str, **kwargs: object
) -> dict[str, object]:
    _ = (ctx, kwargs)
    factory = get_session_factory()
    async with factory() as session:
        await _bind_tenant(session, user_id)
        analysis = await session.get(ResumeFitAnalysis, UUID(analysis_id))
        if analysis is None or str(analysis.user_id) != user_id:
            return {"error": "analysis_not_found"}
        if analysis.status in {"complete", "partial", "failed", "cancelled"}:
            return {"analysis_id": analysis_id, "status": analysis.status, "idempotent_replay": True}
        analysis.status = "running"
        await session.commit()

        # ``set_config(..., true)`` is transaction-local by design. Publishing
        # the running state ends that transaction, so bind the tenant again
        # before the eventual suggestion inserts and analysis update.
        await _bind_tenant(session, user_id)

        manifest = dict(analysis.source_manifest or {})
        current = manifest.get("current_snapshot") or {}
        root = manifest.get("root_snapshot") or current
        current_inventory = build_source_inventory(current, prefix="current")
        root_inventory = build_source_inventory(root, prefix="root")
        all_sources = [*current_inventory, *root_inventory]

        try:
            if analysis.mode == "job_fit":
                state = {
                    "user_id": user_id,
                    "run_id": analysis_id,
                    "jd_text": analysis.job_snapshot.get("requirements_md") or "",
                    "job_company": analysis.job_snapshot.get("company") or "",
                    "job_position": analysis.job_snapshot.get("position") or "",
                }
                parsed = (await parse_jd_ai(state))["jd_parse"]
                evidence = await invoke_structured(
                    user_id=user_id,
                    run_id=analysis_id,
                    node_name="resume_intelligence_map_evidence",
                    contract="evidence_map.v1",
                    output_model=EvidenceMapOutput,
                    system_prompt=(
                        "把岗位要求映射到候选人来源。current来源表示当前稿，root来源表示根简历。"
                        "仅root有证据时必须标为evidence_not_shown；没有来源不得标covered。"
                    ),
                    payload={"requirements": parsed["requirements"], "candidate_sources": all_sources},
                )
                mapped = evidence.model_dump(mode="json")["requirements"]
                categories = {r["requirement_id"]: r["category"] for r in parsed["requirements"]}
                requirements = [
                    RequirementScoreInput(
                        requirement_id=item["requirement_id"],
                        priority=item["priority"],
                        dimension=categories.get(item["requirement_id"], "hard_requirements"),
                        coverage=Coverage(item["coverage"]),
                    )
                    for item in mapped
                ]
                body = str(current)
                quantified = min(100.0, 25.0 + 12.5 * sum(ch.isdigit() for ch in body))
                readability = 85.0 if 200 <= len(body) <= 12000 else 60.0
                score = calculate_job_fit(
                    ScoringInput(
                        requirements=requirements,
                        outcomes_quantification=quantified,
                        expression_readability=readability,
                        jd_completeness=float(parsed["jd_quality"]),
                        evidence_trace_coverage=(
                            sum(bool(item["evidence_refs"]) for item in mapped) / len(mapped)
                            if mapped else 0.0
                        ),
                        schema_validation_quality=1.0,
                    )
                )
                analysis.overall_score = score.overall_score
                analysis.confidence_score = score.confidence_score
                analysis.confidence_band = score.confidence_band
                analysis.dimensions = {
                    "items": [
                        {"key": d.key, "weight": d.weight, "score": d.score, "explanation": "由已验证证据覆盖确定性计算", "requirement_ids": []}
                        for d in score.dimensions
                    ]
                }
                analysis.requirements = gap_payloads(parsed["requirements"], mapped)
                analysis.hard_blockers = score.hard_blockers
            else:
                analysis.overall_score = None
                analysis.confidence_score = None
                analysis.confidence_band = None
                analysis.dimensions = {"items": []}
                analysis.requirements = []

            suggestions = await invoke_structured(
                user_id=user_id,
                run_id=analysis_id,
                node_name="resume_intelligence_suggestions",
                contract="suggestions.v1",
                output_model=SuggestionListOutput,
                system_prompt=(
                    "生成具体、非重复的简历建议。无真实来源时必须needs_supplement、needs_judgment或do_not_write，"
                    "不得把JD要求写成候选人事实。若现有来源可以只通过重排、压缩或改写来改善表达，"
                    "至少生成一条action_mode为direct的建议，并同时返回source_ref、source_refs和replacement_text；"
                    "direct建议不得增加任何事实、数字、技能、职责或结果。若source_ref是current:markdown，"
                    "replacement_text必须是完整Markdown文档，保留原始一级标题与全部章节标题，不能只返回局部段落。"
                ),
                payload={
                    "mode": analysis.mode,
                    "gaps": analysis.requirements,
                    "candidate_sources": all_sources,
                },
            )
            for item in suggestions.suggestions:
                source_ids = set(item.source_refs)
                if not source_ids.issubset({s["source_id"] for s in all_sources}):
                    continue
                proposed_patch = (
                    _patch_for_suggestion(
                        source_ref=item.source_ref,
                        replacement_text=item.replacement_text,
                        current=current,
                    )
                    if item.source_ref in source_ids
                    else []
                )
                action_mode = item.action_mode
                if action_mode == "direct" and not proposed_patch:
                    action_mode = "needs_judgment"
                session.add(
                    ResumeAISuggestion(
                        id=new_uuid_v7(),
                        user_id=analysis.user_id,
                        analysis_id=analysis.id,
                        resume_id=analysis.resume_id,
                        base_resume_version=analysis.resume_version,
                        kind=item.kind,
                        action_mode=action_mode,
                        priority=item.priority,
                        title=item.title,
                        explanation=item.explanation,
                        anchor={"node_id": "markdown", "start": 0, "end": 0, "context_checksum": analysis.resume_hash[:16]},
                        source_refs=[{"source_id": ref} for ref in item.source_refs],
                        requirement_refs=item.requirement_refs,
                        proposed_patch=proposed_patch,
                        page_impact={"status": "needs_measurement", "export_gate_stale": True},
                        status="open",
                    )
                )
            analysis.summary = {"suggestion_count": len(suggestions.suggestions)}
            analysis.status = "complete"
            analysis.finished_at = datetime.now(UTC)
            await session.commit()
            return {"analysis_id": analysis_id, "status": "complete"}
        except Exception as exc:
            log.exception(
                "resume_intelligence.analysis_failed",
                analysis_id=analysis_id,
                user_id=user_id,
                error_category=type(exc).__name__,
            )
            await session.rollback()
            await _bind_tenant(session, user_id)
            locked = (
                await session.execute(
                    select(ResumeFitAnalysis)
                    .where(ResumeFitAnalysis.id == UUID(analysis_id))
                    .with_for_update()
                )
            ).scalar_one_or_none()
            if locked is not None:
                locked.status = "failed"
                locked.error_code = "ANALYSIS_FAILED"
                locked.error_detail_safe = {"category": type(exc).__name__}
                locked.finished_at = datetime.now(UTC)
                await session.commit()
            return {"analysis_id": analysis_id, "status": "failed", "error": type(exc).__name__}
