# Research: Interview Intelligence Engine

**Feature**: REQ-053 | **Date**: 2026-07-09

## 1. ARQ Cron Scheduling Pattern

**Decision**: Follow existing `backend/app/workers/main.py` pattern — add `scan_interview_research` as a cron job with `minute={0, 10, 20, 30, 40, 50}` (every 10 minutes).

**Rationale**:
- Existing project uses ARQ cron extensively (9 cron jobs registered in `WorkerSettings.cron_jobs`)
- Pattern is well-established: async function `(ctx: dict) -> dict`, registered in both `functions` and `cron_jobs`
- Redis lock already used by `auto_release_stale` for dedup — same pattern applies here
- Spec clarification confirmed ARQ cron (not independent scheduler)

**Alternatives considered**:
- APScheduler: Would introduce new dependency; ARQ already provides cron
- Celery Beat: Overkill; ARQ is the project standard
- In-process `asyncio.create_task` loop: Not durable across worker restarts

**Implementation notes**:
- New file: `backend/app/workers/tasks/interview_research.py`
- Cron schedule: `minute={0, 10, 20, 30, 40, 50}` (runs at :00, :10, :20, etc.)
- Use Redis lock with 9-minute TTL to prevent duplicate scans
- Function name: `scan_interview_research`

## 2. Interview Reports Table Extension Strategy

**Decision**: Extend existing `interview_reports` table via Alembic migration (add columns), rather than creating a separate table.

**Rationale**:
- Existing table is accessed via raw SQL (`InterviewReportRepo`), not ORM — easier to extend
- Schema is simple (9 columns + 3 indexes), no complex migration risks
- Single table for all report types simplifies queries and UI
- Spec explicitly says "复用现有 interview_reports 表"

**New columns to add**:
- `report_type` — VARCHAR(50), NOT NULL, default `'mock_interview'`; new enum value `'pre_interview_research'`
- `job_id` — UUID, FK → jobs.id ON DELETE SET NULL, nullable
- `interview_time` — TIMESTAMPTZ, nullable
- `research_task_id` — UUID, FK → interview_research_tasks.id ON DELETE SET NULL, nullable
- `rating` — SMALLINT, nullable, CHECK (1-5) — for SC-009

**Existing nullable fields** (`overall_score`, `per_question_score`, `dimension_scores`, `strengths`, `improvements`, `session_id`) remain NULL for research-type reports.

**Alternatives considered**:
- Separate `research_reports` table: Would duplicate schema, complicate unified report listing
- Single JSONB column for all new fields: Loses type safety and FK integrity

## 3. Job Status Migration Strategy

**Decision**: Single Alembic migration that (a) adds `interview_time` column, (b) updates `status` values in-place, (c) transforms `status_history` JSONB, (d) updates `JOB_TRANSITIONS` in application code.

**Rationale**:
- Status is a plain `Text` column — no DB-level enum to alter
- JSONB `status_history` can be transformed with a SQL `UPDATE ... SET status_history = ...` using `jsonb_array_elements` + `jsonb_set`
- Application-level `JOB_TRANSITIONS` dict in `app/domain/enums.py` is the source of truth for validation
- Migration supports `downgrade()` for rollback

**Mapping** (from spec):
- `applied` → `applied` (unchanged)
- `test` → `test` (unchanged)
- `oa` → `interview_1`
- `hr` → `interview_2`
- `offer` → `passed`
- `rejected` → `failed`
- `withdrawn` → `failed`

**Alternatives considered**:
- Python script migration (not Alembic): Violates constitution — Alembic is the project standard
- New `status_v2` column (dual-write): Unnecessary complexity for a small table

## 4. Tavily Search Parallel Execution

**Decision**: Execute 4 search dimensions concurrently via `asyncio.gather()`, each with independent retry (3 attempts, exponential backoff 2s/4s/8s).

