# 036 — Resume v2 Finalize（全面弃用 v1 + 脏数据清理 + Playwright 成品验收）

**Status**: active / draft
**Spec**: [spec.md](./spec.md)
**Plan**: [plan.md](./plan.md)
**Created**: 2026-06-29（修订 2026-06-30）

---

## 核心目标

1. **全面弃用 v1**：侧边栏 / Topbar / 路由表 / 页面 / 后端 CRUD 全部下线 v1 触点；`resume_branches` 表数据清空（保留 schema）。
2. **脏数据清理**：`resumes_v2` / `resume_statistics_v2` / `resume_analysis_v2` / 关联 outbox 整表清空（仅 dev 环境）。
3. **Playwright 验收**：端到端 UI 实操在 v2 编辑器制作一份成品简历（参照 `C:\Users\30803\Desktop\简历\大模型应用开发简历v1.md`），**禁止 API 注入**。
4. **细分功能清单**：每个功能点实测后产出「未完成功能清单」+「已完成验收功能清单」。

## 子文档

| 文件 | 用途 |
|---|---|
| [spec.md](./spec.md) | 7 US + 35 FR + 12 SC + Assumptions + Risks |
| [plan.md](./plan.md) | 技术上下文 + Constitution Check + 实施阶段 + 风险 |
| [research.md](./research.md) | 7 项关键决策 + 备选方案对比 |
| [data-model.md](./data-model.md) | 4 张表 + cleanup script + alembic 迁移 |
| [quickstart.md](./quickstart.md) | 端到端运行手册（Phase A/B/C） |
| [contracts/](./contracts/) | cleanup-script / playwright-spec / route-redirect 三份契约 |
| [checklists/requirements.md](./checklists/requirements.md) | spec 质量门禁 |

## 前置依赖

- 032 v2 MVP（ship）
- 034 reactive-resume parity（ship）
- reactive-resume 源码：`D:\Project\reactive-resume`
- 参考简历：`C:\Users\30803\Desktop\简历\大模型应用开发简历v1.md`

## 实施三阶段

| Phase | 内容 | 时长估算 |
|---|---|---|
| A | 数据清理 + v1 触点下线 | 0.5 dev day |
| B | v2 编辑器端到端走通 | 0.5 dev day |
| C | Playwright 验收 + 两份清单 | 1.0 dev day（含修复循环） |

## 关键验收关卡

`tests/e2e/036-resume-v2-finalize.spec.ts` 35 个 test() 全部通过 + 两份清单 P1 项 = 0 未完成。

## 参考

- 036 spec: [spec.md](./spec.md)
- 036 plan: [plan.md](./plan.md)
- Constitution: [../../.specify/memory/constitution.md](../../.specify/memory/constitution.md)
- AGENTS 路由: [../../AGENTS.md](../../AGENTS.md)