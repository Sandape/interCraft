# Quickstart: InterCraft Phase 2 端到端验证

**Status**: Phase 2 output · **Date**: 2026-06-13 · **Plan**: [phase-2.md](./phase-2.md) | [plan.md](./plan.md) · **Spec**: [spec.md](./spec.md) · **Contracts**: [contracts/README.md](./contracts/README.md) · **Data Model**: [data-model-phase-2.md](./data-model-phase-2.md) · **Research**: [research-phase-2.md](./research-phase-2.md)

> 本文档提供 **Phase 2 可重复、可独立验证** 的端到端操作步骤。
> 验证 Phase 2 演示场景(spec §5.2):Profile / Jobs / ErrorBook 三个页面在 `VITE_USE_MOCK=false` 下完全可用,所有列表/详情数据来自真实后端。
> 本文**不**列实现细节;数据 schema 见 [data-model-phase-2.md](./data-model-phase-2.md),接口契约见 [contracts/](./contracts/),研究决议见 [research-phase-2.md](./research-phase-2.md)。

---

## 0. 前置条件

| 项 | 要求 | 备注 |
|---|---|---|
| Phase 1 已完成 | ✅ T008b 解封(2026-06-12)、迁移已跑、47 pass / 22 skip | 本文档假设 Phase 1 演示场景可走通 |
| Phase 2 迁移 | `0002_phase2_entities.py` 已 `alembic upgrade head` | 一次性创建 7 张新表 + RLS + 索引 |
| ARQ worker | 已启动,注册 `monthly_quota_reset` cron | `uv run arq app.workers.main.WorkerSettings` |
| VITE_USE_MOCK | `false`(默认) | 演示 Phase 2 真实 API 模式 |
| 后端 | `localhost:8000`,健康检查 OK | 沿用 Phase 1 |
| 前端 | `localhost:5173` | 沿用 Phase 1 |
| Postgres | 在线托管 T008b 库 | 同 Phase 1 |
| Redis | 本地 6379 | 同 Phase 1 |

---

## 1. 启动 Phase 2 开发栈(5 分钟内)

### 1.1 跑 Phase 2 迁移

```bash
cd backend
uv run alembic upgrade head
# 预期:Running upgrade 0001_initial -> 0002_phase2_entities, ...
# 验证 7 张新表存在:
uv run python -c "
import asyncio
from app.core.db import engine
from sqlalchemy import text

async def check():
    async with engine.begin() as conn:
        result = await conn.execute(text(\"\"\"
            SELECT table_name FROM information_schema.tables
            WHERE table_schema='public'
            AND table_name IN ('error_questions','ability_dimensions',
                'ability_dimensions_history','tasks','activities','jobs',
                'interview_sessions')
            ORDER BY table_name;
        \"\"\"))
        tables = [r[0] for r in result]
        print(f'Found {len(tables)}/7 tables:', tables)

asyncio.run(check())
"
# 预期:Found 7/7 tables: ['ability_dimensions', 'ability_dimensions_history', 'activities', 'error_questions', 'interview_sessions', 'jobs', 'tasks']
```

### 1.2 启动 worker(cron 注册)

```bash
cd backend
uv run arq app.workers.main.WorkerSettings
# 预期日志:
# 2026-06-13T... INFO arq.worker.main: Starting worker for 1 cron job
# 2026-06-13T... INFO app.workers.main: monthly_quota_reset cron registered: 0 0 1 * *
```

### 1.3 启动前端(沿用 Phase 1)

```bash
# 另一个终端
npm run gen:api  # 重建 schema.d.ts(包含 Phase 2 端点)
npm run dev
# 浏览器打开 http://localhost:5173
```

### 1.4 验证 OpenAPI 包含 Phase 2 端点

