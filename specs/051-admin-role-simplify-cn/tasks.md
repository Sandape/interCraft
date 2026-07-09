# Tasks: 管理后台角色简化与汉化 (REQ-051)

**Branch**: `051-admin-role-simplify-cn` | **Date**: 2026-07-07 | **Plan**: [plan.md](./plan.md)

## Overview

4 User Stories / ~35 tasks across 4 phases.

## Phase 1: 预备 (Migration + Schema)

- [ ] T001 [P] [US2] 创建 alembic migration 0032_051_is_admin: users 表新增 `is_admin BOOLEAN NOT NULL DEFAULT FALSE` in `backend/migrations/versions/0032_051_is_admin.py`
- [ ] T002 [US2] migration 0032 中执行数据迁移: 所有存量用户 `subscription='pro'` + `demo@intercraft.io` 设 `is_admin=true` (FR-002, FR-003) in `backend/migrations/versions/0032_051_is_admin.py`
- [ ] T003 [US2] 验证 migration upgrade/downgrade 幂等性：重复执行不报错 (Edge Case: migration 半途失败可重跑) in `backend/migrations/versions/0032_051_is_admin.py`

## Phase 2: 后端 Auth 重构 (US1)

- [ ] T004 [P] [US1] 在 `admin_console/auth.py` 中新增 `require_admin()` FastAPI dependency factory：查 `User.is_admin`，非 admin 返回 403 (FR-005) in `backend/app/modules/admin_console/auth.py`
- [ ] T005 [US1] `PublicUser` schema 新增 `is_admin: bool = False` 字段 (FR-007) in `backend/app/modules/auth/schemas.py`
- [ ] T006 [US1] `_user_to_public()` 映射 `is_admin` 字段 (FR-007) in `backend/app/modules/auth/service.py`
- [ ] T007 [US1] admin_console/api.py: 替换 `require_capability(REPLAY_TRIGGER)` / `require_capability(TASK_TAG)` → `require_admin` (FR-005) in `backend/app/modules/admin_console/api.py`
- [ ] T008 [US1] ai_operations/api.py: 替换全部 15 处 `require_capability(AI_OPERATIONS_VIEW)` → `require_admin` (FR-005) in `backend/app/modules/admin_console/ai_operations/api.py`
- [ ] T009 [US1] decision_signals/api.py: 替换全部 `require_capability(COMMAND_CENTER_VIEW)` → `require_admin` (FR-005) in `backend/app/modules/admin_console/decision_signals/api.py`
- [ ] T010 [US1] product_analytics/api.py: 替换全部 `require_capability(PRODUCT_ANALYTICS_VIEW)` / `require_capability(USER_LOOKUP)` → `require_admin` (FR-005) in `backend/app/modules/admin_console/product_analytics/api.py`
- [ ] T011 [US1] incidents/api.py: 替换全部 `require_capability(INCIDENT_VIEW)` / `INCIDENT_CHANGE` / `BADCASE_VIEW` / `BADCASE_CHANGE` → `require_admin` (FR-005) in `backend/app/modules/admin_console/incidents/api.py`
- [ ] T012 [US1] governance/api.py: 替换全部 `require_capability(RBAC_VIEW)` / `SENSITIVE_REVEAL` / `AUDIT_VIEW` / `EXPORT` / `GOVERNANCE_VIEW` / `GOVERNANCE_CHANGE` → `require_admin` (FR-005) in `backend/app/modules/admin_console/governance/api.py`
- [ ] T013 [US1] review_snapshots/api.py: 替换全部 `require_capability(REVIEW_SNAPSHOT)` → `require_admin` (FR-005) in `backend/app/modules/admin_console/review_snapshots/api.py`
- [ ] T014 [US1] saved_views/api.py: 替换全部 `require_capability(SAVED_VIEW_VIEW)` / `SAVED_VIEW_CHANGE` → `require_admin` (FR-005) in `backend/app/modules/admin_console/saved_views/api.py`
- [ ] T015 [US1] 检查 governance/repository.py, governance/schemas.py, governance/service.py, saved_views/schemas.py, saved_views/service.py 中 `ensure_capabilities()` 调用 → 替换/删除 (FR-006) in `backend/app/modules/admin_console/governance/`, `backend/app/modules/admin_console/saved_views/`
- [ ] T016 [US1] 删除 `admin_console/auth.py` 中的 `_ROLE_GRANTS`, `_user_roles`, `_default_role`, `_lock`, 所有 capability 常量, `grant_role()`, `revoke_role()`, `reset_for_tests()`, `set_default_role()`, `user_has_capability()`, `user_capabilities()`, `require_capability()`, `ensure_capabilities()` (FR-006) in `backend/app/modules/admin_console/auth.py`
- [ ] T017 [US1] 保留并导出 `require_admin`, `get_caller_user_id_dep` from auth.py; 更新 `admin_console/__init__.py` 导出 (FR-006) in `backend/app/modules/admin_console/auth.py`, `backend/app/modules/admin_console/__init__.py`
- [ ] T018 [US1] 删除 `main.py` lifespan 中的 `grant_role()` 硬编码 (BUG-2 fix area — 原 fix 由 migration 替代) (FR-006) in `backend/app/main.py`
- [ ] T019 [US1] backend pytest: 全量运行确认无 import error + 无 403 regression; 新增 admin auth test 覆盖 `require_admin` (SC-007) in `backend/tests/`

