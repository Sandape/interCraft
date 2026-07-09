# Implementation Plan: Interview Intelligence Engine

**Branch**: `053-interview-intelligence` | **Date**: 2026-07-09 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/053-interview-intelligence/spec.md`

## Summary

将求职追踪模块从旧 7 状态（applied/test/oa/hr/offer/rejected/withdrawn）迁移到新 7 状态（applied/test/interview_1/interview_2/interview_3/failed/passed），新增面试时间追踪，并在面试前 5 小时通过 ARQ cron 自动触发深度 Web Search 调研，生成结构化备战报告，通过 REQ-052 微信通道推送给用户。

技术方案：扩展现有 `jobs` 模块（新增 `interview_time` 列 + 状态迁移），新增 `research` 模块（调研任务、搜索结果、报告生成），复用 ARQ Workers 调度基础设施，通过 Tavily Search API + DeepSeek V4 Pro LLM 实现调研→报告→推送的端到端流水线。

## Technical Context

**Language/Version**: Python 3.12 (backend), TypeScript 5.x (frontend)

**Primary Dependencies**: FastAPI, SQLAlchemy (async), ARQ, LangGraph, Tavily Search API, DeepSeek V4 Pro (OpenAI-compatible protocol)

**Storage**: PostgreSQL (existing), Redis (ARQ job queue)

**Testing**: pytest (backend unit/integration), Playwright (E2E)

**Target Platform**: Linux server (backend), Web browser (frontend)

**Project Type**: web-service (existing full-stack: FastAPI backend + React/Vite frontend)

**Performance Goals**:
- SC-003: 98% trigger rate within ±5min window (scan every 10 min)
- SC-004: E2E research→report median ≤90s, P95 ≤180s
- SC-006: WeChat delivery ≤2min P95 after report generation

**Constraints**:
- DeepSeek V4 Pro 500K token/month quota (per report ~8K-15K tokens)
- Tavily Search API quota (shared with existing interview web search)
- Redis lock for scheduler dedup (prevents duplicate cron execution)
- RLS enforcement on all user-scoped queries

**Scale/Scope**:
- ~50 interviews/day assumed
- 7 US × ~25 AC scenarios
- 3 new DB tables (interview_research_tasks, interview_research_results) + 1 extended table (interview_reports) + 1 modified table (jobs)
- 1 new ARQ cron job + 1 new ARQ task function
- ~5 new API endpoints
- 2 new frontend components (time picker, report viewer)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

### Pre-Research Check

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Library-First | ✅ PASS | 新 research 模块自包含于 `backend/app/modules/research/`，独立依赖声明，可独立测试 |
| II. CLI Interface | ✅ PASS | FR-025 要求 CLI 命令；遵循现有 typer 模式（参考 `jobs/cli.py`） |
| III. Test-First | ✅ PASS | 将在实现前编写 pytest + Playwright E2E 测试；spec 中 SC-010 已规定 E2E 覆盖范围 |
| IV. Integration Testing | ✅ PASS | 跨模块集成测试覆盖：jobs↔research、research↔agent(WeChat)、research↔notifications |
| V. Observability | ✅ PASS | FR-023/FR-024 要求 Prometheus 指标 + 结构化审计日志；遵循现有模式（`on_job_start`/`on_failure` hooks） |

### Post-Design Re-Check

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Library-First | ✅ PASS | research 模块 contracts 已定义（见 contracts/），API 边界清晰 |
| II. CLI Interface | ✅ PASS | CLI 设计完成：`migrate-status`、`trigger-research`、`research-stats` |
| III. Test-First | ✅ PASS | 测试策略已定义（见 quickstart.md 验证场景） |
| IV. Integration Testing | ✅ PASS | 集成点已在 data-model.md 中标注 FK 关系和 cascade 行为 |
| V. Observability | ✅ PASS | 4 个 Prometheus 指标 + 审计日志 schema 已定义 |

## Project Structure

### Documentation (this feature)

```text
specs/053-interview-intelligence/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
│   ├── api.yaml         # OpenAPI contracts for new endpoints
│   └── events.yaml      # ARQ job contracts + internal events
└── tasks.md             # Phase 2 output (/speckit-tasks)
```

### Source Code (repository root)

```text
backend/
├── app/
│   ├── domain/
│   │   └── enums.py                        # [MODIFY] JOB_TRANSITIONS, JOB_STATUS_CN
│   ├── modules/
│   │   ├── jobs/
│   │   │   ├── models.py                   # [MODIFY] add interview_time column
│   │   │   ├── schemas.py                  # [MODIFY] PatchJobInput + interview_time
│   │   │   ├── service.py                  # [MODIFY] require interview_time for interview states
│   │   │   ├── api.py                      # [MODIFY] add report endpoints
│   │   │   └── cli.py                      # [MODIFY] add migrate-status command
│   │   ├── research/                       # [NEW] interview research module
│   │   │   ├── __init__.py
│   │   │   ├── models.py                   # InterviewResearchTask, InterviewResearchResult
│   │   │   ├── schemas.py                  # Pydantic schemas
│   │   │   ├── repository.py              # Data access with RLS
│   │   │   ├── service.py                 # Research orchestration logic
│   │   │   ├── api.py                      # Report viewing endpoints
│   │   │   ├── report_generator.py         # LLM report generation
│   │   │   ├── quality_checker.py          # FR-018 quality validation
│   │   │   ├── markdown_converter.py       # Markdown→plain text for WeChat
│   │   │   └── cli.py                      # trigger-research, research-stats
│   │   └── agent/
│   │       └── cli.py                      # [MODIFY] add research CLI commands (or keep in research/)
│   ├── workers/
│   │   ├── main.py                         # [MODIFY] add scan_interview_research cron + function
│   │   └── tasks/
│   │       └── interview_research.py       # [NEW] scan + execute research tasks
│   └── repositories/
│       └── interview_report_repo.py        # [MODIFY] support research-type reports
├── migrations/
│   └── versions/
│       └── 0023_053_research.py            # [NEW] Alembic migration
└── tests/
    ├── unit/
    │   └── modules/
    │       └── research/                   # [NEW] unit tests
    └── integration/
        └── test_research_pipeline.py       # [NEW] integration tests

frontend/
├── src/
│   ├── components/
│   │   └── jobs/
│   │       ├── StatusTransition.tsx        # [MODIFY] new status options + time picker
│   │       └── ResearchReport.tsx          # [NEW] report viewer
│   └── pages/
│       └── ResearchReportPage.tsx          # [NEW] full report page
└── tests/
    └── e2e/
        └── 053-interview-intelligence.spec.ts  # [NEW] Playwright E2E
```

**Structure Decision**: Web application pattern (Option 2), consistent with existing InterCraft architecture. New `research` module follows the existing module pattern (models/service/repository/api/cli). No new top-level directories needed.

## Complexity Tracking

> No constitution violations. No entries needed.