```bash
curl -s http://localhost:8000/api/v1/openapi.json | python -c "
import json, sys
spec = json.load(sys.stdin)
phase2_paths = [p for p in spec['paths'] if any(p.startswith(f'/api/v1/{m}') for m in
    ['error-questions','ability-dimensions','tasks','activities','jobs','interview-sessions'])]
print(f'Phase 2 endpoints: {len(phase2_paths)}')
for p in sorted(phase2_paths):
    methods = ', '.join(spec['paths'][p].keys())
    print(f'  {methods.upper():10s} {p}')
"
# 预期:Phase 2 endpoints: 30+
#   GET        /api/v1/ability-dimensions
#   GET        /api/v1/ability-dimensions/dimensions-meta
#   GET        /api/v1/ability-dimensions/history
#   ... (其余)
```

---

## 2. 演示场景(Phase 2 入口验收)

### 场景 A:Profile 页 — 能力画像只读 + 手动校正

**目标**:验证 `GET /ability-dimensions` 返回 6 行,`PATCH` 可改 sub_scores,雷达图渲染。

**步骤**:

```bash
# 1. 注册新用户(自动触发 AbilityService.seed_for_new_user)
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"profile-test@intercraft.io","password":"Test1234","display_name":"小张"}'
# 预期:201 + access_token + refresh_token

TOKEN="<从响应取 access_token>"

# 2. 拉 6 维度(应已自动 seed)
curl -s http://localhost:8000/api/v1/ability-dimensions \
  -H "Authorization: Bearer $TOKEN" | jq
# 预期:data 数组长度 6,各维度 actual_score=0, ideal_score=10

# 3. 浏览器登录 → 访问 /profile
# 预期:雷达图 6 维度显示 0 分(空态);右上角提示「完成首场模拟面试,启动你的能力追踪」(沿用 mockData 提示文案)

# 4. 手动校正一个维度
curl -X PATCH http://localhost:8000/api/v1/ability-dimensions/tech_depth \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "actual_score": 7.5,
    "sub_scores": {
      "fundamentals": {"actual": 8, "ideal": 10},
      "system_design": {"actual": 7, "ideal": 10},
      "depth_specialty": {"actual": 7.5, "ideal": 10}
    }
  }'
# 预期:200 + 更新后的 AbilityDimension

# 5. 浏览器刷新 /profile
# 预期:技术深度维度从 0 → 7.5;3 个子项分数更新
```

**通过标准**:
- 6 维度自动 seed 成功
- 雷达图渲染
- PATCH 持久化,刷新页面仍可见

---

### 场景 B:Jobs 页 — 投递漏斗 + 状态推进 + 任务自动生成

**目标**:验证 Jobs CRUD + 状态转换触发任务 + activities 写入。

**步骤**:

```bash
TOKEN="<access_token>"

# 1. 创建投递(状态默认 applied)
curl -X POST http://localhost:8000/api/v1/jobs \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "company": "字节跳动",
    "position": "高级前端工程师",
    "jd_url": "https://job.bytedance.com/12345"
  }'
# 预期:201 + Job(applied),+ status_history 初始化
# 副作用:任务「准备字节跳动 · 高级前端工程师 面试」自动创建

# 2. 验证任务自动生成(幂等键)
curl -s "http://localhost:8000/api/v1/tasks?type=interview_prep" \
  -H "Authorization: Bearer $TOKEN" | jq
# 预期:data 长度 1,title 含 "准备字节跳动 · 高级前端工程师 面试"

# 3. 状态推进 applied → test
curl -X PATCH http://localhost:8000/api/v1/jobs/<job_id>/status \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"to": "test", "note": "HR 通知笔试"}'
# 预期:200 + Job(status='test'),+ status_history 多一条
# 副作用:任务 title 更新为「准备字节跳动 · 高级前端工程师 面试 · 笔试」

# 4. 验证任务 title 已更新
curl -s "http://localhost:8000/api/v1/tasks?type=interview_prep" \
  -H "Authorization: Bearer $TOKEN" | jq '.data[0].title'
# 预期:"准备字节跳动 · 高级前端工程师 面试 · 笔试"

# 5. 验证 activities 写入
curl -s "http://localhost:8000/api/v1/activities?type=job_status_changed" \
  -H "Authorization: Bearer $TOKEN" | jq
# 预期:data 长度 1,payload.from_status='applied', to_status='test'

# 6. 非法转换验证
curl -X PATCH http://localhost:8000/api/v1/jobs/<job_id>/status \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"to": "applied"}'
# 预期:409 + {error: {code: "invalid_status_transition", ...}}

# 7. 漏斗统计
curl -s http://localhost:8000/api/v1/jobs/stats \
  -H "Authorization: Bearer $TOKEN" | jq
# 预期:counts.test=1, total=1

# 8. 浏览器登录 → 访问 /jobs
# 预期:看到刚创建的「字节跳动 · 高级前端工程师 · 笔试」;漏斗图(如有)显示 test=1
```

