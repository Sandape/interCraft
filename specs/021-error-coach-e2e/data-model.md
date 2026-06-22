# Data Model: Error Coach 3-Correct E2E

**Branch**: `021-error-coach-e2e` | **Date**: 2026-06-22 | **Spec**: [spec.md](./spec.md)

本 feature 不引入新实体。所有数据结构复用 004 既有的 `ErrorQuestion` 与
LangGraph `ErrorCoachState`。此文档仅记录 E2E 依赖的字段与状态机，供测试
断言参考。

---

## 1. 实体（复用，不修改）

### ErrorQuestion

表：`error_questions`（RLS 启用）

| 字段 | 类型 | 说明 | E2E 关心 |
|---|---|---|---|
| `id` | uuid | 主键 | seed 后保存 |
| `user_id` | uuid | 所属用户 | seed 时从 JWT 取 |
| `question_text` | text | 题目原文 | seed 时指定 |
| `reference_answer_md` | text | 标答 | seed 时指定 |
| `dimension` | enum | 维度 | seed 时指定 |
| `frequency` | int (0-3) | 频次 | **核心断言字段** |
| `status` | enum (fresh/practicing/mastered) | 状态 | **核心断言字段** |
| `source_session_id` | uuid nullable | 来源面试 | seed 时 null |
| `source_question_id` | uuid nullable | 来源题目 | seed 时 null |
| `created_at` / `updated_at` | timestamptz | 时间戳 | — |

### ErrorCoachState（LangGraph thread state）

存储：LangGraph checkpointer（Postgres `checkpoints` 表）

| 字段 | 类型 | 说明 | E2E 关心 |
|---|---|---|---|
| `thread_id` | str | 会话 ID | start 后保存 |
| `user_id` | str | 用户 | — |
| `error_question_id` | str | 关联错题 | seed 后传入 |
| `correct_count` | int | 答对次数 | **核心断言字段** |
| `attempt_count` | int | 尝试次数 | **核心断言字段** |
| `current_hint_level` | enum (small/medium/detailed) | 当前提示等级 | **核心断言字段** |
| `session_aborted` | bool | 是否中止 | abort 后断言 |
| `question` | dict | 错题快照 | — |
| `messages` | list[dict] | 对话历史 | — |

---

## 2. 状态机

### ErrorQuestion.status

```
fresh ──(frequency 减到 0)──► mastered
```

- `fresh` → `mastered`：`decrement_frequency` 把 `frequency` 减到 0 时自动翻
- 无 `practicing` 中间态（代码未实现该转换；004 spec 提及但未落地，不在 021 范围）

### ErrorCoach 会话状态

```
running ──(correct_count >= 3)──► completed
running ──(session_aborted=True)──► completed
```

- `GET /state` 的 `status` 字段：`running`（仍有 next node）或 `completed`（END）
- abort 后立即查 `GET /state` 返回 `status=completed`

### hint_level 升级规则（来自 `evaluate.py:64-68`）

```
attempt_count >= 3 且 current_level=small → medium
attempt_count >= 5 且 current_level=medium → detailed
```

E2E EDGE-01（1 错 + 3 对，attempt_count 序列 1/2/3/4）：
- 轮 1：attempt_count=1, level=small
- 轮 2：attempt_count=2, level=small
- 轮 3：attempt_count=3, level=medium ← 触发升级
- 轮 4：attempt_count=4, level=medium

---

## 3. E2E 期望值速查

| 用例 | 错题原 frequency | 提交序列 | 期望 frequency 变化 | 期望 status 变化 |
|---|---|---|---|---|
| HAPPY-01 | 3 | 3 × score≥8 | 3 → 2 | fresh → fresh |
| HAPPY-01-variant | 1 | 3 × score≥8 | 1 → 0 | fresh → mastered |
| EDGE-01 | 3 | 1×score<8 + 3×score≥8 | 3 → 2 | fresh → fresh |
| ABORT-01 | 3 | 1 × score≥8 + abort | 3 → 2 | fresh → fresh |
| ABORT-02 | 3 | 0 提交 + abort | 3 → 2 | fresh → fresh（代码当前行为，spec 差异另起 issue） |

---

## 4. 不在 021 范围

- `practicing` 状态的实现（004 spec 提及但代码未落地）
- `correct_count` 累积到 3 后的「mastered」直接判定（当前依赖 frequency 归零）
- 004 acceptance #2「每次答对减 frequency」的语义对齐
