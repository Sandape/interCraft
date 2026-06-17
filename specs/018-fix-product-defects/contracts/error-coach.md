# Contract: Error Coach（启动反馈 + 新增自动选中）

**Spec refs**: FR-016 / FR-017 / FR-018 / SC-006 / SC-009
**Defects**: #10 错题 Coach 无反馈 / #11 新增错题未自动选中
**Decisions**: R-003 / R-013

---

## A. Coach 启动反馈循环（缺陷 #10 / FR-016 / FR-017）

### 后端契约（已存在）

```text
POST /api/v1/agents/error-coach/start
  Body: { error_question_id: UUID }
  Response 200: { thread_id: UUID, status: "starting" }

GET /api/v1/agents/error-coach/{thread_id}/state
  Response 200: {
    thread_id: UUID,
    status: "starting" | "running" | "awaiting_answer" | "done" | "error",
    last_question?: { id, content, dimension_key },
    error?: { code, message }
  }
```

**已存在**：`backend/app/api/v1/agents_error_coach.py:18,70,139`。

### 前端契约

```ts
// src/hooks/useErrorCoach.ts
function useErrorCoach(errorQuestionId: UUID) {
  // 1. start: 调 POST /start，保存 thread_id
  const start = useMutation({
    mutationFn: () => startCoach(errorQuestionId),
    onSuccess: ({ thread_id }) => setThreadId(thread_id),
  })

  // 2. poll: 用 React Query 轮询 /state
  const state = useQuery({
    queryKey: ['error-coach', threadId],
    queryFn: () => getCoachState(threadId!),
    enabled: !!threadId && start.isSuccess,
    refetchInterval: (q) => {
      const s = q.state.data?.status
      return s === 'done' || s === 'error' ? false : 1500
    },
  })

  return { start, state, isStarting: state.isLoading || state.data?.status === 'starting' }
}
```

### UI 反馈时序

```text
t=0    user 点击「开始强化」
t<1s   显示 loading: 「正在启动强化辅导…」
t<2s   收到 state.status=running → 切到第一道题
t<2s   若 status=error → 显示「启动失败，请重试」+ 保留按钮
       5s 内必须有 loading / error / first-question 之一（SC-006）
```

### 错误处理

```ts
// src/lib/apiErrorToMessage.ts (与 export 共享)
case 'COACH_UNAVAILABLE': return '强化辅导服务暂不可用，请稍后重试'
case 'COACH_TIMEOUT':     return '启动超时，请检查网络后重试'
default:                  return '启动失败，请重试'
```

### 日志契约（结构化）

```text
后端：start 失败 → log.error("error_coach.start.fail", request_id, error_code, error_message, error_question_id)
前端：state.status=error → console.error("[error-coach] start failed", { requestId, code, message })
```

---

## B. 新增错题自动选中（缺陷 #11 / FR-018）

### 时序

```text
handleCreate(form):
  1. await api.createErrorQuestion(input)
  2. const newItem = { ...input, id: created.id, created_at: ... }
  3. queryClient.setQueryData(['error-questions'], (old) => [newItem, ...old ?? []])
  4. setSelectedId(newItem.id)         ← 关键：list 已 prepend 后再 set
  5. 不依赖 invalidateQueries（避免延迟）
```

### 关键修正

```ts
// src/pages/ErrorBook.tsx:114-123 (handleCreate)
const handleCreate = async (form: CreateErrorQuestionInput) => {
  const created = await api.createErrorQuestion(form)
  queryClient.setQueryData(['error-questions'], (old: ErrorQuestion[] | undefined) => [
    { ...form, id: created.id, created_at: new Date().toISOString() },
    ...(old ?? []),
  ])
  setSelectedId(created.id)   // 此时 list 已含该项，filter 不会丢
  setCreateOpen(false)
}
```

### UI 契约

```text
Given 用户在 ErrorBook 列表打开「+ 新建错题」表单
When  提交表单成功
Then  右侧详情区切换到该新错题的内容
And   不再显示「请选择左侧错题查看详情」
And   列表中该项高亮
```

---

## 测试契约

### 单元（`src/components/error-book/__tests__/ErrorCoachPanel.test.tsx`）

```text
- mock start() 5s 才返回 → 1.5s 内见到 loading 指示
- mock state=running → 显示第一道题
- mock state=error → 显示错误 + 「重试」按钮
```

### E2E（`tests/e2e/018-fix-product-defects/error-book/coach-start-feedback.spec.ts`）

```text
- 错题详情点「开始强化」→ 5s 内见到 loading / error / first-question
- 模拟后端 503 → 见到「启动失败，请重试」+ 按钮可点
```

### E2E（`tests/e2e/018-fix-product-defects/error-book/auto-select-new.spec.ts`）

```text
- 打开「+ 新建错题」→ 填内容 → 提交
- 断言：右侧详情区显示该新错题内容
- 断言：列表中该项被选中（高亮）
```

---

## 验收对应

- FR-016 ✓ 启动有反馈
- FR-017 ✓ 失败可重试
- FR-018 ✓ 新建自动选中
- SC-006 ✓ 100% 5s 内有反馈
- SC-009 ✓ 100% 新建自动定位
