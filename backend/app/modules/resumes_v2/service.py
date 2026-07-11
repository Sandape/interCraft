"""M032 — Resume v2 service layer.

Encapsulates business logic for the 5 CRUD endpoints + lock + sharing
+ duplicate (US1, US11, US16) + AI analysis (US14). All RLS-binding
happens in ``db_session_user_dep`` (see app.api.deps) so repository
methods can trust the bound ``app.user_id`` GUC.

Concurrency:
- ``update_resume`` calls ``repo.update_with_version`` which returns
  ``None`` on conflict. The service then re-fetches and returns a
  ``(None, latest)`` tuple so the API layer can build the 409 body.
- ``is_locked`` is checked BEFORE the UPDATE — any PUT to a locked
  resume raises 423 ``RESUME_LOCKED`` per FR-024.

Legacy rejection (T025):
- If the incoming ``data`` contains a ``format_version`` field set to
  ``"v1"``, raise 400 ``LEGACY_FORMAT``. v2 resumes never carry this
  field, so its presence is the canonical signal of a v1 block-based
  payload being routed to a v2 endpoint.

Error envelope (US1 contract):
- All 4xx errors use the *flat* shape ``{"error": "<CODE>", "message": "..."}``
  so clients can do ``r.json()["error"] == "RESUME_LOCKED"`` (per
  ``contracts/01-rest-api.md`` §7). We use ``ServiceError`` exceptions
  that the API layer converts to ``JSONResponse`` so we bypass the
  global ``HTTPException`` handler in ``app.core.exceptions`` (which
  wraps in ``{"error": {"code", "message"}}``).
"""
from __future__ import annotations

import copy
import json
import re
from typing import Any
from uuid import UUID

from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.ids import new_uuid_v7
from app.core.logging import get_logger
from app.modules.resumes_v2.defaults import (
    apply_creation_preferences,
    apply_template,
    default_resume_data_v2,
)
from app.modules.resumes_v2.models import ResumeV2
from app.modules.resumes_v2.repository import ResumeV2Repository
from app.modules.resumes_v2.schemas import TemplateId

# T177: structured logger for service-layer events (analyze retry, etc.)
_svc_log = get_logger("resumes_v2.service")

# REQ-039: defaults used by `merge_resume_data` when the partial PUT
# contains a `metadata.template` value that is not in the `TemplateId`
# Literal whitelist (e.g. legacy values, typos, or the E2E spec's
# "definitely-not-a-template" probe). The first Literal entry is "onyx"
# but the runtime default for new resumes is "pikachu" — we mirror
# that here so fallback keeps the user's existing experience intact.
_DEFAULT_TEMPLATE = "pikachu"
_VALID_TEMPLATES: frozenset[str] = frozenset(TemplateId.__args__)


