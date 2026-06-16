# Data Model: Cross-Module Linking

**Status**: Phase 1 output · **Date**: 2026-06-17 · **Spec**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md) | **Research**: [research.md](./research.md)

> 本文档定义 019-cross-module-linking 涉及的**3 张表的列扩展**,严格不引入新表、不修改 ResumeBranch。Ability Profile(006)与 LangGraph checkpoint 表不在本文档范围。

## 0. 已存在表 — 019 增量变更总览

| 表 | 既有状态 | 019 变更 |
|---|---|---|
| `jobs` | 014 已有,字段:`id / user_id / company / position / jd_url / branch_id / status / status_history / last_status_changed_at / notes_md / created_at / updated_at / deleted_at` | **扩展 5 列**:`base_location / requirements_md / employment_type / salary_range_text / headcount` |
| `interview_sessions` | Phase 2/4 已有,字段:`id / user_id / branch_id / position / company / mode / status / thread_id / checkpoint_ns / started_at / ended_at / duration_sec / overall_score / created_at / updated_at / deleted_at` | **扩展 1 列**:`job_id` (UUID, FK `jobs.id`, ON DELETE SET NULL, nullable, 索引) |
| `error_questions` | 016 已有,字段:`id / user_id / source_session_id / dimension / question_text / answer_text / reference_answer_md / score / status / frequency / tags / archived_at / last_practiced_at / created_at / updated_at / deleted_at` | **扩展 1 列**:`source_question_id` (UUID, FK `interview_questions.id`, ON DELETE SET NULL, nullable, 索引 + 部分唯一约束) |
| `resume_branches` | Phase 1 已有 | **不修改**(019 通过"预填 name/company/position"满足体验需求) |
| `interview_questions` | Phase 4 已有 | **不修改**(019 只读取 `score / dimension / text` 与对应 `ai_message.body`) |
| `ability_dimensions` / `ability_dimensions_history` | 006 已有 | **不修改**(019 仅在数据冒烟上验证) |

## 1. `jobs` 表扩展(5 列)

### E-19-J · `jobs.base_location`

**用途**:岗位所在城市 / 办公地,简文本,1–50 字符,**必填**(默认 `''` 不算未填,业务层校验)。

| 属性 | 值 |
|---|---|
| 列名 | `base_location` |
| 类型 | `TEXT` |
| 约束 | `NOT NULL DEFAULT ''`,业务层校验 `length BETWEEN 1 AND 50`(空字符串视为"未填") |
| 默认 | `''` |
| 索引 | 无 |
| 迁移 | `019_job_fields.py` |

**业务校验**:`CreateJobInput.base_length` Pydantic `Field(min_length=1, max_length=50)`,但允许空字符串(用 `Optional` + validator 区分"未填"与"显式填空")。

### E-19-J · `jobs.requirements_md`

**用途**:招聘需求富文本(Markdown),≤5000 字符,可选。

| 属性 | 值 |
|---|---|
| 列名 | `requirements_md` |
| 类型 | `TEXT` |
| 约束 | `NULL` 允许,业务层 `max_length=5000` |
| 默认 | `NULL` |
| 索引 | 无 |
| 迁移 | `019_job_fields.py` |

**业务校验**:Pydantic `Field(default=None, max_length=5000)`;前端 Markdown textarea 显示字符计数。

### E-19-J · `jobs.employment_type`

**用途**:岗位类型,枚举 `internship / campus / experienced / contract / unspecified`。

| 属性 | 值 |
|---|---|
| 列名 | `employment_type` |
| 类型 | `TEXT` |
| 约束 | `NOT NULL DEFAULT 'unspecified'`,业务层枚举校验 |
| 默认 | `'unspecified'` |
| 索引 | 无 |
| 迁移 | `019_job_fields.py` |

**枚举值**:
- `internship` — 实习
- `campus` — 校招
- `experienced` — 社招
- `contract` — 合同 / 外包
- `unspecified` — 未指定(默认)

**业务校验**:Pydantic `Literal["internship", "campus", "experienced", "contract", "unspecified"]`,前端下拉显示中文名。

### E-19-J · `jobs.salary_range_text`

**用途**:薪资范围,自由文本(如"20-30K · 14薪"),≤100 字符,可选。

| 属性 | 值 |
|---|---|
| 列名 | `salary_range_text` |
| 类型 | `TEXT` |
| 约束 | `NULL` 允许,业务层 `max_length=100` |
| 默认 | `NULL` |
| 索引 | 无 |
| 迁移 | `019_job_fields.py` |

### E-19-J · `jobs.headcount`

**用途**:招聘人数,整数,≥1,可选。

| 属性 | 值 |
|---|---|
| 列名 | `headcount` |
| 类型 | `INTEGER` |
| 约束 | `NULL` 允许,业务层 `>= 1` |
| 默认 | `NULL` |
| 索引 | 无 |
| 迁移 | `019_job_fields.py` |