**Rationale**:
- Existing `tavily_search` tool accepts `queries: list[str]` — can batch or call separately
- 4 separate calls per dimension give finer-grained error handling (one dimension failure doesn't block others)
- `asyncio.gather(return_exceptions=True)` allows partial success
- Each dimension has distinct query logic, making separate calls cleaner

**Dimension queries** (all Chinese):
1. `interview_experience`: `"{company} {position} 面试经验 面经"`
2. `company_product`: `"{company} {keywords} 产品 最新"` (keywords from LLM extraction)
3. `exam_points`: `"{position} 面试知识点 考察点"`
4. `user_weakness`: Local DB read (not a web search)

**Alternatives considered**:
- Single Tavily call with all queries: Less control over per-dimension error handling
- Sequential execution: Simpler but slower; violates SC-004 performance target

## 5. LLM Report Generation Approach

**Decision**: Single LLM call with comprehensive system prompt containing all 4 search dimensions' results, 6-chapter structure template, and quality constraints. Use `llm_client.invoke()` with `max_retries=2`.

**Rationale**:
- DeepSeek V4 Pro context window is large enough for all search results (~3K-5K tokens input)
- Single call is simpler and faster than multi-step summarization
- System prompt enforces structure (6 chapters with emoji headings) and length constraint (2000-3000 chars)
- Existing `llm_client.invoke()` supports retry and quota management

**Prompt structure**:
```
System: You are an interview preparation assistant. Generate a structured pre-interview research report in Chinese with exactly 6 chapters...
User: Company: {company}, Position: {position}, Interview time: {time}, Round: {round}
      [Search results for each dimension]
      [User weakness data from ability_dimensions + error_questions]
```

**Alternatives considered**:
- Multi-step: Summarize each dimension separately, then merge → More LLM calls, higher token cost, slower
- LangGraph agent with tool calls: Over-engineered for a structured generation task

## 6. WeChat Message Delivery Integration

**Decision**: Reuse REQ-052's `POST /agent/internal/send-message` endpoint. Report is split into ~500-char segments, sent sequentially with `(1/N)` numbering.

**Rationale**:
- REQ-052 already provides `Agent.send_message()` capability through the internal API
- `AgentMessage` model in `backend/app/modules/agent/models.py` stores sent messages
- `agents_outbound_drain` ARQ cron (every 30s) drains pending outbound messages — research reports reuse this pipeline

**Markdown→plain text conversion**:
- `**text**` → `【text】`
- `### heading` → `▎heading`
- `- list item` → `- list item` (preserved)
- Code blocks → flattened with `[代码]` prefix

**Fallback path**: If WeChat send fails (3 retries), save complete report to `interview_reports` and create `Notification` via `NotificationService`.

**Alternatives considered**:
- Direct iLink API call from research module: Violates module boundaries; REQ-052 is the canonical send path
- Single long message: WeChat may truncate; segmented messages are more readable

## 7. Business Keyword Extraction for Company Product Search

**Decision**: LLM extracts 2-3 business keywords from job's `position` + `notes_md` fields at research time. No new DB fields.

**Rationale**:
- Clarification session confirmed this approach
- LLM call is lightweight (~200 tokens) and runs before the 4 web searches
- `notes_md` often contains JD snippets with business domain hints
- Falls back gracefully: if extraction fails, use `position` as keyword

**Prompt**: "从以下岗位信息中提取 2-3 个业务关键词..." → returns comma-separated keywords

## 8. Search Result Caching (24h Same-Company Reuse)

**Decision**: Implement as a repository-level lookup: before executing web searches, check `interview_research_results` for same company within last 24 hours. If found, reuse cached results for `interview_experience` and `company_product` dimensions only (exam_points and user_weakness are always fresh).

**Rationale**:
- Reduces Tavily API calls for popular companies (e.g., multiple users interviewing at 字节跳动)
- Spec assumption mentions 24h reuse window
- Simple implementation: `SELECT ... FROM interview_research_results WHERE dimension IN (...) AND searched_at > NOW() - INTERVAL '24h' AND results->>'company' = :company`
- `exam_points` dimension always runs fresh (position-specific) and `user_weakness` is local

## 9. SC-009 Rating Feature Gap

**Finding**: Spec SC-009 requires a 1-5 star rating but no FR defines the endpoint. **Resolution**: Add as part of FR-022 implementation — `PATCH /api/v1/research-reports/{report_id}/rating` with body `{"rating": 1-5}`. Add `rating` column to `interview_reports` in the Alembic migration. This is a trivial CRUD addition.

## 10. Existing Code Patterns to Follow

| Pattern | Reference File | Notes |
|---------|---------------|-------|
| ARQ cron task | `backend/app/workers/tasks/daily_reconcile.py` | `async def task(ctx: dict) -> dict` |
| Module structure | `backend/app/modules/jobs/` | models / service / repository / api / cli / schemas |
| Raw SQL repository | `backend/app/repositories/interview_report_repo.py` | `text()` + `bindparam(type_=JSONB)` |
| CLI with typer | `backend/app/modules/jobs/cli.py` | `typer.Typer` + `asyncio.run()` |
| Notification creation | `backend/app/modules/account/notification.py` | `NotificationService.create(type_, title, message)` |
| RLS enforcement | `backend/app/modules/jobs/repository.py` | `WHERE user_id = :user_id` in all queries |
| Alembic migration | `backend/migrations/versions/0004_phase4_agent.py` | `op.create_table()` + `op.add_column()` |
