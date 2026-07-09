# Feature Specification: 管理后台角色简化与汉化

**Feature Branch**: `051-admin-role-simplify-cn`

**Created**: 2026-07-07

**Status**: Draft

**Input**: User description: "收缩到free、pro、admin三层，存量用户全部调整成pro，新注册用户默认是free，这个free和pro是绑定到未来会加入的付费系统的。admin可以访问完整的管理后台能力。管理后台全面汉化，优化可读性。给admin用户的顶部菜单栏加一个跳转到管理后台的入口。"

## Supersession

REQ-051 supersedes the administration-console RBAC portion of REQ-044
(`specs/044-admin-console-redesign`). REQ-044's workspace definitions,
endpoint contracts, and component architecture remain the implementation
baseline; only the role-permission model is replaced.

REQ-044 sections affected:
- FR-002 (role → workspace visibility matrix)
- FR-031 (least-privilege capability grants)
- FR-009 / FR-020 (capability-based 403 error mapping)

REQ-044 sections NOT affected:
- Workspace definitions (FR-007 through FR-036 endpoint contracts)
- Component architecture and route structure
- Audit, export, retention, and sensitive-action requirements

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Admin 用户访问完整管理后台 (Priority: P1)

作为 InterCraft 内部运营人员（admin），我需要从主应用顶部导航栏一键进入管理后台，查看全部 8 个工作区的数据，以便监控产品运行状态、处理事件、审计操作。

**Why this priority**: 管理后台是运营基础设施。没有入口和权限保障，admin 用户无法开展工作。这是整个 REQ 的基石。

**Independent Test**: 将一个测试用户标记为 admin，验证其能在 Topbar 看到入口按钮、点击后进入完整管理后台、所有工作区可见。

**Acceptance Scenarios**:

1. **Given** 用户 `is_admin=true`，已登录主应用，**When** 用户查看顶部导航栏，**Then** 能看到盾牌图标的「管理后台」按钮（位于帮助按钮旁）
2. **Given** admin 用户点击「管理后台」按钮，**When** 页面跳转，**Then** 进入 `/admin-console/command-center`，侧边栏显示全部 8 个中文标签的工作区
3. **Given** admin 用户在管理后台，**When** 点击任意工作区导航，**Then** 能正常访问该工作区的所有功能和数据
4. **Given** admin 用户在管理后台，**When** 执行写操作（replay trace、修改 retention、发起 export），**Then** 操作成功执行

---

### User Story 2 — 角色模型从 6 角色简化为 3 层 (Priority: P1)

作为系统设计者，我希望权限模型简化为 admin / pro / free 三层，取消 pm/operations/maintainer/reviewer/viewer 的细分，使权限管理直观且易于维护。

**Why this priority**: 当前 6 角色模型实际有效差异不足 5 个 capability，维护成本高且无人理解。简化后降低代码复杂度，为后续付费系统打下清晰基础。

**Independent Test**: 验证数据库中存在 `is_admin` boolean 字段；admin console 认证逻辑仅检查 `is_admin` 而非遍历 6 角色 capability 矩阵。

**Acceptance Scenarios**:

1. **Given** 存量用户 `subscription='free'` 或 `subscription='pro'`，**When** 执行数据迁移后，**Then** 所有存量用户的 `subscription` 更新为 `'pro'`，`demo@intercraft.io` 的 `is_admin` 设为 `true`
2. **Given** 新用户注册，**When** 注册完成，**Then** 该用户的 `subscription='free'`，`is_admin=false`
3. **Given** `is_admin=false` 的用户，**When** 手动访问 `/admin-console` URL，**Then** 页面重定向到 `/dashboard`，不展示管理后台内容
4. **Given** `is_admin=true` 的用户，**When** 访问管理后台任意页面，**Then** 侧边栏展示全部 8 个工作区，不根据历史角色裁剪
5. **Given** 代码库中的 auth 模块，**When** 检查权限，**Then** 不再存在 `_ROLE_GRANTS` 6 角色字典、`roleToWorkspaces()` 多路分支、`ConsoleRole` union type

---

### User Story 3 — 管理后台全面汉化 (Priority: P2)

作为中文母语的运营人员，我希望管理后台的所有界面文字都是中文，工作区名称、按钮、标签、提示词等均为中文表达，以提高阅读效率和操作准确性。

**Why this priority**: 当前管理后台 ~336 处英文硬编码，与产品其他部分（已汉化）风格不一致。汉化是运营效率的直接影响因素，但不阻塞 P1 功能。

**Independent Test**: 遍历管理后台 8 个工作区的所有页面，目视验证关键 UI 元素（导航标签、按钮、表头、卡片标题）均为中文。

