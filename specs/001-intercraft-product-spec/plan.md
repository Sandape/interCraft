# Implementation Plan: InterCraft Phase 1 — P0 基线

**Branch**: `001-intercraft-product-spec` | **Date**: 2026-06-12 | **Spec**: [spec.md](./spec.md) | **Research**: [research.md](./research.md)

**Input**: Feature specification from `specs/001-intercraft-product-spec/spec.md`(全产品 spec)+ 范围限定到 Phase 1(M01-M07 + M23 基础设施)。
**Note**: 本 plan.md 是「**全产品 spec / Phase 1 plan**」结构,后续每个 phase 可在本目录追加 `phase-N.md`,或为每个 phase 建独立 spec 目录。

---

## Summary

落地 **Phase 1 — P0 基线**:用户可在浏览器完成「邮箱注册 → 登录 → 拿到 JWT → 创建/编辑简历核心与分支 → 手动保存版本 → 刷新页面验证持久化」端到端流程。配套 5 设备限制 + 自动踢出、RLS 隔离的租户数据、JSON Patch 版本快照、Repository/React Query/WS 客户端的前端基础设施。后端 7 个模块(M01-M07)+ 前端基础设施(M23 子集)同步就位,**不**涉及 LangGraph、悲观锁、离线、Agent 子图。

技术路径(基于 research.md DEC-* 决议):
- 后端 FastAPI + SQLAlchemy 2.0 async + asyncpg + ARQ + Redis 7 + PostgreSQL 15(uuidv7 自写 + RLS `SET LOCAL app.user_id`)
- 鉴权 fastapi-users 13.x(JWT strategy + bcrypt 12) + PyJWT 2.9
- 简历版本 RFC 6902 JSON Patch(python-jsonpatch + fast-json-patch,跨端 parity 测试)
- 前端 Vite + React 18 + TS strict + Zustand + React Query + openapi-typescript 生成 schema + Vitest/MSW/Playwright 三层测试
- 一键回退:`VITE_USE_MOCK=true` 走 mock,默认 `false` 走真实 API

---

## Technical Context

> **来源**:本节内容由 research.md DEC-1 ~ DEC-12 决议填充,不再保留任何 NEEDS CLARIFICATION。

**Language/Version**:
- 后端:Python 3.11+(uv 管理,`pyproject.toml` 锁定)
- 前端:TypeScript 5.6 strict mode(`tsconfig.json` 已 strict)
- 数据库 SQL:PostgreSQL 15 方言

**Primary Dependencies**:

| 层 | 依赖 | 版本(锁定) | DEC |
|---|---|---|---|
| 后端 - Web | `fastapi` | >=0.115,<0.117 | — |
| 后端 - Web | `uvicorn[standard]` | >=0.30,<0.33 | — |
| 后端 - ORM | `sqlalchemy[asyncio]` | >=2.0.30,<2.1 | — |
| 后端 - DB driver | `asyncpg` | >=0.29,<0.31 | — |
| 后端 - Migrations | `alembic` | >=1.13,<2.0 | — |
| 后端 - Settings | `pydantic-settings` | >=2.4,<3.0 | — |
| 后端 - Logging | `structlog` | >=24.1,<25.0 | — |
| 后端 - Auth | `fastapi-users[sqlalchemy]` | >=13.0,<14.0 | DEC-1 |
| 后端 - JWT | `PyJWT[cryptography]` | >=2.9,<3.0 | DEC-5 |
| 后端 - 加密 | `cryptography` | >=42,<44 | — |
| 后端 - 密码 | `bcrypt` | >=4.2,<5.0 | — |
| 后端 - 队列 | `arq` | >=0.25,<0.27 | — |
| 后端 - 缓存 | `redis>=5.0` (asyncio) | >=5.0,<6.0 | — |
| 后端 - JSON Patch | `jsonpatch` | >=1.33,<2.0 | DEC-4 |
| 后端 - Fractional idx | `python-fractional-indexing` | >=1.0,<2.0 | DEC-3 |
| 后端 - HTTP 测试 | `httpx` | >=0.27,<0.29 | — |
| 后端 - 单测 | `pytest` + `pytest-asyncio` | >=8,<9 / >=0.23,<0.25 | — |
| 前端 - 框架 | `react` + `react-dom` | ^18.3 | — |
| 前端 - 路由 | `react-router-dom` | ^6.27 | — |
| 前端 - 状态 | `zustand` | ^4.5 | — |
| 前端 - 数据 | `@tanstack/react-query` | ^5.59 | — |
| 前端 - 类型生成 | `openapi-typescript` | ^7.4 (devDeps) | DEC-9 |
| 前端 - JSON Patch | `fast-json-patch` | ^3.1 | DEC-4 |
| 前端 - Fractional idx | `fractional-indexing` | ^3.2 | DEC-3 |
| 前端 - 哈希(指纹回退) | `js-sha256` | ^0.11 | DEC-7 |
| 前端 - 单测 | `vitest` + `@testing-library/react` | ^2 / ^16 | DEC-6 |
| 前端 - DOM | `happy-dom` | ^15 | DEC-6 |
| 前端 - API mock | `msw` | ^2 | DEC-6 |
| 前端 - E2E | `@playwright/test` | ^1.48 | DEC-6 |

