# Implementation Plan: Resume Root & Derive (REQ-055)

**Branch**: `055-resume-root-derive` | **Date**: 2026-07-09 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/055-resume-root-derive/spec.md`

## Summary

将简历中心从「多份扁平 v2 简历」升级为 **根简历（职业素材库）+ 岗位绑定派生简历（独立快照）+ 一键派生 + 严格 1/2/3 页 PDF + JD 定向 AI 建议（禁止编造）**，并与求职追踪 `jobs.requirements_md` 闭环。

技术方案（详见 [research.md](./research.md)）：

1. 扩展 `resumes_v2` 增加 `resume_kind` / 绑定字段；新增 `resume_derive_runs` 异步任务表。
2. 新建 LangGraph `resume_derive` + ARQ `execute_resume_derive`；建议采纳走 HITL 确认。
3. 页数：HTML 分页多轮校准 + **导出时 Playwright PDF 页数硬门禁**。
4. 前端：简历中心根/派生分区、一键派生向导、派生三栏工作台；岗位详情挂载派生列表。
5. **不**继续加深 v1 `resume_branches` / M16 块优化路径。

## Technical Context

**Language/Version**: TypeScript (strict) + React 18 (frontend); Python 3.12 (backend)

**Primary Dependencies**:
- Frontend: Vite, TanStack Query, Zustand, existing Markdown resume renderer / pagination
- Backend: FastAPI, SQLAlchemy 2.0 async, Alembic, Redis/ARQ, LangGraph + Postgres checkpointer, `LLMClient`, Playwright export gateway (012), PDF page-count library (e.g. pypdf)

**Storage**: PostgreSQL (`resumes_v2` extended; new `resume_derive_runs`; optional JSONB for JD parse / suggestions / unused materials); Redis for run progress pub if needed

**Testing**:
- Backend: pytest (unit + contract + derive graph eval fixtures)
- Frontend: Vitest (wizard, page gate UI, suggestion apply)
- E2E: Playwright (`tests/e2e/`) — root create → derive → page-equal PDF export; no-JD block; anti-fabrication sample

**Target Platform**: Web app (desktop-first workbench; small screens Tab collapse); Linux backend

**Project Type**: Full-stack web feature (frontend `src/` + backend `backend/app/`)

**Performance Goals**:
- One-click derive to preview: P95 ≤ 5 minutes under normal load (SC-002 aspirational interactive path ≤ 5 min including wait)
- Page calibrate loop: ≤ 5 automatic rounds before human guidance state
- Export page-count check: add ≤ 2s overhead on PDF bytes

**Constraints**:
- Target pages ∈ {1, 2, 3}; export PDF pages MUST equal target
- No fabrication: body claims require source refs
- Derived snapshots do not auto-sync from root
- JD required: non-empty `jobs.requirements_md`
- MVP export: PDF only
- RLS / `app.user_id` remains sole user-data access path
- Readable typography floor: do not shrink below existing theme min line-height / font rules

**Scale/Scope**:
- 7 user stories; ~41 FRs; ~15 UI surfaces
- ~1 Alembic migration; 1 new module (`resume_derive`); 1 new LangGraph; 1 ARQ task
- Touch: `resumes_v2`, `jobs` read APIs, Resume list/editor, Jobs detail panel, export path

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

### Pre-Research Check

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Library-First | ✅ PASS | Derive orchestration as `modules/resume_derive/` + `agents/graphs/resume_derive.py` self-contained libraries |
| II. CLI Interface | ✅ PASS | Plan includes `resume-derive` CLI (run / status / validate-pages) |
| III. Test-First | ✅ PASS | Eval fixtures for anti-hallucination + page gate; E2E for primary path before green impl |
| IV. Integration Testing | ✅ PASS | Contracts cover derive API, jobs reverse list, export page mismatch; cross-module jobs↔resumes |
| V. Observability | ✅ PASS | Structured logs + metrics: derive latency, calibrate rounds, export page mismatches, suggestion adopt rate |

### Post-Design Re-Check

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Library-First | ✅ PASS | See Project Structure; resumes_v2 only gains columns + thin hooks |
| II. CLI Interface | ✅ PASS | [contracts/cli.md](./contracts/cli.md) |
| III. Test-First | ✅ PASS | [quickstart.md](./quickstart.md) scenarios drive TDD |
| IV. Integration Testing | ✅ PASS | [contracts/openapi-resume-derive.yaml](./contracts/openapi-resume-derive.yaml) + data-model FKs |
| V. Observability | ✅ PASS | Metrics listed in research R5/R11 and contracts |

## Project Structure

### Documentation (this feature)

```text
specs/055-resume-root-derive/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── openapi-resume-derive.yaml
│   ├── derive-agent.md
│   └── cli.md
├── checklists/requirements.md
└── tasks.md                 # /speckit-tasks — not created here
```

### Source Code (repository root)

```text
backend/app/
├── modules/
│   ├── resumes_v2/                    # [MODIFY] kind columns, list filters, export gate hooks
│   ├── jobs/                          # [MODIFY] derived-resumes listing endpoint
│   └── resume_derive/                 # [NEW]
│       ├── models.py                  # ResumeDeriveRun
│       ├── schemas.py
│       ├── repository.py
│       ├── service.py                 # start/cancel/status; page calibrate orchestration glue
│       ├── api.py
│       ├── page_count.py              # PDF bytes → page count
│       └── cli.py
├── agents/
│   ├── graphs/resume_derive.py        # [NEW]
│   ├── nodes/resume_derive/           # [NEW] parse_jd, select_materials, draft, calibrate, suggest
│   ├── state/resume_derive_state.py   # [NEW]
│   └── prompts/resume_derive/         # [NEW]
├── workers/
│   ├── main.py                        # [MODIFY] register execute_resume_derive
│   └── tasks/resume_derive.py         # [NEW]
└── api/v1/export.py                   # [MODIFY] optional expected_page_count validation

src/
├── pages/
│   ├── ResumeList.tsx                 # [MODIFY] root card + derived list + CTA
│   └── ResumeEditorV2.tsx             # [MODIFY] root vs derive workbench modes
├── modules/resume/
│   ├── v2/                            # [MODIFY] API client, schema kind fields
│   ├── pagination/                    # [MODIFY] multi-target calibrate helpers (1/2/3)
│   └── derive/                        # [NEW] wizard, progress, suggestion panel, page panel
├── components/jobs/
│   └── JobsDetailPanel.tsx            # [MODIFY] bound derived resumes
└── hooks/…                            # derive mutations/queries

tests/e2e/
└── resume-root-derive.spec.ts         # [NEW]

backend/tests/…                        # derive service, page gate, agent eval fixtures
```

**Structure Decision**: Full-stack extension of existing InterCraft layout (`src/` + `backend/app/`). New derive domain module + agent graph; minimal column extensions on `resumes_v2` and jobs listing — no revival of v1 branch editor as product path.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| Dual page-count path (HTML loop + PDF gate) | Spec requires strict PDF equality; HTML alone drifts | Frontend-only gate fails SC-003 under real fonts/margins |
| New ARQ + run table (vs sync only) | Derive + calibrate exceeds request budget; progress UX required | Sync HTTP times out / poor UX on long JD |
| New LangGraph instead of extending M16 | Content model is v2 Markdown, not v1 blocks | Extending M16 re-couples deprecated `resume_branches` |
