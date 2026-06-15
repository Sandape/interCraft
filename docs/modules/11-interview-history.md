# M11 · 面试历史 & 报告(无 Agent)

> 状态: draft · 所属领域: C · 优先级: P0
> 引用原文档: §3.2 (interview_sessions, interview_messages, interview_reports), §10.5

## 1. 需求摘要

落地面试会话的**纯 CRUD 与历史展示**:`interview_sessions`(会话头)+ `interview_messages`(对话流)+ `interview_reports`(终结报告)。本模块**不含 LangGraph 子图**(由 M15 接入),只提供查询、列表、归档接口。M15 的 Interview Agent 在节点回调里调用本模块的 Service 写入数据。

> **重要**:A1 待澄清——`interview_messages` 与 `ai_messages` 关系。本模块按 A1 方案 A 设计:`interview_messages` 是 `ai_messages` 的脱敏视图(View)。

## 2. 验收标准

- [ ] `GET /api/v1/interview-sessions` 历史列表(分页/筛选)
- [ ] `GET /api/v1/interview-sessions/{id}` 单场详情(含 messages,分页)
- [ ] `GET /api/v1/interview-sessions/{id}/messages` 消息流(游标分页)
- [ ] `GET /api/v1/interview-sessions/{id}/report` 报告
- [ ] `DELETE /api/v1/interview-sessions/{id}` 软删除(级联软删 messages)
- [ ] `POST /api/v1/interview-sessions/{id}/finish` 强制结束(标记 status='aborted'/'finished')
- [ ] Service `create_session(...)`, `append_message(...)`, `finalize_report(...)` 给 M15 用
- [ ] `interview_messages` 视图(如选方案 A)自动从 `ai_messages` 派生
- [ ] 软删除时同步删除 LangGraph checkpoint 数据(参见 §3.4)

## 3. 依赖与被依赖关系

**强依赖**: M02(表)、M05(RLS)
**弱依赖**: M14(LangGraph 基建)、M15(Interview 子图)、M12(悲观锁)
**被以下模块依赖**: M15(写入)、M18(Ability Diagnose 读取)、M23(前端面试列表 / 报告页)
**外部依赖**: 无

## 4. 数据模型

**`interview_sessions` 表**:
```
id UUID PK
user_id UUID NOT NULL (Mixin)
position TEXT NOT NULL
company TEXT NULL
mode TEXT NOT NULL  -- text / voice
status TEXT NOT NULL  -- active / finished / aborted / expired
started_at TIMESTAMPTZ NOT NULL DEFAULT now()
finished_at TIMESTAMPTZ NULL
duration_sec INT NULL  -- finalized 时计算
thread_id TEXT NOT NULL UNIQUE  -- 对应 LangGraph thread,通常 = session.id
question_count_target INT NOT NULL DEFAULT 5
config JSONB NOT NULL DEFAULT '{}'  -- 题目数 / 时长 / 难度
created_at / updated_at / deleted_at
```

**`interview_messages` 视图**(基于 A1 方案 A):
```sql
CREATE VIEW interview_messages AS
SELECT
    am.id,
    ai.context_id AS session_id,
    am.role,
    decrypt(am.content_enc) AS content,  -- 应用层 decrypt
    am.created_at AS timestamp,
    NULL::TEXT AS audio_ref  -- 预留
FROM ai_messages am
JOIN ai_conversations ai ON am.conversation_id = ai.id
WHERE ai.context_type = 'interview';
```

**`interview_reports` 表**:
```
id UUID PK
user_id UUID NOT NULL (Mixin)
session_id UUID NOT NULL UNIQUE FK(interview_sessions.id)
total_score NUMERIC(5,2) NOT NULL
dimensions_json JSONB NOT NULL  -- [{key, score, comment}, ...]
strengths JSONB NULL  -- ["...", "..."]
improvements JSONB NULL  -- ["...", "..."]
ai_summary TEXT NULL  -- 加密?MVP 不加密(报告不含敏感)
created_at  -- 单次生成不更新
```

## 5. 接口契约

**REST**:
| Method | Path | 说明 |
|---|---|---|
| GET | `/api/v1/interview-sessions` | 历史列表(过滤/排序) |
| GET | `/api/v1/interview-sessions/{id}` | 详情(汇总信息) |
| GET | `/api/v1/interview-sessions/{id}/messages` | 消息流(游标分页,解密) |
| GET | `/api/v1/interview-sessions/{id}/report` | 报告详情 |
| POST | `/api/v1/interview-sessions/{id}/finish` | 强制结束 |
| DELETE | `/api/v1/interview-sessions/{id}` | 软删除(级联) |

**Service 接口**(M15 用):
```python
async def create_session(user_id, position, company, mode, config) -> InterviewSession: ...
async def finalize_report(session_id, total_score, dimensions, strengths, improvements, ai_summary): ...
async def mark_aborted(session_id, reason): ...
```

**WebSocket**: 无(数据面由 M15 通过 `agent.{thread_id}` 推送)

## 6. 关键设计点

- **interview_messages 选 View 还是物化视图**:MVP 用 View(实时但需 join 解密);v1.1 评估物化视图性能
- **thread_id 生成**:`thread_id = session.id::text`(直接复用,见 A6)
- **status 流转**:`active → finished` (正常)/ `aborted`(用户主动) / `expired`(60 分钟超时,由 M15 cron 巡检)
- **超时巡检**:ARQ cron `*/5 * * * *`,扫 `status='active' AND started_at < now() - 60min` 标记 expired
- **报告永久保留**(§9.2),不参与软删除清除
- **级联软删**:`DELETE /interview-sessions/{id}` → soft_delete sessions → ARQ 异步 soft_delete messages + checkpoint(原文档 §3.4)

## 7. 待澄清

- **[A1]** interview_messages 三源关系:本模块按方案 A 设计(改 View);若团队最终决议方案 B,需重构成 `interview_messages` 独立表 + 自动同步
- 强制结束(POST /finish)的语义:仅设状态 vs 触发 report 节点 → 决议「仅设状态 = aborted,不强行生成报告」
- 报告中是否引用具体 message 段落(用于 UI 高亮):MVP 不引用,v1.1 加 `message_refs JSONB`

## 8. 实现提示

- 文件: `backend/app/api/v1/interviews.py`、`backend/app/services/interview_service.py`、`backend/app/repositories/interview_repo.py`、`backend/app/workers/tasks/interview_timeout.py`、`backend/migrations/versions/00XX_interview_messages_view.py`
- 复用: M02 ORM、M03 加密(用于解密 ai_messages.content)
- 与 mockData 关系:
  - `mockData.ts:169-273` `InterviewHistory` → 落到 interview_sessions + interview_reports
  - `mockData.ts:182` interview 中 `questions[]` → 由 ai_messages 派生(question_gen 节点产出)
  - `mockData.ts:204` `dimensions` → 落到 interview_reports.dimensions_json
