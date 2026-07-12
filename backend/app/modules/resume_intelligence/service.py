# ruff: noqa: RUF001
"""REQ-059 analysis lifecycle and API projections."""
from __future__ import annotations

import copy
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.ids import new_uuid_v7
from app.modules.jobs.models import Job
from app.modules.resume_intelligence.comparison import compare_analyses, detect_stale_analysis
from app.modules.resume_intelligence.models import (
    ResumeAIChangeSet,
    ResumeAIFeedback,
    ResumeFitAnalysis,
)
from app.modules.resume_intelligence.observability import record_event_metric
from app.modules.resume_intelligence.repository import ResumeIntelligenceRepository
from app.modules.resume_intelligence.snapshots import (
    build_input_fingerprint,
    canonical_hash,
    normalize_jd_text,
)
from app.modules.resume_intelligence.supplements import persist_confirmed_supplement
from app.modules.resume_intelligence.suggestions import (
    SuggestionPatchError,
    apply_patch,
    find_conflicts,
    issue_preview_token,
    patch_digest,
    verify_preview_token,
)
from app.modules.resumes_v2.repository import ResumeV2Repository
from app.modules.versions.service import (
    VersionConflictError,
    assert_optimistic_version,
    build_ai_mutation_evidence,
)


class IntelligenceError(Exception):
    def __init__(
        self,
        status: int,
        code: str,
        message: str,
        *,
        retryable: bool | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        self.status = status
        self.code = code
        self.message = message
        self.retryable = status >= 500 if retryable is None else retryable
        self.details = details or {}
        super().__init__(message)


def _undo_is_safe(
    *,
    change_status: str,
    applied_hash: str,
    current_hash: str,
    current_version: int,
    client_version: int,
) -> bool:
    """Allow harmless version bumps, but never undo across content changes."""
    return (
        change_status == "applied"
        and current_version == client_version
        and current_hash == applied_hash
    )


class ResumeIntelligenceService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = ResumeIntelligenceRepository(session)
        self.resumes = ResumeV2Repository(session)

    async def start_analysis(
        self,
        *,
        user_id: UUID,
        resume_id: UUID,
        mode: str,
        client_version: int,
        job_id: UUID | None,
        force: bool,
    ) -> ResumeFitAnalysis:
        resume = await self.resumes.get(resume_id, user_id=user_id)
        if resume is None:
            raise IntelligenceError(404, "NOT_FOUND", "Resume not found.")
        try:
            assert_optimistic_version(
                current_version=int(resume.version),
                expected_version=int(client_version),
                message="Save or refresh the resume first.",
            )
        except VersionConflictError as exc:
            raise IntelligenceError(409, exc.code, exc.message) from exc
        if mode not in {"general", "job_fit"}:
            raise IntelligenceError(400, "INVALID_MODE", "Unknown analysis mode.")

        effective_job_id = job_id or getattr(resume, "job_id", None)
        job_snapshot: dict[str, Any] = {}
        jd_hash: str | None = None
        if mode == "job_fit":
            if effective_job_id is None:
                raise IntelligenceError(400, "NO_JD", "Job-fit analysis requires a job.")
            job = await self.session.get(Job, effective_job_id)
            if job is None or job.user_id != user_id:
                raise IntelligenceError(404, "JOB_CONTEXT_UNAVAILABLE", "Job not found.")
            jd = normalize_jd_text(job.requirements_md or "")
            if not jd:
                raise IntelligenceError(400, "NO_JD", "Job has no JD text.")
            job_snapshot = {
                "id": str(job.id),
                "company": job.company or "",
                "position": job.position or "",
                "requirements_md": jd,
            }
            jd_hash = canonical_hash(jd)

        current_snapshot = copy.deepcopy(resume.data or {})
        root_snapshot: dict[str, Any] = {}
        if getattr(resume, "root_resume_id", None):
            root = await self.resumes.get(resume.root_resume_id, user_id=user_id)
            if root is not None:
                root_snapshot = copy.deepcopy(root.data or {})
        if not root_snapshot:
            root_snapshot = copy.deepcopy(current_snapshot)

        resume_hash = canonical_hash(current_snapshot)
        fingerprint = build_input_fingerprint(
            operation=mode,
            resume_hash=resume_hash,
            jd_hash=jd_hash,
            prompt_version="resume-intelligence.v1",
            schema_version="analysis.v1",
            scoring_version="scoring.v1",
        )
        if not force:
            for existing in await self.repo.list_analyses(
                resume_id, user_id=user_id, mode=mode
            ):
                if existing.input_fingerprint == fingerprint and existing.status in {
                    "queued", "running", "complete", "partial"
                }:
                    return existing

        row = ResumeFitAnalysis(
            id=new_uuid_v7(),
            user_id=user_id,
            resume_id=resume_id,
            resume_version=int(resume.version),
            resume_hash=resume_hash,
            mode=mode,
            job_id=effective_job_id if mode == "job_fit" else None,
            jd_hash=jd_hash,
            job_snapshot=job_snapshot,
            status="queued",
            source_manifest={
                "current_snapshot": current_snapshot,
                "root_snapshot": root_snapshot,
            },
            input_fingerprint=fingerprint,
            dimensions={},
            requirements=[],
            summary={},
            hard_blockers=[],
            quality_flags={},
            error_detail_safe={},
        )
        runtime = await self._accept_canonical_task(
            user_id=user_id,
            resume_id=resume_id,
            resume_version=int(resume.version),
            job_id=str(effective_job_id) if effective_job_id and mode == "job_fit" else None,
            jd_hash=jd_hash,
            mode=mode,
            domain_run_id=row.id,
        )
        if runtime:
            row.source_manifest = {
                **(row.source_manifest or {}),
                "ai_task_id": runtime.get("task_id"),
                "ai_execution_id": runtime.get("execution_id"),
                "runtime_links": {
                    "status_url": runtime.get("status_url"),
                    "events_url": runtime.get("events_url"),
                },
            }
            row.quality_flags = {
                **(row.quality_flags or {}),
                "acceptance": runtime.get("acceptance_envelope"),
            }
        await self.repo.add_analysis(row)
        await self.session.commit()
        try:
            from app.core.redis import enqueue_job

            await enqueue_job(
                "execute_resume_analysis",
                analysis_id=str(row.id),
                user_id=str(user_id),
                _job_id=f"analysis:{row.id}",
            )
        except Exception as exc:
            row.status = "failed"
            row.error_code = "ENQUEUE_FAILED"
            row.error_detail_safe = {"category": type(exc).__name__}
            row.finished_at = datetime.now(UTC)
            await self.session.commit()
            raise IntelligenceError(503, "ENQUEUE_FAILED", "Analysis worker unavailable.") from exc
        return row

    async def _accept_canonical_task(
        self,
        *,
        user_id: UUID,
        resume_id: UUID,
        resume_version: int,
        job_id: str | None,
        jd_hash: str | None,
        mode: str,
        domain_run_id: UUID,
        service_tier: str = "standard",
        allow_degrade: bool = False,
    ) -> dict[str, Any] | None:
        """Create durable TaskAccepted envelope; best-effort when metering unavailable."""
        from app.modules.ai_runtime.acceptance import AcceptanceError, AcceptanceService
        from app.modules.ai_runtime.adapters import resume_intelligence as intel
        from app.modules.ai_runtime.adapters.runtime_links import (
            acceptance_result_payload,
            envelope_payload,
            runtime_links_for_task,
        )

        snap = intel.build_input_snapshot(
            resume_id=str(resume_id),
            resume_version=resume_version,
            job_id=job_id,
            jd_hash=jd_hash,
            mode=mode,
            extra={"domain_run_id": str(domain_run_id)},
        )
        snap_ref = f"resume-intelligence:{resume_id}:v{resume_version}:{domain_run_id}"
        adapter = intel.ResumeIntelligenceAdapter(action="analyze")
        envelope = adapter.build_acceptance_envelope(
            service_tier=service_tier,
            input_snapshot_ref=snap_ref,
            allow_degrade=allow_degrade,
            input_payload=snap,
        )
        envelope_dict = envelope_payload(envelope)
        try:
            svc = AcceptanceService(self.session)
            quote = await svc.create_quote(
                user_id=user_id,
                capability=intel.CAPABILITY_CODE,
                action="analyze",
                service_tier=service_tier,
                input_snapshot_ref=snap_ref,
                allow_degrade=allow_degrade,
                idempotency_key=f"quote:{domain_run_id}",
            )
            result = await svc.accept(
                user_id=user_id,
                capability=intel.CAPABILITY_CODE,
                action="analyze",
                service_tier=service_tier,
                quote_id=quote.quote_id,
                input_snapshot_ref=snap_ref,
                allow_degrade=allow_degrade,
                idempotency_key=f"accept:{domain_run_id}",
            )
            accepted = acceptance_result_payload(svc, result)
            accepted["acceptance_envelope"] = envelope_dict
            return accepted
        except AcceptanceError:
            # Domain run may still proceed; surface envelope + placeholder links.
            links = runtime_links_for_task(domain_run_id)
            return {
                "task_id": str(domain_run_id),
                "execution_id": None,
                "status": "accepted",
                "status_url": links["status_url"],
                "events_url": links["events_url"],
                "acceptance_envelope": envelope_dict,
                "degraded_acceptance": True,
            }
        except Exception:
            return {
                "acceptance_envelope": envelope_dict,
                "degraded_acceptance": True,
            }

    @staticmethod
    def start_response_payload(row: ResumeFitAnalysis) -> dict[str, Any]:
        """Canonical start envelope for intelligence-runs (REQ-061 T065)."""
        from app.modules.ai_runtime.adapters import resume_intelligence as intel
        from app.modules.ai_runtime.adapters.runtime_links import runtime_links_for_task

        manifest = row.source_manifest or {}
        task_id = manifest.get("ai_task_id")
        links = (
            runtime_links_for_task(task_id)
            if task_id
            else {
                "task_id": None,
                "status_url": f"/api/v1/v2/resume-intelligence/runs/{row.id}",
                "events_url": None,
            }
        )
        return {
            "run_id": str(row.id),
            "analysis_id": str(row.id),
            "status": row.status,
            "status_url": f"/api/v1/v2/resume-intelligence/runs/{row.id}",
            "task_id": task_id,
            "execution_id": manifest.get("ai_execution_id"),
            "runtime": links,
            "acceptance": (row.quality_flags or {}).get("acceptance"),
            "canonical_status": intel.map_domain_status(row.status).value,
            "available_actions": intel.projection_actions(row.status),
            "milestones": [
                {"code": code, "status": "pending"} for code in intel.MILESTONE_CODES
            ],
        }

    async def cancel_analysis(self, *, user_id: UUID, analysis_id: UUID) -> ResumeFitAnalysis:
        row = await self.repo.cancel_analysis(analysis_id, user_id=user_id)
        if row is None:
            raise IntelligenceError(404, "NOT_FOUND", "Run not found.")
        await self.session.commit()
        record_event_metric(operation="analyze", status="cancelled", category="none")
        return row

    async def cancel_run(self, *, user_id: UUID, run_id: UUID) -> dict[str, Any]:
        analysis = await self.repo.get_analysis(run_id, user_id=user_id)
        if analysis is not None:
            row = await self.cancel_analysis(user_id=user_id, analysis_id=run_id)
            return self.run_status_payload(row)
        try:
            from app.modules.resume_derive.service import DeriveError, ResumeDeriveService

            derive = await ResumeDeriveService(self.session).cancel_run(run_id, user_id=user_id)
            return {
                "run_id": str(derive.id),
                "status": derive.status,
                "phase": derive.phase,
                "progress_percent": derive.progress_pct,
                "components": derive.component_status or {},
                "derived_resume_id": str(derive.derived_resume_id) if derive.derived_resume_id else None,
                "analysis_id": str(derive.analysis_id) if derive.analysis_id else None,
                "retryable_components": [],
                "error": None,
                "created_at": derive.created_at.isoformat(),
                "finished_at": derive.finished_at.isoformat() if derive.finished_at else None,
            }
        except Exception as exc:
            if exc.__class__.__name__ == "DeriveError":
                raise IntelligenceError(exc.status, exc.code, exc.message) from exc
            raise

    async def regenerate_suggestions(
        self,
        *,
        user_id: UUID,
        analysis_id: UUID,
        idempotency_key: str,
    ) -> dict[str, Any]:
        analysis = await self.repo.get_analysis(analysis_id, user_id=user_id)
        if analysis is None:
            raise IntelligenceError(404, "NOT_FOUND", "Analysis not found.")
        if analysis.status not in {"complete", "partial"}:
            raise IntelligenceError(409, "RUN_TERMINAL", "Analysis is not ready for suggestion regeneration.")
        try:
            from app.core.redis import enqueue_job

            await enqueue_job(
                "execute_resume_analysis",
                analysis_id=str(analysis.id),
                user_id=str(user_id),
                operation="regenerate_suggestions",
                _job_id=f"suggestions:{analysis.id}:{idempotency_key}",
            )
        except Exception as exc:
            raise IntelligenceError(
                503,
                "MODEL_UNAVAILABLE",
                "Suggestion regeneration worker unavailable.",
                retryable=True,
            ) from exc
        return {
            "run_id": str(analysis.id),
            "status": "queued",
            "status_url": f"/api/v1/v2/resume-intelligence/runs/{analysis.id}",
            "idempotent_replay": False,
        }

    async def update_suggestion_status(
        self,
        *,
        user_id: UUID,
        suggestion_id: UUID,
        action: str,
        reason: str | None,
    ) -> Any:
        target = {"ignore": "ignored", "defer": "deferred", "open": "open", "reopen": "open"}.get(action)
        if target is None:
            raise IntelligenceError(400, "INVALID_STATUS", "Unknown suggestion status action.")
        row = await self.repo.update_suggestion_status(
            suggestion_id,
            user_id=user_id,
            status=target,
            reason=reason,
        )
        if row is None:
            raise IntelligenceError(404, "NOT_FOUND", "Suggestion not found.")
        await self.session.commit()
        return row

    async def submit_feedback(
        self,
        *,
        user_id: UUID,
        analysis_id: UUID,
        category: str,
        suggestion_id: UUID | None = None,
        change_set_id: UUID | None = None,
        comment: str | None = None,
    ) -> ResumeAIFeedback:
        analysis = await self.repo.get_analysis(analysis_id, user_id=user_id)
        if analysis is None:
            raise IntelligenceError(404, "NOT_FOUND", "Analysis not found.")
        if suggestion_id is not None:
            suggestion = await self.repo.get_suggestion(suggestion_id, user_id=user_id)
            if suggestion is None or suggestion.analysis_id != analysis_id:
                raise IntelligenceError(404, "NOT_FOUND", "Suggestion not found.")
        if change_set_id is not None:
            change_set = await self.repo.get_change_set(change_set_id, user_id=user_id)
            if change_set is None or change_set.analysis_id != analysis_id:
                raise IntelligenceError(404, "NOT_FOUND", "Change set not found.")
        row = ResumeAIFeedback(
            id=new_uuid_v7(),
            user_id=user_id,
            analysis_id=analysis_id,
            suggestion_id=suggestion_id,
            change_set_id=change_set_id,
            category=category,
            comment=comment,
        )
        await self.repo.add_feedback(row)
        await self.session.commit()
        record_event_metric(operation="feedback", status="succeeded", category=category)
        return row

    async def compare_analyses(
        self,
        *,
        user_id: UUID,
        before_analysis_id: UUID,
        after_analysis_id: UUID,
    ) -> dict[str, Any]:
        before = await self.repo.get_analysis(before_analysis_id, user_id=user_id)
        after = await self.repo.get_analysis(after_analysis_id, user_id=user_id)
        if before is None or after is None:
            raise IntelligenceError(404, "NOT_FOUND", "Analysis not found.")
        return compare_analyses(
            self.analysis_payload(before),
            self.analysis_payload(after),
        )

    async def confirm_supplement(
        self,
        *,
        user_id: UUID,
        resume_id: UUID,
        question_id: str,
        text: str,
        scope: str,
        confirmed: bool,
    ) -> dict[str, Any]:
        resume = await self.resumes.get(resume_id, user_id=user_id)
        if resume is None:
            raise IntelligenceError(404, "NOT_FOUND", "Resume not found.")
        data = copy.deepcopy(resume.data or {})
        fact = persist_confirmed_supplement(
            data,
            user_id=user_id,
            resume_id=resume_id,
            question_id=question_id,
            text=text,
            scope=scope,  # type: ignore[arg-type]
            confirmed=confirmed,
        )
        new_version = await self.resumes.update_with_version(
            resume_id,
            user_id=user_id,
            if_match=int(resume.version),
            data=data,
        )
        if new_version is None:
            raise IntelligenceError(409, "VERSION_CONFLICT", "Resume changed while confirming supplement.")
        if fact.scope == "root" and getattr(resume, "root_resume_id", None):
            root = await self.resumes.get(resume.root_resume_id, user_id=user_id)
            if root is not None:
                root_data = copy.deepcopy(root.data or {})
                persist_confirmed_supplement(
                    root_data,
                    user_id=user_id,
                    resume_id=root.id,
                    question_id=question_id,
                    text=text,
                    scope="root",
                    confirmed=confirmed,
                )
                await self.resumes.update_with_version(
                    root.id,
                    user_id=user_id,
                    if_match=int(root.version),
                    data=root_data,
                )
        await self.session.commit()
        return {"supplement": fact.to_payload(), "resume_version": new_version}

    async def preview_suggestions(
        self,
        *,
        user_id: UUID,
        resume_id: UUID,
        analysis_id: UUID,
        suggestion_ids: list[UUID],
        client_version: int,
    ) -> dict[str, Any]:
        analysis = await self.repo.get_analysis(analysis_id, user_id=user_id)
        resume = await self.resumes.get(resume_id, user_id=user_id)
        if analysis is None or resume is None or analysis.resume_id != resume_id:
            raise IntelligenceError(404, "NOT_FOUND", "Analysis or resume not found.")
        try:
            assert_optimistic_version(
                current_version=int(resume.version),
                expected_version=int(client_version),
                message="Resume changed; save and preview again.",
            )
        except VersionConflictError as exc:
            raise IntelligenceError(409, exc.code, exc.message) from exc
        requested = []
        for suggestion_id in suggestion_ids:
            suggestion = await self.repo.get_suggestion(suggestion_id, user_id=user_id)
            if suggestion is None or suggestion.analysis_id != analysis_id:
                raise IntelligenceError(404, "NOT_FOUND", "Suggestion not found.")
            requested.append(suggestion)

        blocked = [
            {
                "suggestion_ids": [str(item.id)],
                "code": "FACTS_REQUIRED" if item.action_mode == "needs_supplement" else "NOT_DIRECT",
                "message": "This suggestion requires user facts or judgment.",
            }
            for item in requested
            if item.action_mode != "direct" or not item.proposed_patch
        ]
        compatible = [item for item in requested if item.action_mode == "direct" and item.proposed_patch]
        # Anti-fabrication: never preview explicitly fabricated suggestions.
        from app.modules.ai_runtime.adapters import resume_intelligence as intel

        gated_compatible = []
        for item in compatible:
            verdict = intel.evaluate_quality_gate(
                milestone_code="suggestions",
                result_payload={
                    "action_mode": item.action_mode,
                    "source_refs": item.source_refs or ["legacy"],
                    "fabricated": bool(getattr(item, "fabricated", False)),
                },
            )
            if verdict.code == "FABRICATION_BLOCKED" or not verdict.deliverable:
                blocked.append(
                    {
                        "suggestion_ids": [str(item.id)],
                        "code": verdict.code,
                        "message": verdict.message,
                    }
                )
            else:
                gated_compatible.append(item)
        compatible = gated_compatible
        operations = [operation for item in compatible for operation in item.proposed_patch]
        conflicts = find_conflicts(operations)
        if conflicts:
            return {
                "preview_token": None,
                "expires_at": None,
                "base_resume_version": int(resume.version),
                "compatible": [],
                "conflicts": [{"suggestion_ids": [str(item.id) for item in compatible], "code": "SUGGESTION_CONFLICT", "message": ", ".join(conflicts)}],
                "blocked": blocked,
                "diff": None,
                "page_impact": {"status": "needs_measurement", "export_gate_stale": True},
                "evidence": build_ai_mutation_evidence(
                    operation="preview",
                    resume_id=resume_id,
                    base_version=int(resume.version),
                    suggestion_ids=[str(item.id) for item in requested],
                    fact_gate_passed=False,
                    extra={"conflicts": conflicts},
                ),
            }
        try:
            preview_data, inverse = apply_patch(resume.data or {}, operations)
        except SuggestionPatchError as exc:
            raise IntelligenceError(422, exc.code, str(exc)) from exc
        token = issue_preview_token(
            {
                "user_id": str(user_id),
                "resume_id": str(resume_id),
                "analysis_id": str(analysis_id),
                "suggestion_ids": [str(item.id) for item in compatible],
                "base_resume_version": int(resume.version),
                "patches": operations,
                "inverse": inverse,
                "patch_digest": patch_digest(operations),
            }
        )
        for item in compatible:
            item.status = "previewed"
        evidence = build_ai_mutation_evidence(
            operation="preview",
            resume_id=resume_id,
            base_version=int(resume.version),
            suggestion_ids=[str(item.id) for item in compatible],
            preview_digest=patch_digest(operations) if operations else None,
            fact_gate_passed=True,
        )
        flags = dict(analysis.quality_flags or {})
        lifecycle = list(flags.get("suggestion_lifecycle") or [])
        lifecycle.append(evidence)
        flags["suggestion_lifecycle"] = lifecycle[-20:]
        analysis.quality_flags = flags
        await self.session.commit()
        before_md = (((resume.data or {}).get("metadata") or {}).get("markdown") or {}).get("sourceMarkdown") or ""
        after_md = ((preview_data.get("metadata") or {}).get("markdown") or {}).get("sourceMarkdown") or before_md
        return {
            "preview_token": token,
            "base_resume_version": int(resume.version),
            "compatible": [str(item.id) for item in compatible],
            "conflicts": [],
            "blocked": blocked,
            "diff": {
                "before_markdown": before_md,
                "after_markdown": after_md,
                "patches": operations,
                "before_data": resume.data,
                "after_data": preview_data,
            },
            "page_impact": {"status": "needs_measurement", "export_gate_stale": True},
            "evidence": evidence,
        }

    async def apply_suggestions(
        self,
        *,
        user_id: UUID,
        resume_id: UUID,
        preview_token: str,
        client_version: int,
        idempotency_key: str,
    ) -> tuple[Any, ResumeAIChangeSet]:
        try:
            claims = verify_preview_token(preview_token)
        except SuggestionPatchError as exc:
            raise IntelligenceError(409, exc.code, str(exc)) from exc
        if claims.get("user_id") != str(user_id) or claims.get("resume_id") != str(resume_id):
            raise IntelligenceError(409, "STALE_PREVIEW", "Preview ownership mismatch.")
        if int(claims.get("base_resume_version")) != int(client_version):
            raise IntelligenceError(409, "STALE_PREVIEW", "Preview version mismatch.")
        resume = await self.resumes.get(resume_id, user_id=user_id)
        if resume is None:
            raise IntelligenceError(404, "NOT_FOUND", "Resume not found.")
        try:
            assert_optimistic_version(
                current_version=int(resume.version),
                expected_version=int(client_version),
                message="Resume changed after preview.",
            )
        except VersionConflictError as exc:
            raise IntelligenceError(409, exc.code, exc.message) from exc
        operations = list(claims.get("patches") or [])
        if patch_digest(operations) != claims.get("patch_digest"):
            raise IntelligenceError(409, "STALE_PREVIEW", "Preview content mismatch.")
        try:
            updated_data, inverse = apply_patch(resume.data or {}, operations)
        except SuggestionPatchError as exc:
            raise IntelligenceError(422, exc.code, str(exc)) from exc
        new_version = await self.resumes.update_with_version(
            resume_id,
            user_id=user_id,
            if_match=client_version,
            data=updated_data,
        )
        if new_version is None:
            raise IntelligenceError(409, "VERSION_CONFLICT", "Resume changed during apply.")
        change_set = ResumeAIChangeSet(
            id=new_uuid_v7(),
            user_id=user_id,
            resume_id=resume_id,
            analysis_id=UUID(str(claims["analysis_id"])),
            base_resume_version=client_version,
            result_resume_version=new_version,
            suggestion_ids=list(claims.get("suggestion_ids") or []),
            forward_patch=operations,
            inverse_patch=inverse,
            before_hash=canonical_hash(resume.data or {}),
            after_hash=canonical_hash(updated_data),
            preview_digest=str(claims["patch_digest"]),
            idempotency_key=idempotency_key,
            status="applied",
        )
        self.session.add(change_set)
        evidence = build_ai_mutation_evidence(
            operation="apply",
            resume_id=resume_id,
            base_version=client_version,
            result_version=new_version,
            suggestion_ids=list(claims.get("suggestion_ids") or []),
            change_set_id=str(change_set.id),
            preview_digest=str(claims["patch_digest"]),
            fact_gate_passed=True,
        )
        analysis = await self.repo.get_analysis(UUID(str(claims["analysis_id"])), user_id=user_id)
        if analysis is not None:
            flags = dict(analysis.quality_flags or {})
            lifecycle = list(flags.get("suggestion_lifecycle") or [])
            lifecycle.append(evidence)
            flags["suggestion_lifecycle"] = lifecycle[-20:]
            analysis.quality_flags = flags
        for raw_id in change_set.suggestion_ids:
            suggestion = await self.repo.get_suggestion(UUID(raw_id), user_id=user_id)
            if suggestion:
                suggestion.status = "applied"
                suggestion.applied_change_set_id = change_set.id
        await self.session.commit()
        from app.core.db import set_rls_user_id

        await set_rls_user_id(self.session, user_id)
        canonical = await self.resumes.get(resume_id, user_id=user_id)
        assert canonical is not None
        # Attach evidence for API consumers without changing the tuple contract.
        setattr(change_set, "_evidence", evidence)
        return canonical, change_set

    async def undo_change_set(
        self,
        *,
        user_id: UUID,
        change_set_id: UUID,
        client_version: int,
        idempotency_key: str,
    ) -> tuple[Any, ResumeAIChangeSet]:
        original = await self.repo.get_change_set(change_set_id, user_id=user_id)
        if original is None:
            raise IntelligenceError(404, "NOT_FOUND", "Change set not found.")
        resume = await self.resumes.get(original.resume_id, user_id=user_id)
        if resume is None:
            raise IntelligenceError(404, "NOT_FOUND", "Resume not found.")
        current_hash = canonical_hash(resume.data or {})
        if not _undo_is_safe(
            change_status=original.status,
            applied_hash=original.after_hash,
            current_hash=current_hash,
            current_version=int(resume.version),
            client_version=int(client_version),
        ):
            raise IntelligenceError(409, "UNDO_CONFLICT", "Later edits prevent automatic undo.")
        try:
            restored, redo_patch = apply_patch(resume.data or {}, original.inverse_patch)
        except SuggestionPatchError as exc:
            raise IntelligenceError(409, "UNDO_CONFLICT", str(exc)) from exc
        new_version = await self.resumes.update_with_version(
            resume.id, user_id=user_id, if_match=client_version, data=restored
        )
        if new_version is None:
            raise IntelligenceError(409, "UNDO_CONFLICT", "Resume changed during undo.")
        undo = ResumeAIChangeSet(
            id=new_uuid_v7(),
            user_id=user_id,
            resume_id=resume.id,
            analysis_id=original.analysis_id,
            base_resume_version=client_version,
            result_resume_version=new_version,
            suggestion_ids=original.suggestion_ids,
            forward_patch=original.inverse_patch,
            inverse_patch=redo_patch,
            before_hash=canonical_hash(resume.data or {}),
            after_hash=canonical_hash(restored),
            preview_digest=canonical_hash(original.inverse_patch),
            idempotency_key=idempotency_key,
            status="applied",
            undo_of_change_set_id=original.id,
        )
        self.session.add(undo)
        original.status = "undone"
        original.undone_at = datetime.now(UTC)
        evidence = build_ai_mutation_evidence(
            operation="undo",
            resume_id=resume.id,
            base_version=client_version,
            result_version=new_version,
            suggestion_ids=list(original.suggestion_ids or []),
            change_set_id=str(undo.id),
            preview_digest=undo.preview_digest,
            fact_gate_passed=True,
            extra={"undo_of_change_set_id": str(original.id)},
        )
        if original.analysis_id is not None:
            analysis = await self.repo.get_analysis(original.analysis_id, user_id=user_id)
            if analysis is not None:
                flags = dict(analysis.quality_flags or {})
                lifecycle = list(flags.get("suggestion_lifecycle") or [])
                lifecycle.append(evidence)
                flags["suggestion_lifecycle"] = lifecycle[-20:]
                analysis.quality_flags = flags
        for raw_id in original.suggestion_ids:
            suggestion = await self.repo.get_suggestion(UUID(raw_id), user_id=user_id)
            if suggestion:
                suggestion.status = "undone"
        await self.session.commit()
        from app.core.db import set_rls_user_id

        await set_rls_user_id(self.session, user_id)
        canonical = await self.resumes.get(resume.id, user_id=user_id)
        assert canonical is not None
        setattr(undo, "_evidence", evidence)
        return canonical, undo

    @staticmethod
    def suggestion_payload(row: Any) -> dict[str, Any]:
        return {
            "id": str(row.id),
            "analysis_id": str(row.analysis_id),
            "base_resume_version": row.base_resume_version,
            "kind": row.kind,
            "action_mode": row.action_mode,
            "priority": row.priority,
            "title": row.title,
            "explanation": row.explanation,
            "anchor": row.anchor,
            "source_refs": row.source_refs,
            "requirement_refs": row.requirement_refs,
            "page_impact": row.page_impact,
            "status": row.status,
            "status_reason": row.status_reason,
        }

    @staticmethod
    def run_status_payload(row: ResumeFitAnalysis) -> dict[str, Any]:
        from app.modules.ai_runtime.adapters import resume_intelligence as intel
        from app.modules.ai_runtime.adapters.runtime_links import (
            milestone_projection,
            runtime_links_for_task,
        )

        terminal = row.status in {"complete", "partial", "failed", "cancelled"}
        domain_status = "succeeded" if row.status == "complete" else row.status
        manifest = row.source_manifest or {}
        task_id = manifest.get("ai_task_id")
        delivered = ()
        failed = ()
        if row.status == "complete":
            delivered = ("analysis", "suggestions")
        elif row.status == "partial":
            delivered = ("analysis",)
            failed = ("suggestions",)
        elif row.status == "failed":
            failed = ("analysis",)
        payload = {
            "run_id": str(row.id),
            "analysis_id": str(row.id),
            "status": domain_status,
            "phase": "done" if terminal else "analysis",
            "progress_percent": 100 if terminal else 35,
            "components": {"analysis": "succeeded" if row.status == "complete" else row.status},
            "retryable_components": ["analysis"] if row.status == "failed" else [],
            "error": (
                {"code": row.error_code, "message": row.error_code, "retryable": row.status == "failed"}
                if row.error_code else None
            ),
            "created_at": row.created_at.isoformat(),
            "finished_at": row.finished_at.isoformat() if row.finished_at else None,
            "canonical_status": intel.map_domain_status(domain_status).value,
            "available_actions": intel.projection_actions(domain_status),
            "milestones": milestone_projection(
                codes=intel.MILESTONE_CODES,
                delivered=delivered,
                failed=failed,
                running=None if terminal else "analysis",
            ),
            "acceptance": (row.quality_flags or {}).get("acceptance"),
            "task_id": task_id,
        }
        if task_id:
            payload["runtime"] = runtime_links_for_task(task_id)
        else:
            payload["runtime"] = {
                "task_id": None,
                "status_url": f"/api/v1/v2/resume-intelligence/runs/{row.id}",
                "events_url": None,
            }
        return payload

    @staticmethod
    def analysis_payload(row: ResumeFitAnalysis, *, current_version: int | None = None) -> dict[str, Any]:
        stale_check = detect_stale_analysis(
            analysis_resume_version=row.resume_version,
            current_resume_version=current_version if current_version is not None else row.resume_version,
            analysis_jd_hash=row.jd_hash,
            current_jd_hash=row.jd_hash,
            job_refreshable=row.job_id is not None or row.mode != "job_fit",
            scoring_version=row.scoring_version,
        )
        return {
            "id": str(row.id),
            "resume_id": str(row.resume_id),
            "resume_version": row.resume_version,
            "mode": row.mode,
            "status": row.status,
            "is_stale": stale_check.is_stale,
            "stale_reasons": stale_check.reasons,
            "overall_score": float(row.overall_score) if row.overall_score is not None else None,
            "confidence_score": float(row.confidence_score) if row.confidence_score is not None else None,
            "confidence_band": row.confidence_band,
            "job_context": {
                "job_id": str(row.job_id) if row.job_id else None,
                "company": row.job_snapshot.get("company"),
                "position": row.job_snapshot.get("position"),
                "jd_hash": row.jd_hash,
                "refreshable": row.job_id is not None,
            } if row.mode == "job_fit" else None,
            "dimensions": (row.dimensions or {}).get("items", []),
            "gaps": row.requirements or [],
            "hard_blockers": row.hard_blockers or [],
            "summary": row.summary or {},
            "disclaimer": (
                "匹配分表示当前简历对当前 JD 的证据覆盖与表达质量，"
                "不是 ATS 官方分数，也不预测面试或录用结果。"
                if row.mode == "job_fit" else "通用体检不包含岗位匹配分。"
            ),
            "scoring_version": row.scoring_version,
            "prompt_version": row.prompt_version,
            "schema_version": row.schema_version,
            "error_code": row.error_code,
            "created_at": row.created_at.isoformat(),
            "finished_at": row.finished_at.isoformat() if row.finished_at else None,
        }
