# Resume Branches Endpoints (M06)

> 简历分支 CRUD + 树形结构 + 写时复制(COW,Phase 1 简化为「克隆全部父块」)。
> 块(blocks)见 [blocks.md](./blocks.md);版本(versions)见 [versions.md](./versions.md)。

## 共享类型

```ts
type ResumeBranch = {
  id: string;                       // uuid v7
  parent_id: string | null;
  name: string;
  company: string | null;
  position: string | null;
  status: "draft" | "optimizing" | "ready" | "submitted" | "archived";
  match_score: number | null;       // 0.00-100.00
  is_main: boolean;
  is_pinned: boolean;
  last_edited_at: string;
  created_at: string;
  updated_at: string;
  // Phase 1 聚合字段(由后端 join 计算,不存表)
  version_count: number;
  block_count: number;
}

type CreateBranchInput = {
  name: string;
  company?: string;
  position?: string;
  parent_id?: string;               // 指定则浅拷贝;不指定则创建空分支
  is_main?: boolean;                // 只能创建时设一次,后续 PATCH 不可改
}

type PatchBranchInput = {
  name?: string;
  company?: string;
  position?: string;
  status?: "draft" | "optimizing" | "ready" | "submitted" | "archived";
  is_pinned?: boolean;
  // match_score: Phase 1 不可改(AI 评估写入,Phase 5)
  // parent_id / is_main: 不可改
}
```

---

## 1. `GET /api/v1/resume-branches`

**用途**:列出当前用户所有 active 分支。

**Auth**:Bearer access

**查询参数**:
| 参数 | 类型 | 默认 | 说明 |
|---|---|---|---|
| `is_main` | bool | - | 过滤主简历 |
| `is_pinned` | bool | - | 过滤置顶 |
| `status` | enum | - | 过滤状态 |
| `cursor` | string | - | 游标分页 |
| `limit` | int 1-100 | 20 | 分页大小 |
| `order_by` | enum | `-last_edited_at` | 排序白名单:`-last_edited_at` / `-created_at` / `name` |

**响应 200**:
```json
{
  "data": [ /* ResumeBranch[] */ ],
  "pagination": {
    "next_cursor": "opaque_or_null",
    "has_more": true
  }
}
```

**排序规则**:`is_pinned DESC, is_main DESC, last_edited_at DESC`(UI 默认排序)。

---

## 2. `POST /api/v1/resume-branches`

**用途**:创建新分支。

**Auth**:Bearer access

**请求**:
```json
{
  "name": "字节跳动 · 高级前端",
  "company": "字节跳动",
  "position": "高级前端工程师",
  "parent_id": "<core-branch-uuid>"
}
```

**逻辑**:
- 若指定 `parent_id`:
  1. 校验 `parent_id` 存在且属当前 user(RLS 兜底)
  2. 复制父分支的**所有** blocks 到新分支(Phase 1 简化:全克隆;Phase 2 优化为真 COW)
  3. 新分支 `parent_id = parent_id`
- 若不指定:
  1. 创建空分支(blocks = [])
  2. 若 `is_main=true`,自动撤销当前 user 其他 `is_main=true` 的分支(应用层事务保证唯一性)

**响应 201**:
```json
{
  "branch": { /* ResumeBranch */ }
}
```

**副作用**:
- 创建 `resume_branches` 记录
- 若带 `parent_id`,批量 `INSERT INTO resume_blocks` 复制所有父块(`user_id` 设为当前 user)
- 创建首个「初始化版本」:`is_full_snapshot=true, trigger=manual, label="初始化"`(在 versions 表)

**错误**:
| 状态 | code | 触发 |
|---|---|---|
| 401 | `auth.token_*` | 未登录 |
| 404 | `resume.not_found` | `parent_id` 不存在 |
| 422 | `resume.invalid_status` | status 非法值 |

---

## 3. `GET /api/v1/resume-branches/{branch_id}`

**用途**:取单分支详情。

**Auth**:Bearer access

**响应 200**:
```json
{
  "branch": { /* ResumeBranch */ }
}
```

