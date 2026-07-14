"""Resume derive service — start/cancel/status/export-gate/supplements (REQ-055)."""

from __future__ import annotations

import contextlib
import copy
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.nodes.resume_derive.validate_sources import (
    collect_root_refs,
    validate_sources,
)
from app.core.logging import get_logger
from app.modules.jobs.models import Job
from app.modules.resume_derive.metrics import derive_runs_total, suggestion_apply_total
from app.modules.resume_derive.models import ResumeDeriveRun
from app.modules.resume_derive.repository import ResumeDeriveRepository
from app.modules.resume_derive.root_completeness import compute_root_completeness
from app.modules.resume_derive.themes import normalize_derive_theme_id
from app.modules.resume_intelligence.snapshots import (
    build_input_fingerprint,
    canonical_hash,
    normalize_jd_text,
)
from app.modules.resumes_v2.models import ResumeV2
from app.modules.resumes_v2.repository import ResumeV2Repository

log = get_logger("resume_derive")

# Both the root partial unique index and the slug unique constraint can fire
# during a root-insert race (the repository first flushes a standard row, then
# the service sets resume_kind='root').  Accept either as a valid race indicator.
_EXPECTED_RACE_CONSTRAINTS = frozenset(
    {
        "uq_resumes_v2_one_root_per_user",
        "uq_resumes_v2_user_slug",
    }
)


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
        """Create the user's first (and only) root resume.

        Concurrent / racing POSTs for the same user must always resolve to
        a single row: the second caller must observe a stable
        ``DeriveError(409, "ROOT_EXISTS")`` and not a 500, and must NEVER
        overwrite the row already persisted by the winner. We enforce that
        contract with three layers:

        1. Pre-flight existence check (RLS-scoped `get_root`) — handles the
           common case without a write.
        2. SAVEPOINT around the actual INSERT so a concurrent transaction
           that lost the race raises a unique/conflict error inside the
           savepoint without aborting our transaction.
        3. Post-INSERT re-read — after the savepoint commits the row, we
           re-query `get_root` and, if a different winner is now visible,
           treat this caller as a loser and surface ROOT_EXISTS instead of
           returning the duplicated row.

        Structured logs carry identifiers, outcome codes, and content lengths
        only — never resume content, the marker string, the full JSON payload,
        or raw database exception text. Unit tests enforce both safe key names
        and safe values across success and conflict paths.
        """
        existing = await self.get_root(user_id)
        if existing is not None:
            log.info(
                "resume_derive.create_root.conflict",
                user_id=str(user_id),
                existing_root_id=str(existing.id),
                outcome="root_exists_preflight",
            )
            raise DeriveError(409, "ROOT_EXISTS", "User already has a root resume.")

        from app.modules.resumes_v2.defaults import default_resume_data_v2

        payload = data if isinstance(data, dict) else default_resume_data_v2()
        completeness = compute_root_completeness(payload)
        meta = payload.setdefault("metadata", {})
        if isinstance(meta, dict):
            meta["rootCompleteness"] = completeness

        marker_length = 0
        try:
            md = meta.get("markdown") if isinstance(meta, dict) else None
            if isinstance(md, dict):
                src = md.get("sourceMarkdown")
                if isinstance(src, str):
                    marker_length = len(src)
        except Exception:
            marker_length = 0

        # Race-safe insert: SAVEPOINT isolates the INSERT from any unique /
        # RLS conflict that a concurrent winner may surface, so we can
        # recover into a clean state without aborting the outer transaction.
        savepoint = await self.session.begin_nested()
        try:
            row = await self.resumes.create(user_id=user_id, name=name, slug=slug, data=payload)
            row.resume_kind = "root"
            row.root_resume_id = None
            row.job_id = None
            row.target_page_count = None
            row.derive_meta = {}
            await self.session.flush()
        except IntegrityError as exc:
            # Walk the exc.orig / __cause__ / __context__ chain to find the
            # constraint_name (asyncpg may nest it on __cause__.constraint_name
            # or __context__.diag.constraint_name). Reuses the pattern proven
            # in test_migration_0055.py:_postgres_error_identity.
            constraint_name: str | None = None
            pending: list[BaseException | Any] = [exc.orig]
            seen: set[int] = set()
            while pending:
                current = pending.pop(0)
                if current is None or id(current) in seen:
                    continue
                seen.add(id(current))
                if constraint_name is None:
                    constraint_name = getattr(current, "constraint_name", None)
                if constraint_name is None:
                    diag = getattr(current, "diag", None)
                    if diag is not None:
                        constraint_name = getattr(diag, "constraint_name", None)
                if constraint_name is None:
                    pending.extend(
                        c
                        for c in (
                            getattr(current, "__cause__", None),
                            getattr(current, "__context__", None),
                        )
                        if c is not None
                    )

            # Both the root partial unique index and the slug unique constraint
            # can fire during a root-insert race (the repository first flushes a
            # standard row, then the service sets resume_kind='root').  Accept
            # either as a valid race indicator; for any other constraint name
            # (e.g. a different slug or an FK) we re-raise so the caller sees a
            # legitimate DB error.
            resolved = constraint_name or ""

            # Roll back the SAVEPOINT regardless (it contained the failed
            # INSERT) so the outer transaction is clean for the re-read.
            await savepoint.rollback()

            if resolved not in _EXPECTED_RACE_CONSTRAINTS:
                raise

            # The constraint is one of the expected race indicators.  Re-read
            # the root — if a winner root actually exists this is a genuine
            # ROOT_EXISTS; otherwise something unexpected happened and we
            # propagate the original error.
            winner = await self.get_root(user_id)
            if winner is None:
                raise

            log.info(
                "resume_derive.create_root.conflict",
                user_id=str(user_id),
                existing_root_id=str(winner.id),
                outcome="root_exists_unique_conflict",
            )
            raise DeriveError(409, "ROOT_EXISTS", "User already has a root resume.") from exc
        except Exception:
            # Only the two explicitly recognised uniqueness constraints above
            # may become ROOT_EXISTS. A generic runtime/database failure must
            # keep its original type and traceback even if another request
            # happened to create a root concurrently; otherwise a real defect
            # would be hidden behind a recoverable 409.
            with contextlib.suppress(Exception):
                await savepoint.rollback()
            raise

        # Savepoint succeeded — but a concurrent winner may have written a
        # different root row in the time between our preflight `get_root`
        # and the INSERT. Re-read after the savepoint to detect that case
        # and discard our duplicate without ever overwriting the winner.
        winner_after = await self.get_root(user_id)
        if winner_after is not None and winner_after.id != row.id:
            await savepoint.rollback()
            log.info(
                "resume_derive.create_root.conflict",
                user_id=str(user_id),
                existing_root_id=str(winner_after.id),
                outcome="root_exists_post_insert",
            )
            raise DeriveError(409, "ROOT_EXISTS", "User already has a root resume.")

        await savepoint.commit()
        log.info(
            "resume_derive.create_root.success",
            user_id=str(user_id),
            root_id=str(row.id),
            marker_length=marker_length,
            name_length=len(name or ""),
        )
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
        template_id: str = "muji-default-autumn",
        root_resume_id: UUID | None = None,
        idempotency_key: str | None = None,
        enqueue_immediately: bool = True,
    ) -> ResumeDeriveRun:
        if target_page_count not in (1, 2, 3):
            raise DeriveError(400, "INVALID_TARGET_PAGES", "target_page_count must be 1, 2, or 3.")
        try:
            theme_id = normalize_derive_theme_id(template_id)
        except ValueError as exc:
            raise DeriveError(
                400, "INVALID_THEME", "Select one of the supported resume themes."
            ) from exc

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
        jd = normalize_jd_text(job.requirements_md or "")
        if not jd:
            raise DeriveError(400, "NO_JD", "Job has no requirements_md; supplement JD first.")

        root_data = root.data if isinstance(getattr(root, "data", None), dict) else {}
        company = job.company if isinstance(getattr(job, "company", None), str) else ""
        position = job.position if isinstance(getattr(job, "position", None), str) else ""
        root_snapshot = {
            "id": str(root.id),
            "version": int(root.version),
            "name": root.name,
            "data": copy.deepcopy(root_data),
        }
        job_snapshot = {
            "id": str(job.id),
            "company": company,
            "position": position,
            "requirements_md": jd,
        }
        root_hash = canonical_hash(root_snapshot["data"])
        jd_hash = canonical_hash(jd)
        request_hash = canonical_hash(
            {
                "job_id": str(job_id),
                "root_resume_id": str(root.id),
                "root_hash": root_hash,
                "jd_hash": jd_hash,
                "target_page_count": target_page_count,
                "template_id": theme_id,
            }
        )
        fingerprint = build_input_fingerprint(
            operation="derive",
            resume_hash=root_hash,
            jd_hash=jd_hash,
            prompt_version="resume-intelligence.v1",
            schema_version="derive.v2",
            scoring_version="scoring.v1",
        )
        if idempotency_key:
            existing = await self.runs.get_by_idempotency_key(
                user_id=user_id, idempotency_key=idempotency_key
            )
            if existing is not None:
                if existing.request_hash != request_hash:
                    raise DeriveError(
                        409,
                        "IDEMPOTENCY_MISMATCH",
                        "Idempotency key was already used with different inputs.",
                    )
                return existing

        run = await self.runs.create(
            user_id=user_id,
            job_id=job_id,
            root_resume_id=root.id,
            root_version=int(root.version),
            target_page_count=target_page_count,
            template_id=theme_id,
            root_hash=root_hash,
            jd_hash=jd_hash,
            root_snapshot=root_snapshot,
            job_snapshot=job_snapshot,
            idempotency_key=idempotency_key,
            request_hash=request_hash,
            input_fingerprint=fingerprint,
        )
        runtime = await self._accept_canonical_task(
            user_id=user_id,
            root_resume_id=root.id,
            root_version=int(root.version),
            job_id=job_id,
            target_page_count=target_page_count,
            template_id=theme_id,
            root_hash=root_hash,
            jd_hash=jd_hash,
            domain_run_id=run.id,
            idempotency_key=idempotency_key,
        )
        if runtime:
            artifacts = dict(run.artifacts or {})
            artifacts["ai_task_id"] = runtime.get("task_id")
            artifacts["ai_execution_id"] = runtime.get("execution_id")
            artifacts["runtime_links"] = {
                "status_url": runtime.get("status_url"),
                "events_url": runtime.get("events_url"),
            }
            artifacts["acceptance"] = runtime.get("acceptance_envelope")
            run.artifacts = artifacts
        if not enqueue_immediately:
            await self.session.flush()
            return run
        await self.session.commit()

        try:
            from app.core.redis import enqueue_job

            await enqueue_job(
                "execute_resume_derive",
                run_id=str(run.id),
                user_id=str(user_id),
                _job_id=str(run.id),
            )
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

    async def _accept_canonical_task(
        self,
        *,
        user_id: UUID,
        root_resume_id: UUID,
        root_version: int,
        job_id: UUID,
        target_page_count: int,
        template_id: str,
        root_hash: str | None,
        jd_hash: str | None,
        domain_run_id: UUID,
        idempotency_key: str | None,
        service_tier: str = "standard",
        allow_degrade: bool = False,
    ) -> dict[str, Any] | None:
        from app.modules.ai_runtime.acceptance import AcceptanceError, AcceptanceService
        from app.modules.ai_runtime.adapters import resume_derive as derive
        from app.modules.ai_runtime.adapters.runtime_links import (
            acceptance_result_payload,
            envelope_payload,
            runtime_links_for_task,
        )

        snap = derive.build_input_snapshot(
            root_resume_id=str(root_resume_id),
            root_version=root_version,
            job_id=str(job_id),
            target_page_count=target_page_count,
            template_id=template_id,
            root_hash=root_hash,
            jd_hash=jd_hash,
            extra={"domain_run_id": str(domain_run_id)},
        )
        snap_ref = f"resume-derive:{root_resume_id}:v{root_version}:{domain_run_id}"
        adapter = derive.ResumeDeriveAdapter()
        envelope = adapter.build_acceptance_envelope(
            service_tier=service_tier,
            input_snapshot_ref=snap_ref,
            allow_degrade=allow_degrade,
            input_payload=snap,
        )
        envelope_dict = envelope_payload(envelope)
        accept_key = idempotency_key or f"accept:{domain_run_id}"
        try:
            svc = AcceptanceService(self.session)
            quote = await svc.create_quote(
                user_id=user_id,
                capability=derive.CAPABILITY_CODE,
                action=derive.DEFAULT_ACTION,
                service_tier=service_tier,
                input_snapshot_ref=snap_ref,
                allow_degrade=allow_degrade,
                idempotency_key=f"quote:{accept_key}",
            )
            result = await svc.accept(
                user_id=user_id,
                capability=derive.CAPABILITY_CODE,
                action=derive.DEFAULT_ACTION,
                service_tier=service_tier,
                quote_id=quote.quote_id,
                input_snapshot_ref=snap_ref,
                allow_degrade=allow_degrade,
                idempotency_key=accept_key,
            )
            accepted = acceptance_result_payload(svc, result)
            accepted["acceptance_envelope"] = envelope_dict
            return accepted
        except AcceptanceError:
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
    def start_response_payload(run: ResumeDeriveRun) -> dict[str, Any]:
        from app.modules.ai_runtime.adapters import resume_derive as derive
        from app.modules.ai_runtime.adapters.runtime_links import runtime_links_for_task

        artifacts = run.artifacts or {}
        task_id = artifacts.get("ai_task_id")
        links = (
            runtime_links_for_task(task_id)
            if task_id
            else {
                "task_id": None,
                "status_url": f"/api/v1/v2/resumes/derive-runs/{run.id}",
                "events_url": None,
            }
        )
        return {
            "run_id": run.id,
            "status": run.status,
            "task_id": task_id,
            "execution_id": artifacts.get("ai_execution_id"),
            "runtime": links,
            "acceptance": artifacts.get("acceptance"),
            "canonical_status": derive.map_domain_status(run.status).value,
            "available_actions": derive.projection_actions(run.status),
            "milestones": [{"code": code, "status": "pending"} for code in derive.MILESTONE_CODES],
        }

    @staticmethod
    def status_response_payload(run: ResumeDeriveRun) -> dict[str, Any]:
        from app.modules.ai_runtime.adapters import resume_derive as derive
        from app.modules.ai_runtime.adapters.runtime_links import (
            milestone_projection,
            runtime_links_for_task,
        )

        evidence = derive.build_partial_settlement_evidence(
            domain_status=run.status,
            component_status=run.component_status,
        )
        artifacts = run.artifacts or {}
        task_id = artifacts.get("ai_task_id")
        base = {
            "id": run.id,
            "user_id": run.user_id,
            "job_id": run.job_id,
            "root_resume_id": run.root_resume_id,
            "root_version": run.root_version,
            "target_page_count": run.target_page_count,
            "template_id": run.template_id,
            "derived_resume_id": run.derived_resume_id,
            "status": run.status,
            "phase": run.phase,
            "calibrate_round": run.calibrate_round,
            "progress_pct": evidence.progress_percent or run.progress_pct,
            "error_code": run.error_code,
            "error_message": run.error_message,
            "artifacts": artifacts,
            "component_status": run.component_status or {},
            "analysis_id": run.analysis_id,
            "root_hash": run.root_hash,
            "jd_hash": run.jd_hash,
            "cancel_requested_at": run.cancel_requested_at,
            "created_at": run.created_at,
            "updated_at": run.updated_at,
            "finished_at": run.finished_at,
            "canonical_status": evidence.canonical_status.value,
            "available_actions": derive.projection_actions(run.status),
            "milestones": milestone_projection(
                codes=derive.MILESTONE_CODES,
                delivered=evidence.delivered_milestones,
                failed=evidence.failed_milestones,
            ),
            "settlement": {
                "chargeable_milestone_codes": list(evidence.chargeable_milestone_codes),
                "delivered_milestones": list(evidence.delivered_milestones),
                "failed_milestones": list(evidence.failed_milestones),
                "pending_milestones": list(evidence.pending_milestones),
            },
            "task_id": task_id,
            "acceptance": artifacts.get("acceptance"),
        }
        if task_id:
            base["runtime"] = runtime_links_for_task(task_id)
        else:
            base["runtime"] = {
                "task_id": None,
                "status_url": f"/api/v1/v2/resumes/derive-runs/{run.id}",
                "events_url": None,
            }
        return base

    async def get_run(self, run_id: UUID, *, user_id: UUID) -> ResumeDeriveRun:
        run = await self.runs.get(run_id, user_id=user_id)
        if run is None:
            raise DeriveError(404, "NOT_FOUND", "Derive run not found.")
        return run

    async def cancel_run(self, run_id: UUID, *, user_id: UUID) -> ResumeDeriveRun:
        run = await self.get_run(run_id, user_id=user_id)
        if run.status not in ("pending", "queued", "running", "canceling"):
            raise DeriveError(409, "NOT_CANCELABLE", f"Run status is {run.status}.")
        updated = await self.runs.update_fields(
            run_id,
            user_id=user_id,
            status="cancelled",
            cancel_requested_at=datetime.now(UTC),
            finished_at=datetime.now(UTC),
        )
        derive_runs_total.labels(status="cancelled").inc()
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
                    "confirmed_at": datetime.now(UTC).isoformat(),
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
        meta_out["last_supplement_at"] = datetime.now(UTC).isoformat()
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
        suggestion["applied_at"] = datetime.now(UTC).isoformat()
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