**通过标准**:
- Jobs CRUD 全通
- 状态推进触发任务 title 更新
- activities 写入(游标分页可翻页)
- 非法转换 409
- 漏斗统计正确

---

### 场景 C:ErrorBook 页 — 错题手动创建 + 状态机

**目标**:验证错题 CRUD + 状态机(澄清 Q4 决议 2026-06-13,Phase 2 仅手动数据源)。

**步骤**:

```bash
TOKEN="<access_token>"

# 1. 创建错题(手动)
curl -X POST http://localhost:8000/api/v1/error-questions \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "dimension": "algorithm",
    "question_text": "如何判断链表是否有环?",
    "answer_text": "快慢指针",
    "score": 4,
    "tags": ["linked-list", "two-pointers"]
  }'
# 预期:201 + ErrorQuestion(status='fresh', frequency=3)

# 2. 创建第二条(无 dimension,验证可选,DEC-P2-8)
curl -X POST http://localhost:8000/api/v1/error-questions \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "question_text": "React useEffect 依赖数组何时触发?",
    "score": 5
  }'
# 预期:201,dimension=null,列表显示「未归类」徽章

# 3. 状态推进:fresh → practicing
curl -X PATCH http://localhost:8000/api/v1/error-questions/<id> \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"status": "practicing", "frequency": 2}'
# 预期:200,last_practiced_at 自动更新

# 4. 推进到 mastered
curl -X PATCH http://localhost:8000/api/v1/error-questions/<id> \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"status": "mastered", "frequency": 0}'
# 预期:200

# 5. 非法状态转换(fresh 直接 mastered,frequency 不为 0)
curl -X POST http://localhost:8000/api/v1/error-questions \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"question_text": "测试题", "score": 3}'
ERR_ID=$(curl ... | jq -r .data[0].id)
curl -X PATCH http://localhost:8000/api/v1/error-questions/$ERR_ID \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"status": "mastered", "frequency": 1}'
# 预期:409 + invalid_state_transition(mastered 必须 frequency=0)

# 6. reset 从 mastered → fresh
curl -X POST http://localhost:8000/api/v1/error-questions/<mastered_id>/reset \
  -H "Authorization: Bearer $TOKEN"
# 预期:200,status='fresh', frequency=3

# 7. 浏览器登录 → 访问 /errorbook
# 预期:看到所有错题,按 status+frequency 排序
```

**通过标准**:
- 手动创建成功,dimension 可选
- 状态机合法转换通过
- 非法转换 409
- reset 行为正确
- 列表按 维度+状态+频次 排序

---

### 场景 D:Settings 资料 tab — PATCH /users/me 4 字段

**目标**:验证 Settings「资料」tab 切真实 API(澄清 Q5 决议 2026-06-13)。

**步骤**:

```bash
TOKEN="<access_token>"

# 1. 拉当前用户
curl -s http://localhost:8000/api/v1/users/me \
  -H "Authorization: Bearer $TOKEN" | jq
# 预期:PublicUser(初始值,可能 display_name 来自注册时)

# 2. PATCH 4 字段
curl -X PATCH http://localhost:8000/api/v1/users/me \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "display_name": "林浩然",
    "title": "高级前端工程师",
    "years_of_experience": 5,
    "target_role": "资深前端工程师"
  }'
# 预期:200 + PublicUser 已更新

# 3. 校验:不开放字段(改 email)应 422
curl -X PATCH http://localhost:8000/api/v1/users/me \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"email": "new@example.com"}'
# 预期:422,email 字段不在 schema 中

# 4. 浏览器登录 → 访问 /settings → 切到「资料」tab
# 预期:表单 4 字段已填充;修改后「保存」按钮 → PATCH → 刷新仍可见
# 其他 tab(设备/订阅/安全)仍为 mock 状态,显示「Phase 6 上线」占位
```

