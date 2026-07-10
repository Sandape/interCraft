"""Resume derive service — start/cancel/status/export-gate/supplements (REQ-055)."""
from __future__ import annotations

import copy
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.modules.jobs.models import Job
from app.agents.nodes.resume_derive.validate_sources import (
    collect_root_refs,
    validate_sources,
)
from app.modules.resume_derive.metrics import derive_runs_total, suggestion_apply_total
from app.modules.resume_derive.models import ResumeDeriveRun
from app.modules.resume_derive.repository import ResumeDeriveRepository
from app.modules.resume_derive.root_completeness import compute_root_completeness
from app.modules.resumes_v2.models import ResumeV2
from app.modules.resumes_v2.repository import ResumeV2Repository

log = get_logger("resume_derive")


class DeriveError(Exception):
    def __init__(self, status: int, code: str, message: str) -> None:
        self.status = status
        self.code = code
        self.message = message
        super().__init__(message)


class ResumeDeriveService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.runs = ResumeDeriveRepository(session)
        self.resumes = ResumeV2Repository(session)

    async def get_root(self, user_id: UUID) -> ResumeV2 | None:
        stmt = select(ResumeV2).where(
            ResumeV2.user_id == user_id,
            ResumeV2.resume_kind == "root",
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def create_root(
        self,
        *,
        user_id: UUID,
        name: str,
        slug: str,
        data: dict[str, Any] | None = None,
    ) -> ResumeV2:
        existing = await self.get_root(user_id)
        if existing is not None:
            raise DeriveError(409, "ROOT_EXISTS", "User already has a root resume.")

        from app.modules.resumes_v2.defaults import default_resume_data_v2

        payload = data or default_resume_data_v2()
        completeness = compute_root_completeness(payload)
        meta = payload.setdefault("metadata", {})
        if isinstance(meta, dict):
            meta["rootCompleteness"] = completeness

        row = await self.resumes.create(user_id=user_id, name=name, slug=slug, data=payload)
        row.resume_kind = "root"
        row.root_resume_id = None
        row.job_id = None
        row.target_page_count = None
        row.derive_meta = {}
        await self.session.flush()
        return row

    async def promote_to_root(self, *, user_id: UUID, source_id: UUID) -> ResumeV2:
        existing = await self.get_root(user_id)
        if existing is not None:
            raise DeriveError(409, "ROOT_EXISTS", "User already has a root resume.")

        source = await self.resumes.get(source_id, user_id=user_id)
        if source is None:
            raise DeriveError(404, "NOT_FOUND", "Source resume not found.")

        data = copy.deepcopy(source.data or {})
        completeness = compute_root_completeness(data)
        meta = data.setdefault("metadata", {})
        if isinstance(meta, dict):
            meta["rootCompleteness"] = completeness

        source.resume_kind = "root"
        source.root_resume_id = None
        source.job_id = None
        source.target_page_count = None
        source.actual_page_count = None
        source.data = data
        await self.session.flush()
        return source

    async def start_run(
        self,
        *,
        user_id: UUID,
        job_id: UUID,
        target_page_count: int,
        template_id: str = "pikachu",
        root_resume_id: UUID | None = None,
    ) -> ResumeDeriveRun:
        if target_page_count not in (1, 2, 3):
            raise DeriveError(400, "INVALID_TARGET_PAGES", "target_page_count must be 1, 2, or 3.")

        root = None
        if root_resume_id is not None:
            root = await self.resumes.get(root_resume_id, user_id=user_id)
            if root is None or root.resume_kind != "root":
                raise DeriveError(400, "NO_ROOT", "Specified root resume not found.")
        else:
            root = await self.get_root(user_id)
        if root is None:
            raise DeriveError(400, "NO_ROOT", "Create a root resume before deriving.")

        job = await self.session.get(Job, job_id)
        if job is None or job.user_id != user_id:
            raise DeriveError(404, "JOB_NOT_FOUND", "Job not found.")
        jd = (job.requirements_md or "").strip()
        if not jd:
            raise DeriveError(400, "NO_JD", "Job has no requirements_md; supplement JD first.")

        run = await self.runs.create(
            user_id=user_id,
            job_id=job_id,
            root_resume_id=root.id,
            root_version=int(root.version),
            target_page_count=target_page_count,
            template_id=template_id or "pikachu",
        )
        await self.session.commit()

        try:
            from app.core.redis import enqueue_job

            await enqueue_job("execute_resume_derive", run_id=str(run.id))
            log.info(
                "resume_derive.enqueued",
                run_id=str(run.id),
                job_id=str(job_id),
                calibrate_round=0,
                error_code=None,
            )
        except Exception as exc:
            # REQ-056 US6: surface enqueue failure — do not leave run forever "queued".
            run.status = "failed"
            run.error_code = "ENQUEUE_FAILED"
            run.error_message = f"派生后台暂不可用：{exc}"[:500]
            await self.session.commit()
            log.warning(
                "resume_derive.enqueue_failed",
                run_id=str(run.id),
                job_id=str(job_id),
                error_code="ENQUEUE_FAILED",
                error=str(exc),
            )
            raise DeriveError(
                503,
                "ENQUEUE_FAILED",
                "派生后台暂不可用，请稍后重试。",
            ) from exc

        return run

    async def get_run(self, run_id: UUID, *, user_id: UUID) -> ResumeDeriveRun:
        run = await self.runs.get(run_id, user_id=user_id)
        if run is None:
            raise DeriveError(404, "NOT_FOUND", "Derive run not found.")
        return run

    async def cancel_run(self, run_id: UUID, *, user_id: UUID) -> ResumeDeriveRun:
        run = await self.get_run(run_id, user_id=user_id)
        if run.status not in ("pending", "running"):
            raise DeriveError(409, "NOT_CANCELABLE", f"Run status is {run.status}.")
        updated = await self.runs.update_fields(
            run_id,
            user_id=user_id,
            status="canceled",
            finished_at=datetime.now(timezone.utc),
        )
        derive_runs_total.labels(status="canceled").inc()
        assert updated is not None
        await self.session.commit()
        return updated

    async def export_gate(self, resume_id: UUID, *, user_id: UUID) -> dict[str, Any]:
        from app.modules.resume_derive.metrics import export_page_mismatch_total

        row = await self.resumes.get(resume_id, user_id=user_id)
        if row is None:
            raise DeriveError(404, "NOT_FOUND", "Resume not found.")

        blockers: list[str] = []
        target = row.target_page_count
        actual = row.actual_page_count
        if row.resume_kind == "derived":
            if target is None:
                blockers.append("missing_target_page_count")
            if actual is None or target is None or int(actual) != int(target):
                blockers.append("page_count_mismatch")
            pending = ((row.data or {}).get("metadata") or {}).get("derive", {}).get(
                "pendingClaims"
            ) or []
            if pending:
                blockers.append("pending_claims")
            meta = row.derive_meta or {}
            if meta.get("export_blocked"):
                blockers.append(str(meta.get("export_blocked")))

        if "page_count_mismatch" in blockers:
            export_page_mismatch_total.inc()

        return {
            "exportable": len(blockers) == 0,
            "actual_page_count": actual,
            "target_page_count": target,
            "blockers": blockers,
        }

    async def list_derived_for_job(self, job_id: UUID, *, user_id: UUID) -> list[ResumeV2]:
        root = await self.get_root(user_id)
        root_version = int(root.version) if root else None
        stmt = (
            select(ResumeV2)
            .where(
                ResumeV2.user_id == user_id,
                ResumeV2.job_id == job_id,
                ResumeV2.resume_kind == "derived",
            )
            .order_by(ResumeV2.created_at.desc())
        )
        result = await self.session.execute(stmt)
        rows = list(result.scalars().all())
        # Annotate freshness via derive_meta for API layer
        for row in rows:
            meta = dict(row.derive_meta or {})
            meta["_is_from_latest_root"] = (
                root_version is not None
                and row.root_version_at_derive is not None
                and int(row.root_version_at_derive) >= int(root_version)
            )
            row.derive_meta = meta
        return rows

    async def apply_supplements(
        self,
        resume_id: UUID,
        *,
        user_id: UUID,
        answers: list[dict[str, str]],
        sync_target: str,
    ) -> ResumeV2:
        row = await self.resumes.get(resume_id, user_id=user_id)
        if row is None or row.resume_kind != "derived":
            raise DeriveError(404, "NOT_FOUND", "Derived resume not found.")

        data = copy.deepcopy(row.data or {})
        meta = data.setdefault("metadata", {})
        derive = meta.setdefault("derive", {}) if isinstance(meta, dict) else {}
        confirmed = derive.setdefault("confirmedSupplements", [])
        for ans in answers:
            confirmed.append(
                {
                    "question_id": ans["question_id"],
                    "text": ans["text"],
                    "sync_target": sync_target,
                    "confirmed_at": datetime.now(timezone.utc).isoformat(),
                }
            )
        # Clear matching pending claims
        pending = derive.get("pendingClaims") or []
        qids = {a["question_id"] for a in answers}
        derive["pendingClaims"] = [p for p in pending if p.get("question_id") not in qids]
        row.data = data

        if sync_target == "root":
            root = await self.get_root(user_id)
            if root is not None:
                root_data = copy.deepcopy(root.data or {})
                notes = (
                    root_data.setdefault("metadata", {}).setdefault("supplements", [])
                    if isinstance(root_data.get("metadata"), dict)
                    else []
                )
                notes.extend(confirmed[-len(answers) :])
                root.data = root_data

        # Refresh suggestions after confirmed facts (no fabrication).
        suggestions = list((row.derive_meta or {}).get("suggestions") or [])
        for s in suggestions:
            if isinstance(s, dict) and s.get("status") == "open":
                s["status"] = "needs_refresh"
        meta_out = dict(row.derive_meta or {})
        meta_out["suggestions"] = suggestions
        meta_out["last_supplement_at"] = datetime.now(timezone.utc).isoformat()
        row.derive_meta = meta_out

        log.info(
            "resume_derive.supplements_applied",
            run_id=None,
            job_id=str(row.job_id) if row.job_id else None,
            resume_id=str(resume_id),
            sync_target=sync_target,
            answer_count=len(answers),
        )
        await self.session.flush()
        await self.session.commit()
        return row

    def _find_suggestion(
        self, row: ResumeV2, suggestion_id: str
    ) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        suggestions = list((row.derive_meta or {}).get("suggestions") or [])
        for s in suggestions:
            if isinstance(s, dict) and str(s.get("id")) == suggestion_id:
                return s, suggestions
        raise DeriveError(404, "SUGGESTION_NOT_FOUND", "Suggestion not found.")

    async def preview_suggestion(
        self,
        resume_id: UUID,
        *,
        user_id: UUID,
        suggestion_id: str,
        client_version: int | None = None,
    ) -> dict[str, Any]:
        row = await self.resumes.get(resume_id, user_id=user_id)
        if row is None or row.resume_kind != "derived":
            raise DeriveError(404, "NOT_FOUND", "Derived resume not found.")
        if client_version is not None and int(client_version) != int(row.version):
            raise DeriveError(
                409,
                "VERSION_CONFLICT",
                "Resume changed since last load; refresh before applying.",
            )
        suggestion, _ = self._find_suggestion(row, suggestion_id)
        patch = suggestion.get("patch") or suggestion.get("proposed_patch") or {}
        preview_data = copy.deepcopy(row.data or {})
        if isinstance(patch, dict) and patch:
            preview_data = self._apply_patch(preview_data, patch)
        return {
            "suggestion_id": suggestion_id,
            "apply_mode": suggestion.get("apply_mode") or "direct",
            "preview_data": preview_data,
            "diff_summary": suggestion.get("problem") or suggestion.get("summary") or "",
            "preview_token": f"{resume_id}:{suggestion_id}:{row.version}",
        }

    async def apply_suggestion(
        self,
        resume_id: UUID,
        *,
        user_id: UUID,
        suggestion_id: str,
        client_version: int | None = None,
        preview_token: str | None = None,
    ) -> ResumeV2:
        row = await self.resumes.get(resume_id, user_id=user_id)
        if row is None or row.resume_kind != "derived":
            raise DeriveError(404, "NOT_FOUND", "Derived resume not found.")
        if client_version is not None and int(client_version) != int(row.version):
            suggestion_apply_total.labels(outcome="conflict").inc()
            raise DeriveError(
                409,
                "VERSION_CONFLICT",
                "Unsaved or concurrent edits conflict; cannot overwrite.",
            )
        suggestion, suggestions = self._find_suggestion(row, suggestion_id)
        if suggestion.get("apply_mode") not in (None, "direct"):
            raise DeriveError(
                400,
                "APPLY_MODE_UNSUPPORTED",
                f"apply_mode={suggestion.get('apply_mode')} requires manual edit.",
            )
        expected = f"{resume_id}:{suggestion_id}:{row.version}"
        if preview_token and preview_token != expected:
            suggestion_apply_total.labels(outcome="stale_preview").inc()
            raise DeriveError(409, "STALE_PREVIEW", "Preview is stale; re-preview first.")

        patch = suggestion.get("patch") or suggestion.get("proposed_patch") or {}
        data = copy.deepcopy(row.data or {})
        if isinstance(patch, dict) and patch:
            data = self._apply_patch(data, patch)

        root = None
        if row.root_resume_id:
            root = await self.resumes.get(row.root_resume_id, user_id=user_id)
        allowed = collect_root_refs((root.data if root else {}) or {})
        # Also allow confirmed supplements as sources
        for c in ((data.get("metadata") or {}).get("derive") or {}).get(
            "confirmedSupplements"
        ) or []:
            if isinstance(c, dict) and c.get("question_id"):
                allowed.add(f"supplement:{c['question_id']}")
        data = validate_sources(data, allowed_refs=allowed)

        suggestion["status"] = "applied"
        suggestion["applied_at"] = datetime.now(timezone.utc).isoformat()
        meta = dict(row.derive_meta or {})
        meta["suggestions"] = suggestions
        row.derive_meta = meta
        row.data = data
        row.version = int(row.version) + 1
        await self.session.flush()
        await self.session.commit()
        suggestion_apply_total.labels(outcome="applied").inc()
        log.info(
            "resume_derive.suggestion_applied",
            run_id=None,
            job_id=str(row.job_id) if row.job_id else None,
            resume_id=str(resume_id),
            suggestion_id=suggestion_id,
            calibrate_round=None,
            error_code=None,
        )
        return row

    @staticmethod
    def _apply_patch(data: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
        """Shallow-merge patch into resume data (MVP)."""
        out = copy.deepcopy(data)
        for key, value in patch.items():
            if key == "sections" and isinstance(value, dict):
                sections = out.setdefault("sections", {})
                if not isinstance(sections, dict):
                    out["sections"] = value
                else:
                    for sk, sv in value.items():
                        sections[sk] = sv
            elif key == "metadata" and isinstance(value, dict):
                meta = out.setdefault("metadata", {})
                if isinstance(meta, dict):
                    meta.update(value)
                else:
                    out["metadata"] = value
            else:
                out[key] = value
        return out
