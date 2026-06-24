# Contract: AI Optimize (Enhanced)

**Feature**: 027-resume-center-muji-alignment

AI 优化增强契约：真轮询、per-patch 接受拒绝、diff 视图、确认对话框。

## 端点

### 1. 启动优化 `POST /api/v1/agents/resume-optimize/start`

（不变）请求 `{ branch_id, jd_text }`，响应 `{ thread_id, status: 'starting' }`。

### 2. 轮询状态 `GET /api/v1/agents/resume-optimize/:threadId/state`（增强）

**响应扩展**：

```json
{
  "thread_id": "...",
  "status": "waiting_interrupt",
  "proposed_patches": [
    {
      "path": "blocks[2].content_md",
      "op": "replace",
      "value": "优化后的内容...",
      "old_value": "原始内容...",      // 【新增】用于 diff 展示
      "block_id": "block-uuid",          // 【新增】目标 block 标识
      "block_title": "字节跳动 · 高级前端"  // 【新增】人类可读标题
    }
  ],
  "summary": "共建议 3 项优化...",
  "model_usage": { "tokens": 1234 }      // 【新增】token 用量
}
```

**状态值**:
- `starting` — 正在创建 thread
- `running` — LangGraph 执行中
- `waiting_interrupt` — 等待用户确认（显示 patch 列表）
- `applying` — 正在应用 patch
- `done` — 完成（新版本已创建）
- `error` — 失败
- `timeout` — 超时（前端检测，非后端状态）

### 3. 应用选中 patch `POST /api/v1/agents/resume-optimize/:threadId/confirm`（增强）

**请求变更**：

```json
{
  "decision": "apply",
  "accepted_patches": ["blocks[2].content_md", "blocks[5].content_md"]  // 【新增】接受的 patch path 列表
}
```

**变更**:
- 旧：`{ decision: 'apply' | 'discard' }` — 全量应用或全量放弃
- 新：`{ decision: 'apply', accepted_patches: string[] }` — 只应用 `accepted_patches` 列表中的 patch
- `decision: 'discard'` 仍支持（放弃全部）

**响应**:
```json
{
  "status": "done",
  "new_version_id": "...",
  "version_no": 5,
  "applied_count": 2,
  "skipped_count": 1
}
```

### 4. 版本 diff `GET /api/v1/resume-branches/:branchId/versions/:v1/diff/:v2`（新增）

**请求**: 路径参数 `branchId` / `v1` / `v2`（版本号）

**响应**:

```json
{
  "from_version": 3,
  "to_version": 5,
  "diffs": [
    {
      "type": "modify",
      "block_id": "block-uuid",
      "block_title": "字节跳动 · 高级前端",
      "old_content_md": "...",
      "new_content_md": "...",
      "line_diff": [
        { "type": "context", "text": "..." },
        { "type": "add", "text": "新增的行" },
        { "type": "remove", "text": "删除的行" }
      ]
    },
    {
      "type": "add",
      "block_id": "block-uuid-2",
      "block_title": "新模块",
      "new_content_md": "..."
    },
    {
      "type": "remove",
      "block_id": "block-uuid-3",
      "block_title": "已删除模块",
      "old_content_md": "..."
    }
  ],
  "summary": {
    "added": 1,
    "removed": 1,
    "modified": 1
  }
}
```

**算法**:
- 按 `block.type + block.title` 匹配（LCS）
- 未匹配的旧 block → `remove`
- 未匹配的新 block → `add`
- 匹配的 block 对比 `content_md`，不同则 `modify`（用 `diff` 库算行级 diff）

## 前端轮询契约

`useResumeOptimize` hook 状态机：

```
idle → starting → polling (指数退避) → waiting_patches → applying → done
                                    ↓ 60s
                                  timeout
                                    ↓ error
                                   error → retry → polling
```

**轮询间隔**: `[1000, 2000, 4000, 8000, 16000, 32000]` ms（6 次，总 63s）

**停止条件**:
- `status === 'waiting_interrupt'` → 停止轮询，显示 patch 列表
- `status === 'done'` → 停止轮询，显示成功
- `status === 'error'` → 停止轮询，显示错误 + 重试
- 总时长 > 60s → 标记 `timeout`，显示超时 + 重试

**恢复轮询**（FR-036）: 用户切换页面后返回，若 thread 未结束，从当前状态恢复轮询（基于 thread_id 查询后端状态）。

## 安全

- JD 文本长度 ≤ 10KB
- patch 数量 ≤ 50（防 LLM 输出爆炸）
- `accepted_patches` 中的 path 必须在 `proposed_patches` 列表中（防注入）
- 用户只能对自己的 branch 的 thread 操作（`user_id` 校验）

## 测试契约

- MockLLMClient 返回确定性 patch（复用 021 模式）
- E2E 测试覆盖：轮询成功 / 超时 / 错误重试 / per-patch 接受拒绝 / diff 展示
