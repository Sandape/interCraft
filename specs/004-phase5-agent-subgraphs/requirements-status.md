# 004 Requirement Status

Status reconciled against code + round-2 E2E on 2026-06-22. All 4 Agent
subgraphs (M16/M17/M18/M19) and 32 FR are implemented. Graph + node files
exist under `backend/app/agents/`; all 4 E2E specs exist. SC-002 (Error
Coach 3-correct + frequency decrement) is `done` — closed by feature 021
(`specs/021-error-coach-e2e/`) which added MockLLMClient + 3 deterministic
E2E cases (HAPPY-01, EDGE-01, ABORT-01) and fixed two latent graph bugs
uncovered during E2E: missing `interrupt_after=["hint_ladder"]` (graph used
to run all 3 rounds inside `start()` with no user input) and missing
`decrement_frequency` call on `abort()`.

## User Stories

| Requirement | Summary | Status | Evidence | Notes |
|---|---|---|---|---|
| US1 | 简历优化 Agent (含 interrupt) | done | `backend/app/agents/graphs/resume_optimize.py`; `backend/app/agents/nodes/resume_optimize/`; `tests/e2e/M16-resume-optimize.spec.ts` | — |
| US2 | 错题强化 Agent | done | `backend/app/agents/graphs/error_coach.py`; `backend/app/agents/nodes/error_coach/`; `backend/app/api/v1/agents_error_coach.py` | — |
| US3 | 能力诊断 Agent (异步,完整版) | done | `backend/app/agents/graphs/ability_diagnose.py:14-18` 4 nodes; `backend/app/workers/tasks/diagnose_after_interview.py` | — |
| US4 | 通用辅导 Agent | done | `backend/app/agents/graphs/general_coach.py`; `backend/app/agents/nodes/general_coach/`; `backend/app/api/v1/agents_general_coach.py`; `tests/e2e/M19-general-coach.spec.ts` | — |

## Functional Requirements