**Acceptance Scenarios**:

1. **Given** admin 用户进入管理后台，**When** 查看侧边栏导航，**Then** 8 个工作区名称显示为：「指挥中心」「产品分析」「AI 运营」「事件与差例」「日志与链路」「用户与账户」「报告中心」「治理与审计」
2. **Given** admin 用户在任意工作区，**When** 查看按钮、标签、表头、提示文字，**Then** 关键操作元素均为中文（如「生成报告」「保存视图」「创建快照」）
3. **Given** admin 用户查看数据列表，**When** 列表包含英文枚举值（如 status: success/failed），**Then** 枚举值保持原始英文，但列标题和筛选器标签为中文
4. **Given** admin 用户查看用户菜单，**When** 展开 Topbar 用户下拉菜单，**Then** 菜单项中包含中文「管理后台」入口

---

### User Story 4 — 管理后台入口在主应用导航栏可见 (Priority: P2)

作为 admin 用户，我需要在日常使用产品时能方便地进入管理后台，而不需要手动输入 URL 或记忆路径。

**Why this priority**: 入口发现性是管理后台使用率的直接决定因素。无入口意味着 admin 用户只能通过书签或命令行访问，严重影响运营效率。

**Independent Test**: admin 用户登录后在任意产品页面可见顶部导航栏的管理后台入口。

**Acceptance Scenarios**:

1. **Given** `is_admin=true` 用户登录，**When** 查看 Topbar 右侧区域，**Then** 帮助按钮旁出现盾牌图标的「管理后台」按钮
2. **Given** `is_admin=false` 用户登录，**When** 查看 Topbar 右侧区域，**Then** 不显示「管理后台」按钮
3. **Given** 任意用户展开 Topbar 用户下拉菜单，**When** 查看菜单项，**Then** admin 用户看到「管理后台」菜单项（位于「个人资料」之前），非 admin 用户看到带锁定图标的置灰「管理后台」
4. **Given** admin 用户在侧边栏，**When** 查看导航项，**Then** 侧边栏底部「PM 看板」下方出现「管理后台」链接
5. **Given** admin 用户在管理后台，**When** 点击 Topbar 中的 InterCraft logo 或返回按钮，**Then** 能回到主应用 Dashboard

---

### Edge Cases

- **admin 用户被降级（is_admin 从 true 改为 false）**：其当前管理后台 session 中的页面应在下次导航时重定向到 `/dashboard`。管理后台 API 调用应立即返回 403。
- **用户被删除后重新注册**：新注册流程默认 `is_admin=false`，即使该邮箱之前是 admin。admin 身份必须手动重新授予。
- **subscription 降级（pro → free）且 is_admin=false**：用户在管理后台入口不可见，手动访问 `/admin-console` 被重定向。
- **数据库迁移在半途失败**：迁移脚本应具备幂等性，可安全重跑。
- **管理后台页面内存在中英文混排**：枚举值、数据 ID、trace ID 等技术标识保持英文；所有面向用户的标签、描述、操作文字为中文。

---

## Requirements *(mandatory)*

### Functional Requirements

#### 角色模型重构

- **FR-001**: 系统 MUST 在 `users` 表中新增 `is_admin` 布尔字段，默认值为 `false`，用于标识用户是否具有管理后台访问权限。
- **FR-002**: 系统 MUST 提供数据迁移脚本，将全部存量用户的 `subscription` 字段值更新为 `'pro'`。
- **FR-003**: 数据迁移脚本 MUST 将 `demo@intercraft.io` 用户的 `is_admin` 设为 `true`。
- **FR-004**: 用户注册时，系统 MUST 将新用户 `subscription` 默认设为 `'free'`，`is_admin` 默认设为 `false`。
- **FR-005**: 管理后台 API 的所有受保护端点 MUST 仅检查 `is_admin=true`，不再依赖 `admin_console.auth._ROLE_GRANTS` 内存字典或 capability 枚举。
- **FR-006**: 系统 MUST 删除以下已废弃代码：`admin_console/auth.py` 中的 `_ROLE_GRANTS`、`grant_role()`、`revoke_role()`、`user_has_capability()`、`user_capabilities()`、`require_capability()`、`ensure_capabilities()`。
- **FR-007**: 用户 profile API 响应 MUST 包含 `is_admin` 字段，前端可据此判断是否展示管理后台入口。

#### 管理后台汉化