**Storage**:
- 主库:PostgreSQL 15(uuidv7 主键,RLS 启用所有业务表)
- 缓存/Pub-Sub:Redis 7(本阶段仅用于 last_seen 缓冲,锁服务 Phase 3 引入)
- 文件:`docs/` 持久化(规范/计划/报告),`.specify/` 持久化(spec-kit 元数据)
- 不在 Phase 1:对象存储(用户导出 zip 是 Phase 6 范畴)

**Testing**:
- 后端单测:`pytest` + `pytest-asyncio`,就近放在 `backend/app/**/tests/test_*.py`,`conftest.py` 提供事务回滚 fixture
- 后端集成:`tests/integration/`,起临时 PostgreSQL + Redis(`docker-compose.test.yml`)+ httpx.AsyncClient
- 后端契约:OpenAPI schema 自动(`/api/v1/openapi.json`),由前端 `openapi-typescript` 消费
- 前端单测:`vitest` + `@testing-library/react` + MSW 拦截,文件就近 `src/**/*.test.ts(x)`
- 前端 E2E:`playwright`,`tests/e2e/`,走真实 dev server(真实后端,可在 CI 中以 docker compose 启)

**Target Platform**:
- 后端:Linux 容器(本地开发 Windows + WSL2,CI 跑 Linux),Docker Compose
- 前端:现代桌面浏览器(Chrome / Edge / Firefox / Safari 最近 2 个大版本);移动端按 spec A2 「可用但非主战场」不专门优化

**Project Type**:**web**(frontend + backend,分两个独立子项目,共享契约通过 OpenAPI)。

**Performance Goals**(对齐 spec §4 SC-010 ~ SC-013):
- SC-010 关键 REST API P95 ≤ 500ms
- SC-013 Dashboard 首屏 LCP ≤ 2s(4G)
- Phase 1 演示场景 SC-001:5 分钟内完成「注册 → 登录 → 创分支 → 改 3 块 → 保存版本 → 刷新验证」

**Constraints**:
- 离线/Outbox 暂不实现(M13 Phase 3);断网时 API 失败 → UI 提示重试
- WS 断线重连 + `last_seen_checkpoint_id` 仅落骨架(无业务)
- 第三方 OAuth 仅留路由占位(OOS-6)
- 移动端不专门优化
- i18n 不实现(默认 zh-CN,文案写在组件内)
- 多端同步未启用,无悲观锁(Phase 1 不阻止并发编辑,后写覆盖;Phase 3 引入)

**Scale/Scope**(Phase 1 范围):
- 用户数:≤ 1000(开发期)
- 简历分支:每用户 ≤ 10(按 A4)
- 块:每分支 ≤ 100
- 版本:每分支 ≤ 50(开发期,生产预期 ≤ 200)
- 12 个 UI 页面中 Phase 1 涉及 2 个:**Login** + **ResumeList/ResumeEditor**;其余页面继续读 mockData,Phase 2-6 渐进迁移
- 演示场景 SC-001 必须可重复

---

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

依据 `.specify/memory/constitution.md` v1.0.0 的 5 大原则 + 技术约束 + 工作流,逐条校验:

### 原则 I — Library-First

