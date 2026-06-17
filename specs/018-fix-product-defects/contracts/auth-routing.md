# Contract: Auth Routing (`/login` vs `/register`)

**Spec refs**: FR-001 / FR-002 / SC-003
**Defect**: #1 `/register` 深链不能直接进入注册态
**Decision**: R-012

---

## 行为契约

### 路由层

```text
GET /login    → 渲染 <Login initialMode="login" />
GET /register → 渲染 <Register /> = <Login initialMode="register" />
```

- 未登录用户访问任一路径看到对应表单
- 已登录用户访问任一路径 → 跳转到 `/`（主页），不显示表单
- `Login` 组件需监听 `searchParams.get('mode')` 变化（覆盖到运行时动态切换）

### 组件层

```tsx
// src/pages/Register.tsx
import Login from './Login'
export default function Register() {
  return <Login initialMode="register" />
}

// src/pages/Login.tsx 行为
- 入口: initialMode prop（"login" | "register"）
- 监听: searchParams.get('mode') 变化时同步切换模式
- 渲染:
  - 模式 "login"    → 标题「欢迎回来」+ 单 password 字段 + 主按钮「登录」+ 链接「没有账号?去注册」
  - 模式 "register" → 标题「创建账号」+ password + confirmPassword + 协议勾选 + 主按钮「注册」+ 链接「已有账号?去登录」
- 切换: 在两个链接点击时不卸载组件（用 searchParams 触发 prop 变化）
```

### 已登录守卫

```text
未登录访问 /login 或 /register → 渲染对应表单
已登录访问 /login 或 /register → <Navigate to="/" replace /> （App.tsx:44 既有守卫）
```

---

## 测试契约

### E2E（`tests/e2e/018-fix-product-defects/auth/register-deep-link.spec.ts`）

```text
1. Given 未登录
   When 直接访问 http://localhost:5173/register
   Then 看到标题「创建账号」+ 「注册」按钮 + 「确认密码」字段 + 协议勾选框
   And 看到无 password 字段的「欢迎回来」文案

2. Given 未登录
   When 在 /login 页面点击「去注册」链接
   Then URL 变为 /register?mode=register
   And 表单切换为注册态（不卸载组件）

3. Given 已登录
   When 访问 /register
   Then 跳转到 / (主页)
```

### 组件测试（`src/pages/__tests__/Login.test.tsx`）

```text
- 渲染 initialMode="register" → 见到「创建账号」标题
- 渲染 initialMode="login" → 见到「欢迎回来」标题
- 模拟 searchParams 从 "mode=login" 切到 "mode=register" → 表单切换
```

---

## 验收对应

- FR-001 ✓ 路由层区分 `/login` 与 `/register`
- FR-002 ✓ 已登录态跳转
- SC-003 ✓ 100% 访问 `/register` 显示注册表单
