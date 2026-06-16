# Feature Specification: Topbar New Resume Branch

**Feature Branch**: `017-topbar-new-resume`

**Created**: 2026-06-16

**Status**: Draft

**Input**: User description: "顶栏的"新建简历分支"按钮目前无功能（AppShell 的 onNewResume prop 从未在 App.tsx 传入，按钮 onClick 为 undefined）。实现功能：点击该按钮后跳转到 /resume 页面并自动打开创建分支弹窗。"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - 从顶栏发起新建简历分支 (Priority: P1)

用户在任意页面点击顶栏"新建简历分支"按钮，跳转到简历列表页（/resume），页面加载后自动弹出创建分支弹窗。用户填写分支名称、公司和岗位后提交，弹窗关闭，分支创建成功。用户也可以关闭弹窗继续正常浏览简历列表。

**Why this priority**: 顶栏"新建简历分支"是目前顶栏唯一不工作的按钮，用户点击无反应，直接影响产品完整性和用户信任。

**Independent Test**: 在任意页面（如仪表盘）点击顶栏"新建简历分支"按钮，验证跳转到 /resume?new=true，弹窗出现。直接访问 /resume?new=true 也触发弹窗。关闭弹窗后 URL 变为 /resume。

**Acceptance Scenarios**:

1. **Given** 用户在任何认证页面（如仪表盘），**When** 点击顶栏「新建简历分支」按钮，**Then** 路由跳转到 `/resume?new=true`，URL 参数 `new=true` 存在。
2. **Given** 用户通过顶栏按钮或直接访问到达 `/resume?new=true`，**When** 页面加载完成，**Then** 自动弹出创建分支弹窗（与 ResumeList 页面内点击"新建简历"按钮相同的弹窗）。
3. **Given** 创建分支弹窗已打开，**When** 用户填写名称并提交，**Then** 弹窗关闭，新分支出现在列表中。
4. **Given** 创建分支弹窗已打开，**When** 用户点击「取消」或按 Esc 或点击遮罩层关闭弹窗，**Then** URL 从 `/resume?new=true` 恢复到 `/resume`（`new=true` 参数被清除）。
5. **Given** 用户直接在地址栏访问 `/resume?new=true`，**When** 页面加载，**Then** 行为与场景 2 一致（弹窗自动弹出）。
6. **Given** 用户在 ResumeList 页面内手动点击「新建简历」按钮，**When** 弹窗打开，**Then** 此行为不受影响，URL 保持不变（不加 `?new=true`）。

---

### Edge Cases

- 用户快速连续点击顶栏按钮两次：路由跳转只发生一次（已在同一路径时不会重复跳转）。
- 在 `/resume?new=true` 页面刷新：弹窗重新弹出（因为 URL 参数保留）。
- 用户已经在 `/resume` 页面时点击顶栏按钮：触发路由跳转到 `/resume?new=true`，弹窗弹出。
- 创建弹窗处于 loading 状态时用户关闭弹窗：弹窗关闭，创建请求取消（React Query 自动处理）。

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Topbar「新建简历分支」MUST 调用 `navigate('/resume?new=true')`，而不是接收外部 onNewResume 回调。
- **FR-002**: System MUST 从 Topbar 移除 `onNewResume` prop，改为内部直接 `navigate('/resume?new=true')`。
- **FR-003**: ResumeList 页面 MUST 在加载时检查 URL 参数 `searchParams.get('new') === 'true'`，若匹配则自动将创建弹窗状态 `open` 置为 `true`。
- **FR-004**: System MUST 在创建弹窗关闭（取消 / Esc / 遮罩点击 / 提交成功）时清除 URL 中的 `new=true` 参数，使用 `navigate('/resume', { replace: true })` 避免历史栈污染。
- **FR-005**: ResumeList 页面内原有的「新建简历」按钮行为 MUST 保持不变（点击后设置 `open=true`，不清除 URL）。
- **FR-006**: System MUST 在 App.tsx 中移除 `<AppShell>` 的 `onNewResume` prop 传递（当前不存在传参，需要的是清理代码）。
- **FR-007**: 所有新交互 MUST 暴露 `data-testid` 供 E2E 验证：Topbar 按钮 `data-testid="topbar-new-resume"`（已有）。

### Key Entities *(include if feature involves data)*

该 feature 不涉及新数据实体，仅改变路由交互与弹窗触发逻辑。前端现有组件：
- **Topbar**: 顶栏组件，现有 `data-testid="topbar-new-resume"` 按钮
- **ResumeList**: 简历列表页，已有创建弹窗状态 `open`、表单字段 `name/company/position`
- **AppShell**: 布局壳组件，目前传递未定义的 `onNewResume` prop

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 用户在任意页面点击顶栏按钮后 2 秒内到达 `/resume` 页面且弹窗自动打开。
- **SC-002**: 弹窗关闭后 URL 中 `new=true` 参数被清除，刷新页面不再弹出弹窗。
- **SC-003**: 原有的页面内「新建简历」按钮行为不发生变化（点击后不修改 URL）。
- **SC-004**: 所有 `onNewResume` prop 相关代码从 Topbar 和 AppShell 中移除。

## Assumptions

- 前端使用 React Router v6，`useNavigate` 和 `useSearchParams` API 可用。
- ResumeList 已有完整的创建分支弹窗组件和表单逻辑。本 feature 不改动弹窗内部逻辑和表单验证。
- 关闭弹窗后清除 `new=true` 使用 `setSearchParams` 或 `navigate` 的 `replace` 模式，不触发额外页面重渲染。
- 该 feature 仅涉及前端改动，后端无变更。