| 检查点 | Phase 1 落点 | 状态 |
|---|---|---|
| 后端每个模块自包含(M01-M07),有 README + 公开 API + 配置 + 示例命令 | 每个模块在 `backend/app/<module>/` 下有 `README.md`,`uv run python -m app.<module>.cli --help` 可跑 | ✅ |
| AI 编排子图是「库」 | Phase 1 不涉及(Phase 4-5 范畴) | N/A |
| 前端特性模块是「库」 | `src/repositories/` 每个文件 + `src/api/` 客户端 = 独立模块,有自己的 README | ✅ |

### 原则 II — CLI Interface

| 检查点 | Phase 1 落点 | 状态 |
|---|---|---|
| 文本 I/O,默认人类可读,`--json` 模式可机读 | 每个模块 CLI 入口在 `backend/app/<module>/cli.py`,`make_*.py --json` 输出 JSON | ✅ |
| CLI 退出码有文档(`0` 成功 / 非 0 失败) | README 中列出 | ✅ |
| 本地优先,无需启动完整 Web 栈 | `uv run python -m app.<module>.cli ...` 直接可用 | ✅ |
| 前端核心逻辑可被 CLI 验证 | 关键纯函数(版本 diff 计算、指纹算法)提供 `node scripts/*.mjs` 命令,Phase 1 至少覆盖:`scripts/check-version-diff.mjs` | ✅ |

### 原则 III — Test-First(NON-NEGOTIABLE)

| 检查点 | Phase 1 落点 | 状态 |
|---|---|---|
| 写测试 → 看红 → 签收 → 最小实现 → 重构 | tasks.md 中每个模块任务都先列「test 任务」再做「impl 任务」 | ✅ |
| UI 任务:组件测试 / hook 测试 / E2E 故事先于组件 | ResumeEditor 改 mock 接入真实 API 时,先写 MSW 拦截 + 组件测试再改代码 | ✅ |
| AI prompt 任务:评估样例先于 prompt | Phase 1 不涉及 | N/A |
| 任务只有在测试就位且为绿时才视为「完成」 | tasks.md 用 `[T]` 前缀标记测试任务,完成定义 = 测试绿 | ✅ |

### 原则 IV — Integration & Synchronization Testing

| 检查点 | Phase 1 落点 | 状态 |
|---|---|---|
| 跨服务通信(WS、REST)在真实或内存级适配器上端到端跑通 | `tests/integration/` 起真实 Postgres+Redis(测试容器),不走 mock;`tests/e2e/` Playwright 走真实后端 | ✅ |
| 同步与离线路径 | Phase 1 不涉及同步/离线(Phase 3) | N/A |
| AI 编排边界 | Phase 1 不涉及 | N/A |
| 不允许「全部 mock 的快乐路径」 | 关键集成测试 = 真实 DB + 真实 Redis;前端 E2E = 真实后端;`VITE_USE_MOCK=true` 仅作为 dev fallback,**测试套件不依赖 mock** | ✅ |

### 原则 V — Observability

| 检查点 | Phase 1 落点 | 状态 |
|---|---|---|
| 结构化日志(JSON / key=value),含 `timestamp / level / request_id / message` | `app/core/logging.py` 用 structlog,M01 §6 落实 | ✅ |
| 请求关联 ID 跨服务传播 | FastAPI middleware 注入 `X-Request-ID`(生成或透传),写入日志 context;`audit_logs.request_id` 字段(M02) | ✅ |
| 指标:请求率 / 错误率 / 延迟(p50/p95/p99) | Phase 1 仅 `GET /metrics` 暴露 Prometheus 文本(基础 counter/histogram);不接告警 | ✅ |
| AI 专用指标 | Phase 1 不涉及 | N/A |
| 错误上下文含足够复现信息 | 异常统一经 `app/core/exceptions.py` 包装,带 request_id + endpoint + user_id(若有) | ✅ |
| CLI 即可观测:从保存的输入夹具重放失败场景 | `uv run python -m app.<module>.cli replay <fixture.json>` 路径(Phase 1 至少 `app.modules.auth.cli replay` 落地) | ✅ |

### Technology & Stack Constraints

