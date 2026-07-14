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
git history only for old context if specifically needed.

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

**Current SpecKit focus (2026-07-12):** REQ-063（派生简历满页校准与真实页数一致）
is the active specification — specify、plan、tasks 已完成，next `/speckit-implement`（US1 MVP）。
REQ-061 仍为近期主线实现焦点之一；商业套餐与微信支付为 REQ-062，
在 ICP 备案与商业化批准完成前保持 **deferred**。

| ID | Feature | Status | Source Of Truth | Notes |
|---|---|---|---|---|
| 063 | 派生简历满页校准与真实页数一致 | active | [tasks.md](./063-derive-page-fill/tasks.md) | Specify+plan+tasks complete; next `/speckit-implement`（US1 MVP）。 |
| 061 | 全域 AI / Agent 生产级升级 | in_progress | [spec.md](./061-ai-agent-production/spec.md) | Implementation tasks complete except T183 LangGraph upgrade **deferred** (keep 0.2.x). See [requirements-status.md](./061-ai-agent-production/requirements-status.md). |
| 060 | 微信 Agent 生产级升级 | done | [spec.md](./060-wechat-agent-production/spec.md) | Accepted on PR #84 head `e49defd`: the linear Alembic chain `0055_059_ai_resume -> 0056_060_wechat_agent_prod -> 0057_060_agent_recovery_queue`, queue-only recovery, composite tenant integrity, hardened RLS/SECURITY DEFINER ACLs, and ORM registration passed isolated PostgreSQL 16 Action run `29309352015` with exact live counts (notification 4, REQ-059 7, REQ-060 6), zero skip/failure, plus green frontend/backend/worker and Playwright smoke gates. Merge closes Issue #77. |
| 059 | AI 岗位定制简历与编辑建议闭环 | in_progress | [spec.md](./059-ai-resume-intelligence/spec.md) | Application code and historical browser evidence exist, but the authoritative migration and isolated PostgreSQL CI evidence are pending under Issue #76. Do not mark `done` until both are merged and linked. |
| 058 | 模拟面试 Agent 质量与体验优化 | in_progress | [spec.md](./058-interview-agent-optimize/spec.md) | Implement landed (plan prewarm, plan-driven Q, score-first WS, failure/degrade, sanitize/report). Unit evidence under `docs/evidence/058-interview-agent-optimize/`; harness timing pending. |
| 057 | 求职训练指挥台（工作台首页） | in_progress | [spec.md](./057-dashboard-home-optimize/spec.md) | MVP shipped: summary BFF + Dashboard rewrite; browser-harness accepted. See [requirements-status.md](./057-dashboard-home-optimize/requirements-status.md) + evidence. |
| 056 | Derive Production Hardening | done | [spec.md](./056-derive-prod-hardening/spec.md) | Closes REQ-055 MVP→production gap layers 2–3. Evidence in `docs/evidence/056-derive-prod-hardening/`. See [requirements-status.md](./056-derive-prod-hardening/requirements-status.md). |
| 053 | Interview Intelligence Engine | draft | [spec.md](./053-interview-intelligence/spec.md) | Second of the Personal AI Career Agent triad. New 7-state job model with interview time tracking, 5-hours-before deep web search research, report generation, and WeChat push via REQ-052. Depends on REQ-052. |
| 054 | WeChat Conversational Agent | draft | [spec.md](./054-wechat-conversational-agent/spec.md) | Third of the Personal AI Career Agent triad. NL job CRUD + text mock interview via WeChat. Engineering hardening 2026-07-10 (auth, `/agent` route, send_interim, rule intent path); unit gate green. Awaiting user WeChat functional acceptance — see [docs/evidence/054-wechat-agent-acceptance-2026-07-10.md](../docs/evidence/054-wechat-agent-acceptance-2026-07-10.md). E2E still skipped (T069). |
| 055 | Resume Root & Derive | done | [spec.md](./055-resume-root-derive/spec.md) | Root resume as career vault + job-bound derived snapshots + one-click derive from Job Tracker JD + strict 1/2/3-page PDF + AI suggestions without fabrication. See [requirements-status.md](./055-resume-root-derive/requirements-status.md). |

## In Progress

REQ-057 与 REQ-058 仍有验证或实机验收工作，状态见上方 Active 表；
REQ-001 至 REQ-052 的历史状态见下方基线索引。

