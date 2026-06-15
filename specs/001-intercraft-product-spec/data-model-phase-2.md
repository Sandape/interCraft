# Data Model: InterCraft Phase 2

**Status**: Phase 2 output · **Date**: 2026-06-13 · **Spec**: [spec.md](./spec.md) | **Phase 1 Data Model**: [data-model.md](./data-model.md) | **Phase 2 Research**: [research-phase-2.md](./research-phase-2.md) | **Phase 2 Plan**: [phase-2.md](./phase-2.md)

> 本文档定义 Phase 2 涉及的**全部新增数据库实体**、SQLAlchemy 模型骨架、字段约束、关系、索引,以及与 `src/data/mockData.ts` 的字段映射。
> 全部业务表统一通过 Mixin 注入 `id / user_id / created_at / updated_at / deleted_at`(spec A13 修订,Phase 1 §0 决议)。
> 全部业务表启用 PostgreSQL RLS,策略统一为 `USING (user_id = current_setting('app.user_id', true)::uuid)`(spec FR-004)。
> 全部 7 张新表在单次 Alembic 迁移 `0002_phase2_entities.py` 中创建。

---

## 0. 新增 / 复用 Mixin

Phase 1 Mixin 全部复用(见 data-model.md §0):
- `UUIDv7PrimaryKeyMixin` — uuidv7 主键
- `TimestampedMixin` — `created_at` / `updated_at`
- `SoftDeletableMixin` — `deleted_at`(软删除)
- `TenantScopedMixin` — `user_id` + RLS

Phase 2 无新增 Mixin;7 张表都基于以上 4 个 Mixin 组合。

**Phase 2 业务表 Mixin 组合**:

| 表 | PrimaryKey | Timestamped | SoftDeletable | TenantScoped |
|---|---|---|---|---|
| `error_questions` | ✅ | ✅ | ✅ | ✅ |
| `ability_dimensions` | ✅ | ✅ | ❌(归档走 status) | ✅ |
| `ability_dimensions_history` | ✅(append-only)| ✅ | ❌(永不复用)| ✅ |
| `tasks` | ✅ | ✅ | ✅ | ✅ |
| `activities` | ✅ | ❌(append-only)| ❌(永不复用)| ✅ |
| `jobs` | ✅ | ✅ | ✅ | ✅ |
| `interview_sessions` | ✅ | ✅ | ✅ | ✅ |

`ability_dimensions_history` / `activities` 是 append-only(M09 + M10 决议),无 `updated_at` / `deleted_at`。

---

## 1. 实体清单(Phase 2 增量)

| # | 表名 | 实体 | 文档 | 落地阶段 |
|---|---|---|---|---|
| E-7 | `error_questions` | ErrorQuestion | spec §3.2 / M08 §4 | Phase 2 |
| E-8 | `ability_dimensions` | AbilityDimension | spec §3.2 / M09 §4 | Phase 2 |
| E-9 | `ability_dimensions_history` | AbilityDimensionHistory | spec §3.2 / M09 §4 | Phase 2 |
| E-10 | `tasks` | Task | spec §3.2 / M10 §4 | Phase 2 |
| E-11 | `activities` | Activity | spec §3.2 / M10 §4 | Phase 2 |
| E-12 | `jobs` | Job | spec §3.2 / M10 §4 | Phase 2 |
| E-13 | `interview_sessions` | InterviewSession | spec §3.2 / M11 §4 | Phase 2(只读骨架)|

**Phase 1 表(M01-M07)继续沿用**,无字段变更。Phase 1 已就位的 `users.monthly_token_*` 字段在 Phase 2 才正式被 ARQ cron 重置。

---

## 2. E-7 · `error_questions`(ErrorQuestion)

**用途**:错题本。Phase 2 数据源仅手动创建(FR-042,澄清 Q4 决议 2026-06-13);Phase 4 FR-040 自动从面试报告提取叠加。

### 字段

