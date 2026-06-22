# Specification Quality Checklist: Phase 2 (M5-M11) spec/code 偏差审计与修复

**Purpose**: Validate specification completeness and quality before proceeding to planning
**Created**: 2026-06-22
**Feature**: [spec.md](../spec.md)

## Content Quality

- [x] No implementation details (languages, frameworks, APIs)
- [x] Focused on user value and business needs
- [x] Written for non-technical stakeholders
- [x] All mandatory sections completed

## Requirement Completeness

- [x] No [NEEDS CLARIFICATION] markers remain
- [x] Requirements are testable and unambiguous
- [x] Success criteria are measurable
- [x] Success criteria are technology-agnostic (no implementation details)
- [x] All acceptance scenarios are defined
- [x] Edge cases are identified
- [x] Scope is clearly bounded
- [x] Dependencies and assumptions identified

## Feature Readiness

- [x] All functional requirements have clear acceptance criteria
- [x] User scenarios cover primary flows
- [x] Feature meets measurable outcomes defined in Success Criteria
- [x] No implementation details leak into specification

## Notes

- Spec 024 是 spec/code 偏差审计型 feature，6 个 user story 分别对应 6 项审计 gap，按 P1/P2 分层。
- US1 (Offer 字段 + JobsDetailPanel) 是最大改动，覆盖 spec 014 的 5 个 FR (FR-002/003/009/019/025)，user story 描述以用户可感知的「录入 Offer + 查看时间线」表述，避免泄露 SQLAlchemy/Alembic 实现细节。
- US2 (outbox) 以「地铁弱网」场景表述用户价值，FR-010~015 仅约束行为（持久化/FIFO/重试 3 次/dead letter），不限定 IndexedDB vs localStorage 实现。
- US3 (status_history 字段名) 明确「后端响应字段名不变，前端对齐」，避免 plan 阶段方向性返工。
- US4 (archived 状态移除) 在 acceptance scenario 中明确「fresh→archived 返回 422」，plan 阶段可直接据此写测试。
- US5 (PIN/ProfileView) 是决策项，spec 中保留两种分支（保留并补 spec / 移除并清理），FR-041/042 双分支覆盖，plan 阶段必须做出决策并记录依据。
- US6 (PDF 导出) 明确「直接下载不走 ARQ」，FR-051 允许「移除 ARQ 代码或保留为批量导出独立功能」，给 plan 阶段留灵活性。
- FR-060 限定「除新增 4 个 Offer 字段 + 移除 archived_at 列外不改契约」，避免 plan 阶段 scope 蔓延。
- FR-065 明确「不改动 M5/M6/M10/M11」，范围严格限定在 M7/M8/M9。
- SC-008 明确「既有 E2E 零回归」是硬性约束，与 021/022/023 的 SC 一致。
- Assumptions 中明确「outbox 基础设施已有（用于 resume 模块）」，本 feature 仅扩展到 jobs，避免 plan 阶段重新设计 outbox。
- Assumptions 中明确「不升级既有依赖版本」，避免引入 breaking change。
- 与 022/023 联动：本 feature 不修复性能/可观测性问题（留待 022），不修复 checkpointer 稳定性问题（留待 023），仅修复 Phase 2 spec/code 偏差。
