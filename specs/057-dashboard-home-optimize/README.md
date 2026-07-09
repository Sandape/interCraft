# REQ-057 — 求职训练指挥台（工作台首页）

| Field | Value |
|---|---|
| Requirement ID | REQ-057 |
| Spec | [spec.md](./spec.md) |
| Plan | [plan.md](./plan.md) |
| Tasks | [tasks.md](./tasks.md) |
| Status | draft (tasks ready) |
| Created | 2026-07-10 |
| Status table | [requirements-status.md](./requirements-status.md) |
| Related | REQ-055/056（简历中心）、REQ-018（建议）、REQ-037（首屏）、求职追踪 |

## One-liner

把登录默认工作台从「指标墙 + 装饰建议」升级为**求职训练指挥台**：今日面试 → 简历/漏斗 → 下一步训练；不做岗位 Feed。

## Locked decisions

| Topic | Decision |
|---|---|
| 建议区 | 合并为单一「下一步」面板 |
| 今日列表 | 只展示今日面试岗位 + 跳转，无勾选 |
| 摘要缓存 | 本 REQ 纳入：用户隔离 + 分层新鲜度 + 写后失效 |
| P1 MVP | US1–US5 |
| P2 同 REQ | US6–US10 |

## Story map

| Priority | Stories |
|---|---|
| P1 | US1 今日指挥台 · US2 今日面试 · US3 简历对齐 · US4 单一下一步 · US5 首屏摘要缓存 |
| P2 | US6 漏斗 · US7 准备包 · US8 冷启动 · US9 继续 · US10 活动可读 |

## Artifacts

| Artifact | Path |
|---|---|
| Research | [research.md](./research.md) |
| Data model | [data-model.md](./data-model.md) |
| Quickstart | [quickstart.md](./quickstart.md) |
| Contracts | [contracts/](./contracts/) |

## Next

1. `/speckit-implement` (or execute [tasks.md](./tasks.md) from T001)
2. MVP stop after Phase 7 (US1–US5), then P2 stories