def merge_resume_data(existing: dict[str, Any], partial: dict[str, Any]) -> dict[str, Any]:
    """Deep-merge a partial ResumeDataV2 payload into an existing full doc.

    REQ-039 — Phase B of the REQ-034 fix. The Pydantic schema keeps
    ``extra="ignore"`` (Phase A round 1) and ``metadata.layout/page/
    design/typography`` are required for round-trip safety, so a
    frontend PUT that only touches ``metadata.template`` (e.g. the
    Template Gallery E2E spec) cannot be validated as a full
    ``ResumeDataV2``. Schema-level defaults would be wrong: the
    persisted full doc should always win over the missing fields,
    and explicit user input should always win over stored data.

    Behavior:
      - Top-level keys (``picture``, ``basics``, ``summary``, ``sections``,
        ``customSections``, ``metadata``) are deep-merged so missing
        sub-trees fall back to the existing doc.
      - ``sections.<name>`` deep-merges — preserves ``items`` not
        included in the partial.
      - ``customSections`` is a list — partial lists REPLACE the
        stored list (no list merge — same semantic as frontends that
        send the full list on edits).
      - ``metadata.template`` falls back to the default when the
        partial value is not in the ``TemplateId`` whitelist; a
        structlog warning captures the rejection for observability.
      - Unknown top-level keys are dropped (matches ``extra="ignore"``).

    Returns a NEW dict — ``existing`` is never mutated.
    """
    merged = copy.deepcopy(existing)
    for key, value in partial.items():
        if key not in (
            "picture",
            "basics",
            "summary",
            "sections",
            "customSections",
            "metadata",
        ):
            # Drop unknown top-level keys (extra="ignore" equivalent).
            continue
        if key == "customSections":
            # Lists are replaced wholesale — the partial is treated as
            # the authoritative customSections list when present.
            merged["customSections"] = copy.deepcopy(value) if isinstance(value, list) else value
            continue
        if key == "metadata" and isinstance(value, dict):
            meta = merged.setdefault("metadata", {})
            for mk, mv in value.items():
                if mk == "template" and isinstance(mv, str) and mv not in _VALID_TEMPLATES:
                    # Unknown template ids are sanitized to the runtime
                    # default so persisted documents always keep a valid
                    # TemplateId enum value.
                    _svc_log.warning(
                        "resume_v2.update.template_fallback",
                        requested_template=mv,
                        applied_template=_DEFAULT_TEMPLATE,
                    )
                    meta["template"] = _DEFAULT_TEMPLATE
                    continue
                # Sub-trees (layout/page/design/typography/styleRules
                # /notes) are merged — a partial `metadata.layout`
                # only overlays the fields it ships, leaving the rest
                # of the stored metadata intact.
                if isinstance(mv, dict) and isinstance(meta.get(mk), dict):
                    meta[mk] = _deep_merge_dict(meta[mk], mv)
                else:
                    meta[mk] = copy.deepcopy(mv) if isinstance(mv, (dict, list)) else mv
            continue
        if key == "sections" and isinstance(value, dict):
            sections = merged.setdefault("sections", {})
            for sk, sv in value.items():
                if isinstance(sv, dict) and isinstance(sections.get(sk), dict):
                    sections[sk] = _deep_merge_dict(sections[sk], sv)
                else:
                    sections[sk] = copy.deepcopy(sv) if isinstance(sv, (dict, list)) else sv
            continue
        # Default: deep-copy nested dict/list, leave scalars as-is.
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge_dict(merged[key], value)
        else:
            merged[key] = copy.deepcopy(value) if isinstance(value, (dict, list)) else value
    return merged


def _deep_merge_dict(base: dict[str, Any], over: dict[str, Any]) -> dict[str, Any]:
    """Recursive dict merge: ``over`` wins for scalar/list fields; dicts recurse.

    Returns a NEW dict — neither input is mutated.
    """
    out = copy.deepcopy(base)
    for k, v in over.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge_dict(out[k], v)
        else:
            out[k] = copy.deepcopy(v) if isinstance(v, (dict, list)) else v
    return out

# ── AI Analysis (US14) ─────────────────────────────────────────────────────
# Prompt template (T150). Kept inline as a constant so the service can
# build the messages list without reading the .md file at request time.
_ANALYZE_SYSTEM_PROMPT = (
    "你是一个专业的中英双语文职简历评审,负责基于给定的 v2 简历 JSON 数据,输出"
    "结构化的 AI 分析结果。严格只输出 JSON,不要任何解释、markdown 代码块、"
    "注释或额外文字。响应必须是单个合法 JSON 对象,字段:overallScore (0-100 的"
    "整数),dimensions (正好 10 项,每项 {name, score 0-100}),strengths "
    "(3-5 项,按 impact 降序),suggestions (3-5 项,按 impact 降序)。"
    "strength/suggestion 字段:impact (high|medium|low), text, why, "
    "exampleRewrite。如果简历数据为空,返回 overallScore=0,dimensions "
    "10 项全 0,strengths 与 suggestions 空数组。"
)
_ANALYZE_USER_TEMPLATE = (
    "请评审以下 v2 简历 JSON 数据,按 system 指令输出严格 JSON:\n\n"
    "```json\n{resume_data}\n```"
)

_SLUG_RE = re.compile(r"^[a-z0-9-]+$")
_COPY_SUFFIX_RE = re.compile(r"^(?P<orig>.+)-copy-(?P<n>\d+)$")


