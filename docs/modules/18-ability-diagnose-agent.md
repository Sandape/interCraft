# M18 · Ability Diagnose 子图(异步)

> 状态: draft · 所属领域: E · 优先级: P1
> 引用原文档: §7.3 (ability_diagnose 行), §7.4

## 1. 需求摘要

实现「**能力诊断 Agent**」LangGraph 子图:**面试结束时由 ARQ 异步触发**,基于面试 session 的评分聚合 + 历史数据对比,产出能力维度更新与改进建议。子图与 Interview 子图**完全独立**,通过业务表中转数据(参见 A5)。

## 2. 验收标准

- [ ] ARQ 任务 `diagnose_after_interview(session_id)` 触发后启动子图
- [ ] 节点流程:`aggregate_scores → compare_baseline → generate_insight → update_dimensions`
- [ ] 子图通过工具读取数据:`query_interview_score(session_id)` / `query_history(user_id, dim)` / `query_dimensions(user_id)`
- [ ] 输出:更新 ability_dimensions.actual + 追加 ability_history(M09 接入)
- [ ] 生成的改进建议写入 activities(`type='ability.suggestion'`)
- [ ] 完成后推 WS `agent.{thread_id}/final` 含 summary
- [ ] 失败 → ARQ 重试 3 次,超出后告警
- [ ] 单元测试:输入指定 session → 验证 dimensions 更新值

## 3. 依赖与被依赖关系

**强依赖**: M14(LangGraph 基建)、M11(读 session)、M09(写 dimensions / history)、M10(写 activities)、M15(被触发)
**弱依赖**: 无
**被以下模块依赖**: M23(前端 Profile 页能力曲线)
**外部依赖**: 无

## 4. 数据模型

无新表。

**AbilityDiagnoseState**:
```python
class AbilityDiagnoseState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    user_id: UUID
    session_id: UUID
    interview_scores: list[dict]  # 来自 query_interview_score
    historical_dims: list[dict]  # 来自 query_history
    current_dims: list[dict]  # 来自 query_dimensions
    diagnoses: list[dict]  # 节点输出
    insights: list[str]  # 建议
```

## 5. 接口契约

**REST**: 无对外端点(纯异步任务)
**ARQ 任务**:
```python
@worker_task
async def diagnose_after_interview(ctx, session_id: UUID):
    """M15 报告生成后触发"""
```

**WebSocket**: 子图本身有 `agent.{thread_id}` 频道,前端可订阅查看进度;也可仅订阅 final 事件做 UI 提示

**工具(新增,见 A5)**:
- `query_interview_score(session_id) → list[QuestionScore]` 从 ai_messages / interview_reports 读取
- `query_history(user_id, dim, days=90) → list[AbilityHistoryOut]`
- `query_dimensions(user_id) → list[AbilityDimensionOut]`

## 6. 关键设计点

- **触发来源**:仅 M15 `report` 节点完成时 `arq_pool.enqueue_job('diagnose_after_interview', session_id)`
- **不传业务数据**(A5):ARQ job 只传 session_id,子图通过工具从业务表加载
- **thread_id 派生**:`f"{session_id}::diagnose"`(A6)
- **结果存盘流程**:
  1. `update_dimensions` 节点 → 调 M09 `record_score(user_id, key, score, source='ai_diagnose', source_id=session_id)`
  2. 写 activities:`activity_service.record_activity(user_id, type='ability.updated', title='能力画像已更新', detail='...')`
  3. WS 推 `final` 事件
- **失败重试**:ARQ 自带重试机制,默认 3 次指数退避;3 次后写入 `dead_letter` 表(M22 监控)
- **运行时长容忍**:Agent 异步运行,可容忍 30s-2min,无需流式 UI(前端展示「分析中」骨架)
- **__version__ = "1.0.0"**

## 7. 待澄清

- **[A5]** 子图间数据传递 → 通过 query_* 工具
- **[A15]** 面试报告 vs 能力画像写入时序 → 报告同步、画像异步
- 异步任务可观测:M22 接入失败告警

## 8. 实现提示

- 文件:
  - `backend/app/agents/graphs/ability_diagnose.py`
  - `backend/app/agents/nodes/ability_diagnose/{aggregate_scores,compare_baseline,generate_insight,update_dimensions}.py`
  - `backend/app/agents/tools/query_interview_score.py`(新)
  - `backend/app/workers/tasks/diagnose_after_interview.py`
- 复用: M14 runtime;M09 ability_service;M10 activity_service;M11 interview_service
- 与 mockData 关系:`mockData.ts:424-469` `improvementSuggestions` → 部分内容由本子图生成