- **FR-008**: 管理后台 8 个工作区的导航标签 MUST 显示为中文：「指挥中心」「产品分析」「AI 运营」「事件与差例」「日志与链路」「用户与账户」「报告中心」「治理与审计」。
- **FR-009**: 管理后台所有面向用户的 UI 元素（按钮、标签、表头、卡片标题、提示文字、占位符）MUST 使用中文。
- **FR-010**: 数据层面的枚举值（如 `status: success/failed`、`severity: high/medium/low`）MAY 保留原始英文值，但其对应的展示标签（列标题、筛选器选项名）MUST 为中文。
- **FR-011**: 管理后台汉化 MUST 不引入国际化框架（i18n）；所有中文文本直接硬编码在组件中。

#### 管理后台入口

- **FR-012**: 主应用 Topbar MUST 在帮助按钮旁渲染一个管理后台入口按钮（盾牌图标），仅当 `is_admin=true` 时可见。
- **FR-013**: Topbar 用户下拉菜单 MUST 包含「管理后台」菜单项。admin 用户可点击跳转，非 admin 用户看到置灰锁定状态。
- **FR-014**: 主应用侧边栏 MUST 在「PM 看板」下方新增「管理后台」导航链接，仅 `is_admin=true` 时可见。
- **FR-015**: 管理后台 `AdminShell` 的 header 区域 MUST 提供返回主应用的链接（点击 logo 或返回按钮跳转到 `/dashboard`）。
- **FR-016**: 非 admin 用户手动访问 `/admin-console/*` 路径时，系统 MUST 重定向到 `/dashboard` 并展示无权限提示。

#### 前端代码清理

- **FR-017**: 前端 MUST 移除 `ConsoleRole` TypeScript 类型（`'pm' | 'operations' | 'maintainer' | 'reviewer' | 'owner' | 'unknown'`），改用 `boolean isAdmin`。
- **FR-018**: 前端 MUST 移除 `RoleBadgeDropdown` 组件及相关的角色切换逻辑（`resolveRole()`、`roleToWorkspaces()`）。
- **FR-019**: `AdminAuthGuard` MUST 基于 `useAuthStore` 中的 `isAdmin` 字段判断访问权限，不再依赖 localStorage 角色覆盖。

### Key Entities

- **User（用户）**：新增 `is_admin` 布尔属性，表示该用户是否为内部运营人员。`subscription` 属性取值 `free | pro | enterprise`，表示付费层级。两个属性相互独立：admin 身份不依赖付费层级，付费层级也不授予 admin 权限。
- **Admin Console Workspace（管理后台工作区）**：8 个稳定的工作区定义保持不变（指挥中心、产品分析、AI 运营、事件与差例、日志与链路、用户与账户、报告中心、治理与审计）。admin 用户可见全部 8 个，非 admin 用户不可见任何工作区。

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: admin 用户从主应用 Dashboard 进入管理后台指挥中心，操作步骤不超过 2 步（点击入口按钮 → 自动跳转）。
- **SC-002**: 非 admin 用户手动输入 `/admin-console` URL 后，在 3 秒内被重定向回 `/dashboard`，且看到明确的无权限提示。
- **SC-003**: 管理后台所有面向用户的 UI 文字（~336 处）100% 为中文，目视审查无遗漏英文标签。
- **SC-004**: 代码库中不再存在 `_ROLE_GRANTS`、`roleToWorkspaces`、`ConsoleRole`、`RoleBadgeDropdown` 等已废弃的 6 角色相关代码。
- **SC-005**: 数据迁移完成后，全部存量用户的 `subscription='pro'`，`demo@intercraft.io` 用户 `is_admin=true`。
- **SC-006**: 新注册用户的 `subscription='free'`、`is_admin=false`，无法访问管理后台。
- **SC-007**: 管理后台全部 46+ 后端端点对 admin 用户返回正确数据，对非 admin 用户返回 403。
- **SC-008**: 现有管理后台 E2E 测试（19 pass / 15 skip）在角色模型变更后回归通过率不降低。

---

## Assumptions

- 当前仅 `demo@intercraft.io` 一个用户需要 admin 权限。如需新增 admin，通过数据库直接修改 `is_admin` 字段（暂无自助 UI）。
- 付费系统（free/pro 的功能差异）不在本 REQ 范围内。本 REQ 仅负责角色层级定义和数据迁移。
- 产品仅面向中文用户，因此不引入 i18n 框架，直接硬编码中文。
- 管理后台工作区定义和端点契约维持 REQ-044 不变，本 REQ 不新增或删除工作区。
- `users` 表的 `subscription` CHECK 约束 `IN ('free','pro','enterprise')` 已存在，无需修改。
- `users` 表的 `role` 字段（默认值 `'user'`）保持不变，与管理后台访问解耦。`role` 字段留给未来产品内角色使用。
