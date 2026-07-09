# Data Model: WeChat Conversational Agent

**Feature**: REQ-054 | **Date**: 2026-07-09

## Overview

本特性**不新增 PostgreSQL 业务表**。运行时会话态存 Redis；意图结果可作为 `agent_messages` 可选元数据。业务实体全部复用 REQ-052/053 与既有 Jobs/Interviews/Ability。

```
users 1──1 agents (052)
users 1──* agent_messages (052) ── optional intent metadata (054)
users 1──* jobs (053 status + interview_time)
users 1──* interview_sessions (existing) ── shared Web/WeChat
users 1──* ability_dimensions (existing)

Redis: wechat:conversation:{user_id}  → ConversationContext (TTL 24h)
```

## Runtime Entity: ConversationContext

**Storage**: Redis  
**Key**: `wechat:conversation:{user_id}`  
**TTL**: 86400 seconds（每次读写刷新）

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `state` | enum | yes | `idle` \| `awaiting_confirmation` \| `in_interview` |
| `pending_action` | object\|null | no | 待确认写操作 |
| `pending_action.type` | enum | if pending | `create_job` \| `update_job_status` \| `update_job_fields` |
| `pending_action.params` | object | if pending | 工具参数快照（已解析绝对时间等） |
| `queued_after_confirm` | array | no | 确认期间暂存的后续用户意图（FR-017） |
| `interview_session_id` | UUID\|null | if interviewing | 当前面试 session |
| `interview_round` | int\|null | if interviewing | 当前轮次 1–5 |
| `unknown_streak` | int | yes | 连续无法理解次数（默认 0） |
| `last_active_at` | ISO-8601 | yes | 上次交互时间（Asia/Shanghai 墙钟可派生） |
| `channel_hint` | string\|null | no | 最近活跃渠道提示（`wechat` / `web`），用于互斥文案 |

### State Transitions

```
idle ──(write intent, params complete)──► awaiting_confirmation
awaiting_confirmation ──(confirm)──► idle   (+ execute tool)
awaiting_confirmation ──(cancel)───► idle
idle ──(start_interview ok)──► in_interview
in_interview ──(pause | end | complete)──► idle
in_interview ──(continue from other channel)──► in_interview (same session)
* ──(TTL expire / Redis miss)──► treat as idle (rebuild)
```

**Rules**:
- `awaiting_confirmation` 仅接受确认/取消词；其他消息提示先确认，原文意图可入 `queued_after_confirm`
- `in_interview` 默认把非暂停/结束/继续的消息当作作答；无关指令提示或暂存
- Redis 不可写时：拒绝进入写确认流，回复稍后重试（不静默丢 pending）

## Logical Entity: IntentParseResult

不单独建表。可选写入 `agent_messages.metadata`（见下）。

| Field | Type | Description |
|-------|------|-------------|
| `intent` | enum | 见 [contracts/intents.yaml](./contracts/intents.yaml) |
| `entities` | object | 意图相关实体 |
| `confidence` | float 0–1 | LLM 置信度 |
| `alternatives` | array | confidence&lt;0.6 时的候选意图 |
| `parsed_at` | datetime | |

## Optional PG Extension: `agent_messages` metadata

**Decision**: 可选 Alembic 迁移（非 MVP 阻塞）：

| Column | Type | Description |
|--------|------|-------------|
| `intent` | TEXT NULL | 入站解析意图 |
| `confidence` | REAL NULL | |
| `metadata` | JSONB NULL | tool_calls 摘要、latency_ms 等（不含原文） |

若暂不迁移：指标与结构化日志仍满足 FR-019/020。

## Reused Entities (reference)

### Job（写工具目标）

- 创建：`company`, `position` 必填；可选 `base_location`, `jd_url`, `notes_md`, …
- 状态推进：`JOB_TRANSITIONS`（`app/domain/enums.py`）；面试态必填 `interview_time`（绝对时刻，解析自 Asia/Shanghai）
- 字段更新（微信允许）：仅 `base_location`, `jd_url`, `notes_md`
- 微信禁止：DELETE、Offer 字段

### InterviewSession

| Field | WeChat usage |
|-------|----------------|
| `status` | `pending` → `in_progress` → `completed` / `expired` |
| `mode` | `full` \| `quick_drill` |
| `job_id` | 定向面试可空（通用面试） |
| `thread_id` | `str(session.id)`，checkpoint 共享 |

**Mutex**: 同一 `user_id` 至多一条 `pending|in_progress`。

### Ability Profile

- 读 `GET`-等价 service：六维得分 + 趋势；无数据则引导首次面试

## Validation Rules (cross-cutting)

| Rule | Source |
|------|--------|
| 写操作必须先 pending + 用户确认 | FR-008, SC-005 |
| confidence &lt; 0.6 不执行 | FR-003 |
| LLM 失败重试 1 次后降级、不写 | FR-003a |
| 相对时间 → Asia/Shanghai 绝对时间 | FR-006b |
| 模糊匹配最多 5 候选 | FR-007 |
| 微信回复单段建议 ≤500 字，长文分段 | FR-012, 052 split |

## Relationships to Tools

| Tool | Reads | Writes |
|------|-------|--------|
| `create_job` | — | jobs |
| `update_job_status` | jobs | jobs.status, interview_time |
| `update_job_fields` | jobs | location/jd/notes |
| `query_jobs` | jobs | — |
| `query_reports` | interview_sessions / reports | — |
| `query_ability` | ability_dimensions | — |
| interview adapter | interview_sessions, checkpoint | session + graph state |
