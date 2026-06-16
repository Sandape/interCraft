# Data Model: 018-fix-product-defects

**Phase**: 1 — Design & Contracts
**Date**: 2026-06-17
**Source**: `spec.md` § Key Entities + `research.md` 14 缺陷根因

> **核心结论**：本批次**零 schema 变更**。所有修复在已有实体上做"前端字段映射 / 后端回调补全 / 状态机读路径补全"。

---

## 实体总览

| 实体 | 后端位置 | 本批次影响 | 关键字段 |
|---|---|---|---|
| `User` | `users` | 无 | id, email |
| `ResumeBranch` | `resume_branches` | 无 | id, user_id, title |
| `ResumeBlock` | `resume_blocks` | 无 | id, branch_id, content_md |
| `Job` | `jobs` | **字段对齐**（前端 `note` → `notes_md`） | `notes_md: Text nullable`（已存在） |
| `InterviewSession` | `interview_sessions` | 后端补回调 | id, user_id, branch_id（已有），状态机 |
| `Question` / `Score` | `interview_questions` / `interview_scores` | 无（数据已存） | dimension_key, score (0-10) |
| `AbilityDimension` | `ability_dimensions` | **写入路径补全** | user_id, dimension_key, actual_score (Decimal), source |
| `ErrorQuestion` | `error_questions` | 无 | id, dimension_key, content |
| `ErrorCoachThread` | `error_coach_threads` | 无（轮询读已存在） | thread_id, status |
| `Lock` | `locks` | 已有，新分支 acquire 时机修正 | entity_type='resume_branch', entity_id, owner_user_id |

---

## 关键实体详细说明

### 1. `Job.notes_md`（缺陷 #12 涉及）

```python
# backend/app/modules/jobs/models.py:36
notes_md: Mapped[str | None] = mapped_column(Text, nullable=True)
```

- **状态**：DB 字段已存在；Pydantic schema 同步（`CreateJobInput.notes_md: str | None`）
- **问题**：前端用 `note` 字段名，后端静默丢弃
- **修复方向**：仅前端字段映射，**不改 schema**

### 2. `AbilityDimension`（缺陷 #9 涉及）

```sql
-- 推断（参考 backend/app/modules/ability_dimensions/ 与 ability_profile/service.py）
ability_dimensions (
  user_id UUID NOT NULL,
  dimension_key TEXT NOT NULL,        -- 受 ALLOWED_DIMENSION_KEYS 白名单约束
  actual_score DECIMAL(4,2),          -- 0.00..10.00（与 Q1 量纲一致）
  source TEXT,                        -- 'manual' | 'interview' | 'coach'
  is_active BOOLEAN,
  sub_scores JSONB,
  created_at TIMESTAMPTZ,
  PRIMARY KEY (user_id, dimension_key, source)  -- 推断
)
```

- **状态**：表已存在；`AbilityDimensionRepository.patch` 写方法已实现
- **问题**：interview 完成时不调用 patch
- **修复方向**：在 `interviews/service.py` 的 `complete_session` 末尾补 patch（**零 schema 变更**）

### 3. `InterviewSession` 状态机

```
[setup] ─submit──▶ [in_progress] ─submit_answer×N──▶ [scoring] ─complete_session──▶ [completed]
                                                  │
                                                  └─ user pause / refresh ──▶ [recoverable]
```

- **缺陷 #6 涉及**：`setup` 阶段需新增 `branch_id` 收集
- **缺陷 #7 涉及**：`recoverable → in_progress` 恢复时显示中文文案
- **缺陷 #9 涉及**：`[completed]` 转换时触发 `ability_dimensions.patch`
- **修复方向**：状态机不变；**补 SET 字段 + 补回调**

### 4. `ResumeBranch` 与 `Lock`（缺陷 #3 涉及）

```python
# Lock entity_type = 'resume_branch', entity_id = resume_branch.id
```

- **问题**：新分支创建后未立即 `acquire`，刷新时后端判 `isReadOnly=true`
- **修复方向**：前端在 `createBranch()` 成功后立即 `useLock('resume_branch', branchId).acquire()`

### 5. `ErrorCoachThread` 状态机（缺陷 #10 涉及）

```
[start] ─POST /start──▶ [starting] ─GET /state──▶ [running] / [awaiting_answer] / [done] / [error]
                                                              │
                                                              └─ 用户提交答案 ──▶ [running] 循环
```

- **状态**：endpoint + state 端点均已实现
- **问题**：前端 fire-and-forget，没有反馈循环
- **修复方向**：前端 `useErrorCoach` 加 `useQuery({ refetchInterval: 1500 })` 轮询

---

## 跨实体关系（不变）

```
User ─owns─▶ ResumeBranch ─contains─▶ ResumeBlock
   │
   ├─owns─▶ InterviewSession ─references─▶ ResumeBranch (branch_id)
   │                       ─has─▶ Question ─has─▶ Score
   │
   ├─has─▶ AbilityDimension (per dimension_key)
   │
   ├─owns─▶ Job ─references─▶ ResumeBranch (branch_id, nullable)
   │
   └─owns─▶ ErrorQuestion ─spawns─▶ ErrorCoachThread
```

---

## 验证规则

| 实体 | 字段 | 规则 | 测试 |
|---|---|---|---|
| Job | `notes_md` | nullable; string; trim 后允许空字符串 | `backend/tests/contract/test_jobs_notes_field.py` |
| AbilityDimension | `actual_score` | Decimal(4,2); 0.00..10.00; 与 spec Q1 一致 | `backend/tests/integration/test_interview_to_ability_sync.py` |
| AbilityDimension | `source` | enum: 'manual' \| 'interview' \| 'coach' | 同上 |
| InterviewSession | `branch_id` | nullable; 关联 ResumeBranch（用户态） | `src/pages/__tests__/InterviewLive.setup.test.tsx` |

---

## 索引与性能

- 现有索引（不需新增）：
  - `idx_jobs_user_id` (user_id)
  - `idx_ability_dimensions_user_dim` (user_id, dimension_key)
  - `idx_interview_sessions_user_id_status` (user_id, status)
- 面试完成后 patch `ability_dimensions` 是 O(dim_count)，对每个 user 至多 6 维（Phase 5 ALLOWED_DIMENSION_KEYS 上限），不会触发性能问题

---

## 隐私与 RLS

- 所有实体已配置 RLS（参考 Phase 1 / 2 / 5 的 RLS 策略）
- 缺陷 #2 Dashboard 假数据的修复不引入跨用户读取；档位 2 全局建议仍在 `WHERE user_id = current_setting('app.user_id')` 范围内
- 缺陷 #9 面试完成时 patch 写入 `current_user_id`，由 RLS 强约束

---

## Out of Data-Model Scope

- 不新增 `ability_dimension_history` 行（已有，由 patch 自动 append）
- 不修改 `Job.status` 状态机（缺陷与 status 无关）
- 不引入新 `interview_score_aggregates` 物化表（实时聚合足够）
- 不修改 `users` 表（缺陷不涉及用户字段）