## Deferred

| ID | Feature | Status | Source Of Truth | Notes |
|---|---|---|---|---|
| 062 | 个人商业套餐与微信支付 | deferred | [spec.md](./062-commercial-payment/spec.md) | Owns人民币套餐、购买、微信支付、现金退款、收入与毛利；ICP 备案完成且商业化发布获批后才可进入 plan，不阻塞 REQ-061。 |

## Planned

| ID | Feature | Status | Source Of Truth | Notes |
|---|---|---|---|---|
| 064 | 跨应用交付治理 | in_progress | [tasks.md](./064-delivery-governance/tasks.md) | Stage-A SOP/adapters, Dispatch/Gate, core CI/Playwright/Eval, and clean coding-root cutover are operational. Project v2 remainder, Stage-B, 11 drills, final team regression, and self-contained screenshot HTML remain open. See [requirements-status.md](./064-delivery-governance/requirements-status.md). |

## Done Or Baseline

### v1 Baseline (001–025)

| ID | Feature | Status | Source Of Truth | Notes |
|---|---|---|---|---|
| 001 | Product Baseline | done | [README.md](./001-intercraft-product-spec/README.md) | Phase 1 and Phase 3 are done; Phase 2 remains in progress. |
| 002 | Resume Editor Enhancement | done | [spec.md](./002-resume-editor-enhancement/spec.md) | WYSIWYG split view, PDF/PNG/JPEG export, Markdown import, primary card, multi-style selector. |
| 003 | Phase 4 Interview Agent | done | [spec.md](./003-phase4-interview-agent/spec.md) | LangGraph interview subgraph + WS streaming + checkpointer + ability_diagnose ARQ trigger. |
| 004 | Phase 5 Agent Subgraphs | done | [spec.md](./004-phase5-agent-subgraphs/spec.md) | 4 US + 32 FR + 5 SC done. SC-002 closed by feature 021. |
| 005 | Phase 6 Global Capabilities | done | [spec.md](./005-phase6-global-capabilities/spec.md) | Account lifecycle, export/import, audit logs, subscription, Settings 7 tabs, Resources/Help, monthly-quota cron. |
| 006 | Personal Ability Profile | done | [spec.md](./006-personal-ability-profile/spec.md) | Radar chart, self + system assessment, share links, PDF export, admin read-only. |
| 007 | Interview Resume Guardrails | done | [spec.md](./007-interview-resume-guardrails/spec.md) | Guardrail behavior delivered unless reopened. |
| 008 | Interview Delete Feedback | done | [spec.md](./008-interview-delete-feedback/spec.md) | Delivered feature. |
| 009 | Interview Search Recovery | done | [spec.md](./009-interview-search-recovery/spec.md) | Delivered feature. |
| 010 | Topbar Utility Actions | done | [spec.md](./010-topbar-utility-actions/spec.md) | Notification panel + outside-click + Settings tab URL sync. |
| 011 | Global Search | done | [spec.md](./011-global-search/spec.md) | Delivered search capability. |
| 012 | Resume Export Gateway | done | [spec.md](./012-resume-export-gateway/spec.md) | `POST /export/render` (pdf/png/jpeg) + `ExportError` class. |
| 013 | User Avatar | done | [spec.md](./013-user-avatar/spec.md) | Pillow sanitize + `avatar_id` FK + ProfileTab integration. |
| 014 | Job Tracking | done | [spec.md](./014-job-tracking/spec.md) | Job tracking baseline used by later features. |
| 015 | Jobs Status Alignment | done | [spec.md](./015-jobs-status-alignment/spec.md) | FSM transition matrix + `GET /transitions` + Jobs UI alignment. |
| 016 | Error Book Completion | done | [spec.md](./016-error-book-completion/spec.md) | DELETE / reset / recall endpoints + FSM matrix. |
| 017 | Topbar New Resume Branch | done | [spec.md](./017-topbar-new-resume/spec.md) | `navigate('/resume?new=true')` + auto-open + URL cleanup. |
| 018 | Fix Product Defects | done | [spec.md](./018-fix-product-defects/spec.md) | 8 US + 22 FR + 11 SC done. |
| 019 | Cross-Module Linking | done | [spec.md](./019-cross-module-linking/spec.md) | 5 US + 27 FR + 8 SC done. E2E 18/18 pass. |
| 020 | Fix Round-1 Defects | done | [spec.md](./020-fix-round-1-defects/spec.md) | 12 FIX + 7 AC + 11 SC done. |
| 021 | Error Coach 3-Correct E2E | done | [spec.md](./021-error-coach-e2e/spec.md) | 3/3 E2E green on chromium via MockLLMClient. Commit `a084f71`. |
| 022 | Perf & Observability Enhancement | done | [spec.md](./022-perf-observability-enhancement/spec.md) | 6 US + 22 FR + 7 SC done. request_id, N+1 fix, React.lazy, Vite manualChunks, metrics. |
| 023 | Checkpointer Stability | done | [spec.md](./023-checkpointer-stability/spec.md) | 6 US + 21 FR + 7 SC done. `retry_graph_op` wrapper covering 5 graphs. Commit `dcae326`. |
| 024 | Phase 2 Audit Fix | done | [spec.md](./024-phase2-audit-fix/spec.md) | 6 US + 28 FR + 8 SC done. Frontend 177/177 + E2E 64/64 pass. |
| 025 | A2A Interview Upgrade | done | [spec.md](./025-a2a-interview-upgrade/spec.md) | 12 US + 34 FR + 6 SC done. Planner+Supervisor graph, Tavily integrated. |