## Phase 3: 前端 Auth Gate + AdminShell 简化 (US1 前端)

- [ ] T020 [P] [US1] `PublicUser` 前端类型新增 `is_admin: boolean` (FR-007) in `src/api/types.ts`
- [ ] T021 [US1] `AdminAuthGuard` 增加 `is_admin` 检查：非 admin 用户访问 `/admin-console` 重定向到 `/dashboard` (FR-016) in `src/admin/routes.tsx`
- [ ] T022 [US1] `AdminShell.tsx`: 删除 `resolveRole()` 函数 + `roleToWorkspaces()` 函数 + `ConsoleRole` 类型导入 (FR-017, FR-018) in `src/admin/components/AdminShell.tsx`
- [ ] T023 [US1] `AdminShell.tsx`: 删除 `RoleBadgeDropdown` 导入 + 渲染 (FR-018)；重置 `isAdmin` 逻辑为 `useAuthStore.user?.is_admin` (FR-019) in `src/admin/components/AdminShell.tsx`
- [ ] T024 [US1] `AdminShell.tsx`: `visibleItems` 固定为全部 8 个 workspace (admin 可见全部，无需过滤) (FR-017) in `src/admin/components/AdminShell.tsx`
- [ ] T025 [US1] 删除 `RoleBadgeDropdown.tsx` 组件文件 (FR-018) in `src/admin/components/RoleBadgeDropdown.tsx`
- [ ] T026 [US1] `admin-console.ts` 类型文件: 删除 `ConsoleRole` 类型定义 + `SharedWithRole` 类型 (FR-017) in `src/types/admin-console.ts`
- [ ] T027 [US1] AdminShell header 的 `InterCraft · {title}` 改为可点击返回主应用 `/dashboard` (FR-015) in `src/admin/components/AdminShell.tsx`
- [ ] T028 [US1] 前端 typecheck: 确认所有已删除类型/函数无遗留引用 in `src/`

## Phase 4: 管理后台入口 + 汉化 (US3 + US4)

- [ ] T029 [P] [US4] Topbar: 在 HelpCircle 按钮旁添加盾牌图标「管理后台」按钮，仅 `isAdmin` 可见 (FR-012) in `src/components/layout/Topbar.tsx`
- [ ] T030 [US4] Topbar 用户下拉菜单: 在「个人资料」前添加「管理后台」菜单项。admin 可点击跳转，非 admin 置灰+锁定图标 (FR-013) in `src/components/layout/Topbar.tsx`
- [ ] T031 [US4] Sidebar: `secondaryNav` 中「PM 看板」下方新增「管理后台」链接 (盾牌图标)，仅 `isAdmin` 可见 (FR-014) in `src/components/layout/Sidebar.tsx`
- [ ] T032 [US3] AdminShell: `NAV_ITEMS` 标签替换为 8 个中文工作区名称：「指挥中心」「产品分析」「AI 运营」「事件与差例」「日志与链路」「用户与账户」「报告中心」「治理与审计」(FR-008) in `src/admin/components/AdminShell.tsx`
- [ ] T033 [US3] AdminShell: sidebar brand + header title 汉化 (FR-009) in `src/admin/components/AdminShell.tsx`
- [ ] T034 [US3] 汉化 CommandCenter 页面：按钮/标签/表头/卡片标题 + 筛选器标签 (FR-009, FR-010) in `src/admin/pages/CommandCenter.tsx`
- [ ] T035 [US3] 汉化 ProductAnalytics 页面 (FR-009, FR-010) in `src/admin/pages/ProductAnalytics.tsx`
- [ ] T036 [US3] 汉化 AIOperations 页面 (FR-009, FR-010) in `src/admin/pages/AIOperations.tsx`
- [ ] T037 [US3] 汉化 IncidentsBadcases 页面 (FR-009, FR-010) in `src/admin/pages/IncidentsBadcases.tsx`
- [ ] T038 [US3] 汉化 LogsAndTraces 页面 (FR-009, FR-010) in `src/admin/pages/LogsAndTraces.tsx`
- [ ] T039 [US3] 汉化 UsersAccounts 页面 (FR-009, FR-010) in `src/admin/pages/UsersAccounts.tsx`
- [ ] T040 [US3] 汉化 Reports 页面 (FR-009, FR-010) in `src/admin/pages/Reports.tsx`
- [ ] T041 [US3] 汉化 Governance 页面 (FR-009, FR-010) in `src/admin/pages/Governance.tsx`

