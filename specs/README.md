# InterCraft Specs Index

This directory is the canonical requirements source for InterCraft. Keep the
feature directories in place so SpecKit and `.specify/feature.json` continue to
resolve stable paths.

## How To Use

1. Read this index first.
2. Read the active feature README, then its `spec.md`, `contracts/`, and
   `tasks.md` as needed.
3. When implementation status changes, update both the feature-level row here
   and the requirement-level status table in the feature directory.

Historical requirement material has been folded into these feature specs. Use
git history only for old context is specifically needed.

## Status Vocabulary

| Status | Meaning |
|---|---|
| `active` | Current SpecKit feature or current implementation focus. |
| `in_progress` | Accepted requirement with partial implementation or pending validation. |
| `planned` | Accepted or drafted requirement not yet started. |
| `done` | Implemented and backed by tests or verification evidence. |
| `blocked` | Accepted requirement waiting on an external dependency or unresolved decision. |
| `deferred` | Explicitly postponed to a future feature. |
| `superseded` | Replaced by a newer spec. |
| `legacy` | Historical source material only. |

## Active

v2 iteration — eval/memory/cost/trace/diagnosis/multi-agent enhancement specs.
Specify phase complete; plan/tasks pending.

| ID | Feature | Status | Source Of Truth | Notes |
|---|---|---|---|---|
| 026 | Agent Eval-Driven Self-Improvement Loop | in_progress (US1 + US2 partial) | [spec.md](./026-agent-eval-loop/spec.md) | Chinese fidelity checker + golden dataset loader (10 cases) + pytest eval plugin shipped. US3 trace / US4 DSPy / US5 self-evolution / US2 其余 4 graph 全部 ⏳ 后续. Closes the "prompt changes ship without eval" gap. |
| 027 | Prompt Caching & Token Cost Engineering | active / draft | [spec.md](./027-prompt-caching-cost/spec.md) | DeepSeek V4 context caching + prompt layering + cache-hit observability + quota model alignment. Targets ≥40% input cost reduction. |
| 027 (resume) | Resume Center Muji Alignment | ✅ Done (9 US + B5) | [spec.md](./027-resume-center-muji-alignment/spec.md) | 参照木及简历优化简历中心。9 US 全部完成：统一渲染引擎 + 智能分页 + 主题系统 + 木及自定义语法 + AI 优化增强 + 编辑器交互 + 版本对比 + 双向定位 + 头像系统。Phase B B5 Square 模板市场 (1:1 搬运木及) done。300 前端 + 560 后端 + 40 E2E 绿。Phase B B2-B4 (Muji UX 重写) deferred。 |
| 028 | Long-Term Memory Layer for Agents | in_progress (US1) | [spec.md](./028-long-term-memory/spec.md) | US1 semantic memory shipped: `agent_memory` module + `semantic_memories` table (RLS) + rule-based extractor + token-budget retriever + interview planner_context integration + ARQ `extract_memories` task. 59 tests pass (47 unit + 12 integration). US2/US3/US4 + pgvector embedding + LangMem/Mem0 eval deferred — see `tasks.md`. |
| 029 | OpenTelemetry & LangGraph Distributed Trace | in_progress (US1 partial) | [spec.md](./029-otel-langgraph-trace/spec.md) | US1 single-trace + OTLP export skeleton shipped: `backend/app/observability/` self-contained library + opentelemetry-sdk 1.43 + OTLP HTTP exporter + `@traced_node` decorator on interview (intake/question_gen/score/report) + error_coach (hint_ladder/evaluate) + `@traced_tool` on tavily_search + LLM client child span (model/tokens/latency/cache) + structlog `trace_id`/`span_id` injection + FastAPI lifespan init/shutdown + fail-open (FR-017). 31 tests pass (25 unit + 6 integration). 591 backend tests pass (no regression). US2 cross-process (HTTP/WS/ARQ), US3 sampling config, US4 prometheus exemplars, 3 remaining graphs, PII redaction, 026 trace upgrade all ⏳ deferred. |
| 030 | IRT-Based Adaptive Ability Diagnosis | in_progress (US1 partial) | [spec.md](./030-irt-adaptive-diagnosis/spec.md) | US1 shipped: `app/modules/irt/` self-contained library + 2-PL engine (pure-Python Newton-Raphson) + item/item_response/ability_theta tables (RLS on user-scoped) + `aggregate_scores` additive sidecar. 46 new tests pass (26 engine + 16 schema + 4 integration). US2 (adaptive question selection) / US3 (calibration batch + drift + retirement) / US4 (interview opt-in) / 3-PL / retest reliability production measurement all ⏳ deferred. |
| 031 | A2A Multi-Agent Generalization | active / draft | [spec.md](./031-a2a-multi-agent-generalize/spec.md) | Extract 025 Supervisor+subgraph pattern into reusable framework; apply to error_coach + resume_optimize. |

