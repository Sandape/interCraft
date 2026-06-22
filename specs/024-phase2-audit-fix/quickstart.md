# Quickstart: Phase 2 (M5-M11) spec/code 偏差审计与修复

**Feature**: 024-phase2-audit-fix

## Prerequisites

- 后端: Python 3.11 + uv，PostgreSQL 15+，Redis 6379
- 前端: Node 20+ + npm
- 既有数据: 1 测试用户 + 1 岗位 + 1 错题 + 1 能力画像分享链接

## Setup

```bash
cd backend && uv sync && uv run alembic upgrade head
cd ../frontend && npm install
```

## Validation Scenarios

### Scenario 1: Offer 字段端到端 (SC-001, SC-002)

```bash
# 1. 创建岗位
JOB_ID=$(curl -sX POST http://localhost:8000/api/v1/jobs \
  -H "Authorization: Bearer <token>" \
  -d '{"title":"前端工程师","company":"Acme"}' | jq -r .id)

# 2. 推进到 offered
curl -X PATCH http://localhost:8000/api/v1/jobs/$JOB_ID \
  -H "Authorization: Bearer <token>" \
  -d '{"status":"offered","offer_salary_text":"30K-50K/月","offer_contact_name":"HR 张","offer_contact_info":"hr@acme.com","offer_deadline_at":"2026-06-29T00:00:00Z"}'

# 3. 查询验证
curl http://localhost:8000/api/v1/jobs/$JOB_ID -H "Authorization: Bearer <token>" | jq .
# Expected: 4 个 offer_* 字段值正确

# 4. 前端打开 JobsDetailPanel
# Expected: 时间线 / 编辑按钮 / Offer 区 / activities 全部展示
```

### Scenario 2: outbox 离线兜底 (SC-003)

```bash
# 1. 停止后端 (模拟离线)
kill <backend_pid>

# 2. 前端创建岗位 (应进入 outbox 队列)
# 在浏览器 UI 操作, 应看到 "待同步" 标记, 不报错

# 3. 重启后端
uv run uvicorn app.main:app --port 8000 &

# 4. outbox 自动 flush
# Expected: 岗位出现在列表中, "待同步" 标记消失
```

### Scenario 3: status_history 字段名对齐 (SC-004)

```bash
# 1. 前端 typecheck
cd frontend && npm run typecheck
# Expected: 无类型错误

# 2. 打开岗位详情, 查看时间线
# Expected: 时间线节点显示 from/to/at/note, 不是 from_status/to_status/changed_at
```

### Scenario 4: archived 状态移除 (SC-005)

```bash
# 1. 创建错题
EQ_ID=$(curl -sX POST http://localhost:8000/api/v1/error-questions \
  -H "Authorization: Bearer <token>" -d '{"content":"..."}' | jq -r .id)

# 2. 尝试非法转换
curl -X PATCH http://localhost:8000/api/v1/error-questions/$EQ_ID/status \
  -H "Authorization: Bearer <token>" -d '{"status":"archived"}' -w "\n%{http_code}\n"
# Expected: 422

# 3. 合法转换
curl -X PATCH http://localhost:8000/api/v1/error-questions/$EQ_ID/status \
  -H "Authorization: Bearer <token>" -d '{"status":"practicing"}' -w "\n%{http_code}\n"
# Expected: 200

# 4. 数据库验证
psql $DATABASE_URL -c "\d error_questions"
# Expected: 无 archived_at 列
```

### Scenario 5: PIN/ProfileView 移除 (SC-006)

```bash
# 1. 数据库验证
psql $DATABASE_URL -c "\d ability_profile_shares"
# Expected: 无 pin_hash 列
psql $DATABASE_URL -c "\dt profile_views"
# Expected: 表不存在

# 2. 分享链接访问 (无 PIN)
SHARE_ID=$(curl -sX POST http://localhost:8000/api/v1/ability-profile/shares \
  -H "Authorization: Bearer <token>" -d '{"expires_in_days":7}' | jq -r .id)
curl http://localhost:8000/api/v1/ability-profile/shares/$SHARE_ID -w "\n%{http_code}\n"
# Expected: 200 (无需 PIN header)

# 3. 过期测试 (mock 时间或等 7 天)
# Expected: 410 Gone

# 4. 撤销测试
curl -X DELETE http://localhost:8000/api/v1/ability-profile/shares/$SHARE_ID -H "Authorization: Bearer <token>"
curl http://localhost:8000/api/v1/ability-profile/shares/$SHARE_ID -w "\n%{http_code}\n"
# Expected: 403 Forbidden
```

### Scenario 6: PDF 同步下载 (SC-007)

```bash
# 1. 调用 PDF 导出
time curl -X GET http://localhost:8000/api/v1/ability-profile/export-pdf \
  -H "Authorization: Bearer <token>" \
  -o /tmp/ability-profile.pdf -w "%{http_code} %{time_total}s\n"
# Expected: 200, time_total < 3s
# Expected: /tmp/ability-profile.pdf 是合法 PDF (file 命令输出 "PDF document")

# 2. 检查响应头
curl -I http://localhost:8000/api/v1/ability-profile/export-pdf -H "Authorization: Bearer <token>"
# Expected: Content-Type: application/pdf
# Expected: Content-Disposition: attachment; filename="ability-profile-{user_id}-{date}.pdf"

# 3. 无 ARQ 任务入队
# 检查后端日志, 不应有 "arq.enqueue_job ability_profile_export" 日志
```

### Scenario 7: E2E 零回归 (SC-008)

```bash
cd frontend && npx playwright test --config=playwright.config.ts
# Expected: round-1 + round-2 全部 21/21 通过
```

## Acceptance

所有 7 个 Scenario 通过即视为 024 feature 验收完成。