## Phase 5: E2E + 收尾

- [ ] T042 [P] [E2E] 新建 Playwright spec: admin 入口可见性 + 8 workspace 访问 + 非 admin 重定向 (SC-001, SC-002) in `tests/e2e/051-admin-role-simplify.spec.ts`
- [ ] T043 [E2E] Playwright spec: 管理后台汉化目视验证 (导航标签 + 按钮/表头) (SC-003) in `tests/e2e/051-admin-role-simplify.spec.ts`
- [ ] T044 [E2E] 更新 `044-admin-helpers.ts`: `loginAsDemo` 适配新的 `is_admin` 模型（删除 localStorage role 注入） (SC-008) in `tests/e2e/044-admin-helpers.ts`
- [ ] T045 [CLEANUP] 前端 typecheck 全量通过 (SC-004) in `src/`
- [ ] T046 [CLEANUP] 后端 pytest 全量通过 (SC-007) in `backend/`
- [ ] T047 [CLEANUP] `git grep "_ROLE_GRANTS\|roleToWorkspaces\|ConsoleRole\|RoleBadgeDropdown"` 确认零残留 (SC-004) in project root

---

## Task Dependency Graph

```text
Phase 1 (Migration)
  T001 ─> T002 ─> T003
         │
         v
Phase 2 (Backend Auth)
  T004 ─> T005, T006
  T004 ─> T007 ~ T015 (parallel replace)
  T007~T015 ─> T016, T017, T018
         │
         v
Phase 3 (Frontend Auth Gate)
  T005, T006 ─> T020  (schema sync)
  T020 ─> T021, T022, T023, T024 (parallel)
  T022 ─> T025, T026
  T022 ─> T027
         │
         v
Phase 4 (Entry + I18N)
  T021 ─> T029, T030, T031 (parallel)
  T022 ─> T032, T033
  T032 ─> T034 ~ T041 (parallel)
         │
         v
Phase 5 (E2E + Verify)
  T029~T041 ─> T042, T043 (parallel)
  T016~T018 ─> T045, T046, T047
  T042, T043, T044 ─> E2E acceptance
```

## FR Coverage Matrix

| FR | Task(s) | Description |
|---|---|---|
| FR-001 | T001 | `is_admin` column on `users` table |
| FR-002 | T002 | Data migration: all users → `subscription='pro'` |
| FR-003 | T002 | Data migration: demo@intercraft.io → `is_admin=true` |
| FR-004 | T003 (default) | New user register → `is_admin=false` (DB default) |
| FR-005 | T004, T007~T015 | Admin console endpoints check `is_admin` only |
| FR-006 | T016, T017, T018 | Delete `_ROLE_GRANTS`, `grant_role()`, `require_capability()`, etc. |
| FR-007 | T005, T006, T020 | PublicUser response includes `is_admin` |
| FR-008 | T032 | 8 workspace nav labels → Chinese |
| FR-009 | T033~T041 | All user-facing UI elements → Chinese |
| FR-010 | T034~T041 | Enum values keep English, labels Chinese |
| FR-011 | T034~T041 | No i18n framework, hard-coded Chinese |
| FR-012 | T029 | Topbar admin entry button (shield icon) |
| FR-013 | T030 | User dropdown menu item |
| FR-014 | T031 | Sidebar admin link |
| FR-015 | T027 | AdminShell header → return to main app |
| FR-016 | T021 | Non-admin redirected to /dashboard |
| FR-017 | T022, T024, T026 | Remove ConsoleRole type |
| FR-018 | T022, T023, T025 | Remove RoleBadgeDropdown + role switching |
| FR-019 | T021, T023 | AdminAuthGuard based on isAdmin |

## Success Criteria Mapping

| SC | Verification | Task |
|---|---|---|
| SC-001 | admin 2 步进入管理后台 | T042 |
| SC-002 | 非 admin 3s 内重定向 | T042 |
| SC-003 | ~336 处 UI 100% 中文 | T034~T041, T043 |
| SC-004 | 无 _ROLE_GRANTS / ConsoleRole 残留 | T047 |
| SC-005 | 存量用户 sub=pro, demo is_admin=true | T002 |
| SC-006 | 新用户 sub=free, is_admin=false | T003 |
| SC-007 | 46+ 端点 admin 返回正确数据 | T019 |
| SC-008 | E2E 19/15 回归通过率不降低 | T044 |
