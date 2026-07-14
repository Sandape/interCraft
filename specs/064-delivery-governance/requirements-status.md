# Requirements Status: 跨应用交付治理 (REQ-064)

**Updated**: 2026-07-14

**Overall Status**: in_progress — Stage-A governance, core CI, and clean-root
cutover are operational; Stage-B, final acceptance, and several external
metadata/automation items remain open.

## Functional Requirements

| ID | Description | Status | Evidence |
|---|---|---|---|
| FR-001 | SOP `docs/engineering/delivery-sop.md` 覆盖完整流程 | done | #22; truth alignment #68 |
| FR-002 | Onboarding `docs/engineering/team-onboarding.md` | done | #22; links to canonical SOP |
| FR-003 | ADR 记录关键架构决策 | done | ADR-001 #22, ADR-002 #32, ADR-003 #37 |
| FR-004 | AGENTS.md 精简 | done | #26; short routing layer on master |
| FR-005 | CLAUDE.md 导入公共规则 | done | #26; thin adapter on master |
| FR-006 | Cursor `.cursor/rules/agent-delivery.mdc` 薄适配 | done | #26 |
| FR-007 | 审计 tracked Claude runtime/local 文件 | done | #28 |
| FR-008 | Git 历史 Secret 检查 | done | #28; later credential remediation #70 |
| FR-009 | Issue Forms (Bug/Feature/Agent Task) | done | #30; three forms on master |
| FR-010 | PR Template | done | #30 |
| FR-011 | CODEOWNERS（NekoDreamSensei 不设强制） | done | #30; Sandape routing, Neko optional |
| FR-012 | 标签与五态 Project 模型 | in_progress | #30 created labels; Project v2 board explicitly deferred on open #29 |
| FR-013 | Dispatch 状态机支持必需字段（含 issue_number） | done | #32; boundary correction #35 |
| FR-014 | Inbox/Needs Clarification 可无 Driver；同一 Issue 最多一个活跃 Dispatch（不分 driver） | done | #32 Dispatch tests |
| FR-015 | PR Gate 检查完整性（含确定性 base freshness、规范 AC 字段 hash） | done | #37 Gate implementation/tests |
| FR-016 | 自动化使用 concurrency/idempotency | in_progress | Dispatch singleton/idempotency exists; Phase 8 automation not implemented |
| FR-017 | 同一 Issue 同时最多一个交付 PR 能通过 Gate | done | #37 Gate tests |
| FR-018 | CI 分层 (基础/Contract/E2E/Eval) | in_progress | Playwright #56/#66, core CI #64, deterministic eval #88/#90; final summary/complete suite still pending |
| FR-019 | Required Check 绑定 GitHub Actions 来源 | planned | Stage-B activation intentionally deferred |
| FR-020 | Cursor 自动化初期真人评论触发 | planned | Phase 8 not implemented |
| FR-021 | 自动化最小权限 bot 身份 | planned | Phase 8 not implemented |
| FR-022 | Stage-B 至少 11 项故障验证 | planned | No complete drill pack; Stage-A remains active |
| FR-023 | Team 验收包含 Fresh Clone / Dry-run | in_progress | Fresh clean clone/cutover verified 2026-07-14; multi-client and dedicated dry-run acceptance incomplete |
| FR-024 | 历史 Issues 逐个验证 | planned | No complete per-Issue disposition record |
| FR-025 | 实现/验证/快照/演练证据齐全才标记 done | in_progress | Applied to completed rows; final Stage-B/acceptance evidence incomplete |
| FR-026 | Dirty worktree 所有权分类（发布/归档/忽略/保留） | in_progress | Read-only inventory exists; protected feature assets and historical bulk evidence not fully routed |
| FR-027 | 零未归类脏条目证明（无 reset/clean/stash） | in_progress | Owner acceptance now uses a pristine coding root and preserves the old root as evidence; original per-entry proof not completed |
| FR-028 | HTML 证据素材 sop-walkthrough.html（截图/时间戳/URL/脱敏） | in_progress | External Stage-A walkthrough has URLs and partial screenshots; self-contained full screenshot pack is pending |
| FR-029 | 所有 FR/SC 在 tasks.md 和本表中有对应条目 | done | 52-task matrix and this status table cover all FR/SC IDs |

## Success Criteria

| ID | Description | Status | Measurement |
|---|---|---|---|
| SC-001 | SOP 覆盖完整流程 | done | #22 and #68 manual review |
| SC-002 | 三客户端不推荐直接推送 master | in_progress | Three thin adapters exist; fresh-clone multi-client exercise incomplete |
| SC-003 | PR Gate 正向/负向测试通过 | done | #37 Pester gate suite |
| SC-004 | Dispatch 状态机正确失效旧 Dispatch | done | #32 Pester dispatch suite; live supersede/expire usage |
| SC-005 | CI 基础检查全绿 | done | #88 and #90 PR runs: core CI, Playwright, migrations, readiness, eval green |
| SC-006 | 11 项故障演练通过 | planned | Stage-B drill pack absent |
| SC-007 | Dry-run Issue 完整闭环 | in_progress | Multiple real Issue→Dispatch→PR→checks→owner-bypass→merge chains pass; dedicated team dry-run incomplete |
| SC-008 | `D:\Project\eGGG` 零未归类脏条目 | in_progress | Superseded acceptance uses clean `D:\Project\eGGG-coding`; historical root remains read-only evidence |
| SC-009 | sop-walkthrough.html 覆盖完整 SOP 流程 | in_progress | Stage-A HTML exists; complete embedded screenshot/visual QA pending |

## Phase Completion Tracker

| Phase | PR Status | FR Coverage | SC Coverage | Rollback Verified |
|---|---|---|---|---|
| Phase 5 — Rules & Tools (3 slices) | merged (#22/#26/#28) | FR-001–FR-008 done | SC-001 done; SC-002 partial | squash rollback protocol documented; no live drill |
| Phase 6 — Intake & Gate (3 slices) | in_progress (#30/#32/#35/#37) | FR-009–FR-017 except FR-012/016 remainder | SC-003/004 done | script rollback covered; Project v2 pending |
| Phase 7 — CI Layering (7 slices) | in_progress (#56/#64/#66/#88/#90) | FR-018 partial; FR-019 planned | SC-005 done | failure evidence drill #90; Stage-B checks pending |
| Phase 8 — Cursor Automation | not started | FR-020/021 planned | part of SC-006 | pending |
| Phase 9 — Stage-B Drills | not started | FR-022 planned | SC-006 planned | pending |
| Phase 10 — Acceptance & Recon | in_progress | FR-023–029 mixed | SC-007–009 partial | final acceptance pending |