| 字段 | 类型 | 约束 | 默认 | 说明 |
|---|---|---|---|---|
| `id` | uuid v7 | PK | `new_uuid_v7()` | |
| `user_id` | uuid | FK → `users.id`, NOT NULL | — | |
| `source_session_id` | uuid | NULL, FK → `interview_sessions.id` | NULL | Phase 4 FR-040 写入;Phase 2 手动创建时为 NULL |
| `dimension` | TEXT | NULL | NULL | 6 维度之一(DEC-P2-8 可选);CHECK 约束见下 |
| `question_text` | TEXT | NOT NULL | — | 题干(1-2000 字符) |
| `answer_text` | TEXT | NULL | NULL | 用户的原回答(可空) |
| `reference_answer_md` | TEXT | NULL | NULL | 参考答案(Markdown,Phase 5 Error Coach 写入,Phase 2 手动创建可填) |
| `score` | SMALLINT | NULL | NULL | 0-10;Phase 2 手动创建时用户自评;Phase 4 面试报告写入 |
| `status` | TEXT | NOT NULL | `'fresh'` | fresh / practicing / mastered(DEC-P2-5);枚举见 §1 域枚举 |
| `frequency` | SMALLINT | NOT NULL | 3 | 0-3(CHECK 约束) |
| `tags` | JSONB | NULL | NULL | 用户自填标签(数组) |
| `archived_at` | TIMESTAMPTZ | NULL | NULL | 手动归档时间(非物理删,可恢复) |
| `last_practiced_at` | TIMESTAMPTZ | NULL | NULL | Phase 5 Error Coach 写入 |
| `created_at` | TIMESTAMPTZ | NOT NULL | `func.now()` | |
| `updated_at` | TIMESTAMPTZ | NOT NULL | `func.now()` | |
| `deleted_at` | TIMESTAMPTZ | NULL | NULL | SoftDeletableMixin |

### 约束

- `CHECK (status IN ('fresh','practicing','mastered','archived'))` — DEC-P2-5
- `CHECK (frequency BETWEEN 0 AND 3)` — DEC-P2-5
- `CHECK (score IS NULL OR score BETWEEN 0 AND 10)` — 0-10 评分
- `CHECK (length(question_text) BETWEEN 1 AND 2000)` — 题干长度
- `CHECK (dimension IS NULL OR dimension IN ('tech_depth','architecture','engineering_practice','communication','algorithm','business'))` — DEC-P2-8
- **业务不变量(Repository save 校验)**:`status='mastered'` MUST `frequency=0`;`status='practicing'` MUST `frequency IN (1,2)`;`status='fresh'` MUST `frequency=3` — DEC-P2-5

### 索引

- `UNIQUE INDEX` 暂无业务唯一约束
- `INDEX (user_id, status, frequency DESC)` — 列表按状态+频次筛选
- `INDEX (user_id, dimension)` — 按维度过滤
- `INDEX (user_id, created_at DESC)` — 最近错题
- `INDEX (user_id, last_practiced_at DESC) WHERE last_practiced_at IS NOT NULL` — 待强化题

### 状态机(DEC-P2-5)

```
fresh(freq=3) ─手动 edit / practice─► practicing(freq=1..2) ─手动 mark_mastered─► mastered(freq=0)
                                                                                  │
                                                                                  └─反悔:mastered ─手动 reset─► fresh(freq=3)
任意状态 ─PATCH archived_at─► archived(隐式 status='archived',deleted_at 仍 NULL)
```

- 合法转换在 `errors/service.py::reduce_status()` 纯函数中实现
- 非法转换抛 `InvalidStateTransitionError`(409 Conflict)
- Phase 5 Error Coach 沿用同一函数,trigger 来源是 Agent 评分

### 关系

- N:1 → `users`(E-1)
- N:1 → `interview_sessions`(E-13,nullable;Phase 4 FR-040 写入)

### 状态映射 mockData

`mockData.ts:276-323` ErrorQuestion 字段 → DB:
- `id` → `id`
- `title` → `question_text`(Phase 1 mockData 字段名差异,Phase 2 统一为 `question_text`)
- `dimension` → `dimension`
- `score` → `score`
- `status` → `status`
- `frequency` → `frequency`
- `lastMissed` → `last_practiced_at`(`"3 天前"` 字符串 → 实际 `timestamptz`,前端格式化)

---

## 3. E-8 · `ability_dimensions`(AbilityDimension)