| 检查点 | Phase 1 落点 | 状态 |
|---|---|---|
| 前端 TS strict + React 18 + Vite + TailwindCSS | `tsconfig.json` strict;React 18.3;Vite 5.4;Tailwind 3.4(已配置) | ✅ |
| 前端路由 `react-router-dom` v6 | 已是 v6.27 | ✅ |
| 组件库 / 状态方案需在 plan 给出书面理由 | Zustand + React Query,理由:轻量 / 服务端数据缓存能力强 / 与 Convex/Replicache 等 OSS 方案一致 | ✅ |
| 后端 MUST 暴露 HTTP 契约 + 机器可读 schema | FastAPI 自动 OpenAPI 3.1(`/api/v1/openapi.json`)+ `/api/v1/redoc` | ✅ |
| 持久层 MUST 用项目标准 ORM + 迁移工具,不允许即兴 SQL | SQLAlchemy 2.0 async + Alembic(无裸 SQL 字符串;如需特殊查询,封装在 Repository) | ✅ |
| AI 编排基于 LangGraph | Phase 1 不涉及 | N/A |
| 同步与离线客户端 | Phase 1 不涉及 | N/A |
| 安全与隐私:用户数据 MUST 静态 + 传输加密;密钥从环境变量读 | `app/core/crypto.py` 读 `MASTER_KEY`(base64);所有响应强制 HTTPS(生产);Postgres 端启用 `sslmode=require`;Redis 启用 `requirepass` | ✅ |
| 会话与 RLS(M05)是用户范围数据的唯一合法通道,强制启用 | `get_db_session(user_id=Depends(current_user))` 强制注入 `SET LOCAL app.user_id`;所有业务表 RLS 策略 | ✅ |

### Development Workflow

| 检查点 | Phase 1 落点 | 状态 |
|---|---|---|
| 分支命名 `[###-feature-name]` | `001-intercraft-product-spec`(已是) | ✅ |
| 每个 PR 至少 1 次批准,reviewer 校验 I-V 合规 | Phase 1 内不强制多人 review(单人或对 reviewer),但 tasks.md 标注「**签收**」步骤 | ✅ |
| 质量门禁:lint / typecheck / 单测 / 集成 / 契约 | `pre-commit`:ruff + mypy + tsc + vitest + pytest(本地);CI:同 + Playwright | ✅ |
| Constitution Check 门禁 | 本节 + Plan 末尾「Re-evaluation after Phase 1 design」 | ✅ |
| Semantic Versioning + 公开 API 版本化 | `app/__version__.py = "0.1.0"`;REST 路径 `/api/v1/` | ✅ |
| 库级 README(原则 I) | 每个模块 `README.md` | ✅ |

### 治理

- 原则/约束如需偏离,必须在 Complexity Tracking 中给出理由。
- 任何运行时变更(配置 / 环境 / 工具)与宪法冲突时,以宪法为准。
- 本 plan 与宪法 v1.0.0 完全兼容;无未声明的偏离。

### Constitution Check 结论

**PASS — 无违规项**。Complexity Tracking 为空(下方保留结构占位)。

---

## Project Structure

### Documentation (this feature)

```text
specs/001-intercraft-product-spec/
├── plan.md              # 本文件
├── research.md          # Phase 0 输出 ✓
├── data-model.md        # Phase 1 输出
├── quickstart.md        # Phase 1 输出
├── contracts/           # Phase 1 输出
│   ├── README.md        # 契约总览
│   ├── auth.md          # 鉴权契约(M04)
│   ├── users.md         # 用户/资料契约(M04)
│   ├── sessions.md      # 设备/会话契约(M05)
│   ├── resumes.md       # 简历分支契约(M06)
│   ├── blocks.md        # 块契约(M06)
│   ├── versions.md      # 版本契约(M07)
│   ├── health.md        # /healthz 契约(M01)
│   └── events.md        # 共享错误响应 / 状态码
├── checklists/
│   └── requirements.md  # Spec quality checklist ✓
├── spec.md              # 全产品 spec ✓
└── tasks.md             # Phase 2 输出(/speckit-tasks),Phase 1 计划完成后生成
```

### Source Code (repository root)

