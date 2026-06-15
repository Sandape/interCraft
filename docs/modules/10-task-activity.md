# M10 · 任务 & 活动流

> 状态: draft · 所属领域: C · 优先级: P1
> 引用原文档: §3.2 (tasks, activities), §8.1, §8.2, §8.3

## 1. 需求摘要

落地任务中心(`tasks`)+ 活动流(`activities`)+ 站内通知(`notifications`,v1.0)。任务支持类型(简历/面试/复习/通用)+ 截止时间 + 优先级;活动流游标分页;事件驱动写入(简历提交 → 自动建任务,面试完成 → 写活动);WebSocket 实时推送 `notification.created`。

## 2. 验收标准

- [ ] `GET /api/v1/tasks` 列表(filter by status, due_at <= now+7d)
- [ ] `POST /api/v1/tasks` 新建
- [ ] `PATCH /api/v1/tasks/{id}` 更新状态(todo → doing → done / abandoned)
- [ ] `DELETE /api/v1/tasks/{id}` 软删除
- [ ] `GET /api/v1/activities?cursor=&limit=20` 游标分页倒序
- [ ] `GET /api/v1/notifications` 站内通知列表(未读 / 全部)
- [ ] `PATCH /api/v1/notifications/{id}/read` 标记已读
- [ ] WebSocket 推 `notification.created` 事件
- [ ] Service `record_activity(...)` 接口供其他模块调用(简历提交、面试完成、错题答对)
- [ ] Service `create_interview_prep_task(branch)` 接口给 M06 用(简历 → 任务,见 A12)
- [ ] activities 90 天归档 ARQ 任务(归档冷库或物理删除,v1.0 物理删除)

## 3. 依赖与被依赖关系

**强依赖**: M02(表)、M05(RLS)、M03(ARQ + Redis Pub-Sub)
**弱依赖**: M12(WebSocket 控制面)
**被以下模块依赖**: M06(简历→任务触发)、M11/M15(面试→活动)、M08/M17(错题→活动)、M23(前端 Dashboard)
**外部依赖**: 无

## 4. 数据模型

**`tasks` 表**:
```
id UUID PK
user_id UUID NOT NULL (Mixin)
title TEXT NOT NULL
detail TEXT NULL
type TEXT NOT NULL  -- resume / interview / review / general
due_at TIMESTAMPTZ NULL
priority TEXT NOT NULL DEFAULT 'medium'  -- high / medium / low
status TEXT NOT NULL DEFAULT 'todo'  -- todo / doing / done / abandoned
ref_type TEXT NULL  -- 关联资源类型,如 resume_branch
ref_id UUID NULL  -- 关联资源 id
created_at / updated_at / deleted_at
```

**`activities` 表**:
```
id UUID PK
user_id UUID NOT NULL (Mixin)
type TEXT NOT NULL  -- resume.optimized / interview.completed / error.recovered / ...
title TEXT NOT NULL  -- 简短描述
detail TEXT NULL
ref_type TEXT NULL
ref_id UUID NULL
occurred_at TIMESTAMPTZ NOT NULL DEFAULT now()
```

**`notifications` 表**:
```
id UUID PK
user_id UUID NOT NULL (Mixin)
type TEXT NOT NULL  -- info / warning / urgent / system
title TEXT NOT NULL
body TEXT NULL
ref_url TEXT NULL
read_at TIMESTAMPTZ NULL
occurred_at TIMESTAMPTZ NOT NULL DEFAULT now()
```

**索引**:
- `tasks (user_id, due_at NULLS LAST, priority DESC, status)`
- `activities (user_id, occurred_at DESC)` 游标分页
- `notifications (user_id, read_at NULLS FIRST, occurred_at DESC)`

## 5. 接口契约

**REST**:
| Method | Path | 说明 |
|---|---|---|
| GET | `/api/v1/tasks` | 列表 |
| POST | `/api/v1/tasks` | 新建 |
| PATCH | `/api/v1/tasks/{id}` | 更新 |
| DELETE | `/api/v1/tasks/{id}` | 软删除 |
| GET | `/api/v1/activities` | 游标分页 |
| GET | `/api/v1/notifications` | 通知列表 |
| PATCH | `/api/v1/notifications/{id}/read` | 标记已读 |

**WebSocket**:
| Channel | 事件 | 触发 |
|---|---|---|
| `sync.{user_id}` | `notification.created` | 新通知 |

**Service 接口**(供其他模块):
```python
async def record_activity(user_id, type, title, detail, ref_type, ref_id): ...
async def create_interview_prep_task(branch: ResumeBranch): ...
async def push_notification(user_id, type, title, body, ref_url): ...
```

## 6. 关键设计点

- **事件总线 vs 直接 Service 调用**:MVP 直接调 Service(简单);v1.1 可引入事件总线解耦
- **任务幂等**:`create_interview_prep_task` 基于 `(branch_id, type='interview_prep')` 去重
- **活动流定义**:`type` 用 `domain.action` 命名(`resume.optimized`、`interview.completed`、`error.recovered`、`ability.updated`)
- **WebSocket 推送**:`push_notification` → INSERT notifications → Redis Pub-Sub → 由 M12 的 WS 服务转发
- **90 天归档**:ARQ cron `0 3 * * *`(每日 03:00),`DELETE FROM activities WHERE occurred_at < now() - interval '90 days'`(原文档 §8.2 说归档冷库,v1.0 直接物理删除)

## 7. 待澄清

- **[A12]** 任务自动触发由 M06 显式调用 `TaskService.create_interview_prep_task(branch)`,本模块仅提供接口
- 通知合并策略:同类型短时间多次(如 5 分钟内三次面试完成)是否合并展示 → MVP 不合并,v1.1 引入

## 8. 实现提示

- 文件: `backend/app/api/v1/tasks.py`、`backend/app/api/v1/activities.py`、`backend/app/api/v1/notifications.py`、`backend/app/services/task_service.py`、`backend/app/services/activity_service.py`、`backend/app/services/notification_service.py`、`backend/app/workers/tasks/activities_archive.py`
- 复用: M03 的 Pub-Sub
- 与 mockData 关系:
  - `mockData.ts:481-503` `upcomingTasks` → 直接落地到 tasks
  - `mockData.ts:505-534` `recentActivities` → 落到 activities
