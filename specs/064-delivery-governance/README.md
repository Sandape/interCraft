# REQ-064 — 跨应用交付治理

| Field | Value |
|---|---|
| Requirement ID | REQ-064 |
| Spec directory | `specs/064-delivery-governance` |
| Status | in_progress (Stage-A + core CI operational; Stage-B/final acceptance pending) |
| Spec | [spec.md](./spec.md) |
| Plan | [plan.md](./plan.md) |
| Tasks | [tasks.md](./tasks.md) |
| Requirements status | [requirements-status.md](./requirements-status.md) |
| Contracts | [contracts/](./contracts/) |

## Summary

将 InterCraft 从「SpecKit 文档存在，但代码和 Agent 变更主要直接进入 `master`」迭代为标准化交付流水线：

`Spec → Issue → Dispatch → 独立分支/worktree → Draft PR → CI → Review（默认真人非作者审批；显式 Owner PR-only bypass 可例外）→ Squash Merge`

本需求涵盖治理体系的设计、规则、自动化与团队验收，共六个实施阶段（Phase 5–10）；每个阶段包含一个或多个按序执行、独立可审查且可回滚的 PR slice。

## Scope

- **Phase 5** — 共享规则文档与多客户端工具适配（SOP、Onboarding、ADR、AGENTS.md、CLAUDE.md、Cursor）
- **Phase 6** — Issue Forms、PR Template、CODEOWNERS、标签与 Project 模型、Dispatch 状态机、Handoff 协议、PR Gate
- **Phase 7** — CI 分层修复与 Required Check 预备（基础 → Contract/Integration → E2E → Eval）
- **Phase 8** — Cursor 自动化（真人评论触发 → Webhook）
- **Phase 9** — Stage-B 正向/负向故障演练
- **Phase 10** — 团队验收：Fresh Clone、客户端验证、Dry-run Issue 完整闭环

## Non-Goals

- Phase 4 Spec-only PR 不修改生产代码、CI Workflow、Ruleset、客户端配置文件或产品行为；后续阶段只按 tasks.md 中明确列出的独立 slice 修改治理制品
- 不修改 `.specify/feature.json`（保持指向 `specs/063-derive-page-fill`）
- 自动化身份不合并、不批准、不关闭 Issue、不修改仓库设置；经用户明确授权的 Owner/Codex 验收操作除外
- Phase 4 本身不触及 `D:\Project\eGGG` dirty worktree；但治理体系在 Phase 10 最终验收前 MUST 完成 reconciliation，包括所有权分类和有界路由
- 不部署到任何环境

## Dependencies

- Stage-A Ruleset `18825748` 已激活（PR 必须、默认审批、阻止 force push/branch deletion）
- 状态核对基线为远端 `master` `6b4ddb48ec97ac45821ca7cc62db36b1089473ec`
- Phase 5 文档/适配、Phase 6 Dispatch/Gate 与 Phase 7 核心 CI 已通过独立 PR 落地；详见 `requirements-status.md`

## Next

1. 完成 open #29 的 Project v2 可视化剩余项，或记录明确的长期延期决定；它不承担授权边界。
2. 补齐 Phase 7 summary/source-bound required-check 准备，但在产品 P0 与最终回归稳定前不激活 Stage-B。
3. Phase 8 自动化、Phase 9 十一项 drill、Phase 10 最终自包含截图 HTML/团队验收继续保持未完成。
4. NekoDreamSensei 始终为可选 reviewer；Sandape owner/product-owner 可按 SOP 使用有理由、有证据的 PR-only bypass。
