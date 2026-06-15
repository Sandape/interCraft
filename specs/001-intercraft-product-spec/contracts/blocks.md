# Resume Blocks Endpoints (M06)

> Notion 式块的 CRUD + 拖拽排序。`order_index` 使用字符串分数(fractional-indexing,DEC-3)。

## 共享类型

```ts
type ResumeBlock = {
  id: string;                       // uuid v7
  branch_id: string;
  type: "heading" | "summary" | "experience" | "project" | "skill" | "education" | "custom";
  title: string | null;
  content_md: string;               // Markdown 原文
  content_html: string | null;      // 派生缓存,Phase 1 始终 null
  meta: Record<string, any> | null; // 类型相关扩展
  order_index: string;              // 字符串分数,如 "a0", "a1", "a0V"
  collapsed: boolean;
  created_at: string;
  updated_at: string;
}

type CreateBlockInput = {
  type: "heading" | "summary" | "experience" | "project" | "skill" | "education" | "custom";
  title?: string;
  content_md?: string;              // 默认 ""
  meta?: Record<string, any>;
  // order_index: 不接受,由后端自动算
}

type PatchBlockInput = {
  type?: "heading" | "summary" | "experience" | "project" | "skill" | "education" | "custom";
  title?: string;
  content_md?: string;
  meta?: Record<string, any>;
  collapsed?: boolean;
  // order_index 不可改,只能通过 /reorder
}

type ReorderBlocksInput = {
  block_id: string;                 // 移动的块
  prev_id: string | null;           // 目标位置前一个块(null = 移到最前)
  next_id: string | null;           // 目标位置后一个块(null = 移到最后)
}
```

---

## 1. `GET /api/v1/resume-branches/{branch_id}/blocks`

**用途**:列出某分支所有 active 块,按 `order_index` 升序。

**Auth**:Bearer access

**查询参数**:
| 参数 | 类型 | 默认 | 说明 |
|---|---|---|---|
| `type` | enum | - | 过滤类型 |
| `cursor` | string | - | 游标分页(基于 order_index) |
| `limit` | int 1-100 | 50 | 块通常不多,默认 50 |

**响应 200**:
```json
{
  "data": [ /* ResumeBlock[] */ ],
  "pagination": {
    "next_cursor": "opaque_or_null",
    "has_more": false
  }
}
```

**错误**:
| 状态 | code | 触发 |
|---|---|---|
| 401 | `auth.token_*` | 未登录 |
| 404 | `resume.not_found` | branch 不存在 |

---

## 2. `POST /api/v1/resume-branches/{branch_id}/blocks`

**用途**:新建块。`order_index` 由后端自动算(追加到末尾)。

**Auth**:Bearer access

**请求**:
```json
{
  "type": "experience",
  "title": "高级前端工程师 · 字节跳动",
  "content_md": "## 2022.06 - Present\n负责抖音创作者平台...",
  "meta": {
    "company": "字节跳动",
    "role": "高级前端工程师",
    "start": "2022-06",
    "end": "present",
    "tags": ["React", "TypeScript"]
  }
}
```

**逻辑**:
1. 校验 branch 存在且属当前 user
2. 计算新 `order_index`:取当前最大 `order_index` + 1(后端用 `python-fractional-indexing.generate_key_between`)
3. 插入

**响应 201**:
```json
{
  "block": { /* ResumeBlock */ }
}
```

**副作用**:
- 更新 `resume_branches.last_edited_at = now()`
- 不创建版本快照(增量修改由 M07 在「手动保存版本」时汇总)

**错误**:
| 状态 | code | 触发 |
|---|---|---|
| 401 | `auth.token_*` | 未登录 |
| 404 | `resume.not_found` | branch 不存在 |
| 422 | `validation.*` | 字段错 |

---

## 3. `GET /api/v1/resume-blocks/{block_id}` *(Phase 1 可选,主要走 list)*

**用途**:取单块。

**Auth**:Bearer access

**响应 200**:
```json
{
  "block": { /* ResumeBlock */ }
}
```

---

## 4. `PATCH /api/v1/resume-blocks/{block_id}`

**用途**:部分更新块(内容 / 折叠状态)。

**Auth**:Bearer access

**请求**:
```json
{
  "content_md": "## 2022.06 - Present\n更新后的内容...",
  "collapsed": true
}
```

**响应 200**:
```json
{
  "block": { /* 更新后的 ResumeBlock */ }
}
```

**副作用**:
- 更新 `resume_blocks.updated_at`
- 更新 `resume_branches.last_edited_at`(通过 trigger 或应用层)
- **不**创建版本快照
- **不**做悲观锁校验**(Phase 1 不引入 M12,后写覆盖)**

**错误**:
| 状态 | code | 触发 |
|---|---|---|
| 401 | `auth.token_*` | 未登录 |
| 404 | `block.not_found` | 不存在 |
| 422 | `validation.*` | 字段错 |

---

## 5. `PATCH /api/v1/resume-blocks/{block_id}/reorder`

**用途**:拖拽排序。后端用 `python-fractional-indexing` 计算新 `order_index`。

**Auth**:Bearer access

**请求**:
```json
{
  "block_id": "uuid-of-block-to-move",
  "prev_id": "uuid-of-prev-block-or-null",
  "next_id": "uuid-of-next-block-or-null"
}
```

**逻辑**:
1. 取 prev / next 块的实际 `order_index`
2. `new_order_index = generate_key_between(prev.order_index, next.order_index)`
3. 更新目标 block

**响应 200**:
```json
{
  "block": { /* 更新后的 ResumeBlock,order_index 已变 */ }
}
```

**边界 case**:
- `prev_id = null, next_id = null` → 把块移到末尾(`new = generate_key_between(last_index, None)`)
- `prev_id = null, next_id = X` → 移到最前(`new = generate_key_between(None, X.order_index)`)
- `prev_id = X, next_id = null` → 移到 X 之后
- `prev_id = next_id` → 400(同位置无意义)
- 块之间已经有 `prev_id` 或 `next_id` 不在同分支 → 404

**错误**:
| 状态 | code | 触发 |
|---|---|---|
| 401 | `auth.token_*` | 未登录 |
| 404 | `block.not_found` | 任一 id 不存在 |
| 400 | `validation.range` | prev_id === next_id |

---

## 6. `DELETE /api/v1/resume-blocks/{block_id}`

**用途**:软删除块。

**Auth**:Bearer access

**响应 204**:No Content

**副作用**:
- `resume_blocks.deleted_at = now()`
- 后续 GET 列表不再返回
- `last_edited_at` 更新
- **不**做物理删除(M20 30 天后清理)

**错误**:
| 状态 | code | 触发 |
|---|---|---|
| 401 | `auth.token_*` | 未登录 |
| 404 | `block.not_found` | 不存在 |

---

## 7. 字符串分数算法(plan DEC-3)

**后端**:`python-fractional-indexing` 提供:
- `generate_key_between(a, b)`:在 a、b 之间生成新 key(任一可 None)
- `generate_n_keys_between(a, b, n)`:生成 n 个 key

**前端**:`fractional-indexing` 同名包 + 同算法。

**parity 测试**:`backend/tests/integration/test_jsonpatch_parity.py` 跑同一组 fixture(a, b, 期望值),先后端再前端,值必须一致。

**边界**:
- 分数耗尽(`order_index` 长度接近 64)→ 触发一次「整列重写」(background job,Phase 2 实现);Phase 1 仅 `CHECK (length(order_index) < 64)` 兜底