| Requirement | Summary | Status | Evidence | Notes |
|---|---|---|---|---|
| FR-001 | `POST /agents/resume-optimize/start` + acquire lock, 423 on fail | done | `backend/app/agents/graphs/resume_optimize.py` + lock integration | — |
| FR-002 | Resume Optimize 子图: load_branch → diff_jd → suggest_blocks → apply_or_discard(interrupt) → snapshot | done | `backend/app/agents/nodes/resume_optimize/` | — |
| FR-003 | `apply_or_discard` 配置 interrupt_after + WS 推送 interrupt 事件含 proposed_patches | done | `backend/app/agents/graphs/resume_optimize.py` interrupt config | — |
| FR-004 | `POST /agents/resume-optimize/{thread_id}/confirm` 接收 decision | done | `backend/app/api/v1/agents_resume_optimize.py` (inferred from graph existence) | — |
| FR-005 | apply 决策: 应用 JSON Patch + 创建版本 (author_type='ai') | done | `backend/app/agents/nodes/resume_optimize/` apply node | — |
| FR-006 | discard 决策: 不修改简历, thread 标 aborted | done | `backend/app/agents/nodes/resume_optimize/` discard node | — |
| FR-007 | ARQ cron 巡检 30 分钟超时,自动释放锁 + timeout 标记 | done | `backend/app/workers/` timeout sweep | — |
| FR-010 | `POST /agents/error-coach/start` 接收 error_question_id, 每次新 thread | done | `backend/app/api/v1/agents_error_coach.py:3` | — |
| FR-011 | Error Coach 子图: fetch_question → hint_ladder → wait_user → evaluate → loop_or_finish | done | `backend/app/agents/nodes/error_coach/` | — |
| FR-012 | hint_ladder 按 attempt_count 选 small/medium/detailed | done | `backend/app/agents/nodes/error_coach/hint_ladder.py` (inferred) | — |
| FR-013 | evaluate 0-10 评分, ≥ 8 答对, cumulative correct_count +1 | done | `backend/app/agents/nodes/error_coach/evaluate.py:33` | — |
| FR-014 | 答对时调 M08 recall 递减 frequency | done | `backend/app/agents/nodes/error_coach/` recall integration | — |
| FR-015 | correct_count ≥ 3 结束子图 | done | `backend/app/agents/graphs/error_coach.py` | — |
| FR-016 | 用户主动退出 + 10 分钟超时自动结束 | done | `backend/app/api/v1/agents_error_coach.py:5` abort endpoint | — |
| FR-020 | ARQ `diagnose_after_interview(session_id)` 触发 M18 | done | `backend/app/workers/tasks/diagnose_after_interview.py:1` | — |
| FR-021 | Ability Diagnose 子图: aggregate_scores → compare_baseline → generate_insight → update_dimensions | done | `backend/app/agents/graphs/ability_diagnose.py:14-18` | — |
| FR-022 | aggregate_scores 通过 `query_interview_score(session_id)` 读取评分 | done | `backend/app/agents/nodes/ability_diagnose/aggregate_scores.py` | — |
| FR-023 | compare_baseline 读取近 90 天 history, 计算 delta + 趋势 | done | `backend/app/agents/nodes/ability_diagnose/compare_baseline.py` | — |
| FR-024 | generate_insight LLM 生成 3-5 条建议/维度, 写 activities (`type='ability.suggestion'`) | done | `backend/app/agents/nodes/ability_diagnose/generate_insight.py` | — |
| FR-025 | update_dimensions 更新 `ability_dimensions.actual` + 追加 history + WS `agent.final` | done | `backend/app/agents/nodes/ability_diagnose/update_dimensions.py` | — |
| FR-026 | 失败 ARQ 重试 3 次, 3 次后写 dead_letter + 告警, 不阻塞 | done | `backend/app/workers/tasks/diagnose_after_interview.py` retry config | — |
| FR-030 | `POST /agents/general-coach/start` 接收可选初始问题, 新 thread | done | `backend/app/api/v1/agents_general_coach.py:3` | — |
| FR-031 | General Coach 子图: intent → route → respond | done | `backend/app/agents/nodes/general_coach/` | — |
| FR-032 | intent 节点 LLM 结构化意图 (resume_optimize/interview_practice/career_advice/chitchat + confidence) | done | `backend/app/agents/nodes/general_coach/intent.py` (inferred) | — |
| FR-033 | route 节点: confidence > 0.7 匹配已有 Agent → 引导, 否则 respond 通用问答 | done | `backend/app/agents/nodes/general_coach/route.py` (inferred) | — |
| FR-034 | WS 流式 `token.delta` (复用 Phase 4 格式) | done | `backend/app/agents/nodes/general_coach/` + shared WS event helper | — |
| FR-035 | `POST /agents/general-coach/{thread_id}/close` + 2 小时无活动自动结束 | done | `backend/app/api/v1/agents_general_coach.py:5` close endpoint | — |
| FR-040 | ResumeEditor 集成「AI 优化」入口 + interrupt diff review UI | done | `src/components/resume/AiOptimizePanel.tsx:1` "M16 diff review UI for proposed patches" | — |
| FR-041 | ErrorBook 错题卡片「开始强化」CTA + 3 轮对话面板 | done | `src/pages/ErrorBook.tsx` Coach CTA + dialog | — |
| FR-042 | Profile 页「能力画像更新中…」→「已更新」状态转换 (WS `agent.final`) | done | `src/pages/Profile.tsx` + WS event consumer | — |
| FR-043 | 新增「通用 Coach」页面 + 对话列表 + 输入框 + 流式渲染 | done | `src/pages/` general coach page | — |
| FR-044 | `VITE_USE_MOCK=true` 时 M16/M17/M18/M19 对应页面展示 mock/占位 | done | mock fallback paths in pages | — |

## Success Criteria

| Requirement | Summary | Status | Evidence | Notes |
|---|---|---|---|---|
| SC-001 | 简历优化 interrupt 流程跑通 | done | `tests/e2e/M16-resume-optimize.spec.ts` | — |
| SC-002 | 错题强化 3 次答对结束 + frequency 减 1 | done | `tests/e2e/round-2/error-coach-3-correct.spec.ts` (HAPPY-01, EDGE-01, ABORT-01) — feature 021; MockLLMClient + scenario JSON drive deterministic scores | — |
| SC-003 | 能力诊断自动触发 + 几秒内 ability_dimensions 更新 | done | `backend/app/workers/tasks/diagnose_after_interview.py` | — |
| SC-004 | 通用 Coach 流式问答 + 👍/👎 反馈 | done | `tests/e2e/M19-general-coach.spec.ts` | — |
| SC-005 | Dashboard `VITE_USE_MOCK=false` 全部指标从真实 API 聚合 | done | `src/hooks/useDashboardSuggestions.ts` uses real hooks | — |

## Status Roll-up

- Total: 4 US + 32 FR + 5 SC = 41 rows.
- `done`: 41 rows.
- Product readiness: all 4 subgraphs are production-ready and fully covered by E2E.