**用途**:6 维度能力画像,每用户 6 行(注册时 seed,DEC-P2-2)。Phase 2 写路径:用户手动 PATCH + 注册时 seed;Phase 4 M18 异步聚合叠加。

### 字段

| 字段 | 类型 | 约束 | 默认 | 说明 |
|---|---|---|---|---|
| `id` | uuid v7 | PK | `new_uuid_v7()` | |
| `user_id` | uuid | FK → `users.id`, NOT NULL | — | |
| `dimension_key` | TEXT | NOT NULL | — | 6 维度 enum |
| `actual_score` | NUMERIC(4,2) | NOT NULL | 0.00 | 0.00-10.00 |
| `ideal_score` | NUMERIC(4,2) | NOT NULL | 10.00 | 0.00-10.00 |
| `sub_scores` | JSONB | NOT NULL | `'{}'::jsonb` | `{sub_key: {actual, ideal}}`,DEC-P2-2 |
| `is_active` | BOOL | NOT NULL | TRUE | 用户可禁用某维度(spec M09 §7) |
| `source` | TEXT | NOT NULL | `'manual'` | manual / interview / error / coach |
| `last_updated_at` | TIMESTAMPTZ | NOT NULL | `func.now()` | 显式时间戳(区别 `updated_at`) |
| `created_at` | TIMESTAMPTZ | NOT NULL | `func.now()` | |
| `updated_at` | TIMESTAMPTZ | NOT NULL | `func.now()` | |

**无 `deleted_at`** — 禁用走 `is_active=false`(M09 §7 决议)

### 约束

- `CHECK (dimension_key IN ('tech_depth','architecture','engineering_practice','communication','algorithm','business'))` — DEC-P2-2
- `CHECK (actual_score BETWEEN 0 AND 10)` 
- `CHECK (ideal_score BETWEEN 0 AND 10)`
- `CHECK (source IN ('manual','interview','error','coach'))`

### 索引

- **`UNIQUE (user_id, dimension_key)`** — 6 维度每用户唯一
- `INDEX (user_id, last_updated_at DESC)` — 最近更新

### 6 维度子项(DEC-P2-2)

```json
{
  "tech_depth":        {"fundamentals": {"actual": 0, "ideal": 10}, "system_design": {...}, "depth_specialty": {...}},
  "architecture":      {"decomposition": {...}, "tradeoffs": {...}, "scalability": {...}},
  "engineering_practice": {"code_quality": {...}, "testing": {...}, "observability": {...}},
  "communication":     {"clarity": {...}, "structure": {...}, "conciseness": {...}},
  "algorithm":         {"data_structures": {...}, "complexity": {...}, "edge_cases": {...}},
  "business":          {"domain_knowledge": {...}, "product_sense": {...}, "user_empathy": {...}}
}
```

### 关系

- N:1 → `users`(E-1)
- 1:N → `ability_dimensions_history`(E-9)

### 注册时 seed(DEC-P2-2)

`auth/service.py::on_after_register` 钩子调用 `AbilityService.seed_for_new_user(user_id)`:
- 插入 6 行,`actual_score=0, ideal_score=10, is_active=TRUE, sub_scores={...}`

---

## 4. E-9 · `ability_dimensions_history`(AbilityDimensionHistory)

**用途**:能力画像时序快照(append-only),支撑成长曲线(spec US5 AC-2 / FR-032)。`aggregate='month' | 'day'`。

### 字段

| 字段 | 类型 | 约束 | 默认 | 说明 |
|---|---|---|---|---|
| `id` | uuid v7 | PK | `new_uuid_v7()` | |
| `user_id` | uuid | FK → `users.id`, NOT NULL | — | |
| `dimension_key` | TEXT | NOT NULL | — | 6 维度 enum |
| `snapshot_date` | DATE | NOT NULL | — | 快照日期(UTC) |
| `aggregate` | TEXT | NOT NULL | — | 'month' / 'day' |
| `actual_score` | NUMERIC(4,2) | NOT NULL | — | 0.00-10.00 |
| `ideal_score` | NUMERIC(4,2) | NOT NULL | — | 0.00-10.00 |
| `created_at` | TIMESTAMPTZ | NOT NULL | `func.now()` | |

**无 `updated_at` / `deleted_at`** — append-only

