# REQ-064 — 跨应用交付治理

| Field | Value |
|---|---|
| Requirement ID | REQ-064 |
| Spec directory | `specs/064-delivery-governance` |
| Status | planned (spec ready; implementation pending) |
| Spec | [spec.md](./spec.md) |
| Plan | [plan.md](./plan.md) |
| Tasks | [tasks.md](./tasks.md) |
| Requirements status | [requirements-status.md](./requirements-status.md) |
| Contracts | [contracts/](./contracts/) |

## Summary

将 InterCraft 从「SpecKit 文档存在，但代码和 Agent 变更主要直接进入 `master`」迭代为标准化交付流水线：

`Spec → Issue → Dispatch → 独立分支/worktree → Draft PR → CI → 真人非作者 Review → Squash Merge`

本需求涵盖治理体系的设计、规则、自动化与团队验收，共六个实施阶段（Phase 5–10），每个阶段均为独立可审查、可回滚的 PR。

## Scope

- **Phase 5** — 共享规则文档与多客户端工具适配（SOP、Onboarding、ADR、AGENTS.md、CLAUDE.md、Cursor）
- **Phase 6** — Issue Forms、PR Template、CODEOWNERS、标签与 Project 模型、Dispatch 状态机、Handoff 协议、PR Gate
- **Phase 7** — CI 分层修复与 Required Check 预备（基础 → Contract/Integration → E2E → Eval）
- **Phase 8** — Cursor 自动化（真人评论触发 → Webhook）
- **Phase 9** — Stage-B 正向/负向故障演练
- **Phase 10** — 团队验收：Fresh Clone、客户端验证、Dry-run Issue 完整闭环

## Non-Goals

- 不修改生产代码、CI Workflow 语法、Ruleset、客户端配置文件或产品行为
- 不修改 `.specify/feature.json`（保持指向 `specs/063-derive-page-fill`）
- 不合并 PR、不批准、不关闭 Issue、不修改仓库设置
- Phase 4 本身不触及 `D:\Project\eGGG` dirty worktree；但治理体系在 Phase 10 最终验收前 MUST 完成 reconciliation，包括所有权分类和有界路由
- 不部署到任何环境

## Dependencies

- Stage-A Ruleset `18825748` 已激活（PR 必须、默认审批、阻止 force push/branch deletion）
- 远端 `master` 基线为 `880580a088ecf0186fddcb64c46edd48e60043d7`
- 本 PR 仅含 governance spec 资产，不涉及产品代码

## Next

1. Codex 验收本 PR 后启动 Phase 5（`specs/064-delivery-governance/tasks.md` Phase 5）
2. 按顺序逐个 PR 实施 Phase 5 → Phase 6 → Phase 7 → Phase 8 → Phase 9 → Phase 10
