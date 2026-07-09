# Contract: Route Redirects

**Date**: 2026-06-30 | **Spec**: [spec.md](../spec.md) | **Plan**: [plan.md](../plan.md)

> Phase 1 — 路由重定向契约。

---

## Redirect Rules

| 源路径 | 目标路径 | Replace | 备注 |
|---|---|---|---|
| `/resume-v2` | `/resume` | ✅ | 旧 v2 列表 |
| `/resume-v2/new` | `/resume?new=true` | ✅ | 旧 v2 新建入口 |
| `/resume/v2/:id` | `/resume/:id` | ✅ | 旧 v2 编辑器（按 id 动态替换） |
| `/resume/:branchId` | **404 占位** | — | v1 分支编辑器已下线；不再重定向到 `/resume/:id`（避免误命中 v2 数据） |

## Implementation

**文件**：`src/App.tsx`

```tsx
import { Navigate, useParams } from 'react-router-dom'
import { ResumeEditorV2 } from '@/pages/ResumeEditorV2'
import { NotFound } from '@/components/NotFound'  // 或 fallback UI

// 1. 静态重定向
<Route path="/resume-v2" element={<Navigate to="/resume" replace />} />
<Route path="/resume-v2/new" element={<Navigate to="/resume?new=true" replace />} />
<Route path="/resume/v2/:id" element={<ResumeV2Redirect />} />

// 2. ResumeEditorV2 在 `/resume/:id` 路由；编辑器内部判断 v2 命中/未命中
<Route path="/resume/:id" element={<ResumeEditorV2 />} />

// 3. ResumeV2Redirect 解析 :id 后跳转
function ResumeV2Redirect() {
  const { id } = useParams<{ id: string }>()
  return <Navigate to={`/resume/${id}`} replace />
}
```

## V1 Branch Route Removal

`/resume/:branchId` 路由**完全删除**（不再挂任何元素）。理由：
- v1 数据已被清理脚本清空
- v1 编辑器页面 `ResumeEditor.tsx` 已删除
- 即便有遗留 v1 branchId 命中，渲染 404 占位比"打开 v1 旧编辑器"更安全

```tsx
// 删除这一行（之前存在）
// <Route path="/resume/:branchId" element={<ResumeEditor />} />

// 替换为：/resume/:id 独占编辑器路由
<Route path="/resume/:id" element={<ResumeEditorV2 />} />
```

## Why `:branchId` Is Removed (Not Redirected)

考虑到：
1. v1 分支表已被清空（行数 = 0）
2. UUIDv7 与 UUIDv4 命名空间不同；理论上有 0 概率 v2 id 撞 v1 branchId
3. 即便撞上，把 v1 旧编辑器强开是反用户期望的（用户明确"全面弃用 v1"）

→ 选择完全删除而非 redirect to `/resume/:id`。

## Testing Contract

**测试文件**：`tests/e2e/_fixtures/route-redirect.spec.ts`（共享 fixture）

| Case | Source URL | Expected Final URL | Expected Page |
|---|---|---|---|
| 1 | `/resume-v2` | `/resume` | ResumeList (空状态) |
| 2 | `/resume-v2/new` | `/resume?new=true` | ResumeList (新流程触发) |
| 3 | `/resume/v2/abc-123` | `/resume/abc-123` | ResumeEditorV2 (404 或编辑器，取决于 ID 是否存在) |
| 4 | `/resume/<random-uuid>` | `/resume/<random-uuid>` | ResumeEditorV2 (404 占位) |

每个 case MUST：
- 检查 `page.url()` 最终值
- 检查 `page` 渲染的根组件 testid

## Browser History

`replace: true` 保证：
- 用户从 `/resume-v2` 跳到 `/resume` 后，浏览器返回键直接回上一站（不是 `/resume-v2`）
- 防止 redirect loop（即使有 bug 也不会循环）

## References

- 036 spec FR-005~FR-008: 路由收口
- 036 research Decision 2: Navigate replace 实现
- react-router-dom v6 docs: https://reactrouter.com/en/main/components/navigate