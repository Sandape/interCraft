# Research: Error Coach 3-Correct E2E

**Branch**: `021-error-coach-e2e` | **Date**: 2026-06-22 | **Spec**: [spec.md](./spec.md)

Phase 0 research output. Resolves all NEEDS CLARIFICATION and validates
technical choices against existing code.

---

## R-1 — A2 代码审查决议：`decrement_frequency` 语义

**Decision**: E2E 按实际代码行为断言——**session 结束时调用一次 `decrement_frequency`，每次减 1**。

**Code Evidence**:

1. `backend/app/agents/graphs/error_coach.py:103-110`:
   ```python
   if correct_count >= 3 or session_aborted:
       ...
       if error_question_id and user_id:
           service = ErrorCoachService()
           await service.decrement_frequency(error_question_id, user_id)
   ```
   触发条件是 `correct_count >= 3 OR session_aborted`，单次调用。

2. `backend/app/services/error_coach_service.py:21-59`:
   ```python
   new_freq = max(0, current_freq - 1)  # 减 1，clamp 到 0
   new_status = "mastered" if new_freq == 0 else row[1]
   ```
   固定减 1，不读 `correct_count`。

**Divergence from 004 spec**:
- 004 acceptance #2: "correct_count +1, 调 M08 recall 接口减 frequency" → 暗示每次答对减
- 004 SC-002: "3 次答对结束 + frequency 减 1" → 与代码一致
- 004 FR-014: "答对时调 M08 recall 递减 frequency" → 与代码不一致

004 spec 内部存在自相矛盾。代码实现遵循 SC-002 的「减 1」语义。

**Rationale**: 021 是 E2E 覆盖 feature，不修业务逻辑。E2E 必须断言真实代码行为而非 spec 文字，否则 E2E 会假性失败。004 spec 与代码的语义对齐应另起 feature 处理（建议 025 或纳入 v2-024 audit 范围）。

**Alternatives considered**:
- A：在 021 内顺手修复 004 acceptance #2 → 拒绝，违反「不改后端业务逻辑」Non-Goal
- B：E2E 断言「减 3」让用例失败以暴露 bug → 拒绝，E2E 应是绿灯基线，非告警机制
- C：E2E 断言实际行为（减 1）+ 在 plan.md 记录差异 → **采纳**

---

## R-2 — Mock 注入策略：`LLM_MOCK_MODE` 环境变量

**Decision**: 在 `backend/app/agents/llm_client.py` 的 `get_llm_client()` 工厂函数添加 mock 分支，由 `LLM_MOCK_MODE=1` 环境变量启用。Mock 客户端从 `LLM_MOCK_SCENARIO_PATH` 指向的 JSON 文件读取评分序列。

**Why not page.route()**:
- Error Coach 评分逻辑在后端 `evaluate` 节点内，前端 `page.route()` 只能拦截 `/agents/error-coach/*` REST 调用，无法测试 `score >= 8` 分支判断、`attempt_count` 累积、`hint_level` 升级等节点行为
- 拦截 REST 只能验证 HTTP 契约（round-2 已有 `contract-parity.spec.ts` 覆盖），无法达成 SC-002「错题强化 3 次答对 + frequency 减 1」的端到端验证目标

**Why not OpenAI client mock**:
- `openai.AsyncOpenAI` 内部 HTTP 层不易在 Playwright 进程外拦截
- 后端测试已用 `respx` 类似机制，但 E2E 跨进程，需进程级开关

**Design**:

```python
# llm_client.py (新增 ≤30 行)
def get_llm_client() -> LLMClient:
    global _llm_client_singleton
    if _llm_client_singleton is None:
        if os.environ.get("LLM_MOCK_MODE") == "1":
            from app.agents.llm_client_mock import MockLLMClient
            _llm_client_singleton = MockLLMClient.from_scenario_file(
                os.environ.get("LLM_MOCK_SCENARIO_PATH", "")
            )
        else:
            _llm_client_singleton = LLMClient()
    return _llm_client_singleton
```

`MockLLMClient` 实现：
- `invoke(messages, node_name, ...)` 根据 `node_name` 返回预设响应
- `error_coach_evaluate` 节点：从 scenario 读取 `score_sequence`，按调用次数返回 `{"score": N, "feedback": "..."}`
- `error_coach_hint` 节点：根据 messages 中的 `hint_level` 返回静态文案
- 其他节点：返回空字符串或默认值
- 跳过 `_pre_deduct` / `_actual_adjust` / `_write_ai_message`（避免污染用户配额与 ai_messages 表）

**Scenario 文件格式**（`tests/e2e/round-2/fixtures/error-coach-scenarios/happy.json`）：
```json
{
  "evaluate_scores": [8, 9, 9],
  "hint_contents": {
    "small": "小提示：回忆 useMemo 的依赖数组机制。",
    "medium": "中等提示：对比 useMemo 与 useCallback 的输入输出。",
    "detailed": "详细提示：useMemo 缓存值，useCallback 缓存函数。"
  }
}
```