class ServiceError(Exception):
    """Domain error → flat ``{"error": code, "message": ...}`` JSONResponse.

    Caught by the API layer (see ``_to_response``) and returned as a raw
    ``JSONResponse`` so the global ``HTTPException`` handler doesn't
    re-wrap the envelope.
    """

    def __init__(self, status: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message

    def to_response(self) -> JSONResponse:
        return JSONResponse(
            status_code=self.status,
            content={"error": self.code, "message": self.message},
        )


def raise_service_error(status: int, code: str, message: str) -> None:
    """Helper to raise a ServiceError inline in service methods."""
    raise ServiceError(status, code, message)


class ResumeV2Service:
    """Stateless facade. Constructed per-request with the bound session."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = ResumeV2Repository(session)

    # ── T021: create ───────────────────────────────────────────────────────

    async def create_resume(
        self,
        *,
        user_id: UUID,
        name: str,
        slug: str,
        template: str = "pikachu",
        theme_id: str = "muji-default-autumn",
        from_sample: bool = False,
    ) -> ResumeV2:
        if not _SLUG_RE.match(slug) or not (1 <= len(slug) <= 64):
            raise_service_error(
                400,
                "INVALID_SLUG",
                "Slug must match ^[a-z0-9-]+$ and be 1..64 chars.",
            )

        data = default_resume_data_v2()
        apply_template(data, template)
        apply_creation_preferences(data, theme_id=theme_id, from_sample=from_sample)

        try:
            row = await self.repo.create(
                user_id=user_id,
                name=name,
                slug=slug,
                data=data,
            )
            await self.session.flush()
            return row
        except IntegrityError:
            await self.session.rollback()
            raise_service_error(
                409,
                "SLUG_TAKEN",
                f"Slug '{slug}' is already used by another resume.",
            )

    # ── T021: get ──────────────────────────────────────────────────────────

    async def get_resume(self, resume_id: UUID, *, user_id: UUID) -> ResumeV2:
        row = await self.repo.get(resume_id, user_id=user_id)
        if row is None:
            # RLS hid the row. Use the SECURITY DEFINER helper to
            # disambiguate 404 (doesn't exist) from 403 (exists, other
            # owner). Only returns the owner's UUID — never the data.
            owner = await self.repo.get_owner_id(resume_id)
            if owner is not None and owner != user_id:
                raise_service_error(403, "NOT_OWNER", "You do not own this resume.")
            raise_service_error(404, "NOT_FOUND", "Resume not found.")
        return row

    # ── T021: update (with optimistic concurrency + lock + legacy checks) ─

    async def update_resume(
        self,
        resume_id: UUID,
        *,
        user_id: UUID,
        if_match: int,
        name: str | None = None,
        tags: list[str] | None = None,
        data: dict[str, Any] | None = None,
    ) -> tuple[ResumeV2 | None, ResumeV2 | None]:
        """Returns ``(row, None)`` on success, ``(None, latest)`` on conflict."""
        # Pre-flight: ownership + lock + legacy checks
        current = await self.get_resume(resume_id, user_id=user_id)
        if current.is_locked:
            raise_service_error(
                423,
                "RESUME_LOCKED",
                "This resume is locked and cannot be edited.",
            )
        if data is not None and data.get("format_version") == "v1":
            raise_service_error(
                400,
                "LEGACY_FORMAT",
                "v1 block-based payloads are not accepted on the v2 endpoint.",
            )

        # REQ-039: deep-merge the partial into the stored full doc so
        # PUTs that only ship a subset of fields (e.g. just
        # `data.metadata.template`) preserve the rest of the document.
        # The Pydantic schema's `extra=ignore` + required sub-fields
        # means a partial payload can never validate as a full
        # ResumeDataV2, so we accept the partial as `dict` at the API
        # layer and stitch it together here.
        merged_data = (
            merge_resume_data(current.data, data) if data is not None else current.data
        )

        new_version = await self.repo.update_with_version(
            resume_id,
            user_id=user_id,
            if_match=if_match,
            data=merged_data,
            name=name,
            tags=tags,
        )
        if new_version is None:
            latest = await self.repo.get(resume_id, user_id=user_id)
            if latest is None:
                raise_service_error(404, "NOT_FOUND", "Resume not found.")
            return None, latest

        updated = await self.repo.get(resume_id, user_id=user_id)
        if updated is None:
            raise_service_error(404, "NOT_FOUND", "Resume disappeared after update.")
        return updated, None

    # ── T021: delete ───────────────────────────────────────────────────────

    async def delete_resume(self, resume_id: UUID, *, user_id: UUID) -> bool:
        current = await self.repo.get(resume_id, user_id=user_id)
        if current is None:
            owner = await self.repo.get_owner_id(resume_id)
            if owner is not None and owner != user_id:
                raise_service_error(403, "NOT_OWNER", "You do not own this resume.")
            raise_service_error(404, "NOT_FOUND", "Resume not found.")
        ok = await self.repo.soft_delete(resume_id, user_id=user_id)
        return ok

    # ── T021: duplicate ────────────────────────────────────────────────────

    async def duplicate_resume(
        self, resume_id: UUID, *, user_id: UUID, accept_language: str | None = None
    ) -> ResumeV2:
        source = await self.get_resume(resume_id, user_id=user_id)

        new_slug = await self._next_copy_slug(user_id, source.slug)
        suffix = "（副本）" if (accept_language or "").lower().startswith("zh") else " (Copy)"
        new_name = f"{source.name}{suffix}"
        new_id = new_uuid_v7()

        copy = await self.repo.duplicate(
            resume_id,
            user_id=user_id,
            new_id=new_id,
            new_slug=new_slug,
            new_name=new_name,
        )
        if copy is None:
            raise_service_error(404, "NOT_FOUND", "Resume disappeared during duplicate.")
        return copy

    async def _next_copy_slug(self, user_id: UUID, orig_slug: str) -> str:
        """Compute `<orig>-copy-N` where N = 1 + max existing N (or 1 if none)."""
        existing = await self.repo.list(user_id)
        max_n = 0
        for r in existing:
            m = _COPY_SUFFIX_RE.match(r.slug)
            if not m:
                continue
            if m.group("orig") != orig_slug:
                continue
            try:
                n = int(m.group("n"))
            except (TypeError, ValueError):
                continue
            if n > max_n:
                max_n = n
        return f"{orig_slug}-copy-{max_n + 1}"

    # ── T141: sharing ─────────────────────────────────────────────────────

    async def set_sharing(
        self,
        resume_id: UUID,
        *,
        user_id: UUID,
        is_public: bool,
        password: str | None,
    ) -> dict[str, Any]:
        """Enable/disable public access + (optional) password.

        Validation:
          - When ``password`` is provided as a string, it must be 6..64
            chars per FR-075. The bcrypt-hashed value is stored.
          - When ``password`` is ``None``, any existing hash is cleared
            (which transitively requires ``is_public=True`` per the
            table CHECK constraint).
          - Password-less public access is allowed.

        Returns ``{is_public, password_set, public_url}`` per the
        §2.3 contract.
        """
        # Ownership pre-flight (re-use get_resume for 404 vs 403 split)
        current = await self.get_resume(resume_id, user_id=user_id)

        # Validate password length when provided
        if password is not None:
            if not isinstance(password, str) or not (6 <= len(password) <= 64):
                raise_service_error(
                    400,
                    "INVALID_PASSWORD",
                    "Password must be 6..64 characters when provided.",
                )
            from app.core.security import hash_password

            password_hash = hash_password(password)
        else:
            password_hash = None

        # The DB CHECK constraint forbids password_hash != NULL when
        # is_public = false. The check happens server-side; we
        # surface a clean error here for clarity.
        if password_hash is not None and not is_public:
            raise_service_error(
                400,
                "INVALID_SHARING",
                "A resume must be public to have a password.",
            )

        ok = await self.repo.set_sharing(
            resume_id,
            user_id=user_id,
            is_public=is_public,
            password_hash=password_hash,
        )
        if not ok:
            raise_service_error(404, "NOT_FOUND", "Resume not found.")

        # Compute the public_url from the owner's display_name.
        from app.modules.auth.repository import UserRepository

        user_repo = UserRepository(self.session)
        owner = await user_repo.get_by_id(current.user_id)
        display_name = (
            (owner.display_name if owner else None) or str(current.user_id)
        )
        public_url = f"/r/{display_name}/{current.slug}" if is_public else None

        return {
            "is_public": bool(is_public),
            "password_set": password_hash is not None,
            "public_url": public_url,
        }

    async def ensure_statistics_row(self, resume_id: UUID) -> None:
        """Idempotently insert a zeroed statistics row if missing.

        The increment_views / increment_downloads UPDATE statements are
        no-ops when no row exists; for the public access flow we
        need a row to exist so the counters are visible.
        """
        from app.modules.resumes_v2.models import ResumeStatisticsV2

        existing = await self.repo.get_statistics(resume_id)
        if existing is not None:
            return
        self.session.add(ResumeStatisticsV2(resume_id=resume_id, views=0, downloads=0))
        await self.session.flush()

    async def emit_public_changed(
        self,
        *,
        resume_id: UUID,
        user_id: UUID,
        is_public: bool,
        password_set: bool,
        public_url: str | None,
    ) -> None:
        """Emit the ``resume.public-changed`` SSE event (T147).

        Uses a separate pg_notify channel from ``resume_update_v2``
        so the SSE handler can fan-out public-state changes to all
        open editors of this resume.
        """
        from sqlalchemy import text as sa_text

        try:
            await self.session.execute(
                sa_text(
                    "SELECT pg_notify('resume_v2_public', "
                    "json_build_object("
                    "'type','resume.public-changed',"
                    "'resume_id',CAST(:rid AS uuid),"
                    "'user_id',CAST(:uid AS uuid),"
                    "'is_public',CAST(:pub AS boolean),"
                    "'password_set',CAST(:pwd AS boolean),"
                    "'public_url',CAST(:url AS text),"
                    "'updated_at',to_char(now() AT TIME ZONE 'UTC', 'YYYY-MM-DD\"T\"HH24:MI:SS.MS\"Z\"')"
                    ")::text)"
                ),
                {
                    "rid": str(resume_id),
                    "uid": str(user_id),
                    "pub": bool(is_public),
                    "pwd": bool(password_set),
                    "url": public_url or "",
                },
            )
        except Exception:
            # Notifications are best-effort. We don't fail the request.
            pass

    # ── T152: AI Analysis (US14) ──────────────────────────────────────────

    async def analyze_resume(
        self, resume_id: UUID, *, user_id: UUID
    ) -> dict[str, Any]:
        """Call DeepSeek V4 Pro to analyze the resume and UPSERT the result.

        Implements FR-091a: NO in-memory cache; each call hits DeepSeek
        fresh. Retries 3× on 429/5xx with exponential backoff (1s/2s/4s)
        per the T152 spec. On 3rd failure, stores ``status='failed'`` +
        ``failure_reason`` so the UI can show the error.

        Returns the persisted analysis row (analysis, status,
        failure_reason, updated_at). The shape mirrors
        ``resume_analysis_v2``.
        """
        # Ownership pre-flight (re-uses 404/403 split)
        current = await self.get_resume(resume_id, user_id=user_id)

        # Build the messages list. Per T150 the user message contains the
        # resume JSON so DeepSeek has full context.
        resume_json = json.dumps(
            current.data, ensure_ascii=False, default=str
        )
        messages = [
            {"role": "system", "content": _ANALYZE_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": _ANALYZE_USER_TEMPLATE.format(
                    resume_data=resume_json
                ),
            },
        ]

        # 3× retry with exponential backoff (1s/2s/4s) on 429/5xx.
        # The LLM client's ``invoke()`` already retries 3× internally;
        # we wrap the call with our own retries + observability.
        last_error: str | None = None
        content: str | None = None
        from app.agents.llm_client import LLMInvokeError, get_llm_client

        for attempt in range(3):
            try:
                client = get_llm_client()
                resp = await client.invoke(
                    messages=messages,
                    user_id=str(user_id),
                    thread_id=str(resume_id),
                    node_name="resume_v2_analyze",
                    max_retries=0,  # we own the retry loop
                )
                content = resp.get("content") or ""
                break
            except LLMInvokeError as exc:
                last_error = str(exc)
                # T177: structured log on AI retry
                _svc_log.warning(
                    "resume_v2.analyze.retry",
                    resume_id=str(resume_id),
                    attempt=attempt + 1,
                    max_attempts=3,
                    error=last_error,
                )
                if attempt < 2:
                    import asyncio

                    await asyncio.sleep(2 ** attempt)
            except Exception as exc:  # noqa: BLE001
                last_error = f"{type(exc).__name__}: {exc}"
                # T177: structured log on AI retry (non-LLM error)
                _svc_log.warning(
                    "resume_v2.analyze.retry",
                    resume_id=str(resume_id),
                    attempt=attempt + 1,
                    max_attempts=3,
                    error=last_error,
                )
                if attempt < 2:
                    import asyncio

                    await asyncio.sleep(2 ** attempt)

        if content is None:
            # 3rd failure — store failed row, return it
            await self.repo.upsert_analysis(
                resume_id,
                analysis={
                    "overallScore": 0,
                    "dimensions": [],
                    "strengths": [],
                    "suggestions": [],
                },
                status="failed",
                failure_reason=last_error or "LLM invoke failed",
            )
            return {
                "status": "failed",
                "analysis": None,
                "failure_reason": last_error or "LLM invoke failed",
            }

        # Parse the JSON. DeepSeek sometimes wraps in ```json ... ``` —
        # strip those fences if present.
        cleaned = content.strip()
        if cleaned.startswith("```"):
            # Drop first and last ```-fence lines
            lines = cleaned.splitlines()
            if lines and lines[0].lstrip().startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].lstrip().startswith("```"):
                lines = lines[:-1]
            cleaned = "\n".join(lines).strip()
        try:
            parsed = json.loads(cleaned)
        except (ValueError, TypeError) as exc:
            await self.repo.upsert_analysis(
                resume_id,
                analysis={
                    "overallScore": 0,
                    "dimensions": [],
                    "strengths": [],
                    "suggestions": [],
                },
                status="failed",
                failure_reason=f"Invalid JSON from LLM: {exc}",
            )
            return {
                "status": "failed",
                "analysis": None,
                "failure_reason": f"Invalid JSON from LLM: {exc}",
            }

        # Validate top-level shape; defaults for missing optional fields
        if not isinstance(parsed, dict):
            parsed = {}
        analysis_obj: dict[str, Any] = {
            "overallScore": int(parsed.get("overallScore") or 0),
            "dimensions": list(parsed.get("dimensions") or []),
            "strengths": list(parsed.get("strengths") or []),
            "suggestions": list(parsed.get("suggestions") or []),
        }
        await self.repo.upsert_analysis(
            resume_id, analysis=analysis_obj, status="success"
        )
        return {"status": "success", "analysis": analysis_obj, "failure_reason": None}

    async def get_analysis(
        self, resume_id: UUID, *, user_id: UUID
    ) -> dict[str, Any] | None:
        """Return the latest analysis row for a resume, or None.

        Performs an ownership pre-flight so the caller can return 404
        vs 403 consistently with the rest of the API.
        """
        await self.get_resume(resume_id, user_id=user_id)
        return await self.repo.get_analysis(resume_id)

    async def emit_analysis_completed(
        self,
        *,
        resume_id: UUID,
        status: str,
        overall_score: int | None,
    ) -> None:
        """Emit the ``analysis.completed`` SSE event (T155).

        Per contracts/03-sse-events.md §2.5 the payload is:
          {type, resume_id, status, overall_score?, updated_at}

        Uses the existing ``resume_update_v2`` channel so the SSE
        handler can fan it out alongside other resume events.
        """
        from sqlalchemy import text as sa_text

        try:
            await self.session.execute(
                sa_text(
                    "SELECT pg_notify('resume_update_v2', "
                    "json_build_object("
                    "'type','analysis.completed',"
                    "'resume_id',CAST(:rid AS uuid),"
                    "'status',CAST(:st AS text),"
                    "'overall_score',CAST(:sc AS integer),"
                    "'updated_at',to_char(now() AT TIME ZONE 'UTC', 'YYYY-MM-DD\"T\"HH24:MI:SS.MS\"Z\"')"
                    ")::text)"
                ),
                {
                    "rid": str(resume_id),
                    "st": status,
                    "sc": int(overall_score or 0),
                },
            )
        except Exception:
            # Best-effort: never let SSE break the request
            pass


__all__ = ["ResumeV2Service", "ServiceError"]
