# M01 · 项目骨架 & 基础设施

> 状态: draft · 所属领域: A · 优先级: P0
> 引用原文档: §2.2, §2.3, §11, §12

## 1. 需求摘要

搭建 Python 3.11+ 后端工程的最小可运行骨架:FastAPI + Uvicorn、uv 包管理、Docker Compose 起 PostgreSQL 15 + Redis,提供 `/healthz` 健康检查、统一日志、配置分层(`.env` / `config.yaml`)、Alembic 迁移壳。是所有后续模块的地基。

## 2. 验收标准

- [ ] `git clone && uv sync && docker-compose up -d` 在 5 分钟内启动完整栈
- [ ] `curl http://localhost:8000/healthz` 返回 `{"status":"ok","db":"ok","redis":"ok"}`
- [ ] `alembic upgrade head` 跑通空迁移
- [ ] 日志为 JSON 结构,字段含 `timestamp / level / request_id / message`
- [ ] 配置支持环境变量覆写(如 `DATABASE_URL` 覆盖 yaml 默认)
- [ ] 异步全栈:FastAPI 路由、SQLAlchemy session、Redis 客户端均为 async

## 3. 依赖与被依赖关系

**强依赖**: 无(根模块)
**弱依赖**: 无
**被以下模块依赖**: 所有后续后端模块(M02-M22)
**外部依赖**:
- Python 3.11+,uv 包管理器
- Docker / Docker Compose
- PostgreSQL 15 镜像、Redis 7 镜像

## 4. 数据模型

无业务表。建议引入下列 SQLAlchemy Mixin(给后续模块复用):

```python
class TimestampedMixin:
    created_at: Mapped[datetime] = mapped_column(default=func.now())
    updated_at: Mapped[datetime] = mapped_column(default=func.now(), onupdate=func.now())

class SoftDeletableMixin:
    deleted_at: Mapped[datetime | None] = mapped_column(nullable=True)

class TenantScopedMixin:
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), index=True)
```

## 5. 接口契约

**REST**:
| Method | Path | 说明 |
|---|---|---|
| GET | `/healthz` | 健康检查(DB + Redis + version) |
| GET | `/api/v1/openapi.json` | OpenAPI 3.1 schema(自动生成) |

**WebSocket**: 无
**工具**: 无

## 6. 关键设计点

- **包管理选型**: 用 uv 替代 pip + venv,启动快、锁文件可信
- **配置分层**: `config/base.yaml`(默认)+ `config/{env}.yaml`(覆盖)+ 环境变量(最高优先级);用 `pydantic-settings` 统一加载
- **日志**: `structlog` + 自定义 processor 注入 `request_id`(从 FastAPI middleware 拿)
- **Docker Compose 服务**: `postgres` / `redis` / `arq-worker` / `api`(api 与 worker 共享镜像)
- **目录骨架**: 直接落地原文档 §2.3 的 `backend/app/...` 结构,但 M01 阶段仅创建空文件占位

## 7. 待澄清

- 无原文档冲突,所有决策清晰

## 8. 实现提示

- 文件: `backend/pyproject.toml`、`backend/app/main.py`、`backend/app/core/config.py`、`backend/app/core/db.py`、`backend/app/core/redis.py`、`backend/app/core/logging.py`、`backend/docker-compose.yml`、`backend/alembic.ini`
- 复用: 无
- 与 mockData 关系: 无
