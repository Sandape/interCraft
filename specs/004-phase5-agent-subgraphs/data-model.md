# Phase 5 Data Model: Agent 子图状态 & 消息扩展

**Date**: 2026-06-15 | **Spec**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md)

Phase 5 不涉及新数据库表。所有 Agent 子图的运行时状态通过 LangGraph checkpoints 持久化(PostgreSQL `langgraph` schema,沿用 Phase 4)。以下为每个子图的 GraphState TypedDict 定义。

---

## M16 · ResumeOptimizeState

```python
class ResumeOptimizeState(TypedDict):
    """简历优化 Agent 运行时状态。"""
    messages: Annotated[list[BaseMessage], add_messages]
    user_id: UUID                              # 用户 ID
    branch_id: UUID                            # 目标简历分支 ID
    target_jd: str                             # 目标 JD 文本(来自前端传入或 query_jd 工具)
    current_blocks: list[dict]                 # 当前分支的 blocks 快照(来自 query_branch_blocks)
    proposed_patches: list[dict]               # diff_jd 节点输出的 JSON Patch 数组
    summary: str | None                        # 优化建议的文字摘要
    decision: Literal["apply", "discard"] | None  # interrupt 后用户选择(confirm 端点回填)
    thread_aborted: bool                       # 是否被标记为 aborted(超时/用户取消)
```

**生命周期**: `start` → `load_branch` → `diff_jd` → `suggest_blocks` → `apply_or_discard(interrupt!)` → `snapshot` → END

**持久化**: LangGraph checkpointer(PostgreSQL `langgraph` schema),每个节点执行后自动保存 checkpoint。`interrupt_after(["apply_or_discard"])` 在 interrupt 点保存。

---

## M17 · ErrorCoachState

```python
class ErrorCoachState(TypedDict):
    """错题强化 Agent 运行时状态。"""
    messages: Annotated[list[BaseMessage], add_messages]
    user_id: UUID                              # 用户 ID
    error_question_id: UUID                    # 错题 ID
    question: dict                             # 错题完整记录(来自 query_error_question_by_id)
    correct_count: int                         # 累计答对次数(阈值 ≥ 3)
    attempt_count: int                         # 当前 session 尝试次数
    current_hint_level: Literal["small", "medium", "detailed"]  # 当前提示等级
    session_aborted: bool                      # 是否被用户主动终止
```

**生命周期**: `start` → `fetch_question` → `hint_ladder` → 循环 {`wait_user` → `evaluate` → `loop_or_finish`} → END(correct_count ≥ 3 或 aborted)

**持久化**: LangGraph checkpointer。答对次数通过 M08 `recall` 接口实时持久化到 `error_questions.frequency`(不依赖 checkpoint 恢复)。

---

## M18 · AbilityDiagnoseState

```python
class AbilityDiagnoseState(TypedDict):
    """能力诊断 Agent 运行时状态。"""
    messages: Annotated[list[BaseMessage], add_messages]
    user_id: UUID                              # 用户 ID
    session_id: UUID                           # 面试 session ID(触发源)
    interview_scores: list[dict]               # aggregate_scores 节点输出:每维度加权分
    historical_dims: list[dict]                # compare_baseline 读取的近 90 天历史基线
    current_dims: list[dict]                   # query_dimensions 读取的当前能力值
    diagnoses: list[dict]                      # 诊断结果:每维度的 delta + 趋势标记
    insights: list[dict]                       # generate_insight LLM 输出的改进建议
```

**生命周期**: ARQ `diagnose_after_interview` → `aggregate_scores` → `compare_baseline` → `generate_insight` → `update_dimensions` → END

**持久化**: LangGraph checkpointer。最终结果写入 `ability_dimensions.actual`(M09 表)+ `ability_dimensions_history` + `activities`。

---

## M19 · GeneralCoachState

```python
class GeneralCoachState(TypedDict):
    """通用辅导 Agent 运行时状态。"""
    messages: Annotated[list[BaseMessage], add_messages]
    user_id: UUID                              # 用户 ID
    conversation_id: UUID                      # 对话 ID(= thread_id)
    detected_intent: str | None                # intent 节点输出:resume_optimize / interview_practice / career_advice / chitchat
    confidence: float | None                   # LLM 自报置信度(0-1)
    suggested_redirect: str | None             # route 节点:引导跳转的目标子图名
    session_active: bool                       # 对话是否活跃
```

**生命周期**: `start` → `intent` → `route` → `respond`(或引导跳转) → 循环 {用户消息 → 追加回答} → `close` → END

**持久化**: LangGraph checkpointer。对话历史不写入业务表(仅 `ai_messages` 审计)。

---

## 已有表扩展

Phase 5 不修改现有表结构,仅新增以下数据写入路径:

| 表 | 现有模块 | Phase 5 新增写入 |
|---|---|---|
| `ai_messages` | Phase 4 M15 | M16/M17/M18/M19 的 LLM 调用元数据 |
| `ability_dimensions` | Phase 2 M09 | M18 更新 `actual` 分数 |
| `ability_dimensions_history` | Phase 2 M09 | M18 追加历史快照 |
| `activities` | Phase 2 M10 | M18 写入 `ability.suggestion` 类型活动 |
| `error_questions` | Phase 2 M08 | M17 递减 `frequency`(调 recall 接口) |
| `resume_blocks` | Phase 1 M06 | M16 应用 JSON Patch(apply 决策时) |
| `resume_versions` | Phase 1 M07 | M16 创建 AI 优化版本 |
| `audit_logs` | Phase 4 M22 | M16/M17/M18/M19 关键事件 |
| `ai_conversations` | Phase 4 M14 | M16/M17/M19 的 Agent 会话记录 |