### 约束

- `CHECK (aggregate IN ('month','day'))`
- `CHECK (dimension_key IN (...))`(同 E-8)
- `CHECK (actual_score BETWEEN 0 AND 10)`
- `CHECK (ideal_score BETWEEN 0 AND 10)`

### 索引

- **`UNIQUE (user_id, dimension_key, aggregate, snapshot_date)`** — 防止同维度同日/月重复快照
- `INDEX (user_id, dimension_key, aggregate, snapshot_date DESC)` — 时序查询(列表 API 主查询)

### 写路径

- Phase 2:无写(无能力诊断 Agent,Phase 4-5 M18 落地后由异步任务写入)
- Phase 4-5:`ability_diagnose` 子图完成后,写当天 `aggregate='day'`;ARQ cron 每月 1 日写上月 `aggregate='month'`(聚合)

### 关系

- N:1 → `users`(E-1)
- N:1 → `ability_dimensions`(E-8,逻辑,无 FK)

---

## 5. E-10 · `tasks`(Task)

**用途**:用户任务列表。Phase 2 自动触发:Jobs 创建/状态推进 → 「准备 X 公司面试」任务(DEC-P2-6);手动任务用户可创建。

### 字段

| 字段 | 类型 | 约束 | 默认 | 说明 |
|---|---|---|---|---|
| `id` | uuid v7 | PK | `new_uuid_v7()` | |
| `user_id` | uuid | FK → `users.id`, NOT NULL | — | |
| `type` | TEXT | NOT NULL | — | interview_prep / branch_optimize / application_followup / manual(spec FR-050 延伸)|
| `title` | TEXT | NOT NULL | — | 1-200 字符 |
| `description_md` | TEXT | NULL | NULL | Markdown |
| `related_entity_type` | TEXT | NULL | NULL | job / branch / error_question / null(manual) |
| `related_entity_id` | uuid | NULL | NULL | 多态关联;具体指向由 `related_entity_type` 决定 |
| `status` | TEXT | NOT NULL | `'todo'` | todo / doing / done / archived(FR-052) |
| `due_at` | TIMESTAMPTZ | NULL | NULL | 截止时间 |
| `completed_at` | TIMESTAMPTZ | NULL | NULL | done 时记录 |
| `auto_generated` | BOOL | NOT NULL | FALSE | TRUE = 系统触发,FALSE = 手动 |
| `created_at` | TIMESTAMPTZ | NOT NULL | `func.now()` | |
| `updated_at` | TIMESTAMPTZ | NOT NULL | `func.now()` | |
| `deleted_at` | TIMESTAMPTZ | NULL | NULL | SoftDeletableMixin |

### 约束

- `CHECK (type IN ('interview_prep','branch_optimize','application_followup','manual'))` — DEC-P2-3
- `CHECK (status IN ('todo','doing','done','archived'))` — FR-052
- `CHECK (length(title) BETWEEN 1 AND 200)` — 标题长度
- `CHECK (related_entity_type IN ('job','branch','error_question') OR (related_entity_type IS NULL AND type='manual'))`

### 索引

- **`UNIQUE (user_id, type, related_entity_id) WHERE related_entity_id IS NOT NULL`** — DEC-P2 幂等键(澄清 Q2 决议,2026-06-13);`manual` 类型 `related_entity_id IS NULL`,不在唯一索引覆盖范围
- `INDEX (user_id, status, due_at)` — 列表主查询(按状态 + 截止时间)
- `INDEX (user_id, related_entity_type, related_entity_id) WHERE related_entity_id IS NOT NULL` — 反向查询(从 entity 找 task)

### 状态机

```
todo ─PATCH─► doing ─PATCH─► done
   │           │              │
   │           │              └─反悔: done ─PATCH─► doing
   │           └─PATCH─► archived
   └─PATCH─► archived
```

任意状态可 `soft_delete`(`deleted_at`)。

### 关系

- N:1 → `users`(E-1)
- 多态逻辑关联:`related_entity_type='job' AND related_entity_id=:job_id → jobs.id`,无物理 FK(应用层校验)

### 幂等键行为(DEC-P2-3 + DEC-P2-6 + 澄清 Q2)

