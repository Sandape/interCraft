# Research: REQ-055 Resume Root & Derive

**Date**: 2026-07-09  
**Spec**: [spec.md](./spec.md)

## R1 — Root / Derived data model placement

**Decision**: Extend `resumes_v2` with discriminant columns (`resume_kind`, `root_resume_id`, `job_id`, `target_page_count`, `root_version_at_derive`, …) plus a small companion table `resume_derive_runs` for async generation. Do **not** revive `resume_branches` for new product flows.

**Rationale**:
- Current product surface is already on `resumes_v2` + Markdown editor (036/047).
- v1 `is_main` / `parent_id` is semantically close but bound to retired block editor; M16 optimize still uses it — 055 must not deepen that dependency.
- Keeping content in one JSONB document preserves existing PUT/optimistic-lock/export paths; kind filters the list UX.

**Alternatives considered**:
| Option | Why rejected |
|--------|----------------|
| Separate `root_resumes` + `derived_resumes` tables | Duplicates editor/export stack; higher migration cost |
| Reuse `resume_branches.parent_id` | Couples to v1 blocks; conflicts with 036 deprecation |
| Soft-tag only in `data.metadata` | Weak for RLS queries, uniqueness (one root), and job joins |

## R2 — One root resume per user (MVP)

**Decision**: Enforce at most one `resume_kind='root'` per `user_id` (partial unique index). Existing unmarked `resumes_v2` rows remain `kind='standard'` until user promotes/imports one as root.

**Rationale**: Matches spec Assumption §1; simplifies Agent input and list IA (one Career Vault card).

**Alternatives considered**: Multi-root / persona vaults — deferred to Future Capability Pool (Career Vault).

## R3 — Job binding & JD source

**Decision**:
- Derived resumes store `job_id` (FK → `jobs.id`, ON DELETE SET NULL or RESTRICT with soft-delete policy: prefer SET NULL + keep snapshot).
- JD text for derive MUST come from `jobs.requirements_md` (non-empty). `jd_url` is display-only in MVP.
- Add reverse listing: `GET /jobs/{id}/derived-resumes`.
- Do **not** write new bindings into `jobs.branch_id` (v1). Optionally leave `branch_id` untouched for legacy UI until a follow-up cleanup.

**Rationale**: 019 already made `requirements_md` the canonical JD body; frontend already has `hasRequirements`.

## R4 — Page-count hard constraint (dual gate)

**Decision**:
1. **Authoring loop**: reuse / extend `paginateMarkdownHtml` (+ content budget strategies) for multi-round compress/expand until `actual_page_count == target_page_count` (max 5 rounds).
2. **Export gate (authoritative)**: after Playwright PDF render, count PDF pages server-side; reject export if ≠ target. Persist `actual_page_count` on the derived row / derive run.
3. Frontend preview page count is advisory for UX; export success requires backend PDF page count match.

**Rationale**: Spec SC-003 / FR-018 demand 100% PDF equality. Current pipeline never inspects Playwright output pages; frontend-only trust is insufficient for acceptance.

**Alternatives considered**:
| Option | Why rejected |
|--------|----------------|
| Frontend-only gate | Can diverge from real PDF (fonts, margins) |
| Only backend loop with full PDF each round | Too slow/expensive for every adjust iteration; use HTML pagination for loop, PDF count for final gate |
| Approximate char budget without render | Cannot guarantee strict equality |

**Implementation note**: Prefer `pypdf` / `PyMuPDF` page count on rendered bytes inside export path; keep 012 gateway mostly stateless by accepting optional `expected_page_count` and returning `422 PAGE_COUNT_MISMATCH` when set.

## R5 — Async one-click derive orchestration

**Decision**: New ARQ task `execute_resume_derive` + table `resume_derive_runs` (status machine). API: `POST .../derive` → `202` + `run_id`; client polls `GET .../derive-runs/{id}` or SSE. LangGraph graph `resume_derive` owns JD parse → material select → draft → page calibrate → suggestions seed.

**Rationale**: Mirrors REQ-053 research task pattern; derive can exceed interactive HTTP timeout; progress UI is in-spec.

**Alternatives considered**: Sync HTTP only — fails SC-002 under load; pure frontend LLM — cannot enforce anti-hallucination + PDF gate consistently.

## R6 — Agent architecture vs M16

**Decision**: New graph `agents/graphs/resume_derive.py` (and editor suggestion subgraph or nodes), **not** an extension of `resume_optimize` on `resume_branches`. Reuse patterns: `interrupt`/HITL for applying suggestions, `LLMClient`, structured output, traced nodes. Port useful prompt ideas from `diff_jd` / `suggest_blocks` conceptually onto Markdown + provenance metadata.

**Rationale**: M16 is v1-block JSON Patch; 055 content is Markdown/`ResumeDataV2`. Dual-writing v1 would violate 036 direction.

**Anti-hallucination product rule → technical rule**:
- Every bullet/section written to derived body carries `source_refs[]` (root section ids / user supplement ids).
- LLM outputs structured “claims”; a deterministic validator drops claims without refs before persist.
- JD-only requirements without root evidence become `suggestion` / `supplement_question`, never body text.

## R7 — Editor UX shell

**Decision**: Extend v2 `BuilderShell` / Markdown editor with a **Derive Workbench** mode when `resume_kind='derived'`: left outline, center editor/preview, right tabs (AI suggestions / JD fit / page control). Root editor hides page-target controls and shows completeness hints instead.

**Rationale**: Spec FR-025/026; reuses 032/047 shell instead of a third editor.

## R8 — Import / merge into root

**Decision**: MVP supports (1) create empty root, (2) promote/copy one existing `standard` resume’s `data` into root, (3) optional LLM “merge draft” that writes a **pending** root draft for user confirm. Full multi-file merge quality is best-effort.

**Rationale**: Unblocks US1 without blocking on perfect multi-resume fusion.

## R9 — Versioning semantics

**Decision**:
- Root uses existing `resumes_v2.version` optimistic lock; derive stores `root_version_at_derive`.
- Each one-click derive creates a **new** `resumes_v2` row (`kind=derived`), never overwrites prior derived rows for the same job.
- Manual edits bump derived `version`; AI apply is explicit PATCH after preview.
- Version rollback / side-by-side diff = **MVP+** (spec FR-034 note); regenerate + list history of rows is MVP.

## R10 — Word export / Match score / ATS score

**Decision**: Out of MVP per spec. PDF only for page acceptance. Fit analysis is checklist coverage (covered / weak / missing), not a single score.

## R11 — Complexity / Constitution notes

- New module boundaries: `modules/resume_derive/` (runs + orchestration service) keeps derive concerns out of generic CRUD where possible; thin extensions on `resumes_v2` and `jobs`.
- CLI: `resume-derive run|status|validate-pages` for local/CI replay (Principle II).
- Eval fixtures: golden JD + root fixtures asserting zero fabricated claims + page gate (Principle III for AI).