**通过标准**:
- 4 字段 PATCH 成功
- 不可改字段(email / subscription)422
- 前端表单→API→刷新持久化

---

### 场景 E:游标分页 — activities 翻页

**目标**:验证 DEC-P2-1 游标分页实现 + 跨端 parity。

**步骤**:

```bash
TOKEN="<access_token>"

# 0. 制造 5 条 activities(创建 2 个 jobs + 2 个 tasks + 1 个 error)
# 略(已在场景 A-D 中写过,这里只验证分页)

# 1. 拉首页(limit=2)
RESP=$(curl -s "http://localhost:8000/api/v1/activities?limit=2" \
  -H "Authorization: Bearer $TOKEN")
echo "$RESP" | jq '.data | length'
# 预期:2
NEXT=$(echo "$RESP" | jq -r '.pagination.next_cursor')
echo "Next cursor: $NEXT"

# 2. 翻页
curl -s "http://localhost:8001/api/v1/activities?limit=2&cursor=$NEXT" \
  -H "Authorization: Bearer $TOKEN" | jq '.data | length'
# 预期:2(若总数 ≥ 4)或 has_more=false

# 3. 翻到底
LAST_RESP=$(curl -s "http://localhost:8001/api/v1/activities?limit=2&cursor=$NEXT" \
  -H "Authorization: Bearer $TOKEN")
LAST_NEXT=$(echo "$LAST_RESP" | jq -r '.pagination.next_cursor')
curl -s "http://localhost:8001/api/v1/activities?limit=2&cursor=$LAST_NEXT" \
  -H "Authorization: Bearer $TOKEN" | jq '.data | length, .pagination.has_more'
# 预期:可能 0 或更少,has_more=false

# 4. 验证 cursor 格式(base64url JSON)
echo "$NEXT" | python -c "
import sys, base64, json
opaque = sys.stdin.read().strip()
pad = '=' * (-len(opaque) % 4)
print(json.loads(base64.urlsafe_b64decode(opaque + pad).decode()))
"
# 预期:{"ts": "2026-06-13T...", "id": "01HXX..."}
```

**通过标准**:
- 游标分页 forward-only
- has_more 正确
- cursor 格式 base64url JSON
- 跨端 parity:前端 `src/lib/cursor.ts` 解码后值与后端一致

---

### 场景 F:任务幂等键 — find_or_create

**目标**:验证澄清 Q2 决议 — DB UNIQUE 约束 + service find_or_create(2026-06-13)。

**步骤**:

```bash
TOKEN="<access_token>"

# 1. 创建 1 个 job(自动创建 1 个 task)
JOB_RESP=$(curl -X POST http://localhost:8000/api/v1/jobs \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"company": "测试公司", "position": "前端"}')
JOB_ID=$(echo "$JOB_RESP" | jq -r '.data.id')

# 2. 验证 task 已存在
TASKS_BEFORE=$(curl -s "http://localhost:8001/api/v1/tasks?type=interview_prep" \
  -H "Authorization: Bearer $TOKEN" | jq '.data | length')
echo "Tasks before status change: $TASKS_BEFORE"
# 预期:1

# 3. 多次 PATCH status 推进(模拟状态反复切换)
for to in test oa hr offer; do
  curl -X PATCH "http://localhost:8001/api/v1/jobs/$JOB_ID/status" \
    -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json" \
    -d "{\"to\": \"$to\"}" > /dev/null
done

# 4. 验证 task 仍只有 1 个(title 持续更新)
TASKS_AFTER=$(curl -s "http://localhost:8001/api/v1/tasks?type=interview_prep" \
  -H "Authorization: Bearer $TOKEN" | jq '.data | length')
echo "Tasks after 4 status changes: $TASKS_AFTER"
# 预期:1
# title 应更新为「准备测试公司 · 前端 面试 · Offer」

# 5. 直接调内部 API(用 service 模拟 race condition)
# 通过 service 层重复调用 find_or_create
uv run python -c "
import asyncio
from app.core.db import session_factory
from app.modules.tasks.service import TaskService
from uuid import UUID

async def main():
    async with session_factory() as session:
        for i in range(3):
            t = await TaskService.find_or_create(
                session, user_id=UUID('<your_user_id>'),
                type='interview_prep', related_entity_id=UUID('$JOB_ID'),
                title=f'重复调用 #{i}'
            )
            print(f'#{i} task_id={t.id} title={t.title}')

asyncio.run(main())
"
# 预期:3 次返回相同 task_id,title 取最后一次传入值(若 update_title_if_exists=True)或第一次(若 False)
```

