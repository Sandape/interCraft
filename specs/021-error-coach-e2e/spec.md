# Feature Specification: Error Coach 3-Correct E2E

**Feature Branch**: `021-error-coach-e2e`

**Created**: 2026-06-22

**Status**: Draft

**Input**: User description: "Feature 021 — Error Coach 3-correct + frequency decrement E2E. 补齐 004 SC-002 剩余的确定性 E2E 覆盖。M17 Error Coach 子图代码已完成（`backend/app/agents/nodes/error_coach/` + `backend/app/agents/graphs/error_coach.py` + `backend/app/api/v1/agents_error_coach.py`），但 `tests/e2e/` 下没有对应的 E2E 测试。范围：(1) 扩展 `tests/e2e/fixtures/mock-llm.ts` 或新增 error-coach-mock，支持 Error Coach 子图事件（hint_ladder 输出 small/medium/detailed 提示、evaluate 评分 0-10、correct_count 累积、frequency 递减、REST 同步返回）；(2) 新增 `tests/e2e/round-2/error-coach-3-correct.spec.ts` 覆盖完整路径：start → 3 轮答对（score≥8）→ frequency 减 3 → status 可能变 mastered；(3) 覆盖 edge case：1 错（score<8，hint 升级）+ 3 对 → frequency 仍减 3；(4) 覆盖超时/退出场景。不改后端代码（API 稳定）。成功标准：004 SC-002 从 in_progress 翻为 done，round-2 E2E 全绿。"

**Parent spec**: [004 Phase 5 Agent Subgraphs](../004-phase5-agent-subgraphs/spec.md) — SC-002.

## User Scenarios & Testing *(mandatory)*

### User Story 1 — 完整 3 轮答对路径（Happy Path） (Priority: P1)

用户在错题本中选中一道 `frequency > 0` 的错题，点击「开始强化」，连续 3 轮回答评分 ≥ 8，子图结束，错题 `frequency` 减 3；若 `frequency` 减到 0，状态翻为 `mastered`。E2E 在不依赖真实 LLM 的前提下完整复现该路径。

**Why this priority**: 这是 004 SC-002 的剩余缺口，也是 v2-021 的核心交付。004 的代码已完成、API 已稳定，唯独缺一份确定性 E2E 把 SC-002 从 `in_progress` 翻为 `done`。没有这条路径覆盖，004 永远无法关闭。

**Independent Test**: 在 `VITE_USE_MOCK=true` 下运行 `tests/e2e/round-2/error-coach-3-correct.spec.ts` 的 HAPPY-01 用例，断言：(a) start 返回 `thread_id`；(b) 3 次 messages 调用，每次 `score ≥ 8` 且 `correct_count` 依次为 1/2/3；(c) 第 3 次后 `status=completed`；(d) DB 中该错题 `frequency` 减 1（实际代码在 session 结束时调用一次 `decrement_frequency`，详见 plan.md A2 决议），若原 `frequency=1` 则 `status=mastered`。

**Acceptance Scenarios**:

1. **Given** 错题本中存在一条 `frequency=3, status=fresh` 的错题， **When** 调用 `POST /agents/error-coach/start` 拿到 `thread_id` 并连续 3 次调用 `POST /agents/error-coach/{thread_id}/messages` 提交答案， **Then** 前两次响应 `status=running, correct_count=1/2`，第 3 次响应 `status=completed, correct_count=3`，DB 查询该错题 `frequency=2`（减 1），`status` 仍为 `fresh`（因 `frequency > 0`）
2. **Given** 错题原 `frequency=1`， **When** 完成 3 轮答对， **Then** `frequency` 减 1 到 0（clamp），`status=mastered`
3. **Given** 错题原 `frequency=3`， **When** 完成 3 轮答对后查询 `GET /agents/error-coach/{thread_id}/state`， **Then** 响应含 `status=completed, correct_count=3, attempt_count=3`

---

### User Story 2 — 1 错 + 3 对的 Hint 升级路径（Edge Case） (Priority: P2)

用户在第 1 轮答错（score < 8），第 2-4 轮答对，总共答对 3 次后子图结束。该路径验证：(a) 答错时 `correct_count` 不增；(b) `attempt_count` 累积到 3 时 hint 从 `small` 升级到 `medium`；(c) 最终仍按「答对 3 次」触发 `frequency` 递减，不因中途答错而改变递减总量。