```text
D:\Project\eGGG\
├── backend/                          # 后端 Python 项目(uv 管理)
│   ├── pyproject.toml                # uv 项目配置 + 依赖锁
│   ├── uv.lock
│   ├── Dockerfile                    # api/worker 共享镜像
│   ├── docker-compose.yml            # postgres / redis / api / worker
│   ├── docker-compose.test.yml       # 测试环境(postgres + redis,临时端口)
│   ├── alembic.ini
│   ├── migrations/                   # Alembic 迁移
│   │   ├── env.py
│   │   └── versions/
│   │       └── 0001_initial.py       # M01-M07 一次落地
│   ├── app/
│   │   ├── __init__.py               # __version__ = "0.1.0"
│   │   ├── main.py                   # FastAPI 入口 + lifespan + middleware
│   │   ├── core/                     # 横切:配置/日志/异常/DB/Redis/Crypto/IDs
│   │   │   ├── __init__.py
│   │   │   ├── config.py             # pydantic-settings(YAML + env)
│   │   │   ├── logging.py            # structlog + request_id 注入
│   │   │   ├── exceptions.py         # 统一异常类型 + handler
│   │   │   ├── db.py                 # async engine + session factory
│   │   │   ├── redis.py              # redis.asyncio 客户端
│   │   │   ├── crypto.py             # AES-256-GCM
│   │   │   ├── ids.py                # uuidv7 自写(Phase 1 DEC-2)
│   │   │   ├── security.py           # bcrypt / JWT helpers
│   │   │   ├── deps.py               # current_user / get_db_session
│   │   │   ├── middleware.py         # request_id + last_seen 跟踪
│   │   │   └── rate_limit.py         # Redis token bucket(M03)
│   │   ├── modules/                  # 业务模块(每模块独立库)
│   │   │   ├── auth/                 # M04
│   │   │   │   ├── __init__.py
│   │   │   │   ├── README.md
│   │   │   │   ├── models.py         # User / UserCredential
│   │   │   │   ├── schemas.py        # Pydantic In/Out/Patch
│   │   │   │   ├── service.py
│   │   │   │   ├── repository.py
│   │   │   │   ├── api.py            # /auth/* + /users/me 路由
│   │   │   │   ├── cli.py            # 模块 CLI(principle II)
│   │   │   │   ├── strategy.py       # fastapi-users JWT strategy 适配
│   │   │   │   └── tests/
│   │   │   │       ├── test_models.py
│   │   │   │       ├── test_service.py
│   │   │   │       └── test_api.py
│   │   │   ├── sessions/             # M05
│   │   │   │   ├── README.md
│   │   │   │   ├── models.py         # AuthSession
│   │   │   │   ├── schemas.py
│   │   │   │   ├── service.py        # 5 设备限制 + 设备指纹
│   │   │   │   ├── api.py            # /users/me/sessions
│   │   │   │   └── tests/
│   │   │   ├── resumes/              # M06
│   │   │   │   ├── README.md
│   │   │   │   ├── models.py         # ResumeBranch / ResumeBlock
│   │   │   │   ├── schemas.py
│   │   │   │   ├── service.py        # COW 写时复制
│   │   │   │   ├── repository.py     # fractional-indexing
│   │   │   │   ├── api.py            # /resume-branches + /resume-blocks
│   │   │   │   └── tests/
│   │   │   └── versions/             # M07
│   │   │       ├── README.md
│   │   │       ├── models.py         # ResumeVersion
│   │   │       ├── schemas.py
│   │   │       ├── service.py        # 完整快照 + diff 混合
│   │   │       ├── api.py            # /resume-branches/{id}/versions
│   │   │       ├── auto_snapshot.py  # ARQ 30min cron
│   │   │       └── tests/
│   │   ├── domain/                   # 共享 Mixin + 通用类型(M02)
│   │   │   ├── base.py               # DeclarativeBase
│   │   │   ├── mixins.py             # Timestamped/SoftDeletable/TenantScoped
│   │   │   ├── pagination.py
│   │   │   └── rls.py                # enable_rls Alembic op + 策略模板
│   │   ├── repositories/             # 共享 Repository 抽象
│   │   │   ├── base.py               # BaseRepository[T] 泛型
│   │   │   └── __init__.py
│   │   ├── api/                      # FastAPI 路由聚合
│   │   │   ├── v1/
│   │   │   │   ├── __init__.py       # APIRouter
│   │   │   │   ├── auth.py           # 挂载 modules.auth.api
│   │   │   │   ├── users.py
│   │   │   │   ├── sessions.py
│   │   │   │   ├── resumes.py
│   │   │   │   ├── versions.py
│   │   │   │   └── health.py
│   │   │   └── deps.py               # current_user 依赖
│   │   ├── workers/                  # ARQ(M03)
│   │   │   ├── main.py               # WorkerSettings
│   │   │   └── tasks/
│   │   │       └── dummy.py          # 跑通示例
│   │   └── cli/                      # 顶层 CLI
│   │       └── main.py               # python -m app.cli ...
│   ├── tests/                        # 跨模块集成
│   │   ├── conftest.py               # 事务回滚 + 真实 DB fixture
│   │   ├── integration/
│   │   │   ├── test_health.py
│   │   │   ├── test_auth_flow.py     # 注册 → 登录 → 改密 → 5 设备限制
│   │   │   ├── test_resume_crud.py   # 创分支 → 编辑块 → 排序 → 软删
│   │   │   ├── test_resume_versioning.py  # 手动保存 → 回滚 → diff 还原
│   │   │   ├── test_rls_isolation.py # 用户 A token 查 B 数据 → 空
│   │   │   ├── test_5device_eviction.py
│   │   │   └── test_jsonpatch_parity.py  # 后端 jsonpatch ↔ 前端 fast-json-patch
│   │   └── contract/
│   │       └── test_openapi_schema.py
│   └── scripts/
│       ├── seed.py                   # 开发期种子数据(1 用户 + 1 主简历)
│       └── reset_db.py               # 重建数据库
│
├── src/                              # 前端 React 项目
│   ├── api/                          # M23 基础设施
│   │   ├── client.ts                 # fetch + 拦截器(401→refresh / 423 / 409 / 410)
│   │   ├── ws.ts                     # WS 客户端骨架(无业务,Phase 4 接入)
│   │   ├── ws-events.ts              # WS 事件类型(M23 预定义)
│   │   ├── errors.ts                 # LockConflictError / VersionConflictError / ...
│   │   ├── device-fingerprint.ts     # crypto.subtle + js-sha256 回退
│   │   ├── schema.d.ts               # openapi-typescript 生成(纳入 .gitignore,自动生成)
│   │   ├── gen.ts                    # 生成脚本(pnpm gen:api)
│   │   └── env.ts                    # 读取 VITE_USE_MOCK / VITE_API_BASE_URL
│   ├── repositories/                 # 数据访问层
│   │   ├── BaseRepository.ts
│   │   ├── AuthRepository.ts
│   │   ├── AccountRepository.ts
│   │   ├── ResumeRepository.ts
│   │   ├── ResumeBlockRepository.ts
│   │   ├── ResumeVersionRepository.ts
│   │   ├── SessionRepository.ts
│   │   └── index.ts                  # 工厂:按 VITE_USE_MOCK 选 Http/Mock
│   ├── stores/                       # Zustand UI 状态
│   │   ├── useAuthStore.ts           # 当前 user / token(只放内存,token 走 sessionStorage)
│   │   └── useResumeUIStore.ts       # 选中分支 / 拖拽中块 / 折叠
│   ├── hooks/
│   │   ├── queries/                  # React Query
│   │   │   ├── useCurrentUser.ts
│   │   │   ├── useResumeBranches.ts
│   │   │   ├── useResumeBlocks.ts
│   │   │   ├── useResumeVersions.ts
│   │   │   └── useMySessions.ts
│   │   └── mutations/                # 写操作
│   │       ├── useLogin.ts
│   │       ├── useRegister.ts
│   │       ├── useCreateBranch.ts
│   │       ├── useUpdateBlock.ts
│   │       ├── useReorderBlocks.ts
│   │       ├── useSaveVersion.ts
│   │       └── useRollbackVersion.ts
│   ├── pages/                        # 仅 Login + ResumeList/Editor 改 mock
│   │   ├── Login.tsx                 # ✓ 改为真实 API(测试在 tests/e2e)
│   │   ├── ResumeList.tsx            # ✓ 改为真实 API
│   │   ├── ResumeEditor.tsx          # ✓ 改为真实 API(核心)
│   │   ├── Dashboard.tsx             # 保持 mock(Phase 5 改)
│   │   ├── InterviewList.tsx         # 保持 mock(Phase 4 改)
│   │   ├── InterviewLive.tsx         # 保持 mock
│   │   ├── InterviewReport.tsx       # 保持 mock
│   │   ├── Profile.tsx               # 保持 mock(Phase 2 改)
│   │   ├── Jobs.tsx                  # 保持 mock(Phase 2 改)
│   │   ├── Resources.tsx             # 保持 mock(Phase 6 改)
│   │   ├── Settings.tsx              # 保持 mock(Phase 1 仅保留「设备管理」基础)
│   │   └── Help.tsx                  # 保持 mock(Phase 6 改)
│   ├── components/                   # 不变(layout + ui)
│   │   ├── layout/
│   │   └── ui/
│   ├── data/
│   │   ├── mockData.ts               # 保留,给 MockRepository 用
│   │   └── mockData.types.ts         # mockData 类型 → 与 schema.d.ts 对齐
│   ├── contexts/
│   │   ├── ThemeContext.tsx          # 不变
│   │   └── QueryClientContext.tsx    # 新增:React Query Provider
│   ├── lib/
│   │   ├── utils.ts                  # 不变
│   │   └── fractional-indexing.ts    # re-export npm 包
│   ├── App.tsx                       # 路由微调:Login 路径改 API
│   └── main.tsx                      # 注入 QueryClient + ErrorBoundary
│
├── tests/                            # 前端 E2E
│   ├── e2e/
│   │   ├── playwright.config.ts
│   │   ├── sc-001-demo.spec.ts       # 5 分钟演示 happy path(spec §4 SC-001)
│   │   └── fixtures/
│   │       └── seed-user.json
│   ├── msw/
│   │   ├── handlers.ts               # 与真实 API 对齐的 mock handlers
│   │   ├── browser.ts                # setupWorker
│   │   ├── server.ts                 # setupServer(单测)
│   │   └── seed.ts                   # mock 数据种子
│   └── README.md
│
├── scripts/                          # 前端 CLI(principle II)
│   ├── check-version-diff.mjs        # 验证后端 diff 与前端 diff 一致
│   ├── check-fingerprint.mjs         # 设备指纹算法验证
│   └── gen-api.mjs                   # openapi-typescript 调用
│
├── docs/                             # 不变(模块文档 + ANALYSIS_REPORT 等)
│   ├── ANALYSIS_REPORT.md
│   ├── DEVELOPMENT_ROADMAP.md
│   ├── PERSISTENCE_REQUIREMENTS.md
│   └── modules/
│       └── 01-..23-*.md
│
├── .specify/                         # spec-kit 元数据
│   ├── memory/constitution.md        # 宪法 v1.0.0
│   ├── templates/                    # plan/spec/tasks 模板
│   ├── extensions.yml
│   ├── feature.json
│   ├── integration.json
│   └── scripts/bash/                 # setup-plan / setup-tasks / create-new-feature
│
├── package.json                      # 增加 devDeps:vitest/msw/playwright/openapi-typescript
├── pnpm-lock.yaml                    # 实际是 package-lock.json(本项目用 npm)
├── vite.config.ts                    # 增加 vitest 配置
├── tailwind.config.js
├── postcss.config.js
├── tsconfig.json                     # strict 已开
├── tsconfig.node.json
├── .env.example                      # 模板:MATER_KEY / DATABASE_URL / REDIS_URL / JWT_SECRET
├── .env.local                        # gitignore(开发本地)
├── .gitignore                        # 增加:backend/.venv / .env.local / src/api/schema.d.ts / playwright-report
├── CLAUDE.md                         # 引用本 plan
└── README.md                         # 新增:5 分钟启动指南(参考 quickstart.md)
```

