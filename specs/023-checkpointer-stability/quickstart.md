# Quickstart: LangGraph Checkpointer 连接稳定性修复

**Feature**: 023-checkpointer-stability

## Prerequisites

- 后端: Python 3.11 + uv 已安装，PostgreSQL 15+ 可达（`idle_in_transaction_session_timeout` ≥ 300s），Redis 6379 可达
- 测试数据: 1 个测试用户，每个 agent（interview / error_coach / resume_optimize / ability_diagnose / general_coach）各 1 个 thread

## Setup

```bash
cd backend
uv sync
# 确保 .env 配置 DATABASE_URL / LLM_API_KEY / LLM_MOCK_MODE=0
uv run alembic upgrade head
uv run uvicorn app.main:app --reload --port 8000
```

## Validation Scenarios

### Scenario 1: interview idle 60s 后 submit_answer (SC-001)

```bash
# 1. 启动后端
uv run uvicorn app.main:app --port 8000 &

# 2. 启动面试
TID=$(curl -sX POST http://localhost:8000/api/v1/agents/interview-sessions/start \
  -H "Authorization: Bearer <token>" | jq -r .thread_id)

# 3. 等待 60s (模拟 idle, 让 PostgreSQL/中间设备关闭连接)
sleep 60

# 4. submit_answer, 期望 200
curl -X POST http://localhost:8000/api/v1/interview-sessions/$TID/messages \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"content":"我的答案"}' -w "\n%{http_code}\n"
# Expected: 200

# 5. 检查日志
# Expected: checkpointer.reconnect info 日志 (若发生重连)
# Expected: checkpointer_reconnect_total 指标递增 (若发生重连)
```

### Scenario 2: lifespan 预热 (SC-002)

```bash
# 1. 重启后端
kill <backend_pid>
uv run uvicorn app.main:app --port 8000 &

# 2. 立即调用 agent 接口
time curl -X POST http://localhost:8000/api/v1/agents/error-coach/start \
  -H "Authorization: Bearer <token>"
# Expected: time_total < 0.5s

# 3. 检查启动日志
# Expected: "checkpointer.preheat ok" with pool_config
# Expected: pg_tables 含 checkpoint% 表
psql $DATABASE_URL -c "SELECT tablename FROM pg_tables WHERE tablename LIKE 'checkpoint%';"
```

### Scenario 3: 预热失败降级 (Edge case)

```bash
# 1. 故意停止 PostgreSQL
sudo systemctl stop postgresql

# 2. 启动后端 (应仍能启动)
uv run uvicorn app.main:app --port 8000 &
# Expected: warning 日志 "checkpointer.preheat_failed"
# Expected: 服务正常启动, 非 agent 接口可用

# 3. 启动 PostgreSQL
sudo systemctl start postgresql

# 4. 调用 agent 接口 (懒加载路径)
curl -X POST http://localhost:8000/api/v1/agents/error-coach/start \
  -H "Authorization: Bearer <token>"
# Expected: 200 (get_checkpointer() 懒加载重建)
```

### Scenario 4: 并发重连仅 1 次 (SC-007)

```bash
# 1. 启动后端, 创建 1 个 interview thread
# 2. 手动关闭 checkpointer 底层连接 (psql pg_terminate_backend)
# 3. 10 并发 submit_answer
for i in {1..10}; do
  curl -X POST http://localhost:8000/api/v1/interview-sessions/$TID/messages \
    -H "Authorization: Bearer <token>" -d '{"content":"answer"}' &
done
wait

# 4. 检查日志
grep "checkpointer.reconnect" backend.log | wc -l
# Expected: 1 (仅重建 1 次, 其他 9 请求等待锁后复用新 checkpointer)
```

### Scenario 5: checkpointer 不可用返回 503 (Edge case)

```bash
# 1. 启动后端
# 2. 停止 PostgreSQL
sudo systemctl stop postgresql

# 3. 调用 agent 接口
curl -X POST http://localhost:8000/api/v1/agents/error-coach/start \
  -H "Authorization: Bearer <token>" -w "\n%{http_code}\n"
# Expected: 503
# Expected: {"detail":"面试服务暂时不可用，请稍后重试","retry_after":30}
```

### Scenario 6: metrics 指标 (SC-003)

```bash
# 1. 触发 1 次 reconnect (Scenario 1)
# 2. 查询 metrics
curl http://localhost:8000/metrics | grep checkpointer_reconnect_total
# Expected: checkpointer_reconnect_total 1 (或更多)
```

### Scenario 7: 5 graph 本地 retry 移除 (SC-004)

```bash
# 1. 代码行数审计
wc -l backend/app/agents/graphs/*.py
# Expected: 总行数净减少 (移除 5 个 graph 的 _is_checkpointer_alive / _rebuild_checkpointer)

# 2. grep 确认无本地 retry 实现
grep -r "_is_checkpointer_alive\|_rebuild_checkpointer" backend/app/agents/graphs/
# Expected: 无匹配 (统一走 with_checkpointer_retry)
```

### Scenario 8: E2E 零回归 (SC-005)

```bash
cd frontend
npx playwright test --config=playwright.config.ts
# Expected: round-1 + round-2 全部 21/21 通过
```

## Acceptance

所有 8 个 Scenario 通过即视为 023 feature 验收完成。
