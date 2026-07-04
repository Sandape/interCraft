---
req_id: REQ-044-CROSS
status: locked
locked_at: 2026-07-04
locked_by: main-agent
negotiation_rounds: 1
---

# Acceptance Matrix for REQ-044-CROSS

Cross-cutting: Saved Views + Role 扩展 (FR-006 / FR-002 落地).

This CROSS US lands the US1 stub `savedViewRepository.ts` real persistence
plus tightens the 5-role / 5x8 access matrix and wires the role-aware
AdminShell dropdown.

## SC Gaps
- 无. Spec SC-008 ("100% of unauthorized attempts ... are denied") is fully
  covered by the SAVED_VIEW_VIEW / SAVED_VIEW_CHANGE capability tokens.
- Spec SC-009 ("100% of saved-view changes create audit events") is
  fulfilled by the new 12th audit action `saved_view_change`.

## AC 矩阵

### FR-006 saved views 跨工作空间共享

| AC-ID | 描述 | 验证方式 | 来源 |
|-------|------|---------|------|
| AC-6.1 | `GET /api/v1/admin-console/saved-views?workspace_id=X` 返回 saved_views list 字段: id / name / workspace_id / filters (jsonb) / owner_user_id / description / trust_status (verified/pending/deprecated) / created_at / updated_at / shared_with (array of role) | `cd backend && uv run pytest backend/tests/contract/test_044_saved_views.py::test_list_saved_views_returns_full_envelope -v` 期望 200 + 字段齐 + total ≥ 8 | FR-006 / SC-012 |
| AC-6.2 | `POST /api/v1/admin-console/saved-views` payload: `{name, workspace_id, filters, description}`;response 含 `saved_view_id` + audit event | `pytest ...::test_create_saved_view_returns_id_and_audit -v` 期望 201 + 字段 + audit buffer | FR-006 / SC-009 |
| AC-6.3 | `GET /api/v1/admin-console/saved-views/{id}` 返回单条 detail | `pytest ...::test_get_saved_view_detail -v` 期望 200 + 所有字段 | FR-006 |
| AC-6.4 | `PATCH /api/v1/admin-console/saved-views/{id}` 更新 (audit logged, requires SAVED_VIEW_CHANGE) | `pytest ...::test_patch_saved_view_audited_and_403 -v` 期望 200 + audit; viewer 角色 403 | FR-006 / FR-034 / SC-009 |
| AC-6.5 | `DELETE /api/v1/admin-console/saved-views/{id}` 删除 (audit logged) | `pytest ...::test_delete_saved_view_audited -v` 期望 204 + audit | FR-006 / SC-009 |
| AC-6.6 | filter by workspace_id + role-based access (PM 可见全部;operations 仅可见 shared_with role 含 operations 的) | `pytest ...::test_role_based_filter_pm_sees_all_operations_scoped -v` 期望 PM total=N, operations total<M | FR-031 / SC-008 |
| AC-6.7 | saved_view change 触发 audit event (FR-034 第 12 类 saved_view_change) | `pytest ...::test_audit_action_saved_view_change -v` 期望 `audit.VALID_ACTIONS` 包含 `'saved_view_change'` + audit buffer | FR-034 / SC-009 |
| AC-6.8 | 前端 `savedViewRepository.ts` 5 方法真实实现 (移除 `throw NotImplementedError`): list / get / create / update / delete | `npm run test -- --run src/admin/components/SavedViewsPanel/__tests__/index.test.tsx` 期望 0 throw + fetch 正常 | FR-006 |
| AC-6.9 | 前端 `SavedViewsPanel` 真实渲染 saved_view 列表 + 新建/编辑/删除按钮 + 应用 saved_view 跳 workspace + filters | vitest 断言 `data-testid="saved-views-list"` 渲染 ≥ 1 项 + 3 个操作按钮 | FR-006 |
| AC-6.10 | 前端 AdminShell role-aware: PM 角色看到全部 saved views;非 PM 看到 shared_with 含自己角色的 | vitest 断言 5 角色下可见 saved_view 数量不同 | FR-031 / SC-008 |
| AC-6.11 | workspace 顶部 "Save current view" 按钮 → 触发 POST saved_views,捕获当前 filter state | vitest 断言 `data-testid="save-current-view-button"` 存在 + onClick → `useCreateSavedView` mutation | FR-006 |
| AC-6.12 | 跨 workspace 共享 — saved_view 创建在 workspace A 但 shared_with role B,B 用户可在 workspace A 看到此 saved_view | `pytest ...::test_cross_workspace_role_share -v` 期望 operations 在 workspace A 看到这条但 PM 在 workspace B 看不到 | FR-031 / SC-008 |

### FR-002 5 角色工作空间可见性矩阵