**错误**:
| 状态 | code | 触发 |
|---|---|---|
| 401 | `auth.token_*` | 未登录 |
| 404 | `resume.not_found` | 不存在 / 已软删 / 跨 user |

---

## 4. `PATCH /api/v1/resume-branches/{branch_id}`

**用途**:部分更新分支。**不可**改 `parent_id` / `is_main`。

**Auth**:Bearer access

**请求**:
```json
{
  "name": "字节跳动 · 高级前端 v2",
  "status": "ready",
  "is_pinned": true
}
```

**响应 200**:
```json
{
  "branch": { /* 更新后的 ResumeBranch */ }
}
```

**副作用**:
- 更新 `updated_at` / `last_edited_at`
- 若 `status` 从非 `submitted` 变 `submitted`:触发 M10 的 `create_interview_prep_task`(Phase 1 **仅发事件,不入 tasks 表**,tasks 表 Phase 2 启用)
- Phase 1 实现:`logger.info("task.trigger.interview_prep", branch_id=..., user_id=...)` + 在 `outbox_events` Phase 2 表占位

**错误**:
| 状态 | code | 触发 |
|---|---|---|
| 401 | `auth.token_*` | 未登录 |
| 404 | `resume.not_found` | 不存在 |
| 422 | `validation.*` / `resume.invalid_status` | 字段错 |

---

## 5. `DELETE /api/v1/resume-branches/{branch_id}`

**用途**:软删除分支。

**Auth**:Bearer access

**响应 204**:No Content

**副作用**:
- `resume_branches.deleted_at = now()`
- **级联软删**(应用层,无 DB 外键):所有 `resume_blocks` / `resume_versions` 标记 `deleted_at`
- 后续 `GET /resume-branches` 不再返回此分支
- **Phase 1 物理行为**:不立刻物理删除,30 天后由 M20 lifecycle job 物理清除(Phase 6)

**错误**:
| 状态 | code | 触发 |
|---|---|---|
| 401 | `auth.token_*` | 未登录 |
| 404 | `resume.not_found` | 不存在 |
| 422 | `resume.cannot_delete_main` | 试图删主简历(阻止意外) |

**主简历保护**:若 `is_main=true` 且 user 无其他分支 → 返回 422 + `resume.cannot_delete_main`。需先创建新分支再删主。

---

## 6. `POST /api/v1/resume-branches/{branch_id}/refresh-from-parent`

**用途**:从父分支重新拉取最新内容(覆盖当前 blocks)。

**Auth**:Bearer access

**请求**:无 body

**逻辑**:
1. 取当前分支:必须有 `parent_id`
2. 取父分支最新版本的 snapshot(完整或 diff 还原)
3. 删除当前分支所有 blocks(soft delete)
4. 复制父分支 blocks 到当前分支
5. 创建新版本:`trigger=manual, label="从父分支刷新: {parent_name}"`

**响应 200**:
```json
{
  "branch": { /* 更新后的 ResumeBranch */ },
  "new_version_no": 5
}
```

**错误**:
| 状态 | code | 触发 |
|---|---|---|
| 401 | `auth.token_*` | 未登录 |
| 404 | `resume.not_found` | 当前或父不存在 |
| 422 | `resume.no_parent` | 当前分支无 parent_id |

**Phase 1 简化**:`refresh-from-parent` 走 Phase 1 简化版逻辑(全克隆父 blocks,不管父是否最新版本)。Phase 2 接入 M07 版本还原逻辑后,才按父分支**最新版本**还原。

---

## 7. 「初始化主简历」约定

**用户首次注册**:**不**自动创建主简历(避免用户没准备好时被强制编辑)。前端在 `GET /resume-branches?is_main=true` 返回空时,提示「创建第一份简历」,UI 引导用户:
1. 填写核心信息(姓名 / 邮箱 / 求职目标)
2. 调用 `POST /resume-branches` 传 `{ is_main: true, name: "核心简历" }`(无 parent_id)
3. 创建后跳转 `/resume/{id}` 编辑器

**Phase 1 不做引导脚本**,前端用空状态 UI 处理。