## In Progress

No in-progress specs. All features reconciled against code.

## Planned

No planned specs are currently queued. All previously planned features have
been reconciled against code and moved to Done below.

## Done Or Baseline

| ID | Feature | Status | Source Of Truth | Notes |
|---|---|---|---|---|
| 001 | Product Baseline | done / in_progress | [README.md](./001-intercraft-product-spec/README.md) | Phase 1 and Phase 3 are done; Phase 2 remains in progress. |
| 002 | Resume Editor Enhancement | done | [spec.md](./002-resume-editor-enhancement/spec.md) | WYSIWYG split view, PDF/PNG/JPEG export, Markdown import, primary card, multi-style selector — all shipped. |
| 003 | Phase 4 Interview Agent | done | [spec.md](./003-phase4-interview-agent/spec.md) | LangGraph interview subgraph + WS streaming + checkpointer + ability_diagnose ARQ trigger + 3-page frontend migration. Round-2 mock-LLM E2E (`tests/e2e/round-2/interview-mock-llm.spec.ts` MOCK-01/02/02b/03) closes the 5-round deterministic flow gap. |
| 005 | Phase 6 Global Capabilities | done | [spec.md](./005-phase6-global-capabilities/spec.md) | Account lifecycle, export/import, audit logs, subscription, Settings 7 tabs, Resources/Help, monthly-quota cron — all shipped. |
| 006 | Personal Ability Profile | done | [spec.md](./006-personal-ability-profile/spec.md) | Radar chart, self + system assessment, share links, PDF export, admin read-only — all shipped. |
| 007 | Interview Resume Guardrails | done | [spec.md](./007-interview-resume-guardrails/spec.md) | Guardrail behavior is treated as delivered unless reopened. |
| 008 | Interview Delete Feedback | done | [spec.md](./008-interview-delete-feedback/spec.md) | Delivered feature; verify before changing. |
| 009 | Interview Search Recovery | done | [spec.md](./009-interview-search-recovery/spec.md) | Delivered feature; verify before changing. |
| 010 | Topbar Utility Actions | done | [spec.md](./010-topbar-utility-actions/spec.md) | Notification panel + outside-click + Settings tab URL sync shipped. |
| 011 | Global Search | done | [spec.md](./011-global-search/spec.md) | Delivered search capability; verify before changing. |
| 012 | Resume Export Gateway | done | [spec.md](./012-resume-export-gateway/spec.md) | `POST /export/render` (pdf/png/jpeg) + `ExportError` class shipped. |
| 013 | User Avatar | done | [spec.md](./013-user-avatar/spec.md) | Pillow sanitize + `avatar_id` FK + ProfileTab integration shipped. |
| 014 | Job Tracking | done | [spec.md](./014-job-tracking/spec.md) | Job tracking baseline used by later features. |
| 015 | Jobs Status Alignment | done | [spec.md](./015-jobs-status-alignment/spec.md) | FSM transition matrix + `GET /transitions` + Jobs UI alignment shipped. |
| 016 | Error Book Completion | done | [spec.md](./016-error-book-completion/spec.md) | DELETE / reset / recall endpoints + FSM matrix shipped. |
| 017 | Topbar New Resume Branch | done | [spec.md](./017-topbar-new-resume/spec.md) | `navigate('/resume?new=true')` + auto-open + URL cleanup shipped. |
| 018 | Fix Product Defects | done | [spec.md](./018-fix-product-defects/spec.md) | 8 US + 22 FR + 11 SC all done; 6 round-1 E2E specs shipped. |
| 019 | Cross-Module Linking | done | [spec.md](./019-cross-module-linking/spec.md) | 5 US + 27 FR + 8 SC = 40 rows done. Round-2 E2E evidence: 18/18 tests pass on chromium (`auth-guard` 6 + `contract-parity` 7 + `interview-mock-llm` 4 + `full-edge-r2` 1). |
| 020 | Fix Round-1 Defects | done | [spec.md](./020-fix-round-1-defects/spec.md) | 12 FIX + 7 AC + 11 SC = 30 rows done. Round-2 E2E suite (18 tests across 4 spec files) passes on chromium. Feature 020 is complete. |
| 004 | Phase 5 Agent Subgraphs | done | [spec.md](./004-phase5-agent-subgraphs/spec.md) | 4 US + 32 FR + 5 SC = 41 rows done. SC-002 closed by feature 021 (`tests/e2e/round-2/error-coach-3-correct.spec.ts` 3/3 pass). |
| 021 | Error Coach 3-Correct E2E | done | [spec.md](./021-error-coach-e2e/spec.md) | 3/3 E2E cases (HAPPY-01, EDGE-01, ABORT-01) green on chromium via MockLLMClient; 004 SC-002 closed. Backend graph received two latent-bug fixes uncovered by E2E (`interrupt_after=["hint_ladder"]` + abort decrement_frequency). Commit `a084f71`. |
| 025 | A2A Interview Upgrade (Planner + Interviewer) | done | [spec.md](./025-a2a-interview-upgrade/spec.md) | 12 US + 34 FR + 6 SC all done. Tavily+MockTavily integrated, Planner+Supervisor graph built, frontend plan display in InterviewLive+InterviewReport, E2E tests (HAPPY-02, BC-01) in `tests/e2e/interview-a2a-planner.spec.ts`. |
| 022 | Perf & Observability Enhancement | done | [spec.md](./022-perf-observability-enhancement/spec.md) | 6 US + 22 FR + 7 SC done. request_id `ContextVar` 关联 / Resume `selectinload` N+1 修复 / errors 部分索引 / 路由 `React.lazy` / Vite `manualChunks` / metrics 补全 — shipped in baseline. |
| 023 | Checkpointer Stability | done | [spec.md](./023-checkpointer-stability/spec.md) | 6 US + 21 FR + 7 SC done. 连接池配置 + lifespan 预热 + 共享 `retry_graph_op` wrapper 覆盖 5 graphs (interview / error_coach / resume_optimize / ability_diagnose / general_coach). Commit `dcae326`. |
| 024 | Phase 2 Audit Fix | done | [spec.md](./024-phase2-audit-fix/spec.md) | 6 US + 28 FR + 8 SC done. Jobs Offer 字段 + outbox 接入 + status_history 字段对齐 / archived 状态移除 / PIN+ProfileView 移除 / PDF 同步直接下载. Frontend 177/177 + round-1+round-2 E2E 64/64 pass on chromium; code commit pending. |
| 033 | Eval + PM Dashboard V1 | done (US6 deferred) | [requirements-status.md](./033-eval-pm-dashboard/requirements-status.md) | 10 US + ~50 FR + ~25 SC done. Eval runner + golden cases + dual-approval override + US10 redaction/retention + badcase FSM (US8) + PM Dashboard V1 6 panels (Overview + Funnel + Resume Diagnosis + Mock Interview + AI Operations + Version & Experiment). US6 LangSmith sync deferred per 026 v2 cycle precedent. Key evidence: `test-reports/REQ-033-US{1,2,3,4,5,7,8,9,10}-test.md` + `test-reports/REQ-033-POLISH-test.md` + `test-reports/REQ-033-{frontend,backend,quickstart}-validation.md`. 53/53 eval tests + 87/88 unit tests + 39/39 frontend PM dashboard tests pass. 0 new TS errors in 033 files. 4 module READMEs (`backend/app/{eval,modules/pm_dashboard,modules/badcases,modules/telemetry_contracts}/README.md`). E2E spec at `tests/e2e/033-pm-dashboard.spec.ts`. |

## Blocked

No blocked specs are recorded in this index. If a requirement is blocked, add it
here and explain the dependency in that feature's requirement status table.

## Trial-Launch Readiness

- **Product code**: 100% complete across all 20 specs (001-020).
- **E2E coverage**: round-1 (8 spec files) + round-2 (5 spec files, 21/21 pass)
  + feature-level specs (M16, M19, auth, error-book, jobs, avatar, etc.).
- **Unit tests**: backend 88/88 + frontend 4/4 vitest pass; typecheck clean.
- **004 SC-002** closed by feature 021 — Error Coach 3-correct + frequency
  decrement E2E (3/3 deterministic cases pass via MockLLMClient). Two latent
  graph bugs fixed during E2E: `interrupt_after=["hint_ladder"]` and
  `decrement_frequency` on abort.