`TaskService.find_or_create(user_id, type, related_entity_id, title)`:
1. `SELECT * FROM tasks WHERE user_id=:u AND type=:t AND related_entity_id=:r LIMIT 1`
2. 若存在:返回已存在记录(必要时 PATCH title)
3. 若不存在:`INSERT INTO tasks ...`;若 `IntegrityError`(并发竞争),重试 1

`UNIQUE` 约束的 `IntegrityError` 兜底,杜绝 race condition。

---

## 6. E-11 · `activities`(Activity)

**用途**:统一活动流(M10)。append-only,游标分页(DEC-P2-1)。

### 字段

| 字段 | 类型 | 约束 | 默认 | 说明 |
|---|---|---|---|---|
| `id` | uuid v7 | PK | `new_uuid_v7()` | |
| `user_id` | uuid | FK → `users.id`, NOT NULL | — | |
| `type` | TEXT | NOT NULL | — | task_created / task_completed / job_status_changed / job_created / interview_started / interview_completed / branch_created / error_logged / manual |
| `actor_type` | TEXT | NOT NULL | `'user'` | user / system / agent |
| `payload_json` | JSONB | NOT NULL | — | 类型相关数据(`{job_id, from_status, to_status}` 等) |
| `request_id` | TEXT | NULL | NULL | 关联请求(审计可观测,M22 准备) |
| `occurred_at` | TIMESTAMPTZ | NOT NULL | `func.now()` | 事件时间,游标分页键 |

**无 `updated_at` / `deleted_at`** — append-only,90 天物理删除(M10 §6 + §8 决议:`0 3 * * *` cron)

### 约束

- `CHECK (type IN (...))` — DEC-P2-4 枚举值
- `CHECK (actor_type IN ('user','system','agent'))`

### 索引

- `INDEX (user_id, occurred_at DESC, id DESC)` — 游标分页主查询(`(occurred_at, id) DESC` 复合)
- `INDEX (user_id, type, occurred_at DESC)` — 按类型过滤

### 游标分页(DEC-P2-1)

```python
# Encode
cursor = base64.urlsafe_b64encode(
    json.dumps({"ts": occurred_at.isoformat(), "id": str(id)}).encode()
).decode().rstrip("=")

# Decode
def decode_cursor(opaque: str) -> tuple[datetime, UUID]:
    pad = "=" * (-len(opaque) % 4)
    payload = json.loads(base64.urlsafe_b64decode(opaque + pad))
    return datetime.fromisoformat(payload["ts"]), UUID(payload["id"])

# Query (forward-only, DESC)
SELECT * FROM activities
WHERE user_id = :u
  AND (occurred_at, id) < (:cursor_ts, :cursor_id)  -- 严格小于
ORDER BY occurred_at DESC, id DESC
LIMIT :n;
```

`limit` 范围 1-50,默认 20;响应 `{items: [...], next_cursor: "..."|null}`。

### 写触发器

- `TaskService.create()` 成功后:`activities` 写一条 `type='task_created'`
- `TaskService.update_status(done)`:`type='task_completed'`
- `JobService.create()` / `update_status()`:对应 `job_created` / `job_status_changed`
- Phase 4:`interview_started` / `interview_completed`(Agent 触发)
- `error_questions` 创建:`error_logged`
- 手动:`manual`(用户在 Settings 触发的「记录笔记」等)

### 关系

- N:1 → `users`(E-1)
- 无物理 FK 到 `payload_json` 中引用的实体(append-only,不强约束)

---

## 7. E-12 · `jobs`(Job)

**用途**:求职追踪记录(M10 jobs 部分)。状态机驱动任务自动生成(DEC-P2-6)。

### 字段