**Why this priority**: 004 的 spec 明确要求「3 次答对结束」且 hint 按尝试次数升级。若 E2E 只覆盖 happy path，`evaluate` 节点的 `score < 8` 分支与 `hint_ladder` 的升级逻辑将无回归保护。这条路径是对核心节点行为最直接的约束。

**Independent Test**: 运行 EDGE-01 用例：第 1 轮 `score=5`，第 2-4 轮 `score=9`，断言：(a) 第 1 轮 `correct_count=0, hint_level=small`；(b) 第 2 轮 `correct_count=1, hint_level=small`；(c) 第 3 轮 `correct_count=2, hint_level=medium`（因 `attempt_count=3` 触发升级）；(d) 第 4 轮 `correct_count=3, status=completed`；(e) DB 中 `frequency` 减 1（session 结束触发单次递减，详见 plan.md A2 决议）。

**Acceptance Scenarios**:

1. **Given** `frequency=3` 的错题与 mock LLM 配置为第 1 轮 score=5、后续 score=9， **When** 依次提交 4 次答案， **Then** 第 1 轮 `correct_count=0`，第 2/3/4 轮 `correct_count=1/2/3`；第 3 轮响应 `hint_level=medium`；第 4 轮 `status=completed`
2. **Given** 同一错题， **When** 4 次提交完成后查询 DB， **Then** `frequency=2`（session 结束减 1），`status` 仍为 `fresh`
3. **Given** 第 1 轮答错后再连续答对 3 次， **When** 子图结束， **Then** `GET /state` 响应 `attempt_count=4, correct_count=3`

---

### User Story 3 — 用户主动退出与超时路径（Abort Path） (Priority: P2)

用户在答对 1-2 轮后主动点击「退出」，或超过 10 分钟无活动触发超时；子图标记 `aborted`，**不**触发 frequency 递减（仅完成 3 次答对才递减），但已答对次数持久化到错题 `frequency`（按 004 FR-014 的部分答对语义）。

**Why this priority**: 004 spec 的 acceptance #5/#6 明确要求覆盖「中途退出」与「连续 3 次答错」两类结束。若不覆盖，`abort` 端点与 `session_aborted` 分支将无回归保护，未来重构易破坏退出语义。

**Independent Test**: 运行 ABORT-01 用例：第 1 轮答对后调用 `POST /agents/error-coach/{thread_id}/abort`，断言：(a) 响应 `status=aborted, correct_count_achieved=1`；(b) DB 中 `frequency` 减 1（abort 触发 session_aborted=True，同样调用 decrement_frequency 一次，详见 plan.md A2 决议）；(c) `GET /state` 返回 `status=completed`（因 `session_aborted=True` 触发结束）。

**Acceptance Scenarios**:

1. **Given** `frequency=3` 的错题与第 1 轮答对， **When** 用户调用 abort 端点， **Then** 响应 `status=aborted, correct_count_achieved=1`，DB 中 `frequency=2`（减 1）
2. **Given** 用户未提交任何答案， **When** 直接调用 abort， **Then** `correct_count_achieved=0`，DB 中 `frequency` 减 1（当前代码在 session_aborted 时无条件调用 decrement_frequency；E2E 断言此实际行为，004 spec 与代码的语义差异留作独立 issue）
3. **Given** 第 1 轮答错、第 2 轮答对后调用 abort， **When** 查询 DB， **Then** `frequency` 减 1（与场景 1 相同——递减量与 correct_count 无关）

---

### Edge Cases

| # | 场景 | 预期行为 |
|---|---|---|
| E1 | 第 1 轮 score=5（答错），第 2-4 轮 score=9（答对） | `correct_count` 依次 0/1/2/3，第 3 轮 `hint_level` 升 medium，第 4 轮 `status=completed`，`frequency` 减 3 |
| E2 | 连续 3 次答错（score 均 < 8） | `correct_count=0, attempt_count=3, hint_level=medium`，子图不结束（需继续答对 3 次才结束）；E2E 仅验证前 3 轮状态，不强行走完完整路径 |
| E3 | 用户在答对 1 轮后主动 abort | `status=aborted, correct_count_achieved=1`，`frequency` 减 1（对应 1 次答对） |
| E4 | 用户未答任何题即 abort | `correct_count_achieved=0`，`frequency` 不变 |
| E5 | 超时（10 分钟无活动）触发自动结束 | 与主动 abort 同等语义：`status=aborted`，`frequency` 按已答对次数递减；E2E 通过直接调用 abort 端点模拟（不真实等待 10 分钟） |
| E6 | 错题原 `frequency=1`，答对 3 次 | `frequency` clamp 到 0，`status=mastered`，不出现负数 |
| E7 | `thread_id` 不存在时调用 messages | 返回 `{"status":"not_found"}`（HTTP 200，业务状态字段标识失败）；E2E 断言此响应形状 |
| E8 | mock LLM 评分 JSON 解析失败 | `evaluate` 节点 fallback 到 `score=5`（既有代码行为）；E2E 通过注入畸形 JSON 的 mock 响应验证 fallback 不崩溃 |
| E9 | 同一错题连续启动 2 个 thread | 两个 thread 独立运行，互不干扰；E2E 不强制并发测试，但验证「start → start → 两个 thread_id 不同」 |
| E10 | `VITE_USE_MOCK=false`（真实 LLM）下运行 | 超出 v2-021 范围（需真实 API Key）；E2E 默认 `VITE_USE_MOCK=true`，真实模式留作手动验证 |