**Structure Decision**:
- **Option 2: Web application**(frontend + backend)→ 选这条。`backend/` 与 `src/` 平级。
- 业务代码按「**模块(M01-M07)→ 子目录**」组织,横切关注点(crypto/ids/logging)集中在 `app/core/`
- 前端按「**关注点(api/repositories/stores/hooks/pages)**」组织,页面渐进式迁移(M23)
- 测试分层:
  - 后端 `app/<module>/tests/` 放单测(就近)
  - 后端 `tests/integration/` 放跨模块测试(端到端)
  - 前端 `src/**/*.test.ts(x)` 放单测
  - 前端 `tests/e2e/` 放 Playwright
  - 前端 `tests/msw/` 放共享 mock handlers(单测 + E2E 共用)
- 前端 `src/api/schema.d.ts` 自动生成,纳入 `.gitignore`,首次启动或后端 schema 变更时 `npm run gen:api`
- 不创建 `packages/` monorepo 结构(避免 yarn workspaces 复杂度,本项目 npm 单根)

---

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

| Violation | Why Needed | Simpler Alternative Rejected Because |
|---|---|---|
| (无) | — | — |

### 已记录的轻微偏离(非违规,但需要 reviewer 注意)

| 项 | 描述 | 处理 |
|---|---|---|
| 密码策略文档对齐 | M04 §2 写「≥10 位大小写数字符号」,spec FR-001 写「≥8 位 + 数字 + 字母」。Phase 1 落地以 spec 为准 | research.md R-8 已决议。Phase 1 实施时在 `app/modules/auth/service.py` 顶部留 `TODO(Phase 2 align): see M04 §2`,待 M04 文档 v0.3 修订时一起同步 |
| bcrypt cost 性能 | spec SC-010 要求 500ms P95。bcrypt 12 cost 单次验证 ~250ms,登录接口在 5 设备并发踢出场景下可能超 500ms | research.md RK-7 已记录降级路径(临时 cost=10)。Phase 1 监控 `/auth/login` P95,超阈值则降为 10(在 `app/core/config.py` 暴露 `BCRYPT_COST_ROUNDS` 配置) |
| 5 设备限制的并发竞态 | 两设备同时登录时,可能两个会话都认为自己是第 5 个 | research.md RK-4:用 SERIALIZABLE 事务 + 唯一约束 `UNIQUE (user_id, device_id)`,事务冲突时一方重试 |

