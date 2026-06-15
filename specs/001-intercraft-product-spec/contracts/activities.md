# Activities Endpoints (M10 activities)

> 统一活动流(append-only,90 天物理删除,M10 §6 + §8 决议)。
> 游标分页(DEC-P2-1,base64url JSON)。
> 数据模型见 [../data-model-phase-2.md](../data-model-phase-2.md) §6。

## 共享类型

```ts
type Activity = {
  id: string;                           // uuid v7
  type: ActivityType;
  actor_type: "user" | "system" | "agent";
  payload: { [key: string]: any };      // 类型相关
  request_id: string | null;
  occurred_at: string;
}

type ActivityType =
  | "task_created"
  | "task_completed"
  | "job_created"
  | "job_status_changed"
  | "interview_started"
  | "interview_completed"
  | "branch_created"
  | "error_logged"
  | "manual"

type CursorPage<T> = {
  data: T[];
  pagination: {
    next_cursor: string | null;         // opaque base64
    has_more: boolean;
  }
}
```

**payload schema 约定**(按 type 区分):

| `type` | payload schema |
|---|---|
| `task_created` | `{task_id, task_type, title}` |
| `task_completed` | `{task_id, task_type, title, completed_at}` |
| `job_created` | `{job_id, company, position, status}` |
| `job_status_changed` | `{job_id, company, position, from_status, to_status, at}` |
| `interview_started` | `{session_id, position, company, mode}` (Phase 4) |
| `interview_completed` | `{session_id, position, company, overall_score}` (Phase 4) |
| `branch_created` | `{branch_id, name, parent_id, is_main}` |
| `error_logged` | `{error_question_id, dimension, score, action?}` (`action='reset'` 标识重置) |
| `manual` | 自由 JSON |

---

## 1. `GET /api/v1/activities`

**用途**:列出当前用户的活动流(游标分页,forward-only,DESC 排序)。

**Auth**:Bearer access

**查询参数**:
| 参数 | 类型 | 默认 | 说明 |
|---|---|---|---|
| `type` | enum | - | 单类型过滤(见上) |
| `actor_type` | enum | - | user / system / agent |
| `from` | datetime | - | 起始时间(ISO 8601) |
| `to` | datetime | - | 结束时间 |
| `cursor` | string | - | 游标(首次不传) |
| `limit` | int 1-50 | 20 | 分页大小 |

**响应 200**:`CursorPage<Activity>`

**游标格式**(DEC-P2-1):
```
cursor = base64url(JSON.stringify({"ts": "2026-06-13T10:30:00Z", "id": "01HXX..."}))
```

**响应示例**:
```json
{
  "data": [
    {
      "id": "01HXX...",
      "type": "job_status_changed",
      "actor_type": "user",
      "payload": {
        "job_id": "01HWX...",
        "company": "字节跳动",
        "position": "高级前端工程师",
        "from_status": "applied",
        "to_status": "test"
      },
      "request_id": "01HXZ...",
      "occurred_at": "2026-06-13T10:30:00.123Z"
    }
  ],
  "pagination": {
    "next_cursor": "eyJ0cyI6IjIwMjYtMDYtMTNUMTA6MzA6MDAuMTIzWiIsImlkIjoiMDFIWFguLi4ifQ",
    "has_more": true
  }
}
```

**排序规则**:`occurred_at DESC, id DESC`(新到旧)

**索引**:`(user_id, occurred_at DESC, id DESC)` 复合索引,游标扫描 P95 ≤ 50ms

---

## 2. 内部 API(非公开)

### `POST /internal/activities/log`

**Auth**:Internal(middleware 校验 source IP)

**请求体**:
```json
{
  "user_id": "uuid",
  "type": "task_created",
  "actor_type": "system",
  "payload": { /* ... */ },
  "request_id": "uuid"
}
```

**响应 201**:`Activity`

**用途**:Service 内部调用(JobService 状态变更、TaskService 创建、ErrorService 写错题等)。

**Phase 2 触发点**:
- `errors.service.create()` → `error_logged`
- `tasks.service.create()` → `task_created`
- `tasks.service.update_status(done)` → `task_completed`
- `jobs.service.create()` → `job_created`
- `jobs.service.update_status()` → `job_status_changed`
- `resumes.service.create_branch()` (Phase 1 已有) → `branch_created`

---

## 错误码

| 状态码 | 触发场景 |
|---|---|
| 400 | 游标格式错误(返回 400 而非 500,让前端 retry-without-cursor) |
| 401 | JWT 缺失/过期 |
| 403 | RLS 拒绝 |
| 422 | `type` 不在白名单 |
| 429 | 速率限制 |
| 500 | 服务端异常 |

---

## 保留期

- `activities` 保留 90 天,ARQ cron `0 3 * * *`(每日 03:00 UTC)物理删除 `occurred_at < now() - interval '90 days'`
- M10 §6 决议(v0.3 修订):无冷库归档,直接物理删
- 删除走 ARQ,不分批(10000 行/用户 × 1000 用户 = 1000 万行,单 DELETE 即可)
- 结构化日志 `activities.purged` 记录删除行数

---

## 游标分页实现细节

### 后端(`app/core/pagination.py`)

```python
import base64, json
from datetime import datetime
from uuid import UUID

def encode_cursor(occurred_at: datetime, id: UUID) -> str:
    payload = json.dumps(
        {"ts": occurred_at.isoformat(), "id": str(id)},
        separators=(",", ":")
    ).encode("utf-8")
    return base64.urlsafe_b64encode(payload).decode("ascii").rstrip("=")

def decode_cursor(opaque: str) -> tuple[datetime, UUID]:
    pad = "=" * (-len(opaque) % 4)
    payload = json.loads(base64.urlsafe_b64decode(opaque + pad).decode("utf-8"))
    return datetime.fromisoformat(payload["ts"]), UUID(payload["id"])
```

### 查询 SQL(模板)

```sql
-- 首页
SELECT id, type, actor_type, payload_json, request_id, occurred_at
FROM activities
WHERE user_id = :u
ORDER BY occurred_at DESC, id DESC
LIMIT :limit + 1;  -- 多取 1 条判断 has_more

-- 翻页
SELECT id, type, actor_type, payload_json, request_id, occurred_at
FROM activities
WHERE user_id = :u
  AND (occurred_at, id) < (:cursor_ts, :cursor_id)
ORDER BY occurred_at DESC, id DESC
LIMIT :limit + 1;
```

### 前端(`src/lib/cursor.ts`)

```typescript
export function encodeCursor(ts: string, id: string): string {
  return btoa(JSON.stringify({ ts, id }))
    .replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
}

export function decodeCursor(opaque: string): { ts: string; id: string } {
  const pad = '='.repeat((4 - opaque.length % 4) % 4);
  return JSON.parse(atob(opaque.replace(/-/g, '+').replace(/_/g, '/') + pad));
}
```

**跨端 parity test**:`tests/integration/test_cursor_parity.py` + `src/lib/__tests__/cursor.test.ts` 互验。
