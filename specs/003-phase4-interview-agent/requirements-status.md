# 003 Requirement Status

Status reconciled against code + round-2 E2E on 2026-06-22. All 26 FR and
2 SC are `done`. LangGraph interview subgraph, WS streaming, checkpointer,
ability_diagnose ARQ trigger, and 3-page frontend migration all in place.
Round-2 mock-LLM E2E (`tests/e2e/round-2/interview-mock-llm.spec.ts`) closes
the deterministic 5-round flow gap.

## User Stories

| Requirement | Summary | Status | Evidence | Notes |
|---|---|---|---|---|
| US1 | 启动 AI 模拟面试 (5 轮对话 + 报告) | done | `backend/app/agents/interview/graph.py` (intake → question_gen → score → report, 5-round loop); `backend/app/api/v1/ws/interview.py` WS streaming | — |

## Functional Requirements

| Requirement | Summary | Status | Evidence | Notes |
|---|---|---|---|---|
| FR-001 | LangGraph Interview Agent 子图 (intake → question_gen → score → report, 5 轮循环) | done | `backend/app/agents/interview/graph.py:4` | — |
| FR-002 | LangGraph checkpointer 持久化到 PostgreSQL,按 thread_id + checkpoint_ns 恢复 | done | `backend/app/agents/checkpointer.py` | — |
| FR-003 | 统一 LLM 客户端 (速率限制 / 重试 3 次指数退避 / 结构化日志) | done | `backend/app/agents/llm_client.py` | — |
| FR-004 | 节点执行前预扣 token 配额,超出抛 `QuotaExceededError` | done | `backend/app/agents/llm_client.py` + `users.monthly_token_used` / `monthly_token_quota` | — |
| FR-005 | 集中收集 token 用量 / 缓存命中 / 失败率 → Prometheus | done | `backend/app/agents/` metrics + `/metrics` endpoint | — |
| FR-010 | 文字面试模式,WS 流式输出 | done | `backend/app/api/v1/ws/interview.py` | — |
| FR-011 | intake 节点收集岗位/公司/简历/难度 | done | `backend/app/agents/interview/nodes/intake.py` | — |
| FR-012 | question_gen 基于简历+岗位生成问题,带 dimension + difficulty | done | `backend/app/agents/interview/nodes/` question_gen node | — |
| FR-013 | score 节点 0-10 评分 + feedback_json (维度子项 + 评语) | done | `backend/app/agents/interview/nodes/score.py` | — |
| FR-014 | report 节点汇总 (overall/per_question/dimension/strengths/improvements/summary_md) | done | `backend/app/agents/interview/nodes/` report node | — |
| FR-015 | report 完成后同步写 `interview_reports` + 异步触发 ability_diagnose | done | `backend/app/modules/interviews/service.py:21,304` `sync_ability_dimensions`; `backend/app/workers/tasks/diagnose_after_interview.py` | — |
| FR-016 | WS 推送 node.started / token.delta / node.completed / error | done | `backend/app/api/v1/ws/interview.py:10,28-29` `make_node_started` / `make_token_delta` | — |
| FR-020 | 创建面试 session (user_id/position/company/mode/branch_id) + 初始化 thread | done | `backend/app/modules/interviews/api.py:53`; `service.py` create | — |
| FR-021 | 从 checkpoint 恢复中断面试,通过 last_seen_checkpoint_id | done | `backend/app/modules/interviews/service.py:336,354` | — |
| FR-022 | session 状态机 (pending/in_progress/completed/expired) | done | `backend/app/modules/interviews/models.py` + service transitions | — |
| FR-023 | session 完成后记录 duration_sec | done | `backend/app/modules/interviews/models.py` `duration_sec` field | — |
| FR-024 | report 完成后异步触发 ability_diagnose (ARQ) + 失败重试 3 次 | done | `backend/app/workers/tasks/diagnose_after_interview.py`; `backend/app/agents/graphs/ability_diagnose.py` | — |
| FR-030 | LLM 调用元数据写入 `ai_messages` 表 (双源) | done | `backend/app/agents/` ai_messages writes | — |
| FR-031 | 每日对账任务 ai_messages ↔ checkpoints | done | `backend/app/modules/audit/` reconciliation + `backend/app/api/v1/internal.py:87` | — |
| FR-032 | 关键节点结构化日志 (request_id/session_id/node_name/duration_ms/result) | done | `backend/app/agents/` structlog calls | — |
| FR-033 | Prometheus 指标 (interview_started/completed/failed_total + node_duration + token_consumed) | done | `backend/app/agents/` metrics + `/metrics` | — |
| FR-040 | InterviewList 切真实 API (`GET /interview-sessions`) | done | `src/pages/InterviewList.tsx:25,27,37` `useInterviewSessions` | — |
| FR-041 | InterviewLive: WS 流式 + 节点状态机 UI + 文字输入 + 进度指示器 | done | `src/pages/InterviewLive.tsx` | — |
| FR-042 | InterviewReport 切真实 API (`GET /interview-sessions/{id}/report`) | done | `src/pages/InterviewReport.tsx:28-29,37` `useQuery` | — |
| FR-043 | WS 客户端完整版 (自动重连指数退避 1s/2s/4s/8s/16s max 5 次 + last_seen_checkpoint_id) | done | `src/pages/InterviewLive.tsx` WS client | — |
| FR-044 | `VITE_USE_MOCK=false` 时三个面试页面完整可用 | done | All three pages use real API hooks | — |

## Success Criteria

| Requirement | Summary | Status | Evidence | Notes |
|---|---|---|---|---|
| SC-001 | SC-002 10 分钟走通 start → 5 轮 → 报告 → 画像刷新 | done | `tests/e2e/round-2/interview-mock-llm.spec.ts` MOCK-01/02/02b/03 (4/4 pass on chromium) | — |
| SC-002 | 断线重连无重复 token | done | `InterviewLive.tsx` WS reconnect + `last_seen_checkpoint_id` | — |

## Status Roll-up

- Total: 1 US + 26 FR + 2 SC = 29 rows.
- `done`: 29 rows.
- Feature 003 is complete; no remaining work.