**Safety**:
- `LLM_MOCK_MODE` 默认 unset；仅在 E2E 启动后端的 `playwright.config.ts` webServer 中设置
- `MockLLMClient` 位于独立文件 `llm_client_mock.py`，不污染主客户端
- 新增单测 `backend/tests/test_llm_client_mock.py` 验证 mock 客户端的 scenario 解析与 fallback 行为
- 单测验证 `LLM_MOCK_MODE` 未启用时 `get_llm_client()` 返回真实客户端

**Alternatives considered**:
- A：在 `evaluate` 节点内加 mock 分支 → 拒绝，违反「不改业务节点」Non-Goal
- B：用 `pytest monkeypatch` 在测试启动时替换客户端 → 拒绝，E2E 跨进程无法 monkeypatch
- C：用 `httpx` 拦截 DeepSeek API → 复杂度高，且 `openai` 库内部不一定走 httpx

---

## R-3 — Mock fixture 复用 vs 新增

**Decision**: 新增 `tests/e2e/round-2/fixtures/error-coach-mock.ts`，**不**扩展 `tests/e2e/fixtures/mock-llm.ts`。

**Rationale**:
- 现有 `mock-llm.ts` 是 WS 流式面试专用（`questionEvent` / `scoreEvent` 结构），与 Error Coach 的 REST 同步模式语义完全不同
- 扩展会导致一个 fixture 文件承载两种不相关语义，违反 Constitution I（自包含、有目的）
- 新 fixture 负责生成 scenario JSON 文件路径并写入临时目录，供后端 `MockLLMClient` 读取
- 两个 fixture 独立演进，互不污染

**Fixture API**：
```typescript
// tests/e2e/round-2/fixtures/error-coach-mock.ts
export interface ErrorCoachScenario {
  evaluate_scores: number[]
  hint_contents: { small: string; medium: string; detailed: string }
}

export function writeScenarioFile(
  scenario: ErrorCoachScenario,
): string  // returns absolute path to temp JSON file
```

---

## R-4 — E2E 用例种子与清理

**Decision**: 复用 `tests/e2e/round-1/helpers/{auth,api,db}.ts`。每个用例 `beforeEach` seed 一条 `frequency=3, status=fresh` 的错题，`afterEach` 清理。

**Seed 方式**:
- 通过 `POST /api/v1/error-questions` API 创建（走真实后端 + RLS），不直接插 DB
- 清理通过 `tests/e2e/round-1/helpers/db.ts` 的 `deleteErrorQuestion` helper（直连 DB 绕 RLS，按既有 round-1 模式预置 `app.user_id` GUC）

**Why API 创建而非 DB 插入**:
- 验证 FR-042（用户手动创建错题）路径，回归保护
- 避免直接 SQL 插入导致的字段缺失（如 `source_session_id` 的 partial unique index）

**Why DB 清理而非 API 删除**:
- 用例结束后 thread_id 已失效，API 删除可能因 FK 约束失败
- DB 直连清理更彻底，按 round-1 既有模式

---

## R-5 — Playwright `webServer` 配置

**Decision**: 在 `playwright.config.ts` 的 `webServer` 启动后端时注入 `LLM_MOCK_MODE=1`，但仅当 `VITE_USE_MOCK=true` 时。真实 LLM 模式下不注入。

**Problem**: 现有 `playwright.config.ts` 可能已有一个 webServer 配置（启动后端 + 前端）。需要确认是否支持按环境变量切换。

**Plan**: plan 阶段不深入配置细节，留给 tasks/implement 阶段。若现有 webServer 不支持环境变量切换，允许在 `playwright.config.ts` 添加条件分支（视为基础设施改动，非业务改动）。

---

## R-6 — 004 SC-002 翻 done 的流程

**Decision**: E2E 全绿后，更新 `specs/004-phase5-agent-subgraphs/requirements-status.md` 的 SC-002 行：
- Status: `in_progress` → `done`
- Evidence: 指向 `tests/e2e/round-2/error-coach-3-correct.spec.ts`

同时更新 `specs/README.md` 的 004 行 Notes：
- 移除「SC-002 requires a live-LLM scoring loop; code is complete and production-ready, only deterministic E2E coverage is pending」
- 改为「All 41 rows done. Round-2 E2E covers Error Coach 3-correct + frequency decrement.」

**Why not update 004 spec.md**: 004 spec 是历史冻结文档，行为变更应通过新 feature（021）记录，而非回改 004。

---

## Summary

| ID | 决议 | 影响 |
|---|---|---|
| R-1 | decrement_frequency 语义按代码：session 结束减 1 | 修正 spec 断言；004 spec 差异另起 issue |
| R-2 | LLM_MOCK_MODE + MockLLMClient + scenario JSON | 后端新增 ≤30 行 hook + 独立 mock 文件 |
| R-3 | 新增 error-coach-mock.ts，不扩展 mock-llm.ts | 语义隔离，Constitution I 合规 |
| R-4 | API 创建 + DB 清理 | 复用 round-1 helpers，回归保护 |
| R-5 | playwright.config.ts 条件注入 LLM_MOCK_MODE | 基础设施改动，非业务 |
| R-6 | E2E 全绿后翻 004 SC-002 + README Notes | 流程收尾 |

所有 NEEDS CLARIFICATION 已解决，可进入 Phase 1 设计。