| 字段 | 类型 | 约束 | 默认 | 说明 |
|---|---|---|---|---|
| `id` | uuid v7 | PK | `new_uuid_v7()` | |
| `user_id` | uuid | FK → `users.id`, NOT NULL | — | |
| `company` | TEXT | NOT NULL | — | 1-100 字符 |
| `position` | TEXT | NOT NULL | — | 1-100 字符 |
| `jd_url` | TEXT | NULL | NULL | JD 链接,可选 |
| `branch_id` | uuid | NULL, FK → `resume_branches.id` | NULL | 关联简历分支(可选) |
| `status` | TEXT | NOT NULL | `'applied'` | applied / test / oa / hr / offer / rejected / withdrawn(FR-090) |
| `status_history` | JSONB | NOT NULL | `'[]'::jsonb` | `[{from, to, at, note}]` 时间线 |
| `last_status_changed_at` | TIMESTAMPTZ | NOT NULL | `func.now()` | 漏斗统计用 |
| `notes_md` | TEXT | NULL | NULL | 用户备注 |
| `created_at` | TIMESTAMPTZ | NOT NULL | `func.now()` | |
| `updated_at` | TIMESTAMPTZ | NOT NULL | `func.now()` | |
| `deleted_at` | TIMESTAMPTZ | NULL | NULL | SoftDeletableMixin |

### 约束

- `CHECK (status IN ('applied','test','oa','hr','offer','rejected','withdrawn'))` — FR-090
- `CHECK (length(company) BETWEEN 1 AND 100)`
- `CHECK (length(position) BETWEEN 1 AND 100)`
- `CHECK (jd_url IS NULL OR jd_url ~ '^https?://')` — URL 格式
- 业务约束:`status_history` 是 append-only 数组,Repository save 时 push 新条目

### 索引

- `INDEX (user_id, status, last_status_changed_at DESC)` — 漏斗统计
- `INDEX (user_id, created_at DESC)` — 最近创建
- `INDEX (user_id, branch_id) WHERE branch_id IS NOT NULL` — 从 branch 反查 jobs

### 状态机(DEC-P2-6)

```
[新创建] ──► applied ──► test ──► oa ──► hr ──► offer
   │            │          │       │       │
   │            ▼          ▼       ▼       ▼
   └─►(any)─► rejected / withdrawn (终态)
```

合法转换矩阵(应用层校验):
- `applied → test / oa / hr / offer / rejected / withdrawn` ✅
- `test → oa / hr / offer / rejected / withdrawn` ✅
- `oa → hr / offer / rejected / withdrawn` ✅
- `hr → offer / rejected / withdrawn` ✅
- `offer → rejected / withdrawn`(罕见,允许反悔)
- 终态(`rejected / withdrawn`)不可转换(只能 `soft_delete`)

`status_history` push:每次成功转换 push `{from: old, to: new, at: now, note: ""}`。

### 任务触发(DEC-P2-6)

- `JobService.create(status='applied')` 成功后:`TaskService.find_or_create(user_id, 'interview_prep', job.id, "准备 {company} · {position} 面试")`
- `JobService.update_status(from='applied', to='test' | 'oa' | 'hr' | 'offer')` 成功后:更新对应 task 的 `title`(`"准备 {company} · {position} 面试 · {new_status_cn}"`)+ 写 activity
- `JobService.update_status(to='rejected' | 'withdrawn')`:若有 `interview_prep` 任务,置 `status='archived'`

### 漏斗统计 API(供 Phase 5 Dashboard)

`GET /jobs/stats`(Phase 2 已开放,Phase 5 Dashboard 切真实时直接消费):
```json
{
  "counts": {
    "applied": 5, "test": 2, "oa": 1, "hr": 1, "offer": 0, "rejected": 3, "withdrawn": 1
  },
  "total": 13
}
```

### 关系

- N:1 → `users`(E-1)
- N:1 → `resume_branches`(E-4,nullable)
- 1:N → `tasks`(逻辑,E-10 `related_entity_id`)

---

## 8. E-13 · `interview_sessions`(InterviewSession)

**用途**:面试会话记录。Phase 2 **只读骨架**(澄清 Q3 决议,2026-06-13):表落地 + list/get API,无 create/update/delete。Phase 4 M15 Agent 启动 session 时补 create。

### 字段