| AC-ID | 描述 | 验证方式 | 来源 |
|-------|------|---------|------|
| AC-2.1 | 后端 access matrix 5 role × 8 workspace × 6 capability 二维表完整 (US6 已建 governance.access_matrix,本 CROSS 扩 saved_view 相关 capability 列) | `pytest ...::test_access_matrix_includes_saved_view_view_change -v` 期望 5x8x6 完整 + capability 列含 saved_view | FR-031 / SC-008 |
| AC-2.2 | 后端 `_ROLE_GRANTS` 完整覆盖 5 角色 (US3 5+ role grants 已 ship,本 CROSS 验证全 5 角色都列 + viewer 故意空) | `pytest ...::test_role_grants_all_five_roles_listed -v` 期望 admin / owner / pm / reviewer / operations / maintainer 全列 + viewer 故意空 | FR-002 / FR-031 |
| AC-2.3 | 前端 AdminShell role-aware 显式测试: PM / operations / maintainer / reviewer / owner 5 角色各自 sidebar 可见 workspace 子集 (与 `resolveRole` 4 层 fallback 一致) | `npm run test -- --run src/admin/components/AdminShell.role.test.tsx` 期望 5 角色各自 nav items 数量精确 | FR-002 |
| AC-2.4 | 顶部 role badge 显示当前 role (US1 已建,本 CROSS 升级为可点击切换 dropdown 用于 testing) | vitest 断言 `data-testid="topbar-role-badge"` 可点击 → 5 角色 dropdown | FR-002 |
| AC-2.5 | 5 角色前端 union 已含 (US1 已建 ConsoleRole type,本 CROSS 验证 type completeness) | `npm run typecheck` 期望 0 error + TypeScript 编译检查 | FR-002 |

### 整合测试 (regression)

| AC-ID | 描述 | 验证方式 | 来源 |
|-------|------|---------|------|
| IT-1 | 跨 US 回归 — US1/2/3/4/5/6/7 所有 AC 矩阵 + savedViewRepository 实现后仍 PASS | `cd backend && uv run pytest backend/tests/contract/test_044_*.py -q` + `npm run test -- --run` 期望 0 fail | 回归铁律 |
| IT-2 | 跨 US 类型同步 — 前端 SavedView + WorkspaceId + ConsoleRole 与后端 Pydantic Literal 完全对齐 | `npm run typecheck` + `pytest ...::test_workspace_id_literal_alignment` 期望 union 全覆盖 | 跨 team 合同 |
| IT-3 | 跨 US auth 同步 — 5 角色 × 12 capability (COMMAND_CENTER/PRODUCT_ANALYTICS/AI_OPERATIONS/INCIDENT/BADCASE/USER_LOOKUP/RBAC/SENSITIVE_REVEAL/AUDIT/EXPORT/GOVERNANCE/REVIEW_SNAPSHOT/SAVED_VIEW) 完整 RBAC map | `pytest ...::test_role_grants_cover_12_capabilities -v` 期望每个 role 都覆盖 (除了 viewer 故意空) | FR-031 |

### Edge Cases

| AC-ID | 描述 | 验证方式 | 来源 |
|-------|------|---------|------|
| EC-1 | saved_view filters 引用已删除的 cohort → 打开 saved_view 时显示 "filter references deleted cohort, please update" | `pytest ...::test_saved_view_deleted_cohort_warning -v` 期望 warning 字段 | FR-006 |
| EC-2 | shared_with role 改 → 已打开 saved_view 的用户下次访问显示 "permission revoked" | `pytest ...::test_shared_with_revoke_shows_warning -v` 期望 permission_revoked=true | FR-031 / SC-008 |
| EC-3 | saved_view 创建并发冲突 (optimistic locking) → 422 with "version conflict" | `pytest ...::test_saved_view_concurrent_422_version_conflict -v` 期望 422 + version_conflict | FR-006 |
| EC-4 | viewer 角色尝试 create saved_view → 403 (viewer 空 grants) | `pytest ...::test_viewer_cannot_create_saved_view -v` 期望 403 | FR-031 / SC-008 |

## 起草说明

### 设计意图
- **US1 stub 真实化** — `savedViewRepository.ts` 移除 `throw NotImplementedError`,5 方法
  真实实现 + `audit.py` 新增第 12 类 `saved_view_change` action。
- **跨 US 类型对齐** — 前端 `SavedView` 加 `shared_with: ConsoleRole[]`,`WorkspaceId` 已与后端 Pydantic Literal 同步。
- **role-aware 显式收紧** — 5 角色可见的 saved_view 子集不同;非 PM 角色通过
  `shared_with` 过滤;viewer 故意空 (FR-031 least-privilege)。
- **5×8×N capability 扩展** — access matrix 不变 (6 capability) 但 `_ROLE_GRANTS`
  增加 `SAVED_VIEW_VIEW` / `SAVED_VIEW_CHANGE` 两 token,US6 governance 矩阵 5x8x6 已锁。
- **role badge dropdown** — 测试工具;Playwright EC-3b 通过 localStorage 注入,
  新 dropdown 让 dev / tester 不用手动改 localStorage 也能切换 role。

### 已覆盖的边界
- 跨 workspace shared_with (AC-6.12) — PM A 创建 saved_view,operations B 在 A 中可见。
- optimistic locking 版本冲突 (EC-3) — 422 with version_conflict。
- 删除 cohort filter 引用 (EC-1) — warning 字段 + 不崩溃。
- viewer 空 grants 拒绝 (EC-4) — 403。
- role badge dropdown 切换 (AC-2.4) — 5 角色可选。
- audit 12 类 (AC-6.7) — DB-persisted `saved_view_change`。
- 5 角色前端 union typecheck (AC-2.5)。

### 未覆盖的边界 (已知风险)
- **真实 DB 持久化** — 沿用 US4/6/7 pattern,in-memory buffer;Phase 2 batch 5 才会真 DB。
  已记录 [CROSS-TEAM-DEBT] tag 在 saved_views/repository.py 模块顶部。
- **saved view template sharing 跨组织** — 当前仅角色级共享,不支持跨租户。
- **saved view diff** — 当前无 saved_view 之间的 diff;Phase 3 视情况加入。
- **webhook / 通知** — saved_view change 无外部通知机制。
- **saved view 权限 owner vs shared_with** — 当前 owner 隐式拥有所有权限,无细粒度 owner-can-delete-but-not-share 选项。