**通过标准**:
- 多次状态推进不创建重复 task
- DB 唯一约束兜底
- 内部 API 可手动调用,幂等

---

### 场景 G:ARQ cron 月度配额重置

**目标**:验证澄清 Q1 决议 — UTC cron 每月 1 日 00:00 重置(2026-06-13)。

**步骤**:

```bash
# 1. 制造一个超量用户
TOKEN="<access_token>"
# 直接 PATCH monthly_token_used 不可(无 API),用 SQL 模拟
psql $DATABASE_URL -c "
UPDATE users
SET monthly_token_used = 50000, quota_reset_at = now() - interval '31 days'
WHERE email = 'profile-test@intercraft.io';
"

# 2. 验证当前值
psql $DATABASE_URL -c "
SELECT email, monthly_token_used, quota_reset_at
FROM users WHERE email = 'profile-test@intercraft.io';
"
# 预期:monthly_token_used=50000, quota_reset_at=31 天前

# 3. 手动触发 cron(不等到下月 1 日)
uv run python -c "
import asyncio
from app.workers.tasks.monthly_quota_reset import monthly_quota_reset
from app.core.db import session_factory, engine

async def main():
    # 容错窗口检查会 skip,需要 bypass:直接调用 SQL
    async with engine.begin() as conn:
        from sqlalchemy import text
        result = await conn.execute(text('''
            UPDATE users
            SET monthly_token_used = 0, quota_reset_at = now()
            WHERE subscription IN ('free', 'pro')
        '''))
        print(f'Reset {result.rowcount} users')

asyncio.run(main())
"
# 预期:Reset 1 user

# 4. 验证已重置
psql $DATABASE_URL -c "
SELECT email, monthly_token_used, quota_reset_at
FROM users WHERE email = 'profile-test@intercraft.io';
"
# 预期:monthly_token_used=0, quota_reset_at=当前时间

# 5. 验证 cron 注册(用 arq CLI)
uv run arq app.workers.main.WorkerSettings --check
# 预期:列出 monthly_quota_reset cron,schedule "0 0 1 * *"
```

**通过标准**:
- cron 注册成功,定时 `0 0 1 * *` UTC
- 手动触发可重置 `monthly_token_used=0` + `quota_reset_at=now()`
- 结构化日志 `monthly_quota_reset.completed` 含 rowcount

---

### 场景 H:RLS 隔离(2 用户互访)

**目标**:验证 spec FR-004 — 任何 user 不可访问他人数据。

**步骤**:

```bash
# 1. 注册 2 个用户
USER_A=$(curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"rls-a@intercraft.io","password":"Test1234"}' | jq -r '.access_token')

USER_B=$(curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"rls-b@intercraft.io","password":"Test1234"}' | jq -r '.access_token')

# 2. 用户 A 创建错题
ERR_A=$(curl -X POST http://localhost:8000/api/v1/error-questions \
  -H "Authorization: Bearer $USER_A" \
  -H "Content-Type: application/json" \
  -d '{"question_text": "用户 A 的错题", "score": 3}' | jq -r '.data.id')

# 3. 用户 B 试图访问 A 的错题
curl -s -w "\nHTTP %{http_code}\n" \
  -H "Authorization: Bearer $USER_B" \
  "http://localhost:8000/api/v1/error-questions/$ERR_A"
# 预期:HTTP 404(RLS 强制空集,等同不存在)

# 4. 用户 B 列错题,不应看到 A 的
curl -s -H "Authorization: Bearer $USER_B" \
  "http://localhost:8000/api/v1/error-questions" | jq '.data | length'
# 预期:0(B 自己还没创建)

# 5. 对 7 张表都跑一遍(略,自动化测试覆盖)
uv run pytest tests/integration/test_rls_isolation_phase2.py -v
# 预期:全部 pass
```

