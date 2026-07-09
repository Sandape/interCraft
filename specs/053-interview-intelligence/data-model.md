# Data Model: Interview Intelligence Engine

**Feature**: REQ-053 | **Date**: 2026-07-09

## Entity Overview

```
┌──────────┐       ┌──────────────────────────┐       ┌─────────────────────────┐
│   Job    │──1:N──│ InterviewResearchTask     │──1:N──│ InterviewResearchResult  │
│(modified)│       │ (new)                     │       │ (new)                    │
└──────────┘       └──────────┬───────────────┘       └─────────────────────────┘
                              │
                              │ 1:1 (nullable)
                              ▼
                   ┌──────────────────────┐
                   │  InterviewReport      │
                   │  (extended)           │
                   └──────────────────────┘
```

## Entity: Job (Modified)

**Table**: `jobs` (existing)
**Module**: `backend/app/modules/jobs/models.py`

### New Column

| Column | Type | Constraints | Default | Notes |
|--------|------|------------|---------|-------|
| `interview_time` | `TIMESTAMPTZ` | nullable | NULL | Set when status transitions to test/interview_1/interview_2/interview_3 |

### Modified Column Behavior

| Column | Change | Notes |
|--------|--------|-------|
| `status` | New valid values | Old values (`oa`, `hr`, `offer`, `rejected`, `withdrawn`) replaced by new 7-state model |
| `status_history` | JSONB values updated | Migration transforms historical `from`/`to` values |

### New Index

```sql
CREATE INDEX idx_jobs_interview_time ON jobs (interview_time)
    WHERE interview_time IS NOT NULL AND status IN ('test', 'interview_1', 'interview_2', 'interview_3');
```

### State Machine (Application Level)

Defined in `backend/app/domain/enums.py`:

```python
JOB_TRANSITIONS: dict[str, set[str]] = {
    "applied":     {"test", "interview_1", "interview_2", "interview_3", "failed", "passed"},
    "test":        {"interview_1", "interview_2", "interview_3", "failed", "passed"},
    "interview_1": {"interview_2", "interview_3", "failed", "passed"},
    "interview_2": {"interview_3", "failed", "passed"},
    "interview_3": {"failed", "passed"},
    "failed":      set(),
    "passed":      set(),
}

JOB_STATUS_CN = {
    "applied": "已投递", "test": "笔试中",
    "interview_1": "一面中", "interview_2": "二面中", "interview_3": "三面中",
    "failed": "已失败", "passed": "已通过",
}
```

### Validation Rules (FR-003, FR-008)

- `interview_time` REQUIRED when transitioning TO `test`/`interview_1`/`interview_2`/`interview_3`
- `interview_time` must be in the future (5-minute clock skew tolerance)
- `interview_time` must be ISO 8601 format
- `interview_time` NOT allowed when transitioning TO `applied`/`failed`/`passed`
- Terminal states (`failed`, `passed`) have no outgoing transitions

---

## Entity: InterviewResearchTask (New)

**Table**: `interview_research_tasks` (new)
**Module**: `backend/app/modules/research/models.py`

### Columns

| Column | Type | Constraints | Default | Notes |
|--------|------|------------|---------|-------|
| `id` | `UUID` | PK | `uuid7()` | |
| `job_id` | `UUID` | FK → jobs.id ON DELETE CASCADE, NOT NULL | | |
| `user_id` | `UUID` | FK → users.id ON DELETE CASCADE, NOT NULL | | RLS anchor |
| `interview_time` | `TIMESTAMPTZ` | NOT NULL | | The interview time this task was triggered for |
| `status` | `VARCHAR(20)` | NOT NULL, CHECK IN (pending/running/completed/cancelled/failed) | `'pending'` | |
| `search_dimensions` | `JSONB` | NOT NULL | `{}` | Per-dimension status: `{"interview_experience": "completed", ...}` |
| `report_id` | `UUID` | FK → interview_reports.id ON DELETE SET NULL, nullable | NULL | |
| `triggered_at` | `TIMESTAMPTZ` | NOT NULL | `now()` | When the scheduler triggered this task |
| `started_at` | `TIMESTAMPTZ` | nullable | NULL | When execution began |
| `completed_at` | `TIMESTAMPTZ` | nullable | NULL | When execution finished |
| `error_message` | `TEXT` | nullable | NULL | |
| `created_at` | `TIMESTAMPTZ` | NOT NULL | `now()` | |
| `updated_at` | `TIMESTAMPTZ` | NOT NULL | `now()` | |

### Unique Constraint

```sql
UNIQUE (job_id, interview_time)
```

### Indexes

```sql
CREATE INDEX idx_research_tasks_status ON interview_research_tasks (status);
CREATE INDEX idx_research_tasks_user_id ON interview_research_tasks (user_id);
CREATE INDEX idx_research_tasks_interview_time ON interview_research_tasks (interview_time);
```

### State Transitions

```
pending ──→ running ──→ completed
  │           │
  └──→ cancelled         └──→ failed
```