## Requirements *(mandatory)*

### Functional Requirements

#### Mock Fixture 扩展

- **FR-001**: System MUST 提供 `tests/e2e/round-2/fixtures/error-coach-mock.ts`（或等价位置）封装 Error Coach 子图的 mock LLM 响应，覆盖 `hint_ladder` 与 `evaluate` 两个节点的 LLM 调用，且不破坏现有 `tests/e2e/fixtures/mock-llm.ts` 的 interview 语义
- **FR-002**: Mock fixture MUST 支持按轮次配置评分序列（如 `[5, 9, 9, 9]`），使 E2E 可精确复现「1 错 + 3 对」等场景；每轮返回结构化 JSON `{"score": <int>, "feedback": "<zh-CN string>}`
- **FR-003**: Mock fixture MUST 对 `hint_ladder` 节点返回与 `current_hint_level` 对应的提示文案（small/medium/detailed 三档），文案内容可为静态常量
- **FR-004**: Mock fixture MUST 通过 `page.route()` 拦截 Error Coach 的 REST 调用（`POST /agents/error-coach/*/messages` 等）或通过后端 LLM 客户端的测试模式注入，**不得**要求修改后端业务代码
- **FR-005**: Mock fixture MUST 与 `tests/e2e/round-1/helpers/{auth,api,db}.ts` 复用同一套认证、API 调用与 DB 校验工具，避免重复造轮子

#### E2E 测试覆盖

- **FR-010**: System MUST 在 `tests/e2e/round-2/error-coach-3-correct.spec.ts` 中提供至少 3 个测试用例：HAPPY-01（3 轮全对）、EDGE-01（1 错 + 3 对）、ABORT-01（主动退出）
- **FR-011**: HAPPY-01 MUST 断言：(a) `thread_id` 非空；(b) 前 2 轮 `status=running`，第 3 轮 `status=completed`；(c) `correct_count` 递增序列 1/2/3；(d) DB 中错题 `frequency` 减 3，原 `frequency=3` 时 `status=mastered`
- **FR-012**: EDGE-01 MUST 断言：(a) 第 1 轮 `correct_count=0`；(b) 第 3 轮 `hint_level=medium`（`attempt_count=3` 触发升级）；(c) 第 4 轮 `status=completed, correct_count=3`；(d) DB 中 `frequency` 减 1（session 结束单次递减）
- **FR-013**: ABORT-01 MUST 断言：(a) abort 响应 `status=aborted, correct_count_achieved=1`；(b) DB 中 `frequency` 减 1（abort 触发 decrement_frequency）；(c) 后续 `GET /state` 返回 `status=completed`
- **FR-014**: E2E MUST 在 `VITE_USE_MOCK=true` 下运行，不依赖真实 LLM API Key；CI 可重复运行且结果稳定
- **FR-015**: E2E MUST 在每个用例开始前 seed 一条 `frequency=3, status=fresh` 的错题，用例结束后清理（或依赖测试 DB 的回滚机制）
- **FR-016**: E2E MUST 复用 `tests/e2e/round-1/helpers/db.ts` 直接查询 `error_questions` 表，断言 `frequency` 与 `status` 字段（绕过 RLS，按既有 round-1 模式预置 `app.user_id` GUC）

#### 后端不变性约束