**通过标准**:
- 用户 A 看不到 B 的错题、维度、任务、活动、Jobs、面试会话
- 自动化测试 `test_rls_isolation_phase2.py` 全部通过

---

## 3. Phase 2 入口验收清单(spec §5.2)

> 三个页面在 `VITE_USE_MOCK=false` 下完全可用,所有列表/详情数据来自真实后端。

- [ ] Profile 页 `/profile` — 雷达图 6 维度渲染,数据来自 `GET /ability-dimensions`
- [ ] Jobs 页 `/jobs` — 列表/创建/状态推进/漏斗,数据来自 `/jobs/*`
- [ ] ErrorBook 页 `/errorbook` — 列表/创建/状态机,数据来自 `/error-questions/*`
- [ ] Settings 页「资料」tab `/settings` — 4 字段 PATCH,数据来自 `/users/me`
- [ ] Dashboard 仍读 mock(Phase 5 改;Phase 2 不要求)
- [ ] InterviewList 仍读 mock(Phase 4 改;M11 只读骨架不影响前端)
- [ ] 11 设备限制、鉴权、JWT 续签 — 沿用 Phase 1,无 regression
- [ ] 后端单元 + 集成测试全绿(预计 70+ pass)
- [ ] 前端 typecheck + vitest 全绿
- [ ] Playwright E2E Phase 2 套件全绿
- [ ] Constitution v1.0.0 五原则 I-V 仍合规(无 violations)

---

## 4. 演示录屏(15 分钟)

按以下顺序录屏:

1. (0:00) 启动栈 + 跑迁移(2 分钟)
2. (0:02) 注册新用户 + 登录(1 分钟)
3. (0:03) 访问 /profile → 雷达图 6 维度空态(0.5 分钟)
4. (0:03:30) 校正 1 个维度 → 雷达图更新(1 分钟)
5. (0:04:30) 访问 /jobs → 创建 2 条投递 → 漏斗图(2 分钟)
6. (0:06:30) 推进状态 → 任务自动 title 更新(1.5 分钟)
7. (0:08) 访问 /errorbook → 创建 2 条错题 → 状态机推进(3 分钟)
8. (0:11) 访问 /settings 资料 tab → 改 4 字段(1 分钟)
9. (0:12) 跨用户 RLS 验证(1 分钟)
10. (0:13) 总结:Phase 2 演示场景全部通过(2 分钟)

---

## 5. 故障排查

| 现象 | 原因 | 解决 |
|---|---|---|
| `alembic upgrade` 报 7 张表已存在 | 重复执行 | `alembic downgrade -1 && alembic upgrade head` |
| `GET /ability-dimensions` 返回 `data: []` | 旧用户未 seed | 注册新用户,或手工 `psql` 插入 6 行 |
| `POST /jobs` 后任务未出现 | `TaskService.find_or_create` 未注入 | 检查 `app/modules/jobs/service.py` import 与 DI |
| 月度 cron 不触发 | arq worker 未启动 | `uv run arq app.workers.main.WorkerSettings` |
| 前端 typecheck 失败 | schema.d.ts 未更新 | `npm run gen:api` 重新生成 |
| 405 on POST /interview-sessions | 符合 Phase 2 预期 | 检查是否走错路由 |
| RLS 403 跨用户访问 | 正常 | 验证 `user_id` JWT 解析正确 |

---

## 6. Next Step

Phase 2 演示场景全部通过后:
- 更新 spec §4 SC-002 / SC-006 状态
- 进入 Phase 3 规划(/speckit-plan Phase 3)
- 提交 PR,触发 CI 全套验证(lint / typecheck / 单测 / 集成 / 契约 / E2E)
