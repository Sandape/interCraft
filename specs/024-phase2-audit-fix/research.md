# Research: Phase 2 (M5-M11) spec/code 偏差审计与修复

**Date**: 2026-06-22

## Research Questions

### RQ-001: PIN/ProfileView 保留还是移除?

**Decision**: **移除**。

**Rationale**:
- v1 spec 006 已发布，FR-008/010 仅要求 `expires_at` 过期 + `revoked_at` 撤销，无 PIN/ProfileView FR 覆盖。
- 保留需补 spec FR + acceptance scenario（PIN 输错 3 次锁定、IP 追踪隐私声明等），scope 蔓延到 spec 修订。
- 移除代码量小: `pin_hash` 列 + `ProfileView` 表 + 3-4 个 service 函数（service.py:277, 352-356）+ 1 个 API 中间件。
- 数据迁移简单: `DROP COLUMN pin_hash` + `DROP TABLE profile_views`，无数据备份需求（既有数据量小，且属过度实现）。
- 若 v2.1 真有需求，走独立 feature spec 流程，重新设计（含暴力破解防护、隐私合规、审计日志）。
- 符合 Constitution I: Library-First 要求每个特性边界清晰、有目的，不为组织结构而设立。

**Alternatives considered**:
- **保留并补 spec FR**: 需重新走 spec 流程（spec 006 修订 + plan + tasks），scope 蔓延到 v2.1。**拒绝**。
- **保留但标记 deprecated**: 代码仍在，运维负担不减。**拒绝**。
- **仅移除 PIN，保留 ProfileView**: 两者都依赖 `pin_hash`，且 ProfileView 无独立价值（PIN 撤销后 ProfileView 失去意义）。**拒绝**。

### RQ-002: PDF 导出同步 vs 异步如何选?

**Decision**: 同步生成，直接返回 PDF。

**Rationale**:
- spec 006 FR-018 明确「直接下载」，实现语义偏差是 v1 bug。
- 单用户能力画像内容 < 1MB，PDF 生成耗时 ≤ 3s（reportlab / weasyprint 基准测试），同步可接受。
- 异步 ARQ 任务需轮询，UX 差（用户期望「点击即下载」）。
- 同步路径不阻塞 event loop: FastAPI 同步端点用 `run_in_threadpool` 包装 CPU-bound PDF 生成。
- 既有 ARQ PDF 任务代码（service.py:419-420）移除，避免维护两套路径。
- 若未来能力画像内容扩展（> 5MB），可重新评估异步，但 v2.0 不需要。

**Alternatives considered**:
- **保留 ARQ 异步 + 加同步路径**: 维护两套代码，复杂度高。**拒绝**。
- **批量导出走 ARQ，单次走同步**: spec 未提批量需求，YAGNI。**拒绝**。
- **流式响应（streaming response）**: PDF 是二进制，流式无优势，一次性返回更简单。**拒绝**。

### RQ-003: outbox 接入用 IndexedDB 还是 localStorage?

**Decision**: 复用既有 `src/lib/outbox/` 基础设施（resume 模块已用）。

**Rationale**:
- 既有 outbox 基础设施已在 resume 模块运行，本 feature 仅扩展到 jobs 模块，不重新设计。
- 既有实现用什么存储（IndexedDB / localStorage）就跟随，保持一致性。
- jobs 写操作数据量小（4 类操作 × 单次 payload < 5KB），localStorage 4MB 上限够用。
- 若既有 outbox 用 IndexedDB，本 feature 自动获益于更大存储空间。

**Alternatives considered**:
- **重新设计 outbox 用 IndexedDB**: 重复造轮子，违反 DRY。**拒绝**。
- **用 Service Worker 后台同步**: 复杂度高，需 HTTPS + SW 注册，v2.0 不需要。**拒绝**。

### RQ-004: archived 状态移除后，既有数据如何处理?

**Decision**: 直接移除 `archived_at` 列，既有 `archived_at` 非空记录转为 `deleted_at`。

**Rationale**:
- `archived_at` 列仅后端有，UI 未暴露，用户无感知。
- 既有 `archived_at` 非空记录（若有）语义上等同于软删，迁移时 `UPDATE error_questions SET deleted_at = archived_at WHERE archived_at IS NOT NULL AND deleted_at IS NULL`。
- 迁移后 `DROP COLUMN archived_at`，表结构干净。
- 若 `archived_at` 无数据（需 grep 生产库确认），迁移直接 DROP。

**Alternatives considered**:
- **保留 `archived_at` 列但禁用转换**: 代码气味，未来开发者困惑。**拒绝**。
- **保留 `archived` 状态并补 spec FR**: scope 蔓延，spec 016 明确不授权此状态。**拒绝**。
- **将 `archived` 数据迁移到 `mastered`**: 语义错误，mastered 表示已掌握，archived 仅是归档。**拒绝**。

### RQ-005: status_history 字段名对齐方向 (后端改还是前端改)?

**Decision**: 前端对齐后端 `{from, to, at, note}`。

**Rationale**:
- 后端 `jobs/service.py:49,100` 已用 `{from, to, at, note}`，且 `from` / `to` 是 Python 关键字友好（SQLAlchemy 序列化时无冲突）。
- 前端 `{from_status, to_status, changed_at}` 是 v1 开发时未对齐的疏漏。
- 前端改动范围小: `JobRepository.ts` 类型定义 + `JobTimeline.tsx` 读取逻辑，2 个文件。
- 后端响应字段名改动会破坏既有客户端契约（即使有版本化，避免不必要 breaking change）。

**Alternatives considered**:
- **后端对齐前端**: 破坏 API 契约，既有客户端需同步升级。**拒绝**。
- **前后端都改用新字段名（如 `from_state` / `to_state`）**: 无必要，两边都改风险大。**拒绝**。
- **后端同时返回两套字段名**: 代码冗余，且 spec 014 已承诺修复。**拒绝**。

### RQ-006: JobsDetailPanel 重写 vs 增量补齐?

**Decision**: 重写。

**Rationale**:
- 既有 `JobsDetailPanel.tsx` 仅渲染 basic info + 2 CTA，80% FR 缺失，增量补齐会产生大量条件分支，可读性差。
- 重写可重新设计 5 大区域布局（basic info / timeline / edit mode / offer section / activities），结构清晰。
- 重写成本与增量补齐相近（既有代码量小），但长期维护成本低。
- 测试先写（TDD），重写过程测试覆盖 5 大区域。

**Alternatives considered**:
- **增量补齐**: 既有结构限制，新功能塞不下。**拒绝**。
- **拆分为多个子组件（JobBasicInfo / JobTimeline / JobOfferEditor / JobActivities）**: 与重写等效，但需重新设计父组件布局。**采纳为重写的一部分**。

## Decisions Summary

| ID | Decision | Alternatives Rejected |
|----|----------|----------------------|
| D1 | PIN/ProfileView 移除 | 保留并补 spec, 保留标记 deprecated, 仅移除 PIN |
| D2 | PDF 同步生成直接返回 | 保留 ARQ + 加同步, 批量 ARQ 单次同步, 流式响应 |
| D3 | 复用既有 `src/lib/outbox/` | 重新设计 IndexedDB, Service Worker |
| D4 | 移除 `archived_at` 列，既有数据转 `deleted_at` | 保留列禁用转换, 保留并补 spec, 转为 mastered |
| D5 | 前端对齐后端 `{from, to, at, note}` | 后端对齐前端, 两边改新字段, 同时返回两套 |
| D6 | JobsDetailPanel 重写（含子组件拆分）| 增量补齐 |
