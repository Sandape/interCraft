# Jobs Endpoints (M10 jobs)

> 求职追踪 — 公司/岗位/状态/关联简历分支/状态时间线。
> 状态变更自动触发任务(澄清 Q2 决议 2026-06-13 + DEC-P2-6)。
> 数据模型见 [../data-model-phase-2.md](../data-model-phase-2.md) §7。

## 共享类型

```ts
type Job = {
  id: string;                           // uuid v7
  company: string;                      // 1-100 字符
  position: string;                     // 1-100 字符
  jd_url: string | null;                // https?://
  branch_id: string | null;             // 关联 resume_branches.id
  status: JobStatus;
  status_history: StatusChange[];       // append-only 时间线
  last_status_changed_at: string;
  notes_md: string | null;
  created_at: string;
  updated_at: string;
}

type JobStatus =
  | "applied"
  | "test"
  | "oa"
  | "hr"
  | "offer"
  | "rejected"
  | "withdrawn"

type StatusChange = {
  from: JobStatus | null;               // null 表示创建初始状态
  to: JobStatus;
  at: string;                           // ISO 8601
  note: string;                         // 1-500 字符
}

type CreateJobInput = {
  company: string;                      // 1-100
  position: string;                     // 1-100
  jd_url?: string | null;
  branch_id?: string | null;
  notes_md?: string | null;
}

type PatchJobInput = {
  company?: string;
  position?: string;
  jd_url?: string | null;
  branch_id?: string | null;
  notes_md?: string | null;
}

type UpdateJobStatusInput = {
  to: JobStatus;
  note?: string;                        // 1-500,默认 ""
}
```

---

## 1. `GET /api/v1/jobs`

**用途**:列出当前用户的投递记录(漏斗 + 时间线)。

**Auth**:Bearer access

**查询参数**:
| 参数 | 类型 | 默认 | 说明 |
|---|---|---|---|
| `status` | enum | - | 单状态过滤 |
| `branch_id` | uuid | - | 按简历分支过滤 |
| `cursor` | string | - | 游标分页 |
| `limit` | int 1-50 | 20 | 分页大小 |
| `order_by` | enum | `-last_status_changed_at` | 排序:`-last_status_changed_at` / `-created_at` / `company` |

**响应 200**:
```json
{
  "data": [ /* Job[] */ ],
  "pagination": { "next_cursor": "...", "has_more": true }
}
```

**排序规则**:`status ASC(applied/test/oa/hr/offer 在前,rejected/withdrawn 末尾), last_status_changed_at DESC`

---

## 2. `POST /api/v1/jobs`

**用途**:创建投递记录。

**Auth**:Bearer access

**请求体**:`CreateJobInput`

**校验**:
- `company` 长度 1-100
- `position` 长度 1-100
- `jd_url` 匹配 `^https?://` 或 null
- `branch_id` 存在(若非 null)

**响应 201**:完整 `Job`(status='applied')

**副作用**(DEC-P2-6):
- `status_history` 初始化:`[{from: null, to: "applied", at: now, note: ""}]`
- `TaskService.find_or_create(user_id, 'interview_prep', job.id, "准备 {company} · {position} 面试")`
- 写 `activities` 表 `type='job_created'`
- 结构化日志 `job.created` + `task.duplicate_skipped|created`

---

## 3. `GET /api/v1/jobs/{id}`

**用途**:获取单条投递详情。

**Auth**:Bearer access

**响应 200**:完整 `Job`

**响应 404**:不存在或 RLS 隔离

---

## 4. `PATCH /api/v1/jobs/{id}`

**用途**:更新投递基本信息(company / position / jd_url / branch_id / notes_md)。

**Auth**:Bearer access

**请求体**:`PatchJobInput`

**校验**:
- 不可改 `status`(用 PATCH /jobs/{id}/status)
- 不可改 `status_history`(append-only,系统管)
- 不可改 `last_status_changed_at`

**响应 200**:更新后的 `Job`

---

## 5. `PATCH /api/v1/jobs/{id}/status`

**用途**:推进状态(applied → test → oa → hr → offer;或 → rejected/withdrawn)。

**Auth**:Bearer access

**请求体**:`UpdateJobStatusInput`

