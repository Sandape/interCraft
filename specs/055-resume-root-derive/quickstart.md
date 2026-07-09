# Quickstart Validation: REQ-055 Resume Root & Derive

**Purpose**: Runnable validation scenarios for TDD and acceptance — not a full implementation guide.  
**Contracts**: [openapi-resume-derive.yaml](./contracts/openapi-resume-derive.yaml), [derive-agent.md](./contracts/derive-agent.md), [cli.md](./contracts/cli.md)  
**Data model**: [data-model.md](./data-model.md)

## Prerequisites

- Backend venv + DB migrated (includes 055 migration once implemented)
- Redis + ARQ worker running (for async derive)
- Frontend `npm run dev` (for UI paths)
- Test user with Job Tracker access
- At least one job with non-empty `requirements_md`
- PDF export path (012) healthy

## Setup (once implemented)

```powershell
cd D:\Project\eGGG\backend
uv run alembic upgrade head
uv run pytest -q app/modules/resume_derive tests/agents/resume_derive -q

cd D:\Project\eGGG
npm run test -- --run src/modules/resume/derive
```

CLI smoke:

```powershell
cd D:\Project\eGGG\backend
uv run python -m app.modules.resume_derive.cli run --user-id <u> --job-id <j> --pages 1 --json
uv run python -m app.modules.resume_derive.cli status --run-id <run> --json
```

## Scenario A — Root create & long content (US1)

1. Open `/resume` → create root (or promote existing).
2. Paste a long multi-project Markdown body (>3 pages worth).
3. Save. Confirm **no** 1/2/3 page hard error on root.
4. Completeness hints may show gaps; saving still succeeds.

**Expect**: One root per user; second create root → `409 ROOT_EXISTS`.

## Scenario B — Block derive without JD (US2)

1. Create job with empty `requirements_md`.
2. Click 一键派生 → select that job.

**Expect**: Cannot start; CTA to fill JD. API `400 NO_JD`.

## Scenario C — One-click derive happy path (US2/US3)

1. Ensure root has real projects/skills matching JD keywords.
2. Job with solid `requirements_md`.
3. 一键派生 → select job → pages=1 → template → start.
4. Progress shows phases; on success open preview/editor.
5. Verify bindings: `job_id`, `root_version_at_derive`, `target_page_count=1`.
6. Export PDF → open in reader → **exactly 1 page**.

**Expect**: `GET export-gate` → `exportable: true`; export `200`.  
**Fail if**: PDF has 2+ pages or export allowed while `actual_page_count != 1`.

## Scenario D — Page infeasible → guidance (US3)

1. Use extremely dense root + restrictive template + pages=1 (fixture).
2. Run derive until `needs_guidance`.

**Expect**: Guidance offers ≥2 actions (switch template / hide modules / change pages / …). Final export still blocked until pages match.

## Scenario E — Anti-fabrication (US6)

1. JD requires niche skill absent from root (e.g. “LLM Evals” with no related text).
2. Complete derive.

**Expect**: Body does **not** claim that skill as experience; suggestions/questions ask user to supplement. Eval fixture asserts zero illegal claims.

## Scenario F — Suggestion apply HITL (US5)

1. Open derived editor → AI panel → pick `direct` suggestion.
2. Preview → Apply.
3. Confirm content changes only after confirm; dismiss leaves body unchanged.

## Scenario G — Snapshot isolation (US7)

1. Note derived content snippet.
2. Edit root heavily; save (version++).
3. Re-open derived.

**Expect**: Derived body unchanged; banner offers regenerate → creates **new** derived row.

## Scenario H — Job detail binding (US7)

1. Open `/jobs` → job detail.

**Expect**: List of derived resumes for that job with page counts and timestamps.

## Scenario I — Manual edit breaks pages

1. In derived editor, paste huge content so preview pages > target.
2. Attempt export.

**Expect**: Blocked (`EXPORT_BLOCKED` / `PAGE_COUNT_MISMATCH`); user must recalibrate or trim.

## E2E (planned)

```powershell
cd D:\Project\eGGG
npm run e2e -- tests/e2e/resume-root-derive.spec.ts
```

Cover at minimum: A (root), B (no JD), C (derive+1-page PDF), E (no fabrication smoke), G (no auto-sync), H (job panel).

## Definition of validation done

- [ ] Unit/contract tests green for page gate + source validator
- [ ] Agent eval fixtures 1–4 green (see derive-agent.md)
- [ ] E2E C + B + G pass on chromium
- [ ] Manual PDF page count spot-check for pages=2 and pages=3 once each