| 字段 | 类型 | 约束 | 默认 | 说明 |
|---|---|---|---|---|
| `id` | uuid v7 | PK | `new_uuid_v7()` | |
| `user_id` | uuid | FK → `users.id`, NOT NULL | — | |
| `branch_id` | uuid | NULL, FK → `resume_branches.id` | NULL | 可选关联 |
| `position` | TEXT | NULL | NULL | 目标岗位(Phase 4 M15 启动时必填,Phase 2 占位) |
| `company` | TEXT | NULL | NULL | 目标公司(同上) |
| `mode` | TEXT | NULL | NULL | text / voice(同上) |
| `status` | TEXT | NOT NULL | `'pending'` | pending / running / completed / aborted(Phase 2 仅读;`pending` 是默认) |
| `thread_id` | TEXT | NULL | NULL | LangGraph thread_id(Phase 4 启用,DEC-2 §A6 决议) |
| `checkpoint_ns` | TEXT | NULL | NULL | LangGraph checkpoint namespace(同上) |
| `started_at` | TIMESTAMPTZ | NULL | NULL | Phase 2 占位,Phase 4 启动时填 |
| `ended_at` | TIMESTAMPTZ | NULL | NULL | 同上 |
| `duration_sec` | INT | NULL | NULL | 同上 |
| `overall_score` | NUMERIC(4,2) | NULL | NULL | Phase 4 report 节点填 |
| `created_at` | TIMESTAMPTZ | NOT NULL | `func.now()` | |
| `updated_at` | TIMESTAMPTZ | NOT NULL | `func.now()` | |
| `deleted_at` | TIMESTAMPTZ | NULL | NULL | SoftDeletableMixin |

### 约束

- `CHECK (status IN ('pending','running','completed','aborted'))`
- `CHECK (mode IS NULL OR mode IN ('text','voice'))`
- `CHECK (duration_sec IS NULL OR duration_sec >= 0)`
- `CHECK (overall_score IS NULL OR overall_score BETWEEN 0 AND 10)`
- **`UNIQUE (thread_id, checkpoint_ns) WHERE thread_id IS NOT NULL`** — A6 决议预留(Phase 4 启用)

### 索引

- `INDEX (user_id, started_at DESC NULLS LAST)` — 列表主查询
- `INDEX (user_id, status)` — 按状态过滤
- `INDEX (thread_id) WHERE thread_id IS NOT NULL` — Phase 4 checkpointer 查询

### Phase 2 范围(澄清 Q3)

- **表存在,但不开放 create/update/delete API**
- 列表 API:`GET /interview-sessions?status=&limit=&offset=`(简单分页,Phase 4 升级游标)
- 详情 API:`GET /interview-sessions/{id}`
- 写操作全部 405 Method Not Allowed
- Phase 4 M15 启动时补:`POST /interview-sessions`(Agent 入口)

### 关系

- N:1 → `users`(E-1)
- N:1 → `resume_branches`(E-4,nullable)
- 1:N → `interview_messages`(E-14,Phase 4 落地)
- 1:1 → `interview_reports`(E-15,Phase 4 落地)
- 1:N → `ai_messages`(M14 同名,跨模块)

---

## 9. 域枚举(`app/domain/enums.py`)

```python
from enum import Enum

class AbilityDimension(str, Enum):
    TECH_DEPTH = "tech_depth"
    ARCHITECTURE = "architecture"
    ENGINEERING_PRACTICE = "engineering_practice"
    COMMUNICATION = "communication"
    ALGORITHM = "algorithm"
    BUSINESS = "business"

class ErrorStatus(str, Enum):
    FRESH = "fresh"
    PRACTICING = "practicing"
    MASTERED = "mastered"
    ARCHIVED = "archived"

class JobStatus(str, Enum):
    APPLIED = "applied"
    TEST = "test"
    OA = "oa"
    HR = "hr"
    OFFER = "offer"
    REJECTED = "rejected"
    WITHDRAWN = "withdrawn"

class TaskType(str, Enum):
    INTERVIEW_PREP = "interview_prep"
    BRANCH_OPTIMIZE = "branch_optimize"
    APPLICATION_FOLLOWUP = "application_followup"
    MANUAL = "manual"

class TaskStatus(str, Enum):
    TODO = "todo"
    DOING = "doing"
    DONE = "done"
    ARCHIVED = "archived"

class ActivityType(str, Enum):
    TASK_CREATED = "task_created"
    TASK_COMPLETED = "task_completed"
    JOB_CREATED = "job_created"
    JOB_STATUS_CHANGED = "job_status_changed"
    INTERVIEW_STARTED = "interview_started"
    INTERVIEW_COMPLETED = "interview_completed"
    BRANCH_CREATED = "branch_created"
    ERROR_LOGGED = "error_logged"
    MANUAL = "manual"

class ActivityActor(str, Enum):
    USER = "user"
    SYSTEM = "system"
    AGENT = "agent"

class InterviewStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    ABORTED = "aborted"

class InterviewMode(str, Enum):
    TEXT = "text"
    VOICE = "voice"
```

