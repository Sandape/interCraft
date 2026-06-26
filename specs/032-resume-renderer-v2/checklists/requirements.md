# Specification Quality Checklist: Resume Renderer v2 (JSON Schema + Multi-Template)

**Purpose**: Validate specification completeness and quality before proceeding to planning
**Created**: 2026-06-25
**Feature**: [spec.md](../spec.md)

## Content Quality

- [x] No implementation details (languages, frameworks, APIs) — spec stays at capability level (e.g. "强类型 sections", "JSON Schema 持久化" 记录在 Assumptions 作为约束而非 FR)
- [x] Focused on user value and business needs — each US describes a user-visible journey (切换模板、设计 style slots、签名分享等)
- [x] Written for non-technical stakeholders — 语言以用户视角 (用户在编辑器中, 弹出 Template Gallery)
- [x] All mandatory sections completed — User Scenarios & Testing, Requirements (FR), Key Entities, Success Criteria, Assumptions, Out of Scope, Technical Risks 全到位
- [x] Clarifications section present — 11 个 Q&A 决策落地 (JSON Schema / Playwright 后端 / 8-10 模板 / 范围 / 旧数据 / 027 基础设施保留 / 乐观并发 / 去除 DOCX / AI 裸调用 / Duplicate 支持 / Undo+Ctrl+Z)

## Requirement Completeness

- [x] No [NEEDS CLARIFICATION] markers remain — 11 个澄清已在两个 session 中逐条回答并写入 Clarifications
- [x] Requirements are testable and unambiguous — FR-001..FR-108 每条都有可验证行为 (Pikachu 模板 1 秒内切换, 15+ style slots, HMAC + bcrypt + 10-min cookie, If-Match 乐观并发 409, AI 3 次 retry)
- [x] Success criteria are measurable — SC-001..SC-018 全部可量化 (≥99% 漂移比, ≤2s 模板切换, ≥3 浏览器, 95% 单页一致性)
- [x] Success criteria are technology-agnostic — SC 关注结果 (一致性, 响应时间, 覆盖率, 业务指标), 不嵌入 React/Tiptap/dnd-kit 等技术细节
- [x] All acceptance scenarios are defined — 17 US × 平均 6 scenarios ≈ 100+ 个 Given/When/Then
- [x] Edge cases are identified — 大数据渲染 (50 items / 20 certs / 20 pubs)、CJK 字体、XSS、AI 输出合规、空数据回退、版本冲突、并发编辑、Cookie 过期、AI 限流、字符长度、JSON Patch 失败、SSR hydration、MIME 嗅探、URL 篡改、Worker 队列积压、Playwright 不可用等 16+ 条
- [x] Scope is clearly bounded — Out of Scope 明确不动 auth / jobs / interviews / errors / ability_profile / agents / chatbi; 旧 block 简历只读
- [x] Dependencies and assumptions identified — 18 assumptions 覆盖网络 / 浏览器 / 数据迁移 / 字体许可 / 模板素材许可 / API 配额 / Playwright 兼容性 / 设计 tokens / 隐私合规 / 业务规则

## Feature Readiness

- [x] All functional requirements have clear acceptance criteria — FR-001..FR-108 每条可在至少 1 个 US 的 acceptance scenario 验证
- [x] User scenarios cover primary flows — 17 US 覆盖数据模型 / 模板 / 设计系统 / 富文本 / 自定义 section / 拖拽 / 缩放 / 分享 / 导出 / AI / 缩略图 / 同步 / 旧数据只读 / 实时协作 / 设置面板 / Duplicate 变体 / Undo-Redo
- [x] Feature meets measurable outcomes defined in Success Criteria — SC 与 FR 双向追溯 (e.g. SC-001 ≤2s 模板切换 ↔ FR-009 实时切换)
- [x] No implementation details leak into specification — 仅在 Assumptions 标注技术栈 (Tiptap / dnd-kit / PostgreSQL JSONB / Playwright / SSE / Zod) 作为约束
- [x] Key entities identified — Resume v2 / Section / Item / Metadata / Style / Template / Page / CustomSection / AI Patch / ShareLink / ResumeSyncEvent 共 11 个
- [x] Technical risks & mitigations documented — 11 项风险 (Playwright 依赖、CJK 字体、AI 输出、JSONB 数据迁移、模板素材版权、缩略图体积、Cookie TTL、Worker 积压、并发编辑、AI 限流、CSP)

## Notes

- Spec 已就绪进入 `/speckit-plan` (推荐下一步)。
- 规模庞大 (17 US / 108 FR / 18 SC / 11 实体) — plan.md 必须分阶段实施，建议 7 阶段：
  1. 数据模型与 JSON Schema 验证 (US1)
  2. 8-10 模板与 Gallery (US2) + 渲染管线 (US4)
  3. 设计系统 15 style slots + Typography + Design (US3, US5)
  4. 富文本 Tiptap + Custom Section + DnD (US6, US7)
  5. 分享 + 同步 (US11, US12) + 乐观并发锁 (FR-084a~d)
  6. Duplicate 变体 (US16) + Undo/Redo (US17) + AI 优化 (US14)
  7. 旧数据兼容 + 设置面板 + 模板市场 (US15, US13, US3.5)
- 宪法遵守: Test-First (NON-NEGOTIABLE) — plan.md 必须先于实现编写测试任务，每个 US 都需至少一个 E2E 场景。
- 决策表 (11 项保留回查):
  - 数据模型: **JSON Schema 路线** (抛弃 Markdown)
  - 渲染: **后端 Playwright** (与 027 一致)
  - 模板数量: **8-10 个精选**
  - 范围: **仅限简历中心**
  - 旧数据: **新建数据表 + 旧简历只读**
  - 027 基建保留: **零漂移 + 双向定位 + auto-save + COW + 版本快照**
  - 并发锁: **乐观并发 (If-Match + 409)** — is_locked 仅用于 owner 主动永久锁
  - DOCX: **完全去除**，只导 PDF + JSON
  - AI 调用: **不设限 / 裸调用** + 3 次指数退避 retry
  - Duplicate: **支持** — 列表卡片 + 编辑器 dock 双入口
  - Undo/Redo: **20 步历史栈 + Ctrl+Z**，30 分钟无活动清空
- 与 [[resume_editor_redesign_2026_06_25]] 的潜在冲突: 刚完成的 Notion 风格 UIUX 重设计可能与 v2 的右侧 12 模块 Settings 面板冲突，plan 时需明确取舍（保留 Notion 风格还是迁移到 Settings 面板）。