### v2 Enhancement Era (026–036)

| ID | Feature | Status | Source Of Truth | Notes |
|---|---|---|---|---|
| 026 | Agent Eval-Driven Self-Improvement Loop | done | [spec.md](./026-agent-eval-loop/spec.md) | Chinese fidelity checker + golden dataset loader (10 cases) + pytest eval plugin shipped. |
| 027 | Prompt Caching & Token Cost Engineering | done | [spec.md](./027-prompt-caching-cost/spec.md) | DeepSeek V4 context caching + prompt layering + cache-hit observability. |
| 027 (resume) | Resume Center Muji Alignment | done | [spec.md](./027-resume-center-muji-alignment/spec.md) | 9 US all done + Phase B B5 Square template market. 300 frontend + 560 backend + 40 E2E green. |
| 028 | Long-Term Memory Layer for Agents | done | [spec.md](./028-long-term-memory/spec.md) | US1 semantic memory shipped: `agent_memory` module + `semantic_memories` table (RLS) + ARQ task. 59 tests pass. |
| 029 | OpenTelemetry & LangGraph Distributed Trace | done | [spec.md](./029-otel-langgraph-trace/spec.md) | US1 shipped: `backend/app/observability/` + OTLP HTTP exporter + `@traced_node` + structlog injection. 31 tests pass. |
| 030 | IRT-Based Adaptive Ability Diagnosis | done | [spec.md](./030-irt-adaptive-diagnosis/spec.md) | US1 shipped: `app/modules/irt/` + 2-PL Newton-Raphson + item/response/theta tables. 46 tests pass. |
| 031 | A2A Multi-Agent Generalization | done | [spec.md](./031-a2a-multi-agent-generalize/spec.md) | Extract 025 Supervisor+subgraph pattern into reusable framework. |
| 032 | Resume Renderer v2 | done | [spec.md](./032-resume-renderer-v2/spec.md) | MVP shipped 2026-06-29: 6 US (CRUD + 1 template + 3 panels + PDF + Undo). E2E pass. |
| 033 | Eval + PM Dashboard V1 | done | [requirements-status.md](./033-eval-pm-dashboard/requirements-status.md) | 10 US done. Eval runner + golden cases + badcase FSM + PM Dashboard 6 panels. 53/53 eval + 87/88 unit + 39/39 frontend pass. |
| 034 | v2 Reactive-Resume Parity | done | [spec.md](./034-v2-reactive-resume-parity/spec.md) | Content editing gaps documented and resolved. |
| 035 | Admin Dashboard MVP | superseded | — | Superseded by REQ-044 on 2026-07-03. |
| 036 | Resume v2 Finalize | done | [spec.md](./036-resume-v2-finalize/spec.md) | v1 deprecation + data cleanup + Playwright acceptance. 3 commits (9d00867/5d77291/76688f4). |

### Post-v1 Quality & Performance (037–039)