Job status 中文映射(前端):
```python
JOB_STATUS_CN = {
    "applied": "已投递",
    "test": "笔试",
    "oa": "OA",
    "hr": "HR 面",
    "offer": "Offer",
    "rejected": "已拒",
    "withdrawn": "已撤回",
}
```

---

## 10. RLS 策略(全部 7 张新表)

```sql
-- 启用 RLS
ALTER TABLE error_questions ENABLE ROW LEVEL SECURITY;
ALTER TABLE ability_dimensions ENABLE ROW LEVEL SECURITY;
ALTER TABLE ability_dimensions_history ENABLE ROW LEVEL SECURITY;
ALTER TABLE tasks ENABLE ROW LEVEL SECURITY;
ALTER TABLE activities ENABLE ROW LEVEL SECURITY;
ALTER TABLE jobs ENABLE ROW LEVEL SECURITY;
ALTER TABLE interview_sessions ENABLE ROW LEVEL SECURITY;

-- 统一策略
CREATE POLICY user_isolation ON error_questions
  USING (user_id = current_setting('app.user_id', true)::uuid);
-- (其余 6 张表同模板)
```

应用层强制:`get_db_session(user_id=Depends(current_user))` 注入 `SET LOCAL app.user_id = :uuid`,沿用 Phase 1 M05 决议。

---

## 11. 迁移策略

**单次迁移**:`migrations/versions/0002_phase2_entities.py`
- `op.create_table()` × 7(顺序:interview_sessions → error_questions → ability_dimensions → ability_dimensions_history → jobs → tasks → activities)
- `op.create_index()` × 全部
- `op.create_check_constraint()` × 全部
- `op.enable_rls()` + `op.create_policy()` × 7
- **回滚**:`op.drop_table()` 顺序倒置

**Phase 1 表无字段变更**;`users.monthly_token_quota` 字段已就位(T008b 解封时迁移),Phase 2 才有 cron 读它。

---

## 12. 与 mockData 字段映射汇总

| mockData 字段 | DB 字段 | 备注 |
|---|---|---|
| ErrorQuestion.title | `question_text` | 字段名统一 |
| ErrorQuestion.dimension | `dimension` | 6 维度 enum |
| ErrorQuestion.score | `score` | 0-10 |
| ErrorQuestion.status | `status` | fresh/practicing/mastered |
| ErrorQuestion.frequency | `frequency` | 0-3 |
| ErrorQuestion.lastMissed | `last_practiced_at` | 字符串 → timestamptz |
| AbilityDimension.dimensionKey | `dimension_key` | 6 维度 |
| AbilityDimension.actualScore | `actual_score` | 0-10 |
| AbilityDimension.idealScore | `ideal_score` | 0-10 |
| AbilityDimension.subScores | `sub_scores` | JSONB,18 子项 |
| Task.title | `title` | |
| Task.status | `status` | todo/doing/done/archived |
| Task.dueDate | `due_at` | timestamptz |
| Activity.type | `type` | (Phase 2 新增枚举,见 §9) |
| Activity.timestamp | `occurred_at` | |
| Job.company | `company` | |
| Job.position | `position` | |
| Job.status | `status` | 7 态 |
| Job.jdUrl | `jd_url` | |
| Job.appliedAt | `created_at` | |
| InterviewSession.position | `position` | Phase 2 占位 |
| InterviewSession.company | `company` | Phase 2 占位 |
| InterviewSession.mode | `mode` | text/voice |
| InterviewSession.status | `status` | pending/running/completed/aborted |

mockData 中 Phase 2 不再使用的字段(标注「Phase 2 后改 mock」):
- 任何 Phase 2 真实 API 接入后,mockData 中对应 list 改为空数组,Repository 内部 fallback。
