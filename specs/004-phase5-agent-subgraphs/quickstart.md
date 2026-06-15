# Phase 5 Quickstart: P1 Agent 子图扩展

**Date**: 2026-06-15 | **Spec**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md)

## Prerequisites

- Phase 1-4 全部基础设施已部署并运行(PostgreSQL 15 + Redis 7 + FastAPI + Vite dev server)
- Phase 4 M14 LangGraph 基础设施已落地(统一 LLM 客户端 + checkpointer + WS 事件协议)
- Phase 1-2 业务表已创建(migrations 0001-0003)
- `VITE_USE_MOCK=false` 以验证真实 API

## Setup

```bash
# 后端:安装依赖(Phase 4 已包含,无新增)
cd backend && uv sync

# 前端:安装依赖(无新增)
cd frontend && npm install

# 数据库:Phase 5 无新 migration

# 启动后端
cd backend && uvicorn app.main:app --reload --port 8000

# 启动前端
cd frontend && npm run dev -- --port 5173
```

## Validation Scenarios

### Scenario 1: M16 Resume Optimize — 简历 AI 优化

**Objective**: 验证简历优化 Agent 启动 → interrupt → apply 完整流程。

**Steps**:
1. 登录系统,进入简历编辑器
2. 选择某个简历分支
3. 点击「AI 优化」按钮,输入目标 JD(`target_jd` 或 `company` + `position`)
4. 等待 Agent 分析(5-15 秒),观察 WS `interrupt` 事件
5. 在前端审阅 proposed_patches diff(内联 before/after)
6. 点击「应用」调用 confirm 端点
7. 验证:
   - 简历分支内容已更新(JSON Patch 已应用)
   - 版本历史中出现 AI 优化记录(author_type='ai', trigger='ai')
   - 分支锁已释放(其他端可编辑)

**CLI alternative**:
```bash
# 启动
curl -X POST http://localhost:8000/api/v1/agents/resume-optimize/start \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"branch_id": "$BRANCH_ID", "target_jd": "资深前端工程师,5年React经验..."}'

# 获取状态
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/api/v1/agents/resume-optimize/$THREAD_ID/state

# confirm(apply)
curl -X POST http://localhost:8000/api/v1/agents/resume-optimize/$THREAD_ID/confirm \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"decision": "apply"}'
```

---

### Scenario 2: M18 Ability Diagnose — 面试后能力诊断

**Objective**: 验证面试完成后能力诊断自动触发,Profile 页看到更新。

**Steps**:
1. 完成一场模拟面试(Phase 4 完整流程)
2. 等待 10-30 秒(ARQ 任务调度 + 子图执行)
3. 进入 Profile 页面
4. 验证:
   - 能力雷达图分数已更新(6 维度)
   - 改进建议清单出现(3-5 条/维度)
   - 活动流中出现「能力画像已更新」记录
   - 能力维度历史曲线可用

**ARQ manual trigger**:
```bash
# 手动触发诊断(用于调试)
uv run python -m app.workers.tasks.diagnose_after_interview --session-id $SESSION_ID
```

---

### Scenario 3: M17 Error Coach — 错题强化

**Objective**: 验证错题强化 Agent 3 轮梯度提示完整流程。

**Steps**:
1. 进入错题本,选择某道错题(frequency > 0)
2. 点击「开始强化」
3. 第 1 轮看到提示(easy),输入回答
4. 观察评分反馈(基于 0-10 分制,≥ 8 答对)
5. 累计答对 3 次后,子图自动结束
6. 验证:
   - 错题 frequency 已递减
   - 如果 frequency=0,状态变更为「已掌握」
   - 可重复强化同一题

**CLI alternative**:
```bash
# 启动
curl -X POST http://localhost:8000/api/v1/agents/error-coach/start \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"error_question_id": "$QUESTION_ID"}'

# 提交回答
curl -X POST http://localhost:8000/api/v1/agents/error-coach/$THREAD_ID/messages \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"content": "我的理解是..."}'
```

---

### Scenario 4: M19 General Coach — 通用辅导

**Objective**: 验证通用 Coach 意图分类与回答。

**Steps**:
1. 进入通用 Coach 页面
2. 输入「如何准备系统设计面试」
3. 验证 WS 流式回答逐字呈现,意图识别为 `career_advice`
4. 输入「帮我优化简历中的项目描述」
5. 验证意图识别为 `resume_optimize`,Agent 给出跳转引导
6. 关闭对话

**CLI alternative**:
```bash
# 启动
curl -X POST http://localhost:8000/api/v1/agents/general-coach/start \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"initial_question": "如何准备系统设计面试"}'

# 发送消息
curl -X POST http://localhost:8000/api/v1/agents/general-coach/$THREAD_ID/messages \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"content": "React 动画有哪些方案"}'

# 关闭
curl -X POST http://localhost:8000/api/v1/agents/general-coach/$THREAD_ID/close \
  -H "Authorization: Bearer $TOKEN"
```

---

## Mock Mode

```bash
# 前端使用 mock 数据运行
VITE_USE_MOCK=true npm run dev

# Phase 5 mock 数据:
# - M16: 预设 1 组 proposed_patches 演示数据,模拟 interrupt
# - M17: 预设 1 道错题 + 3 轮预置对话
# - M18: 预设 6 维度诊断结果,模拟 agent.final 事件
# - M19: 预设意图分类和回答,模拟 WS 流式
```

## Verification Checklist

- [ ] M16: 简历优化 start → interrupt → confirm(apply) → 内容更新 + 版本创建
- [ ] M16: confirm(discard) → 内容不变 + thread aborted
- [ ] M16: 锁冲突时返回 423
- [ ] M16: 30 分钟超时自动释放锁
- [ ] M18: 面试完成后 30 秒内能力画像自动更新
- [ ] M18: 改进建议写入 activities
- [ ] M18: 失败后 ARQ 重试 3 次
- [ ] M17: 3 轮答对后 frequency 递减
- [ ] M17: 10 分钟超时自动结束
- [ ] M17: 评分使用 0-10 分制,≥ 8 答对
- [ ] M19: 意图分类正确(resume_optimize / career_advice / chitchat)
- [ ] M19: WS 流式 token 渲染
- [ ] M19: 2 小时无活动自动结束
- [ ] 前端 `VITE_USE_MOCK=true` 下 4 个子图均可独立演示
- [ ] 4 个子图 LLM 调用走统一客户端(复用 M14),配额不超额
