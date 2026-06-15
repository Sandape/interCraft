# Quickstart: Phase 4 — Interview Agent

**Status**: Phase 1 output · **Date**: 2026-06-13

> 5 分钟快速验证 Phase 4 核心功能:启动面试 → 完成 5 轮 → 查看报告 → 断线恢复。

## 前置条件

- Phase 1/2/3 基础设施已就位(PostgreSQL/Redis/ARQ)
- `VITE_USE_MOCK=false`(真实 API 模式)
- Anthropic API key 已配置(`ANTHROPIC_API_KEY` 环境变量)
- Phase 4 migration 已执行(`uv run alembic upgrade head`)
- 已有测试用户(通过 Phase 1 注册)

## 场景 1:完整面试流程(SC-001)

```bash
# 1. 启动后端(含 ARQ worker)
uv run uvicorn app.main:app --reload &
uv run arq app.workers.main.WorkerSettings &

# 2. 启动前端
npm run dev

# 3. 浏览器操作:
#    a. 登录测试用户
#    b. 进入 InterviewList 页 → 确认列表加载(有历史记录或空态)
#    c. 点击「新建面试」→ 填写岗位"高级前端工程师"+ 公司"字节跳动"
#    d. 点击「开始模拟面试」→ 跳转 InterviewLive
#    e. 观察 WS 事件流:
#       - node.started(intake) → token.delta × N → node.completed(intake)
#       - 循环 5 轮:node.started(question_gen) → 流式问题 → 输入回答 → node.started(score) → 流式反馈
#    f. 5 轮完成后 → node.started(report) → report 流式输出 → node.completed(report)
#    g. 自动跳转 InterviewReport 页 → 查看完整报告(总分/每题得分/维度得分/优势/改进建议)

# 4. API 验证:
curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/api/v1/interview-sessions | jq '.data | length'
# 预期:返回 1 条记录,status=completed

curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/api/v1/interview-sessions/{id}/report | jq '.data.overall_score'
# 预期:返回数字(0-10)
```

**预期时间**:≤ 10 分钟(不含思考时间)

**验证点**:
- [ ] WS 事件流完整(node.started / token.delta / node.completed 全部收到)
- [ ] token.delta 逐字渲染,无卡顿
- [ ] 报告页数据完整且持久化(刷新后仍在)
- [ ] SC-002:WS 延迟 P95 ≤ 200ms

## 场景 2:断线重连(SC-004)

```bash
# 1. 启动面试进行到第 3 轮
# 2. 关闭浏览器 Tab(模拟断线)
# 3. 等待 5 秒
# 4. 重新打开 InterviewList 页
# 5. 看到该面试标记为「进行中」+ 「继续面试」按钮
# 6. 点击「继续面试」
# 7. 验证:从第 4 轮开始(前 3 轮内容保留),无重复 token

# API 验证:
curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/api/v1/interview-sessions/{id} | jq '.data.status'
# 预期:"in_progress"(继续后)
```

**验证点**:
- [ ] 断线后 InterviewList 显示「进行中」标记
- [ ] 重连后从正确 checkpoint 恢复(下一轮,非从头开始)
- [ ] 无重复 token(前 3 轮的问题/评分不重放)
- [ ] SC-004:恢复在 5s 内完成

## 场景 3:错误处理

```bash
# 模拟:QuotaExceededError
# 1. 手动设置用户 monthly_token_used 接近上限:
psql -h $DB_HOST -U $DB_USER -d intercraft \
  -c "UPDATE users SET monthly_token_used = monthly_token_quota - 100 WHERE email = 'test@example.com'"

# 2. 尝试启动新面试
# 3. 预期:前端显示「本月 AI 额度已用尽」+ 订阅升级引导

# 恢复:
psql -h $DB_HOST -U $DB_USER -d intercraft \
  -c "UPDATE users SET monthly_token_used = 0 WHERE email = 'test@example.com'"
```

**验证点**:
- [ ] 配额不足时阻止新面试启动(不扣 token)
- [ ] 错误信息清晰,引导升级
- [ ] 错误日志包含 request_id / user_id / thread_id

## 场景 4:双源对账

```bash
# 手动触发对账(用于验证):
uv run python -m app.audit.reconcile --date 2026-06-13

# 预期输出:
# [INFO] Reconcile 2026-06-13: scanned 15 threads, 0 mismatches
# 或: [WARN] Reconcile 2026-06-13: 1 mismatch found → audit_logs + metrics

# 查看对账结果:
curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/api/internal/audit-logs?action=reconcile | jq
```

**验证点**:
- [ ] 对账完成无错误
- [ ] 不一致时 audit_logs 有记录 + Prometheus counter +1
- [ ] SC-006:一致性 ≥ 99.9%

## 开发快速切换

```bash
# Mock 模式(前端不走真实 API):
VITE_USE_MOCK=true npm run dev

# 真实模式(默认):
VITE_USE_MOCK=false npm run dev
```

## 常见问题

1. **Anthropic API key 未配置**:检查 `ANTHROPIC_API_KEY` 环境变量 → 或在 `.env.local` 设置
2. **Checkpoint 恢复失败**:检查 `langgraph` schema 是否存在 → `uv run alembic upgrade head`
3. **WS 连接失败**:检查 CORS 配置(`CORS_ALLOWED_ORIGINS`) + token 是否有效
4. **token 配额异常**:手动重置 `users.monthly_token_used = 0` → 或等 cron(每月 1 日 00:00 UTC)
