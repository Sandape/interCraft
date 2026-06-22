# Quickstart: 性能与可观测性增强

**Feature**: 022-perf-observability-enhancement

## Prerequisites

- 后端: Python 3.11 + uv 已安装，PostgreSQL 15+ 可达，Redis 6379 可达
- 前端: Node 20+ + npm 已安装
- 既有数据: 1 个测试用户 + 10 个 resume_branches（每分支 3 版本 + 5 块）+ 500 条 error_questions（status 分布 fresh/practicing/mastered）

## Setup

```bash
# 后端
cd backend
uv sync
uv run alembic upgrade head
uv run uvicorn app.main:app --reload --port 8000

# 前端
cd frontend
npm install
npm run dev
```

## Validation Scenarios

### Scenario 1: request_id 关联 (SC-001)

```bash
# 1. 发起带 X-Request-ID 的请求
curl -X POST http://localhost:8000/api/v1/agents/error-coach/start \
  -H "Authorization: Bearer <token>" \
  -H "X-Request-ID: test-req-001" \
  -H "Content-Type: application/json" \
  -d '{"question_type":"coding"}'

# 2. 验证响应头
# Expected: X-Request-ID: test-req-001

# 3. grep 后端日志
# Expected: llm.invoke 日志含 request_id=test-req-001
```

### Scenario 2: Resume 列表 N+1 修复 (SC-002)

```bash
# 1. 准备 10 分支 × 3 版本 × 5 块测试数据
curl -X POST http://localhost:8000/api/v1/resume-branches/seed-test-data

# 2. 访问列表
curl -w "\n%{time_total}\n" \
  http://localhost:8000/api/v1/resume-branches \
  -H "Authorization: Bearer <token>"

# Expected: 响应含 version_count=3 / block_count=15
# Expected: time_total < 0.3s (P95 ≤ 300ms)

# 3. SQL 计数 (后端日志或 pg_stat_statements)
# Expected: ≤ 2 条 SQL
```

### Scenario 3: error_questions 索引 (SC-003)

```bash
# 1. 准备 500 条错题数据
psql $DATABASE_URL -c "INSERT INTO error_questions (...) SELECT ... FROM generate_series(1, 500);"

# 2. 查询 + EXPLAIN
curl "http://localhost:8000/api/v1/error-questions?source=all" \
  -H "Authorization: Bearer <token>"

# 3. 验证查询计划
psql $DATABASE_URL -c "EXPLAIN ANALYZE SELECT * FROM error_questions WHERE user_id='...' AND deleted_at IS NULL ORDER BY status, frequency, created_at;"
# Expected: Index Scan using idx_error_questions_user_status_freq_created
```

### Scenario 4: 首屏体积 (SC-004)

```bash
cd frontend
npm run build
# 检查 dist/assets/
ls -la dist/assets/
# Expected: vendor-*.js 存在, 体积 ≥ 40% 总 JS

# gzip 体积
gzip -c dist/assets/index-*.js | wc -c
# Expected: ≤ 500000 bytes (500KB)
```

### Scenario 5: metrics 端点 (SC-005)

```bash
curl http://localhost:8000/metrics | grep -E "^(llm_quota|checkpointer|ws_|arq_)" | sort -u
# Expected: 至少 6 个新增指标名

curl http://localhost:8000/metrics | grep -c "^[a-z_]" 
# Expected: ≥ 15 (总指标数)
```

### Scenario 6: vendor 分包稳定 (SC-006)

```bash
cd frontend
npm run build
sha1sum dist/assets/vendor-*.js  # 记录 hash

# 修改业务代码 (如 src/pages/Login.tsx 加一行注释)
echo "// test" >> src/pages/Login.tsx
npm run build
sha1sum dist/assets/vendor-*.js
# Expected: hash 未变
```

### Scenario 7: E2E 零回归 (SC-007)

```bash
cd frontend
npx playwright test --config=playwright.config.ts
# Expected: round-1 + round-2 全部 21/21 通过
```

## Acceptance

所有 7 个 Scenario 通过即视为 022 feature 验收完成。
