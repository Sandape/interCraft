# Contract: Shell UX（路由警告 + 退出登录菜单）

**Spec refs**: FR-021 / FR-022 / SC-007 / SC-008
**Defects**: #14 React Router warnings / #13 退出登录菜单语义
**Decisions**: R-011 / R-010

---

## A. React Router v7 Future Flags（缺陷 #14 / FR-021）

### 路由配置契约

```tsx
// src/App.tsx
import { BrowserRouter } from 'react-router-dom'

<BrowserRouter
  future={{
    v7_startTransition: true,
    v7_relativeSplatPath: true,
    v7_fetcherPersist: true,
    v7_normalizeFormMethod: true,
    v7_partialHydration: true,
    v7_skipActionErrorRevalidation: true,
  }}
>
  <AppRoutes />
</BrowserRouter>
```

### 不变量

- `react-router-dom@6.27.0` 已支持所有 v7 future flag
- 行为差异：导航走 React 18 `startTransition`（与现有 StrictMode 兼容）
- 一次性 opt-in 消除 console 警告

### 行为差异笔记

| Flag | 行为变化 | 风险评估 |
|---|---|---|
| `v7_startTransition` | 导航走 startTransition，loading 状态更平滑 | 低（与 React 18 StrictMode 兼容） |
| `v7_relativeSplatPath` | `*` 路径相对路径解析 | 中（需要全应用巡检嵌套路由的相对路径） |
| `v7_fetcherPersist` | fetcher 状态在卸载后保留 | 低（form 提交场景影响小） |
| `v7_normalizeFormMethod` | form method 解析统一 | 低 |
| `v7_partialHydration` | 部分 hydrate | 低（Vite SPA 不涉及 SSR） |
| `v7_skipActionErrorRevalidation` | action 错误时不自动 revalidate | 低（业务可控 revalidate） |

---

## B. 退出登录菜单语义（缺陷 #13 / FR-022）

### 行为契约

```text
Topbar 菜单结构（src/components/layout/Topbar.tsx）:
  - 个人资料     (nav, 常规)
  - 设置         (nav, 常规)
  - 数据导出     (action, 常规)
  ─────────────  (separator)
  - 退出登录     (button, 常规色)   ← 从 danger 区移出
  ─────────────  (separator)
  - 注销账号     (button, danger 色)  ← 保留在 danger 区
```

### 组件契约

```tsx
// src/components/layout/Topbar.tsx
<Menu>
  <MenuItem onSelect={goToProfile}>个人资料</MenuItem>
  <MenuItem onSelect={goToSettings}>设置</MenuItem>
  <MenuItem onSelect={exportData}>数据导出</MenuItem>
  <MenuSeparator />
  <MenuItem
    role="button"
    name="退出登录"   // a11y name
    onSelect={logout}
  >退出登录</MenuItem>
  <MenuSeparator />
  <MenuItem
    role="button"
    name="注销账号"
    intent="danger"
    onSelect={deleteAccount}
  >注销账号</MenuItem>
</Menu>
```

### 颜色与可访问性

- 「退出登录」用中性色（与「数据导出」同区）
- 「注销账号」保留 danger 色（红色），需二次确认对话框
- 两者用 separator 视觉分组，a11y 树清晰

### 不变量

- 两个动作 API 路径不变（POST /auth/logout vs DELETE /users/me）
- 仅改 UI 分组与文案
- a11y tree：`getByRole('button', { name: '退出登录' })` 必须命中

---

## 测试契约

### E2E（`e2e/shell/router-future-flags.spec.ts`）

```text
- 加载 / 切换路由 → console 不出现以下警告：
  - "React Router Future Flag Warning: v7_startTransition"
  - "React Router Future Flag Warning: v7_relativeSplatPath"
  - "React Router Future Flag Warning: v7_fetcherPersist"
  - "React Router Future Flag Warning: v7_normalizeFormMethod"
  - "React Router Future Flag Warning: v7_partialHydration"
  - "React Router Future Flag Warning: v7_skipActionErrorRevalidation"
```

### E2E（`e2e/auth/logout-menu-semantics.spec.ts`）

```text
- 打开个人菜单 → 用 page.getByRole('button', { name: '退出登录' }) 命中
- 点击 → 跳转到 /login
- 「注销账号」保留 danger 色（不与「退出登录」混色）
```

### 单元（`src/components/layout/__tests__/Topbar.test.tsx`）

```text
- 菜单渲染时 "退出登录" 与 "注销账号" 不在同一危险色区
- 两者之间有 separator
- 键盘 Tab 可达两项
```

---

## 验收对应

- FR-021 ✓ 路由 future flag 全 opt-in
- FR-022 ✓ 退出登录有 button role + name
- SC-007 ✓ 100% 页面无 future flag warning
- SC-008 ✓ 100% 可被 getByRole 定位