| ID | Feature | Status | Source Of Truth | Notes |
|---|---|---|---|---|
| 037 | Post-Login First-Screen Performance | done | [spec.md](./037-post-login-first-screen-performance/spec.md) | Root cause diagnosed and fixed. |
| 038 | LLM Structured Output Hardening | done | [spec.md](./038-llm-structured-output-hardening/spec.md) | US1~US4 all merged 2026-07-03 via cdb9aef. 14/14 FR covered. |
| 039 | Log Center Full | superseded | — | Superseded by REQ-044 on 2026-07-03. |

### LangGraph Modernization Arc (040–043)

| ID | Feature | Status | Source Of Truth | Notes |
|---|---|---|---|---|
| 040 | Agent Architecture Refactor | done | [spec.md](./040-agent-arch-refactor/spec.md) | Merged 2026-07-03 commit 72b9263. InputState/OutputState/OverallState three-layer state with override_reducer. |
| 041 | Agent Stability Refactor | done | [spec.md](./041-agent-stability-refactor/spec.md) | Merged 2026-07-03 commit 7b4b7fd. Error handling + tool LLM-ization + P0 follow-up (0ad2dfc). |
| 042 | Agent Runtime Refactor | done | [spec.md](./042-agent-runtime-refactor/spec.md) | Merged 2026-07-04 commit 353753d. Memory compression + loop termination. |
| 043 | Agent Production Refactor | done | [spec.md](./043-agent-production-refactor/spec.md) | Merged 2026-07-04 commit 5669c7d. Observability hardening + checkpoint pooling. |

### Admin & Ops (044–046)

| ID | Feature | Status | Source Of Truth | Notes |
|---|---|---|---|---|
| 044 | Admin Console Redesign | done | [spec.md](./044-admin-console-redesign/spec.md) | Supersedes 035 and 039. 8-workspace IA shell + role-aware nav shipped. |
| 045 | LLM Ops Eval Workflow | done | [requirements-status.md](./045-llm-ops-eval-workflow/requirements-status.md) | OTel-first trace correlation, LangSmith-assisted eval sync, production full-content export policy, Chrome Control E2E evidence completed. |
| 046 | Production-Grade LLM Evals | done | [requirements-status.md](./046-production-llm-evals/requirements-status.md) | Production operating system: LangSmith Dataset/Experiment evidence, release gates, SLOs/alerts, export governance. |

### Resume v2/v3 (047, 049)

| ID | Feature | Status | Source Of Truth | Notes |
|---|---|---|---|---|
| 047 | Resume Editor v3 for InterCraft v2 | done | [requirements-status.md](./047-resume-editor-v3/requirements-status.md) | First v2 product-development spec. Muji-compatible Markdown rendering, 3 themes, line spacing, smart one-page, PDF/MD export. |
| 049 | Markdown Editor Cutover and Pagination | done | [requirements-status.md](./049-markdown-editor-cutover/requirements-status.md) | Markdown-only editing, legacy conversion, contact row rendering, multi-page pagination, export parity. |

### Agent & Interview (048)

| ID | Feature | Status | Source Of Truth | Notes |
|---|---|---|---|---|
| 048 | Interview Mode Split + Doubao Card Export | done | [spec.md](./048-interview-modes-and-doubao-card/spec.md) | 6 US + 22 SC + 50+ FR done. Mode selection, hybrid quick-drill (BM25+BGE+rerank), full interview, Doubao card renderer, variant toggle. |

### Session & Role (050–051)

| ID | Feature | Status | Source Of Truth | Notes |
|---|---|---|---|---|
| 050 | Login Session Stability | done | [spec.md](./050-login-session-stability/spec.md) | Multi-tab session overwrite fix + refresh reuse detection + frontend retry hardening. |
| 051 | Admin Role Simplify + Full Chinese Localization | done | [spec.md](./051-admin-role-simplify-cn/spec.md) | Role model simplified to free/pro/admin; ~336 UI text items localized to Chinese; Topbar admin entry. |

### Personal Agent WeChat (052)

| ID | Feature | Status | Source Of Truth | Notes |
|---|---|---|---|---|
| 052 | Personal Agent + WeChat Channel | done | [spec.md](./052-personal-agent-wechat/spec.md) | Agent entity + iLink WeChat integration + QR binding + message send/receive + multi-user fault isolation. Acceptance completed 2026-07-09. |

## Blocked

No blocked specs are recorded in this index. If a requirement is blocked, add it
here and explain the dependency in that feature's requirement status table.