## 2. `interview_sessions` 表扩展(1 列)

### E-19-I · `interview_sessions.job_id`

**用途**:关联到 `jobs.id`,标识这场面试对应的岗位。

| 属性 | 值 |
|---|---|
| 列名 | `job_id` |
| 类型 | `UUID` (PG `UUID AS UUID`) |
| 约束 | `NULL` 允许,`FK jobs.id ON DELETE SET NULL` |
| 默认 | `NULL` |
| 索引 | `interview_sessions_job_id_idx` (B-tree on `job_id`) |
| 迁移 | `019_interview_job_id.py` |

**关系**:
- `interview_sessions.job_id → jobs.id`,1:N(一个 job 可对应多场面试)
- `interview_sessions.branch_id → resume_branches.id`,1:N(已有)
- 同一 session 同时有 `job_id` 与 `branch_id` 时,服务端校验二者同属当前 user;若 user 不匹配,返回 422

**迁移前校验**(research.md R-1):
```sql
-- 用 dbq.py 跑
SELECT column_name FROM information_schema.columns
WHERE table_name='interview_sessions' AND column_name='job_id';
-- 期望:0 行
```

## 3. `error_questions` 表扩展(1 列 + 部分唯一约束)

### E-19-E · `error_questions.source_question_id`

**用途**:溯源到 `interview_questions.id`,标识错题来自哪道面试题。

| 属性 | 值 |
|---|---|
| 列名 | `source_question_id` |
| 类型 | `UUID` (PG `UUID AS UUID`) |
| 约束 | `NULL` 允许,`FK interview_questions.id ON DELETE SET NULL` |
| 默认 | `NULL` |
| 索引 | `error_questions_source_question_id_idx` (B-tree on `source_question_id`) |
| 部分唯一约束 | `UNIQUE (source_question_id) WHERE source_question_id IS NOT NULL` |
| 迁移 | `019_error_source_question_id.py` |

**溯源三元组**:
- `source_session_id` (016 已有)— 关联 session
- `source_question_id` (019 新增)— 关联 question
- 三者都可空(纯手动录入错题),三者均非空(自动沉淀错题)

**幂等保证**(research.md R-2):
```sql
-- 部分唯一约束
ALTER TABLE error_questions
ADD CONSTRAINT error_questions_source_question_id_key
UNIQUE (source_question_id);

-- 但需要 PG 部分唯一索引(因 PG UNIQUE 约束默认不允许 WHERE)
CREATE UNIQUE INDEX error_questions_source_question_id_uidx
ON error_questions (source_question_id)
WHERE source_question_id IS NOT NULL;
```

**ON CONFLICT DO UPDATE**(service 层):
```sql
INSERT INTO error_questions (
  user_id, source_session_id, source_question_id,
  dimension, question_text, answer_text, reference_answer_md,
  score, status, frequency
) VALUES (...)
ON CONFLICT (source_question_id) WHERE source_question_id IS NOT NULL
DO UPDATE SET
  score = EXCLUDED.score,
  answer_text = EXCLUDED.answer_text,
  reference_answer_md = EXCLUDED.reference_answer_md,
  updated_at = now();
-- 注意:dimension / question_text / status / frequency 不覆盖,保留首次创建
```

## 4. `interview_questions` 表引用(不修改)

019 错题自动沉淀读取 `interview_questions.score / dimension / text`,与对应 `ai_messages.body` 作为 `answer_text`。Phase 4 既有,019 不修改。

## 5. `interview_sessions` 与 `error_questions` 数据流

```
interview_sessions (id) ───┐
                           ├──> error_questions.source_session_id (FK, ON DELETE SET NULL)
interview_questions (id) ──┴──> error_questions.source_question_id (FK, ON DELETE SET NULL, UNIQUE)
```

## 6. 迁移脚本清单

| 文件 | 顺序 | 内容 |
|---|---|---|
| `backend/alembic/versions/019_job_fields.py` | 1 | `jobs` 加 5 列 + down-migration(各列 DROP) |
| `backend/alembic/versions/019_interview_job_id.py` | 2 | `interview_sessions` 加 `job_id` 列 + 索引 + FK + down-migration |
| `backend/alembic/versions/019_error_source_question_id.py` | 3 | `error_questions` 加 `source_question_id` 列 + 部分唯一索引 + FK + down-migration |

**down-migration 顺序**:与 up 相反(3 → 2 → 1)。

**前置校验**:迁移 1 前用 `dbq.py` 跑 `SHOW COLUMNS FROM jobs` 确认 5 列不存在;迁移 2 前确认 `interview_sessions.job_id` 不存在;迁移 3 前确认 `error_questions.source_question_id` 不存在。
