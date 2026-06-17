# 020 Data Model Changes

This feature is dominated by **behavior fixes**, not schema changes. Only one
field-level change is required: the write-end of `error_questions` must accept
the same `source_*` fields that the read-end already returns. All other schema
columns added in 019 (`jobs` 5 new fields, `interview_sessions.job_id`,
`error_questions.source_question_id`) remain as-is.

## 1. Summary of Changes

| Table | Column | Change | Required by | Migration |
|---|---|---|---|---|
| `error_questions` | `source_session_id` | Pydantic write schema (`CreateErrorQuestionInput`) now accepts this UUID on POST. **No DB change** — the column already exists from 019. | FIX-001 | None |
| `error_questions` | `source_question_id` | Pydantic write schema now accepts this UUID on POST. **No DB change** — the column already exists from 019. | FIX-001 | None |
| `error_questions` | `source_session_id`, `source_question_id` | Service-layer `clear_source` raises 400 `source_already_cleared` when both are already NULL. **No DB change.** | FIX-003 | None |
| (Jobs UI HTML) | n/a | `headcount` input gains `type="number"`, `min="1"`, `step="1"`. **No DB change.** | FIX-010 | None |

## 2. Why No New Migration

The 019 Alembic migrations are sufficient:

- `0009_019_job_fields.py` — 5 new `jobs` columns.
- `0010_019_interview_job_id.py` — `interview_sessions.job_id` column + FK + index.
- `0011_019_error_source_question_id.py` — `error_questions.source_question_id` column + partial unique index.

`error_questions.source_session_id` already existed pre-019 (it was the first
part of the 016 schema). All Round-1 defects in this feature are caused by
**the application layer failing to read or write what the database already
stores** — not by missing columns.

## 3. Pydantic Schema Diff (FIX-001)

**File**: `backend/app/modules/errors/schemas.py`

```python
# Before
class CreateErrorQuestionInput(BaseModel):
    dimension: str
    question_text: str
    answer_text: str | None = None
    reference_answer_md: str | None = None
    score: int | None = None
    tags: list[str] | None = None

# After
class CreateErrorQuestionInput(BaseModel):
    dimension: str
    question_text: str
    answer_text: str | None = None
    reference_answer_md: str | None = None
    score: int | None = None
    tags: list[str] | None = None
    # 019/020 — traceable auto-deposit (FIX-001)
    source_session_id: UUID | None = None
    source_question_id: UUID | None = None
```

Pydantic v2 default behavior is `ignore` for unknown fields, so prior
implementations silently dropped these. The fix is a strict schema declaration;
no `model_config = ConfigDict(extra="forbid")` is added (that would break
other valid use cases), but the field is now in the schema and round-trips.

## 4. Pydantic Schema Diff (FIX-007)

**File**: `backend/app/modules/interviews/schemas.py`

```python
# Before
@router.post("", response_model=InterviewSessionCreateOut, status_code=201)
async def create_session(...):
    result = await service.create(...)
    return {"data": result}  # dict wrapping ORM; response_model ignored

# After
@router.post("", response_model=InterviewSessionCreateOut, status_code=201)
async def create_session(...):
    result = await service.create(...)
    return {"data": InterviewSessionCreateOut.model_validate(result).model_dump()}
```

`InterviewSessionCreateOut` already declares `id, status, thread_id,
checkpoint_ns, job_id, branch_id`. The fix is to actually construct the
Pydantic instance, not just declare `response_model=`. No schema change.

## 5. `CreateJobInput` HTML Constraint Diff (FIX-010)

This is a frontend-only change. The backend Pydantic already has
`headcount: int | None = Field(default=None, ge=1)`. The frontend `<Input>`
component must match.

**File**: `src/pages/Jobs.tsx` (create modal) and the Job edit modal

```tsx
// Before
<Input
  value={headcount}
  onChange={(e) => setHeadcount(e.target.value.replace(/[^0-9]/g, ''))}
  placeholder="如:5"
  inputMode="numeric"
  data-testid="job-create-headcount"
/>

// After
<Input
  type="number"
  min={1}
  step={1}
  value={headcount}
  onChange={(e) => setHeadcount(e.target.value.replace(/[^0-9]/g, ''))}
  placeholder="如:5"
  inputMode="numeric"
  data-testid="job-create-headcount"
/>
```

## 6. Cross-Module Constraints (No Change, Restated for Clarity)

The following are invariants that 019 introduced and this feature must
preserve. They are not changes; they are reminders.

- `(error_questions.source_session_id, error_questions.source_question_id)`
  has a partial unique index: re-running the auto-deposit for the same
  `(session, question)` pair is a no-op (UPDATE not INSERT).
- `jobs.branch_id` is a nullable FK to `resume_branches.id`; deleting a
  resume branch must NOT cascade (preserved by 014 outbox semantics).
- `interview_sessions.job_id` is a nullable FK to `jobs.id`; the interview
  service rejects mismatched `job_id` / `branch_id` pairs at the application
  layer.

## 7. Round-2 DB Assertions (delta from Round-1)

Round-1 already covers most DB-side invariants. The only **new** DB assertion
in Round-2 is for FIX-001:

```ts
// MOCK-02 — auto-deposit round
dbQuery(
  `SELECT id, source_session_id, source_question_id
   FROM error_questions
   WHERE source_session_id = '<session-id>'
     AND source_question_id = '<question-id>'`,
  { userId }
)
// → exactly 1 row, both source_* populated
```

If Round-1's S5 or MOCK-01 (Round-2) returns NULL `source_session_id`, the
Pydantic schema is still wrong — fail fast.
