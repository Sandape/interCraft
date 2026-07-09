# Specification Quality Checklist: 简历 v2 收口（036-resume-v2-finalize）

**Purpose**: Validate specification completeness and quality before proceeding to planning
**Created**: 2026-06-29 (修订 2026-06-30)
**Feature**: [spec.md](../spec.md)

## Content Quality

- [x] No implementation details (languages, frameworks, APIs) — 仅在 FR/Notes 中引用具体文件名作为锚点（Sidebar.tsx、App.tsx、reactive-resume 路径），属于"实现触点"而非"实现细节"
- [x] Focused on user value and business needs — 7 US 全部从用户视角描述"易用"、"无版本号"、"全面弃用 v1"、"Playwright 实操"
- [x] Written for non-technical stakeholders — User Story 用中文陈述，Acceptance Scenarios 用 Given/When/Then
- [x] All mandatory sections completed — User Scenarios / Requirements / Success Criteria / Assumptions 全部到位

## Requirement Completeness

- [x] No [NEEDS CLARIFICATION] markers remain — 关键决策（v1 全面弃用、清理脚本幂等、Template Gallery 复用、Playwright 实操）都给出合理默认值
- [x] Requirements are testable and unambiguous — FR-001~FR-035 全部可断言（grep 命中、DB 行数、Playwright 截图数）
- [x] Success criteria are measurable — SC-001~SC-012 含 grep 计数、DB 行数、Playwright 步骤数、PDF 字段对比
- [x] Success criteria are technology-agnostic — SC 锚定可观察现象（DB 行数、Playwright 步骤、grep 命中数）
- [x] All acceptance scenarios are defined — 7 US 共 38 条 Given/When/Then 覆盖主流程 + 边界
- [x] Edge cases are identified — 11 条边界场景（清理回滚、悬挂外键、redirect loop、公开链接失效、Playwright selector 失败、移动端等）
- [x] Scope is clearly bounded — Out of Scope 明确排除 v1→v2 迁移、AI、模板扩展等
- [x] Dependencies and assumptions identified — Assumptions 列举 032/034 ship 依赖 + Playwright 可用性 + 用户接受清理过渡

## Feature Readiness

- [x] All functional requirements have clear acceptance criteria — FR-001~FR-035 每条都可被 SC-001~SC-012 验证
- [x] User scenarios cover primary flows — US1 菜单 + US2 路由 + US3 数据清理 + US4 新建流程 + US5 列表 + US6 体验补强 + US7 Playwright 实操 = 完整 MVP
- [x] Feature meets measurable outcomes defined in Success Criteria — SC-001~SC-012 全部对应 US1~US7
- [x] No implementation details leak into specification — FR 中提到的文件是必要锚点；SC 用 grep/Playwright 等可观察指标

## Dependency Check

- [x] 032 v2 ship（数据模型 + 编辑器 + 模板 + PDF）— ✅ 已 ship
- [x] 034 US1-US10 ship（10 类 item dialog + basics + 8 settings 面板真实现）— ✅ 已 ship
- [x] 027 ship（v1 Markdown 渲染 + 主题 + 导出）— ✅ 已 ship
- [x] reactive-resume 源码可参考 — ✅ `D:\Project\reactive-resume` 存在
- [x] Playwright 在本机已可用 — ✅ `playwright.config.ts` 已配置

## Risk Acknowledgment

- [x] Risk #1：清理脚本误删 prod 数据 — 仅 dev 环境 + dump 备份 + 用户接受清理过渡
- [x] Risk #2：悬挂外键 — LEFT JOIN + 事务包裹
- [x] Risk #3：Playwright 找不到 selector — 参考 reactive-resume 源码修复
- [x] Risk #4：dev server 启动失败 — backend health-check + arq + frontend 顺序
- [x] Risk #5：redirect 循环 — FR-008 `replace: true`
- [x] Risk #6：删除文件导致 import 失败 — FR-025 + 实施步骤要求"先改 import 再删文件"
- [x] Risk #7：跨模块引用残留 — FR-023/FR-024 + SC-006 grep 收口
- [x] Risk #8：e2e fixture 写死老路径 — US2 AC4 + SC-003 保留兼容断言
- [x] Risk #9：编辑器 dialog 字段命名不一致 — 实施 US7 时对照 reactive-resume 源码

## Notes

- 本 spec 通过 Phase 1（specify 阶段）质量门禁，可进入 Phase 2（plan/tasks）
- 关键验收关卡 = US7（Playwright 实操）；实施必须用 UI 操作，禁止 API 注入
- 实施遇到问题可参考 `D:\Project\reactive-resume/apps/artboard/src/dialogs/resume/sections/` 对应组件
- 后续 PR 评审需校验：清理脚本是否幂等；删除文件前是否先 grep 引用；Topbar"+" 流程是否桌面/移动端同源；Playwright 是否全程 UI 操作