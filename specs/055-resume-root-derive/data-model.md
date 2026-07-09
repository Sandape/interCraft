# Data Model: REQ-055 Resume Root & Derive

**Date**: 2026-07-09  
**Spec**: [spec.md](./spec.md) | **Research**: [research.md](./research.md)

## Entity Overview

```text
User
 └─ ResumeV2 (kind=root) ───────────── 0..1 per user (MVP)
 └─ ResumeV2 (kind=standard) ───────── legacy / non-root copies
 └─ ResumeV2 (kind=derived) ────────── N
      ├─ root_resume_id → ResumeV2(root)
      ├─ job_id → Job
      ├─ root_version_at_derive
      ├─ target_page_count ∈ {1,2,3}
      └─ actual_page_count (last measured)
 └─ ResumeDeriveRun ────────────────── N (async generation)
      ├─ job_id, root_resume_id, derived_resume_id?
      └─ status / progress / artifacts
Job
 └─ requirements_md (JD body, required for derive)
 └─ derived resumes (1:N via resumes_v2.job_id)
```

## 1. ResumeV2 extensions (`resumes_v2`)

Existing columns unchanged in meaning. **Add**:

| Column | Type | Null | Description |
|--------|------|------|-------------|
| `resume_kind` | `text` | NO | `'root' \| 'derived' \| 'standard'`; default `'standard'` for backfill |
| `root_resume_id` | `uuid` | YES | Required when `derived`; FK → `resumes_v2.id` |
| `job_id` | `uuid` | YES | Required when `derived`; FK → `jobs.id` |
| `root_version_at_derive` | `int` | YES | Root `version` snapshot at generation time |
| `target_page_count` | `smallint` | YES | Required when `derived`; CHECK ∈ (1,2,3) |
| `actual_page_count` | `smallint` | YES | Last successful measured PDF/HTML count |
| `derive_meta` | `jsonb` | NO default `{}` | JD parse summary ref, unused materials, takeaway notes, template id, export flags |

### Constraints

- `CHECK (resume_kind IN ('root','derived','standard'))`
- Partial unique: **one root per user** — `UNIQUE (user_id) WHERE resume_kind = 'root'`
- `CHECK (resume_kind <> 'derived' OR (root_resume_id IS NOT NULL AND job_id IS NOT NULL AND target_page_count IN (1,2,3)))`
- `CHECK (resume_kind <> 'root' OR (root_resume_id IS NULL AND job_id IS NULL AND target_page_count IS NULL))`
- RLS unchanged: row owned by `user_id` / `app.user_id`

### `data` JSONB (product fields)

Continue `ResumeDataV2` / Markdown settings. For derived, additionally allow:

```json
{
  "metadata": {
    "markdown": { "pageCount": 2, "paginationState": "ready" },
    "derive": {
      "unusedMaterials": [ { "ref": "...", "reason": "low_relevance|page_budget" } ],
      "sourceMap": { "sectionOrBulletId": ["root:project:uuid", "supplement:uuid"] },
      "pendingClaims": []
    }
  }
}
```

Root may store completeness hints under `metadata.rootCompleteness` (non-blocking).

### Validation rules

- Root: no target page enforcement; may be arbitrarily long.
- Derived: export allowed only if `actual_page_count == target_page_count` and no unresolved `pendingClaims`.
- Mutating root never updates derived `data` automatically.

## 2. ResumeDeriveRun (`resume_derive_runs`) — NEW

| Column | Type | Description |
|--------|------|-------------|
| `id` | uuid PK | Run id |
| `user_id` | uuid | Owner |
| `job_id` | uuid | Target job |
| `root_resume_id` | uuid | Root used |
| `root_version` | int | Pinned root version |
| `target_page_count` | smallint | 1/2/3 |
| `template_id` | text | Template key |
| `derived_resume_id` | uuid NULL | Set when draft row created |
| `status` | text | See state machine |
| `phase` | text | `parse_jd` / `select` / `draft` / `render` / `calibrate` / `suggest` / `done` / `failed` / `needs_guidance` |
| `calibrate_round` | int | 0..5 |
| `progress_pct` | int | 0..100 UX |
| `error_code` | text NULL | e.g. `NO_JD`, `NO_ROOT`, `PAGE_INFEASIBLE`, `LLM_FAILED` |
| `error_message` | text NULL | User-safe message |
| `artifacts` | jsonb | JD parse, selection plan, suggestions seed, guidance options |
| `created_at` / `updated_at` / `finished_at` | timestamptz | |

### Status state machine

```text
pending → running → succeeded
                 ↘ needs_guidance → running (after user adjusts) → succeeded
                 ↘ failed (terminal; retry creates new run)
canceled (from pending/running)
```

- `succeeded`: derived row exists; `actual_page_count == target_page_count` at success time.
- `needs_guidance`: auto calibrate exhausted; UI shows guidance; export still blocked until resolved via new calibrate or user edits + recheck.
- Regenerating for same job always **inserts** a new derived resume + new run.

## 3. Job (`jobs`) — no new columns required for MVP

| Existing field | Use |
|----------------|-----|
| `requirements_md` | JD body; empty ⇒ block derive |
| `jd_url` | Display only |
| `company` / `position` / `status` | Wizard list |
| `branch_id` | Legacy v1; **do not** use for 055 bindings |

Reverse relation via `resumes_v2.job_id` where `resume_kind='derived'`.

## 4. Supporting logical entities (stored in JSONB / artifacts)

### JdParseResult

Structured parse: role direction, duties, hard skills, nice-to-haves, industry, years, keywords, priority tiers, evidence present/missing vs root.

### AiSuggestion

| Field | Notes |
|-------|-------|
| id, priority (`high\|mid\|low`) | |
| type | keyword / project_boost / data_gap / cut / reorder / wording / ats_format / page / evidence_gap / keyword_stuffing |
| location | module / bullet anchor |
| rationale | JD + root refs |
| apply_mode | `direct` / `needs_supplement` / `do_not_write` |
| patch | structured edit preview |
| status | `open` / `accepted` / `dismissed` / `later` |

### UserSupplement

Q&A answers; `sync_target`: `derived_only` / `root` / `discard`; becomes source ref when confirmed.

## 5. Relationships & lifecycle

1. Create/import **root** → user edits freely.
2. Start derive run → pin `root_version` → parse JD → select materials → write **new** derived row → calibrate pages → seed suggestions.
3. Root later edits → derived unchanged; UI may show `root_version_at_derive < root.version` → offer regenerate (new row).
4. Delete derived → row delete; runs retained or cascade per migration choice (prefer keep runs with nullified `derived_resume_id` for audit).
5. Delete job → derived `job_id` SET NULL **or** block delete if derived exist (product: prefer warn + SET NULL keeping snapshot content).

## 6. Migration notes

- Alembic: add columns + partial unique + FKs; backfill `resume_kind='standard'`.
- No automatic promotion of existing resumes to root; first-run UX prompts create/promote.
- Indexes: `(user_id, resume_kind)`, `(job_id) WHERE resume_kind='derived'`, `(user_id, status)` on runs.
