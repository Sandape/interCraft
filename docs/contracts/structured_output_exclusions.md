# Structured Output Exclusions

This document lists LLM-producing Agent tasks that are **excluded** from
structured-output enforcement (`with_structured_output` + Pydantic contract
validation). See `backend/app/agents/structured_output/registry.py` for the
canonical source of truth.

| node_id | kind | exclusion_reason |
|---|---|---|
| error_coach.hint_ladder | free_form | 用户可见中文提示文本，不被业务逻辑作为结构化数据消费。 |
| general_coach.respond | free_form | 用户可见中文回复文本，不被业务逻辑作为结构化数据消费。 |
| interview.question_gen | deferred | 输出仍被后续面试流程消费，但迁移不在 US4 范围内。 |
| interview.report | deferred | 输出仍被后续报告渲染流程消费，但迁移不在 US4 范围内。 |
| general_coach.intent | deferred | 输出仍被后续意图路由消费，但迁移不在 US4 范围内。 |
| resume_optimize.diff_jd | deferred | 输出仍被后续 JD 比对流程消费，但迁移不在 US4 范围内。 |
| resume_optimize.suggest_blocks | deferred | 输出仍被后续推荐流程消费，但迁移不在 US4 范围内。 |
| ability_diagnose.generate_insight | deferred | 输出仍被后续洞察分析流程消费，但迁移不在 US4 范围内。 |
