# Phase 5 — P1 Agent 子图扩展 (M16–M19)

Phase 4 (M14) 的 LangGraph 基础设施之上构建的 4 个独立 Agent 子图：
AI 简历优化、错题强化、能力画像诊断、通用 Coach。

## Agent 列表

| ID | Agent | Graph | Type | Interrupt |
|----|-------|-------|------|-----------|
| M16 | **Resume Optimize** | `graphs/resume_optimize.py` | StateGraph | `interrupt_after=["apply_or_discard"]` |
| M17 | **Error Coach** | `graphs/error_coach.py` | StateGraph (循环) | 无 |
| M18 | **Ability Diagnose** | `graphs/ability_diagnose.py` | StateGraph (线性) | 无 |
| M19 | **General Coach** | `graphs/general_coach.py` | StateGraph (线性) | 无 |

## 公共 API

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/agents/resume-optimize/start` | M16 启动优化 |
| POST | `/api/v1/agents/resume-optimize/{thread_id}/confirm` | M16 确认/放弃 |
| GET | `/api/v1/agents/resume-optimize/{thread_id}/state` | M16 查询状态 |
| POST | `/api/v1/agents/error-coach/start` | M17 启动强化 |
| POST | `/api/v1/agents/error-coach/{thread_id}/messages` | M17 提交回答 |
| POST | `/api/v1/agents/error-coach/{thread_id}/abort` | M17 中止 |
| GET | `/api/v1/agents/error-coach/{thread_id}/state` | M17 查询状态 |
| POST | `/api/v1/agents/general-coach/start` | M19 启动对话 |
| POST | `/api/v1/agents/general-coach/{thread_id}/messages` | M19 发送消息 |
| POST | `/api/v1/agents/general-coach/{thread_id}/close` | M19 关闭对话 |
| GET | `/api/v1/agents/general-coach/{thread_id}/state` | M19 查询状态 |
| ARQ | `diagnose_after_interview` | M18 自动触发诊断 |

## 共享基础设施

- **LLM 客户端**: 统一 `get_llm_client()` (Phase 4 M14)
- **Checkpointer**: PostgreSQL `AsyncPostgresSaver` (Phase 4 M14)
- **WS 事件协议**: `make_agent_interrupt()` / `make_agent_final()` (Phase 5 扩展)
- **共享工具**: `tools/query_resume_blocks.py`, `tools/query_error_question.py`, `tools/query_interview_score.py`

## 配置

| Agent | 配置 | 默认 |
|-------|------|------|
| M16 | LOCK_TIMEOUT | 30 min |
| M17 | MAX_CORRECT | 3 |
| M17 | SCORE_THRESHOLD | 8 |
| M18 | ARQ 重试 | 3 次 |
| M19 | 会话超时 | 2 h |

## 示例命令

```bash
# M16: 启动简历优化
curl -X POST http://localhost:8000/api/v1/agents/resume-optimize/start \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"branch_id": "...", "target_jd": "资深前端工程师"}'

# M17: 启动错题强化
curl -X POST http://localhost:8000/api/v1/agents/error-coach/start \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"error_question_id": "..."}'

# M18: 手动触发能力诊断
uv run python -m app.workers.tasks.diagnose_after_interview --session-id $SESSION_ID

# M19: 启动通用对话
curl -X POST http://localhost:8000/api/v1/agents/general-coach/start \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"initial_question": "如何准备系统设计面试"}'
```

## 目录结构

```
agents/
├── graphs/              # StateGraph 定义 (编译入口)
├── nodes/               # 节点函数 (按 agent 分组)
│   ├── resume_optimize/
│   ├── error_coach/
│   ├── ability_diagnose/
│   └── general_coach/
├── state/               # TypedDict 状态定义
├── tools/               # 共享工具
└── prompts/             # 系统提示 (按 agent 分组)
    ├── resume_optimize/
    ├── error_coach/
    ├── ability_diagnose/
    └── general_coach/
```