---

## Re-evaluation after Phase 1 design

*Phase 1 设计完成,复检 Constitution Check:*

| 原则 | Phase 0 结论 | Phase 1 复检 |
|---|---|---|
| I. Library-First | ✅ | ✅(每模块独立 + README + CLI + 独立测试) |
| II. CLI Interface | ✅ | ✅(每模块 `cli.py`,`python -m app.<module>.cli --help` 可跑) |
| III. Test-First | ✅ | ✅(tasks.md 中 test 任务在 impl 任务前) |
| IV. Integration & Synchronization Testing | ✅ | ✅(`tests/integration/` 真实 DB/Redis,前端 E2E 走真实后端) |
| V. Observability | ✅ | ✅(structlog + request_id + /metrics + replay CLI) |
| Technology & Stack | ✅ | ✅(严格遵守 Vite/React 18/SQLAlchemy async/RLS) |
| Development Workflow | ✅ | ✅(branch 命名 / lint+test+typecheck / 双重 Constitution Check) |

**结论**:**PASS — 无新增违规,Phase 1 可以进入任务拆解(tasks.md,Phase 2 输出)**。

---

## Out of Scope(Phase 1 明确排除)

| 项 | 原因 | 何时引入 |
|---|---|---|
| LangGraph / AI Agent 任何代码 | spec §6 / M14 | Phase 4 |
| 悲观锁服务 + WS 控制面 | M12 | Phase 3 |
| 客户端离线 + Outbox | M13 | Phase 3 |
| 错题本 / 能力 / 任务 / 活动流 / Jobs CRUD | M08-M11 | Phase 2+ |
| Resume Optimize / Error Coach / Ability Diagnose / General Coach Agent | M16-M19 | Phase 5 |
| 软删除回收站 + 注销 + 导出/导入 + 审计 | M20-M22 | Phase 6 |
| Resources / Help 真实内容 | spec 12 | Phase 6 |
| 第三方 OAuth 真实实现 | OOS-6 | 不在 MVP |
| i18n | OOS-4 | 不在 MVP |
| 移动端专门优化 | A2 | 不在 MVP |
| 实时音视频 | OOS-5 | 不在 MVP |
| 移动 App | OOS-3 | 不在 MVP |
| Dashboard 真实数据聚合 | M23 Phase 4 迁移 | Phase 5 |
| 设备信任标记(trusted_at / MFA) | spec FR-005 + M05 §7 | v1.1 |

---

## References

- 全产品 spec:`specs/001-intercraft-product-spec/spec.md`
- Phase 0 研究:`specs/001-intercraft-product-spec/research.md`
- 宪法:`.specify/memory/constitution.md` v1.0.0
- 模块文档:`docs/modules/{01..07,23}-*.md`
- 一致性审视:`docs/ANALYSIS_REPORT.md`(A1-A17 阻塞项已映射到 Phase 2-6 入口)
- 持久化需求:`docs/PERSISTENCE_REQUIREMENTS.md`
- 路线图:`docs/DEVELOPMENT_ROADMAP.md`
- Spec quality checklist:`specs/001-intercraft-product-spec/checklists/requirements.md`
