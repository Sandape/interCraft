# M16 · Resume Optimize 子图

> 状态: draft · 所属领域: E · 优先级: P1
> 引用原文档: §7.3 (resume_optimize 行)

## 1. 需求摘要

实现「**简历优化 Agent**」LangGraph 子图:基于目标 JD,对当前简历分支提出修改建议;**必须 `interrupt_after(apply_or_discard)`** 等待用户确认,确认后才落盘;落盘时通过 `save_resume_version` 工具创建新版本。这是唯一启用人类介入的子图,前端展示「待确认」对话框。

## 2. 验收标准

- [ ] `POST /api/v1/agents/resume-optimize/start` 启动(branch_id + 目标 JD)
- [ ] 节点流程:`load_branch → diff_jd → suggest_blocks → apply_or_discard(interrupt!) → snapshot`
- [ ] 在 `apply_or_discard` 节点暂停,前端 WS 收到 `interrupt` 事件,展示建议 diff
- [ ] `POST /api/v1/agents/resume-optimize/{thread_id}/confirm` 解决中断 → 子图恢复
- [ ] 中断 payload 含「建议 diff(JSON Patch)」+「应用 / 取消」二选一
- [ ] 应用 → 写 resume_blocks + 调 save_resume_version(`author_type='ai'`, `trigger='ai'`)
- [ ] 取消 → 不修改简历,标记 thread aborted
- [ ] 30 分钟无活动自动 timeout
- [ ] 集成测试:启动 → 中断 → confirm(apply) → 验证简历更新 + 版本创建
- [ ] 集成测试:启动 → 中断 → confirm(discard) → 简历未变

## 3. 依赖与被依赖关系

**强依赖**: M14(LangGraph 基建)、M06(resume_blocks 写)、M07(版本创建)、M12(悲观锁)
**弱依赖**: 无
**被以下模块依赖**: M23(前端简历编辑器)
**外部依赖**: 无

## 4. 数据模型

无新表。

**ResumeOptimizeState**:
```python
class ResumeOptimizeState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    user_id: UUID
    branch_id: UUID
    target_jd: str  # 来自 query_jd 或前端传入
    current_blocks: list[dict]  # 来自 query_branch_blocks
    proposed_patches: list[dict]  # diff_jd 节点输出
    decision: Literal["apply", "discard"] | None  # interrupt 后用户回填
```

## 5. 接口契约

**REST**:
| Method | Path | 说明 |
|---|---|---|
| POST | `/api/v1/agents/resume-optimize/start` | 启动(branch_id + target_jd 或 company+position) |
| POST | `/api/v1/agents/resume-optimize/{thread_id}/confirm` | 解决中断:`{"decision": "apply"\|"discard"}` |
| GET | `/api/v1/agents/resume-optimize/{thread_id}/state` | 状态快照 |

**WebSocket**:`agent.{thread_id}/interrupt` 事件 payload:
```json
{
  "event": "interrupt",
  "thread_id": "...",
  "graph": "resume_optimize",
  "node": "apply_or_discard",
  "data": {
    "proposed_patches": [{"op":"replace","path":"/blocks/0/content","value":"..."}],
    "summary": "AI 建议:加强项目描述、调整技能顺序"
  }
}
```

**工具使用**:
- `query_jd(company, position)`(可选,如前端未传 JD)
- `query_branch_blocks(branch_id)` 加载现有块(持锁校验)
- `save_resume_version(branch_id, snapshot, version_label)` 落盘后创建版本

## 6. 关键设计点

- **interrupt_after 配置**:
  ```python
  graph = builder.compile(
      checkpointer=checkpointer,
      interrupt_after=["apply_or_discard"],
  )
  ```
- **持锁要求**:start 时必须先 acquire lock on `resume_branch:{branch_id}`,失败返回 423
- **diff 格式**:RFC 6902 JSON Patch,前端用 `fast-json-patch` 库渲染 diff 视图
- **apply 实现**:`apply_or_discard` 节点判定 `decision==apply` → 应用 patch 到 resume_blocks → save_resume_version
- **discard 实现**:节点直接走 END,thread 标记为 aborted
- **30min timeout**:ARQ cron 巡检 `ai_conversations.status='active' AND last_event_at < now() - 30min` → mark aborted + 释放锁
- **__version__ = "1.0.0"**

## 7. 待澄清

- **[A6]** thread_id 派生 → 复用 branch_id
- 多轮优化建议(用户 reject 后是否允许「再来一版」):MVP 不支持,用户需重新 start;v1.1 加 `regenerate` 端点
- diff 粒度:块级 vs 字段级:MVP 块级(整块替换),v1.1 字段级

## 8. 实现提示

- 文件:
  - `backend/app/agents/graphs/resume_optimize.py`
  - `backend/app/agents/nodes/resume_optimize/{load_branch,diff_jd,suggest_blocks,apply_or_discard,snapshot}.py`
  - `backend/app/api/v1/agents_resume_optimize.py`
  - `backend/app/services/resume_optimize_service.py`
- 复用: M14 runtime;M06 resume_block_service;M07 resume_version_service;M12 lock_service
- 与 mockData 关系:
  - `mockData.ts:424-469` `improvementSuggestions` → 由 suggest_blocks 节点动态生成
