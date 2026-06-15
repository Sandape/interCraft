# M02 · 数据库 & ORM

> 状态: draft · 所属领域: A · 优先级: P0
> 引用原文档: §2.2, §3.* (所有实体), §4.3 (RLS)

## 1. 需求摘要

接入 SQLAlchemy 2.0 async + asyncpg,落地 §3.2 的核心实体表(领域模型 + Pydantic Schema + Repository 模式),搭建 PostgreSQL RLS 框架(SET LOCAL `app.user_id`),提供 Alembic 迁移基础。本模块**只建表 + 跑通会话注入 + Repository 抽象**,不实现具体业务逻辑(交给 M06-M11)。

## 2. 验收标准

- [ ] 所有 §3.2 实体(users, resume_branches, resume_blocks, resume_versions, interview_sessions, interview_messages, interview_reports, error_questions, ability_dimensions, ability_history, tasks, activities, ai_conversations, ai_messages, tool_call_logs, auth_sessions, audit_logs, user_credentials)的 SQLAlchemy 模型就绪,通过 `alembic upgrade head` 创建
- [ ] 所有业务表自动带 `id / user_id / created_at / updated_at / deleted_at` 五字段(通过 Mixin 复用,见 A13 修订)
- [ ] RLS 策略已为所有业务表注入:`USING (user_id = current_setting('app.user_id', true)::uuid)`
- [ ] 提供 `get_db_session(user_id)` 依赖,自动 `SET LOCAL app.user_id`
- [ ] 抽象 `BaseRepository[T]`,覆盖 list / get / create / update / soft_delete 通用操作
- [ ] 单元测试:跨用户查询返回空(RLS 验证)

## 3. 依赖与被依赖关系

**强依赖**: M01(项目骨架)
**弱依赖**: 无
**被以下模块依赖**: M04(账号)、M05(会话/RLS)、M06-M22(所有业务模块)
**外部依赖**: SQLAlchemy 2.0+, asyncpg, alembic, Pydantic v2

## 4. 数据模型

落地 §3.2 全部 18 张表。统一约束:
- 主键:UUID v7(时间有序,索引友好)
- 时间:`timestamptz`,UTC 存储
- JSON 字段:`jsonb`(可索引)
- 软删除:`deleted_at IS NULL` 视为存活
- 外键:级联软删除(物理外键 ON DELETE NO ACTION,逻辑级联在应用层实现)

**敏感字段**(详见 §3.3):
- `user_credentials.id_card_enc / real_name_enc / salary_range_enc`: BYTEA(AES-GCM 密文)
- `ai_messages.content`: TEXT(应用层加密,见 M03)

## 5. 接口契约

**REST**: 本模块不暴露 API,仅提供 ORM 与 Repository
**WebSocket**: 无
**Repository 接口模板**:
```python
class BaseRepository(Generic[T]):
    async def list(self, *, filter: dict, cursor: str | None, limit: int) -> Page[T]: ...
    async def get(self, id: UUID) -> T | None: ...
    async def create(self, data: dict) -> T: ...
    async def update(self, id: UUID, data: dict) -> T: ...
    async def soft_delete(self, id: UUID) -> None: ...
```

## 6. 关键设计点

- **uuidv7 主键**:替代 uuid4,索引友好;通过 `psycopg.extras.uuid_v7()` 或 `uuid6` 库生成
- **Mixin 组合**:`TimestampedMixin + SoftDeletableMixin + TenantScopedMixin`(后两个对业务表)
- **RLS 注入时机**: FastAPI 依赖 `get_db_session(user_id=Depends(current_user))` 在事务开始即 `SET LOCAL app.user_id = :uid`
- **Alembic 自定义指令**: `op.enable_rls('table_name')`,自动注入策略
- **Pydantic Schema 分层**: `*In`(入参)/ `*Out`(出参)/ `*Patch`(部分更新)
- **JSON 字段类型化**: 用 `Annotated[JSONB, type_hint]` 自动转 Pydantic 模型

## 7. 待澄清

- **[A2]** LangGraph checkpoints 表的 RLS 隔离方案(应用层校验 vs thread_id 编码 vs 手工 RLS)。M02 阶段决定**应用层校验**(配合 M14)
- **[A13]** §3.2 隐含字段需在本模块统一标注;所有 Repository 默认过滤 `deleted_at IS NULL`

## 8. 实现提示

- 文件: `backend/app/domain/{users,resumes,interviews,errors,abilities,tasks,activities,ai,audit}.py`、`backend/app/schemas/...`、`backend/app/repositories/base.py`、`backend/app/core/db.py`、`backend/migrations/versions/0001_initial.py`
- 复用: 与 `src/data/mockData.ts` 的字段一一对照(`ResumeBranch` / `ResumeBlock` / `InterviewHistory` / `ErrorQuestion` / `AbilityDimension`),保证前后端 schema 对齐