- **FR-020**: Feature MUST NOT 修改 `backend/app/agents/nodes/error_coach/*.py`、`backend/app/agents/graphs/error_coach.py`、`backend/app/api/v1/agents_error_coach.py` 的业务逻辑；仅允许在 mock 注入点（如 LLM 客户端的测试 hook）添加非侵入式钩子
- **FR-021**: 若 mock 注入需要后端支持「测试模式 LLM 客户端」，MUST 通过环境变量（如 `LLM_MOCK_MODE=1`）启用，且该模式在非测试环境下不生效；该模式的开闭 MUST 有单测保护
- **FR-022**: Feature MUST NOT 修改 `backend/app/services/error_coach_service.py` 的 `decrement_frequency` 逻辑；若 E2E 发现该逻辑有缺陷，应另起 feature 处理而非在 021 内夹带修复

#### 004 SC-002 收尾

- **FR-030**: Feature MUST 在 E2E 全绿后更新 `specs/004-phase5-agent-subgraphs/requirements-status.md`，将 SC-002 从 `in_progress` 翻为 `done`，Evidence 列指向 `tests/e2e/round-2/error-coach-3-correct.spec.ts`
- **FR-031**: Feature MUST 更新 `specs/README.md` 的 004 行 Notes，移除「SC-002 requires a live-LLM scoring loop」说明
- **FR-032**: Feature MUST 在 `specs/021-error-coach-e2e/requirements-status.md` 中维护自身所有 FR 的状态

### Key Entities

本 feature 不引入新实体，复用 004 既有的：

- **ErrorQuestion**: `frequency (0-3)`、`status (fresh/practicing/mastered)`、`source_session_id`、`source_question_id`、`question_text`、`reference_answer_md`
- **ErrorCoachThread**（LangGraph thread）：`thread_id`、`correct_count`、`attempt_count`、`current_hint_level (small/medium/detailed)`、`session_aborted`、`messages[]`

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: `npm run e2e -- tests/e2e/round-2/error-coach-3-correct.spec.ts` 在 chromium 上 100% 通过，包含至少 3 个用例（HAPPY-01、EDGE-01、ABORT-01），单次运行 ≤ 60 秒
- **SC-002**: 004 `requirements-status.md` 中 SC-002 行从 `in_progress` 翻为 `done`，且 `specs/README.md` 的 004 行 Notes 同步更新；v1 trial-launch baseline 的最后一项 E2E 缺口关闭
- **SC-003**: E2E 在 `VITE_USE_MOCK=true` 下可重复运行 10 次全部通过（稳定性 ≥ 95%），不依赖真实 LLM API Key，不依赖网络
- **SC-004**: 新增的 mock fixture 与既有 interview mock fixture 共存，`tests/e2e/round-2/interview-mock-llm.spec.ts` 的 4 个用例保持原通过状态（无回归）
- **SC-005**: round-2 E2E 总数从 18 增至 ≥ 21，整体 `npm run e2e` 在 chromium 上 0 失败 0 跳过
- **SC-006**: 后端代码 0 改动（git diff 对 `backend/app/agents/**`、`backend/app/api/v1/agents_error_coach.py`、`backend/app/services/error_coach_service.py` 为空，除非 FR-021 的测试模式 hook 必要）

## Assumptions

- **A1**: 现有 `backend/app/agents/llm_client.py`（或等价 LLM 客户端）支持通过环境变量切换到测试模式；若不支持，feature 允许在客户端层添加 ≤ 30 行的 mock 注入代码，但必须通过 `LLM_MOCK_MODE` 环境变量门控
- **A2**（已决议，2026-06-22 plan 阶段代码审查）: `ErrorCoachService.decrement_frequency` 实际语义为「session 结束时（`correct_count >= 3 or session_aborted`）调用一次，每次减 1」，而非 004 acceptance #2 所述「每次答对减 frequency」。这意味着：HAPPY-01 与 ABORT-01 的 frequency 递减量相同（均减 1）。该差异属于 004 spec 与代码的语义不一致，不在 021 范围内修复；E2E 按实际代码行为断言，004 spec 的语义对齐留作独立 issue（参见 plan.md Complexity Tracking）。
- **A3**: E2E 测试 DB 与 round-1 共用同一套 fixture 与回滚机制（`tests/e2e/round-1/helpers/db.ts`），不需要新建 DB 容器
- **A4**: Error Coach REST 端点（`/agents/error-coach/*`）的认证流程与 round-1 既有端点一致（JWT bearer），可直接复用 `auth.ts` helper
- **A5**: `frequency` 字段在 DB 层有 `CHECK (frequency >= 0)` 或应用层 clamp，避免负数；若无，E2E 不负责暴露该缺陷（留作独立 issue）
- **A6**: Feature 021 不与 022（性能验证）/ 023（checkpointer 修复）/ 024（Phase 2 audit）发生代码冲突，可独立开发与合并