- `pending → running`: When ARQ worker picks up the job
- `running → completed`: All 4 dimensions searched + report generated + quality passed
- `running → failed`: Fatal error (all dimensions failed, or quality check failed twice)
- `pending → cancelled`: User modified interview_time, changed status away from interview state, or deleted job

### Validation Rules

- Only one non-cancelled task per `(job_id, interview_time)` pair (enforced by UNIQUE constraint)
- `triggered_at` set once on creation, never modified
- `started_at` set when worker begins execution
- `completed_at` set when task reaches terminal state (completed/failed/cancelled)

---

## Entity: InterviewResearchResult (New)

**Table**: `interview_research_results` (new)
**Module**: `backend/app/modules/research/models.py`

### Columns

| Column | Type | Constraints | Default | Notes |
|--------|------|------------|---------|-------|
| `id` | `UUID` | PK | `uuid7()` | |
| `task_id` | `UUID` | FK → interview_research_tasks.id ON DELETE CASCADE, NOT NULL | | |
| `dimension` | `VARCHAR(30)` | NOT NULL, CHECK IN (interview_experience/company_product/exam_points/user_weakness) | | |
| `query` | `TEXT` | NOT NULL | | The search query string used |
| `results` | `JSONB` | NOT NULL | `[]` | Array of `{title, url, content, score}` |
| `result_count` | `INTEGER` | NOT NULL | 0 | |
| `company` | `VARCHAR(200)` | NOT NULL | | Denormalized for 24h cache lookup |
| `error` | `TEXT` | nullable | NULL | Error message if search failed |
| `searched_at` | `TIMESTAMPTZ` | NOT NULL | `now()` | |

### Indexes

```sql
CREATE INDEX idx_research_results_task_id ON interview_research_results (task_id);
CREATE INDEX idx_research_results_company_time ON interview_research_results (company, searched_at DESC)
    WHERE dimension IN ('interview_experience', 'company_product');
```

### Validation Rules

- `results` is a JSONB array; each element must have `title` (str), `url` (str), `content` (str), `score` (float)
- `result_count` must equal `jsonb_array_length(results)`
- `dimension='user_weakness'` has `query` = "local_db" (not a web search)
- 24h cache: for `interview_experience` and `company_product` dimensions, check if a result for the same `company` exists within 24h before executing a new search

---

## Entity: InterviewReport (Extended)

**Table**: `interview_reports` (existing, extended)
**Repository**: `backend/app/repositories/interview_report_repo.py`

### New Columns

| Column | Type | Constraints | Default | Notes |
|--------|------|------------|---------|-------|
| `report_type` | `VARCHAR(30)` | NOT NULL | `'mock_interview'` | New enum value: `'pre_interview_research'` |
| `job_id` | `UUID` | FK → jobs.id ON DELETE SET NULL, nullable | NULL | NULL for mock_interview reports |
| `interview_time` | `TIMESTAMPTZ` | nullable | NULL | The interview time this report was generated for |
| `research_task_id` | `UUID` | FK → interview_research_tasks.id ON DELETE SET NULL, nullable | NULL | NULL for mock_interview reports |
| `rating` | `SMALLINT` | nullable, CHECK (1-5) | NULL | User rating of report usefulness (SC-009) |

### Notes

- Existing columns (`overall_score`, `per_question_score`, `dimension_scores`, `strengths`, `improvements`, `session_id`) are NULL for `report_type='pre_interview_research'`
- `session_id` FK remains but is NULL for research reports
- `summary_md` stores the full Markdown report content (reused for both report types)
- Backfill: existing rows get `report_type='mock_interview'` (default)

### New Index

```sql
CREATE INDEX idx_report_job_id ON interview_reports (job_id) WHERE report_type = 'pre_interview_research';
```

---

## Migration Plan

**File**: `backend/migrations/versions/0023_053_research.py`
**Down revision**: Latest migration (check current head)
**Operations**:

1. `op.add_column('jobs', Column('interview_time', TIMESTAMPTZ, nullable=True))`
2. `op.create_index('idx_jobs_interview_time', 'jobs', ['interview_time'], ...)`
3. `op.create_table('interview_research_tasks', ...)`
4. `op.create_table('interview_research_results', ...)`
5. `op.add_column('interview_reports', Column('report_type', VARCHAR(30), nullable=False, server_default='mock_interview'))`
6. `op.add_column('interview_reports', Column('job_id', UUID, nullable=True))`
7. `op.add_column('interview_reports', Column('interview_time', TIMESTAMPTZ, nullable=True))`
8. `op.add_column('interview_reports', Column('research_task_id', UUID, nullable=True))`
9. `op.add_column('interview_reports', Column('rating', SMALLINT, nullable=True))`
10. Status migration: `UPDATE jobs SET status = ... WHERE status IN (...)` + `UPDATE jobs SET status_history = ...` (JSONB transform)
11. `op.create_index('idx_report_job_id', 'interview_reports', ['job_id'], ...)`
12. Foreign key constraints for new tables/columns

**Downgrade**: Reverse status mapping + drop new columns/tables. Status downgrade preserves original values from `status_history` note field (`"原状态: rejected"`).
