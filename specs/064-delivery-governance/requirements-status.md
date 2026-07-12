# Requirements Status: 跨应用交付治理 (REQ-064)

**Updated**: 2026-07-12

**Overall Status**: planned — spec-ready; implementation Phase 5–10 pending.

## Functional Requirements

| ID | Description | Status | Evidence |
|---|---|---|---|
| FR-001 | SOP `docs/engineering/delivery-sop.md` 覆盖完整流程 | planned | — |
| FR-002 | Onboarding `docs/engineering/team-onboarding.md` | planned | — |
| FR-003 | ADR 记录关键架构决策 | planned | — |
| FR-004 | AGENTS.md 精简 | planned | — |
| FR-005 | CLAUDE.md 导入公共规则 | planned | — |
| FR-006 | Cursor .cursor/rules/agent-delivery.mdc 薄适配 | planned | — |
| FR-007 | 审计 tracked Claude runtime/local 文件 | planned | — |
| FR-008 | Git 历史 Secret 检查 | planned | — |
| FR-009 | Issue Forms (Bug/Feature/Agent Task) | planned | — |
| FR-010 | PR Template | planned | — |
| FR-011 | CODEOWNERS | planned | — |
| FR-012 | 标签与五态 Project 模型 | planned | — |
| FR-013 | Dispatch 状态机支持必需字段 | planned | — |
| FR-014 | Inbox/Needs Clarification 可无 Driver | planned | — |
| FR-015 | PR Gate 检查完整性 | planned | — |
| FR-016 | 自动化使用 concurrency/idempotency | planned | — |
| FR-017 | 同一 Issue 最多一个有效 PR 通过 Gate | planned | — |
| FR-018 | CI 分层 (基础/Contract/E2E/Eval) | planned | — |
| FR-019 | Required Check 绑定 GitHub Actions 来源 | planned | — |
| FR-020 | Cursor 自动化初期真人评论触发 | planned | — |
| FR-021 | 自动化最小权限 bot 身份 | planned | — |
| FR-022 | Stage-B 至少 11 项故障验证 | planned | — |
| FR-023 | Team 验收包含 Fresh Clone / Dry-run | planned | — |
| FR-024 | 历史 Issues 逐个验证 | planned | — |
| FR-025 | 实现/验证/快照/演练证据齐全才标记 done | planned | — |

## Success Criteria

| ID | Description | Status | Measurement |
|---|---|---|---|
| SC-001 | SOP 覆盖完整流程 | planned | Manual review |
| SC-002 | 三客户端不推荐直接推送 master | planned | Fresh Clone test |
| SC-003 | PR Gate 正向/负向测试通过 | planned | Pester test results |
| SC-004 | Dispatch 状态机正确失效旧 Dispatch | planned | Pester test results |
| SC-005 | CI 基础检查全绿 | planned | CI run results |
| SC-006 | 11 项故障演练通过 | planned | Drill results doc |
| SC-007 | Dry-run Issue 完整闭环 | planned | Closed dry-run PR |

## Phase Completion Tracker

| Phase | PR Status | FR Coverage | SC Coverage | Rollback Verified |
|---|---|---|---|---|
| Phase 5 — Rules & Tools | not started | FR-001–FR-008 | SC-001, SC-002 | pending |
| Phase 6 — Intake & Gate | not started | FR-009–FR-017 | SC-003, SC-004 | pending |
| Phase 7 — CI Layering | not started | FR-018, FR-019 | SC-005 | pending |
| Phase 8 — Cursor Automation | not started | FR-020, FR-021 | (part of SC-006) | pending |
| Phase 9 — Stage-B Drills | not started | FR-022 | SC-006 | pending |
| Phase 10 — Acceptance | not started | FR-023–FR-025 | SC-007 | pending |