**校验**(DEC-P2-6 状态机):
- 合法转换矩阵见 [data-model-phase-2.md §7](../data-model-phase-2.md) 状态机
- 非法转换返回 409 Conflict `{error: {code: "invalid_status_transition", ...}}`
- 终态(`rejected` / `withdrawn`)不可再转换
- `note` 长度 0-500

**响应 200**:更新后的 `Job`

**副作用**(DEC-P2-6):
- `status_history` push: `{from: old, to: new, at: now, note}`
- `last_status_changed_at = now()`
- 推进路径(`applied → test/oa/hr/offer`):更新对应 `interview_prep` 任务的 `title`(`"准备 {company} · {position} 面试 · {new_status_cn}"`)+ 写 `activities` 表 `type='task_completed' | manual` 简化版
- 终态路径(`→ rejected/withdrawn`):若存在 `interview_prep` 任务,置 `status='archived'`
- 写 `activities` 表 `type='job_status_changed', payload={job_id, company, position, from_status, to_status, at}`
- 结构化日志 `job.status_changed` + `task.title_updated` 或 `task.archived`

**响应 409 示例**:
```json
{
  "error": {
    "code": "invalid_status_transition",
    "message": "Cannot transition from 'rejected' to 'applied'.",
    "details": { "from": "rejected", "to": "applied" }
  }
}
```

---

## 6. `DELETE /api/v1/jobs/{id}`

**用途**:软删除(撤回整条投递)。

**Auth**:Bearer access

**响应 204**

**副作用**:
- 写 `deleted_at = now()`
- 若存在 `interview_prep` 任务,置 `status='archived'`(DEC-P2-6)
- Repository 默认过滤
- 结构化日志 `job.soft_deleted`

---

## 7. `GET /api/v1/jobs/stats`

**用途**:漏斗统计(供 Phase 5 Dashboard 切真实时消费)。

**Auth**:Bearer access

**响应 200**:
```json
{
  "counts": {
    "applied": 5,
    "test": 2,
    "oa": 1,
    "hr": 1,
    "offer": 0,
    "rejected": 3,
    "withdrawn": 1
  },
  "total": 13
}
```

**Phase 2 范围**:
- 端点开放,Phase 2 Dashboard 仍读 mock
- Phase 5 Dashboard 切真实时,直接消费此端点

**实现**:`SELECT status, COUNT(*) FROM jobs WHERE user_id=:u AND deleted_at IS NULL GROUP BY status`,O(N) 全表扫描,可接受(每用户 ≤ 50)。

---

## 8. `GET /api/v1/jobs/{id}/timeline`

**用途**:返回 `status_history` + 关联 activities 合并的时间线(Phase 2 简化版可只返回 status_history)。

**Auth**:Bearer access

**响应 200**:
```json
{
  "job_id": "uuid",
  "status_history": [
    { "from": null, "to": "applied", "at": "2026-06-10T...", "note": "" },
    { "from": "applied", "to": "test", "at": "2026-06-12T...", "note": "HR 通知笔试" }
  ]
}
```

**Phase 5 扩展**:合并 activities 列表(MVP 阶段前端本地 concat)。

---

## 错误码

| 状态码 | 触发场景 |
|---|---|
| 400 | 字段类型错误 |
| 401 | JWT 缺失/过期 |
| 403 | RLS 拒绝 |
| 404 | Job 不存在或已删 |
| 409 | 状态机非法转换 |
| 422 | 字段值越界(URL 格式、长度) |
| 429 | 速率限制 |
| 500 | 服务端异常 |

---

## 状态机合法转换矩阵(完整)

| from \ to | applied | test | oa | hr | offer | rejected | withdrawn |
|---|---|---|---|---|---|---|---|
| **applied** | ❌ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| **test** | ❌ | ❌ | ✅ | ✅ | ✅ | ✅ | ✅ |
| **oa** | ❌ | ❌ | ❌ | ✅ | ✅ | ✅ | ✅ |
| **hr** | ❌ | ❌ | ❌ | ❌ | ✅ | ✅ | ✅ |
| **offer** | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ | ✅ |
| **rejected** | ❌(终态)| ❌(终态)| ❌(终态)| ❌(终态)| ❌(终态)| ❌(终态)| ❌(终态)|
| **withdrawn** | ❌(终态)| ❌(终态)| ❌(终态)| ❌(终态)| ❌(终态)| ❌(终态)| ❌(终态)|

`❌` 表示非法,返回 409。
