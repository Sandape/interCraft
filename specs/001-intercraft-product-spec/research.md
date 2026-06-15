# Phase 1 Research: P0 基线(账号 + 简历 CRUD + 前端基础设施)

**Status**: Phase 0 output · **Date**: 2026-06-12 · **Spec**: [spec.md](./spec.md) · **Modules in scope**: M01 · M02 · M03 · M04 · M05 · M06 · M07 · M23(基线)

> 本文档记录 Phase 1 中**仍然存在的不确定点**与最终决议;不再讨论已经写进模块文档(M01-M07、M23)且无歧义的「默认选择」。所有决议都在 spec §6 假设的延展之内,**没有**违反宪法(Constitution)。

## 0. 上下文

Phase 1 的目标(参见 spec §5.1):「用户可注册 → 登录 → 创建/编辑/查看/删除简历分支 → 保存版本。**首个端到端可演示版本**」。

需要落地的能力:后端 M01-M07 全部 + 前端 M23 的基础设施层(Repository/Zustand/React Query/WS 客户端骨架 + VITE_USE_MOCK + 登录页 + 简历列表/编辑器 mock 切换)。

**Phase 1 不涉及**:LangGraph(M14+)、悲观锁(M12)、离线/Outbox(M13)、错题本(M08)、能力画像(M09)、任务活动流(M10)。本阶段**不引入**这些模块的代码或迁移文件,留空待 Phase 2-5 填充。

## 1. 已知决策(从 spec §6 + M01-M07 文档继承)

| # | 决策 | 来源 | Phase 1 是否需要进一步研究 |
|---|---|---|---|
| D-1 | 后端 = FastAPI (Python 3.11+) + SQLAlchemy 2.0 async + asyncpg | spec §6 A5 / M01-M02 | 否 |
| D-2 | DB = PostgreSQL 15,主键 uuidv7,时间 timestamptz UTC | M02 | **是**:uuidv7 库选型未定 |
| D-3 | 队列 = ARQ(非 Celery) | spec §6 A10 / M03 | 否 |
| D-4 | 缓存/Pub-Sub = Redis 7 | M01 | 否 |
| D-5 | 加密 = AES-256-GCM,密钥从环境变量读(后续可换 KMS) | spec §6 A11 / M03 | 否 |
| D-6 | 鉴权 = JWT(access 15min + refresh 7d) | M04 / spec FR-002 | **是**:JWT 库选型未定 |
| D-7 | 鉴权库 = `fastapi-users[sqlalchemy]`(M04 §7 推荐) | M04 | **是**:与自研 JWT 二选一,需评估 |
| D-8 | 密码 = bcrypt(cost=12) | M04 | 否 |
| D-9 | 5 设备限制、自动踢出最早活跃 | spec FR-003 / M05 | 否(规则清晰) |
| D-10 | RLS = `SET LOCAL app.user_id = :uuid` + 所有业务表启用 | M02 §6 | 否 |
| D-11 | 写时复制(COW)用于分支继承 | M06 §6 | 否 |
| D-12 | order_index = 字符串分数(fractional indexing) | M06 §6 | **是**:库选型未定(后端 + 前端) |
| D-13 | 版本存储 = 完整快照 + diff(JSON Patch RFC 6902)混合 | spec FR-013 / M07 | **是**:JSON Patch 库选型 |
| D-14 | 月度 token 配额字段就位,ARQ 每月 1 日重置 | M04 §6 | 否(Phase 1 仅落字段 + 一次 cron 注册) |
| D-15 | 前端 = TypeScript strict + React 18 + Vite + TailwindCSS | Constitution 1.0 §「Technology」/ M23 | 否 |
| D-16 | 前端状态 = Zustand(UI) + React Query(服务端) | M23 | 否 |
| D-17 | 数据访问 = Repository 模式,Mock/真实/IndexedDB 镜像可替换 | M23 | 否 |
| D-18 | 错误拦截:401→refresh → 失败跳登录 / 423 锁冲突 / 409 版本冲突 | M23 | 否(Phase 1 暂不触发 423/409 路径) |
| D-19 | 端到端测试 = Playwright(已有 vite 生态 → Vitest 单测) | M23 | **是**:Vitest + MSW + Playwright 栈确认 |

## 2. Phase 1 需要进一步研究的不确定点

### R-1:鉴权方案 — `fastapi-users[sqlalchemy]` vs 自研 JWT

**问题**:M04 §7 推荐 fastapi-users,但 spec §6 A9 与宪法原则 I(Library-First)+ II(CLI)都强调「库需自包含、可独立测试」。fastapi-users 内置 OAuth + JWT + 密码策略,落地快,但耦合其数据库模型;自研 JWT 更轻,但要自己实现 refresh 滚动、设备 5 限制钩子。

**研究范围**:
- 评估 fastapi-users 的 [sqlalchemy adapter](https://fastapi-users.github.io/fastapi-users/) 是否能接入我们自定义的 `users` 表结构(含 `email_sha256` 索引列、`monthly_token_quota` 等)
- 评估自研方案的工作量(估算 ~150 行)与可控性
- 5 设备限制、自动踢出最早活跃 → 是登录流程的副作用,fastapi-users 的 `on_after_login` 钩子是否支持

**评估结论**:
- 选 `fastapi-users[sqlalchemy]` 的 **password + DB session + JWT strategy** 子集,**不**用其内置 OAuth(Phase 1 不需要);OAuth 接口仅在路由层留空 endpoint 占位(参见 spec OOS-6)
- 借助其 `UserDatabase` 抽象,把 `email_sha256` 等自定义列放在同一张表(M02 的 mixin 由我们控制)
- 5 设备限制通过 `on_after_login` 钩子调用 M05 的 `SessionService.register_session()` 实现

**理由**:
- 起步快(注册/登录/refresh 路由立即可用)
- 内置密码策略校验、bcrypt 哈希、JWT 颁发,与 D-6/D-8 一致
- 留出后续可替换的「实现层」抽象(Constitution I: 库可独立替换)

**被拒方案**:
- **自研 JWT**:虽然完全可控,但需 ~5 人日开发密码策略 + bcrypt + 撤销机制,对 Phase 1 价值密度低
- **`authlib`**:擅长 OAuth,对邮箱密码场景不简洁

### R-2:uuidv7 生成 — `psycopg.extras.uuid_v7` vs `uuid6` vs `uuid_utils`

**问题**:M02 §6 指定 uuidv7 主键(时间有序、索引友好),但需要选库。Python 3.11 标准库不直接提供 uuidv7。

**评估**:
| 库 | 优势 | 劣势 | 评估 |
|---|---|---|---|
| `psycopg[binary]` 自带 `psycopg.types.uuid.uuid_ossp` | 已经在 M02 依赖里 | 需要 PostgreSQL 端启用 `pgcrypto` / `uuid-ossp` extension | **不选**(在 app 层生成不依赖 DB) |
| `uuid6`(python) | 纯 Python,提供 `uuid6()` / `uuid7()` | 包小,API 接近标准库 | **可选** |
| `uuid_utils`(C 扩展) | 快,纯计算 | 需要 C 编译 | **可选,但需 pre-built wheel** |
| **手写 16 字节 RFC 9562 v7**(8 字节 unix_ts_ms + 4 字节 ver=7 + 12 字节随机) | 零依赖,完全可控 | 需要单测覆盖 RFC 兼容性 | **推荐** |

**决议**:M02 中**自写 `uuidv7()` 工具函数** 放在 `app/core/ids.py`,参考 [RFC 9562 §5.7](https://www.rfc-editor.org/rfc/rfc9562#name-uuid-version-7)。理由:
- 零依赖(不增加 poetry/uv 锁定文件的复杂度)
- 与宪法 V(Observability)对齐:可注入时间/随机源便于测试
- 单测覆盖:同毫秒产生 1k 个 ID 仍然单调递增;用 `time.time_ns()` 模拟时钟回拨

**后续可替换**:`app/core/ids.py` 仅暴露 `def new_uuid_v7() -> UUID: ...`,内部实现可换。

### R-3:fractional-indexing 字符串分数

**问题**:M06 §6 写 order_index 用字符串分数实现「拖拽排序」(无重排代价,只需重算受影响两块的中间值)。

**评估**:
| 端 | 库 | 备注 |
|---|---|---|
| 后端 (Python) | [`python-fractional-indexing`](https://pypi.org/project/fractional-indexing/) (PyPI) | 与 JS 版同算法(`fractional-indexing` npm) |
| 前端 (TS) | [`fractional-indexing`](https://www.npmjs.com/package/fractional-indexing) | 同名包,基于 `base62.js` |

**决议**:后端 `python-fractional-indexing` + 前端 `fractional-indexing`,**两端用同一算法实现**避免不一致。

### R-4:JSON Patch (RFC 6902)

**问题**:M07 §5 / spec FR-013 要求版本 diff 存 RFC 6902 格式。

**评估**:
- 后端:`jsonpatch` (PyPI) 提供 `apply_patch` / `make_patch` / `JsonPatch` 容器
- 前端:`fast-json-patch`(npm) 提供同标准实现 + 双向 apply

**决议**:
- 后端 `python-jsonpatch` (或 `jsonpatch`, 同一包)
- 前端 `fast-json-patch`
- 算法一致性:两端都用 `diff(a, b) → patch` 与 `apply_patch(doc, patch) → newDoc`,在 `tests/integration/versioning/test_jsonpatch_parity.py` 端到端校验(同一 fixture 跑两端)

### R-5:JWT 库 — `python-jose` vs `pyjwt`

**问题**:M04 §3 列举 `python-jose[cryptography]`,但 `pyjwt` 更轻、更现代。

**评估**:
| 库 | 优势 | 风险 |
|---|---|---|
| `python-jose[cryptography]` | fastapi-users 默认推荐 | 已停止活跃维护(2022 后无 release) |
| **`PyJWT[ cryptography ]`** | 活跃维护,API 简洁,fastapi-users 2024+ 已支持 | 需确认 fastapi-users 适配版本 |
| `authlib` | 大而全 | 杀鸡用牛刀 |

**决议**:`PyJWT[ cryptography ]` + 显式锁版本 `>=2.9,<3`(fastapi-users 13.x 已支持)。在 `pyproject.toml` 中固定。

### R-6:前端测试栈 — Vitest + MSW + Playwright 协同

**问题**:M23 §8 提到 MSW(Mock Service Worker) + Playwright,但 package.json 当前**未**包含测试依赖。

**研究**:
- **Vitest**:与 Vite 同生态,运行快,支持 TS / React(组件测试用 `@testing-library/react`)
- **MSW**:拦截网络层,mock 后端 API 给单测 + Storybook + 浏览器 DevTools 都能用
- **Playwright**:E2E,Phase 1 至少覆盖 SC-001(5 分钟 demo)的 happy path

**决议**(新增 devDependencies):
```
vitest@^2
@testing-library/react@^16
@testing-library/jest-dom@^6
msw@^2
@playwright/test@^1.48
happy-dom@^15  # 轻量 DOM 环境(避免 jsdom 慢)
```

**目录约定**:
- `src/**/*.test.ts(x)` → Vitest 单测,就近
- `tests/msw/handlers.ts` → MSW handlers(对应真实 API),单测/E2E 共用
- `tests/e2e/` → Playwright 测试

**Phase 1 覆盖目标**:
- Vitest:Repository 单元(每个 repository ≥ 3 个 case:list / get / create)
- MSW:登录流 / 简历 CRUD 端到端(组件 + repository)
- Playwright:SC-001 happy path(注册 → 登录 → 创分支 → 改 3 块 → 保存版本 → 刷新可见)

### R-7:设备指纹算法

**问题**:M05 §6 写指纹 = `sha256(UA + screen_resolution + timezone)`,但需要前端落地。

**研究**:
```ts
// src/api/device-fingerprint.ts
export function deviceFingerprint(): string {
  const parts = [
    navigator.userAgent,
    `${window.screen.width}x${window.screen.height}x${window.screen.colorDepth}`,
    Intl.DateTimeFormat().resolvedOptions().timeZone,
    navigator.language,
  ];
  return sha256Hex(parts.join('|'));
}
```

**注意事项**:
- 浏览器升级/插件变更会改变 UA → 接受多设备记录(5 设备上限按 `last_seen_at` 裁剪,M05 已规定)
- 移动设备旋转:Phase 1 仅考虑桌面(移动端按 spec A2 「可用但非主战场」延后)
- 使用 `crypto.subtle.digest('SHA-256', ...)`(HTTPS/localhost 才有,失败回退到 `js-sha256`)

**决议**:
- `crypto.subtle` 优先,失败回退到 `js-sha256`(devDependencies)
- 写入 `auth_sessions.device_fingerprint` 列(可读,与 `device_id`(哈希)区分)
- Phase 1 暂不做 `trusted_at` 标记(spec FR-005 提及,MVP v1.1 启用)

### R-8:bcrypt cost factor + 密码策略

**问题**:M04 §2 写 bcrypt cost=12 + 密码策略 ≥10 位大小写数字符号。但 spec FR-001 写「默认 8 位 + 数字 + 字母」,**两文档不一致**。

**决议**:采用 spec FR-001(更宽松,降低 onboarding 摩擦),即 **≥ 8 位 + 数字 + 字母**。bcrypt cost 仍 = 12。**M04 文档标记为待对齐**:
- 在 plan.md 的 Complexity Tracking 中标注「密码策略文档对齐」为非阻塞的已知差异
- Phase 1 落地以 spec 为准;M04 文档在 Phase 2 启动时同步修订

### R-9:JSON 字段类型化(JSONB ↔ Pydantic ↔ TS)

**问题**:M02 §6 写 `Annotated[JSONB, type_hint]` 自动转 Pydantic;前端 TS 类型如何从后端 schema 自动生成?

**评估**:
- 后端 Pydantic v2 自动 OpenAPI
- 前端 `openapi-typescript` 从 `/api/v1/openapi.json` 生成 TS 类型

**决议**:
- Phase 1 用 `openapi-typescript` 跑 `pnpm gen:api`(npm script),输出到 `src/api/schema.d.ts`
- Repository 方法签名直接用生成的类型:`resumeRepository.list(): Promise<components['schemas']['ResumeBranch'][]>`
- Phase 1 不强制 100% 覆盖(新写的后端 schema 优先,老 mockData.ts 类型保留)

### R-10:WS 客户端 — Phase 1 是否需要

**问题**:M23 §6 写 WS 客户端,带自动重连 + `last_seen_checkpoint_id`。但 Phase 1 不涉及 Interview Agent,**没有真正的 WS 用途**。

**决议**:
- Phase 1 落地 **WS 客户端骨架** + 单测(connect / disconnect / 指数退避重连 / 事件分发),但不接任何业务
- 真实业务(M14+ 在 Phase 4)接入
- 这是 Constitution I(Library-First)的体现:WSClient 作为独立库可独立测试

### R-11:ARQ Worker 启动方式

**问题**:M03 §6 写 `docker-compose` 起 `arq-worker` 服务,与 api 共享镜像。但 M01 §6 的 docker-compose 模板未明确。

**决议**:
- `backend/Dockerfile` 单镜像,启动命令由 docker-compose 决定:
  - `api` 服务:`CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]`
  - `worker` 服务:`CMD ["arq", "app.workers.main.WorkerSettings"]`
- 本地开发:`uv run uvicorn app.main:app` + 另一个终端 `uv run arq app.workers.main.WorkerSettings`
- Phase 1 落地的 ARQ 任务:
  1. `auth.quota_reset` 每月 1 日 00:00 UTC(由 cron 触发,Phase 1 仅落接口,Phase 2 真实重置)

### R-12:Phase 1 不引入的依赖(显式禁止)

为避免过度工程,以下库/技术**禁止**在 Phase 1 引入:

| 项 | 原因 | 何时引入 |
|---|---|---|
| `langgraph` / `langchain-anthropic` | M14 专属 | Phase 4 |
| 悲观锁服务(`app/services/lock_service.py` + Redis Lua) | M12 专属 | Phase 3 |
| Outbox 客户端(Dexie + IDB schema) | M13 专属 | Phase 3 |
| `ai_messages` / `ai_conversations` / `checkpoints` 表 | M14 依赖 | Phase 4 |
| 错题本 / 能力 / 任务 / 活动流 / Jobs 任何表 | M08-M11 专属 | Phase 2+ |
| `langsmith` SDK | A17 决策待定 | 不在 Phase 1 |
| 国际化(i18n) | A18 不在 MVP | 不在 Phase 1 |
| 第三方 OAuth 真实实现 | A20 / OOS-6 | 不在 Phase 1(仅路由占位) |

**Verification**:Phase 1 代码审查时,grep 上述关键词,命中 → 退回。

## 3. 风险与缓解

| # | 风险 | 影响 | 缓解 |
|---|---|---|---|
| RK-1 | fastapi-users 与我们自定义 `users` 表结构冲突 | M04 落地阻塞 | 已在 R-1 决议中确认:仅用其 JWT strategy + 密码策略,users 表用 M02 自定义模型,fastapi-users 通过 `UserDatabase` 适配 |
| RK-2 | uuidv7 自写实现踩到 RFC 9562 边缘 case(时钟回拨 / 重复) | 数据完整性 | 单测覆盖:同毫秒 1k 个 ID 仍唯一 + 单调;RFC 9562 test vectors |
| RK-3 | RLS `SET LOCAL` 与 SQLAlchemy async session 生命周期错配(连接池复用) | 跨用户数据泄露 | 集成测试:用户 A token 查用户 B 资源 → 空集;每次 session begin 即 SET LOCAL |
| RK-4 | 5 设备限制的并发竞态(同时 2 个设备登录) | 计数错误 | 登录流程用 SERIALIZABLE 事务 + 唯一约束 `UNIQUE (user_id, device_id)` |
| RK-5 | `mockData.ts` 字段命名与后端 Pydantic 漂移(版本切换时) | 前端编译失败 | openapi-typescript 自动生成 + 启动时校验(若 `/openapi.json` 不可达则 fail-fast) |
| RK-6 | Vitest + MSW 跑得太慢,反馈周期长 | 开发体验 | 限制 Phase 1 单测 ≤ 200 case;E2E 仅 1 个 happy path(SC-001) |
| RK-7 | bcrypt cost=12 在容器内登录耗时 > 500ms | 性能 SC-010 告警 | 接受(单用户登录 1 次/会话);若 5 设备并发踢出场景超时 → 临时降为 cost=10 |
| RK-8 | `VITE_USE_MOCK` 切换在 vite HMR 时不生效 | 演示路径失灵 | 在 `src/repositories/index.ts` 用 `import.meta.env` + 模块顶层求值,HMR 不会重新执行;在 README 中说明需重启 dev server |

## 4. 备选方案一览(被拒的)

| 备选 | 被拒原因 |
|---|---|
| 自研 JWT(M04) | R-1 已述 |
| Celery(队列) | A10 决议,ARQ 异步原生 |
| Django + DRF | 不在 spec §6 A5,迁移成本高 |
| Next.js / Remix(前端) | spec §6 锁定 Vite + React;React Router v6 路由 |
| `redux-toolkit`(状态) | Zustand 更轻,Constitution I 偏好库小巧 |
| `swr`(数据缓存) | React Query 的 mutation / optimistic 工具更全 |
| `ky` / `axios`(HTTP 客户端) | 浏览器原生 `fetch` + 拦截器足够,Phase 1 不引第三方 |
| `msw` 替代品(nock / fetch-mock) | nock 仅 Node.js,fetch-mock 不支持 Service Worker |
| 完整的 UUID v4 + 默认索引 | M02 锁定 v7,索引/排序性能更优 |

## 5. 决议汇总(供 plan.md 引用)

下列决议在 plan.md 的「Technical Context」中以**具体版本号**呈现,不再标 NEEDS CLARIFICATION:

| ID | 决议 | 备注 |
|---|---|---|
| DEC-1 | 鉴权 = `fastapi-users[sqlalchemy]` 13.x(JWT strategy + bcrypt 密码策略子集),不引入内置 OAuth | R-1 |
| DEC-2 | uuidv7 = 自写 `app/core/ids.py`,RFC 9562 §5.7 实现,8B unix_ts_ms + ver=7 + 12B random | R-2 |
| DEC-3 | fractional-indexing = 后端 `python-fractional-indexing` + 前端 `fractional-indexing` 同算法 | R-3 |
| DEC-4 | JSON Patch = 后端 `python-jsonpatch` + 前端 `fast-json-patch`,跨端 parity 测试 | R-4 |
| DEC-5 | JWT 库 = `PyJWT[ cryptography ] >=2.9,<3` | R-5 |
| DEC-6 | 前端测试栈 = Vitest 2 + Testing Library 16 + MSW 2 + Playwright 1.48 + happy-dom 15 | R-6 |
| DEC-7 | 设备指纹 = `crypto.subtle.digest('SHA-256', UA + screen + tz + lang)`,失败回退 `js-sha256` | R-7 |
| DEC-8 | 密码策略 = ≥ 8 位 + 数字 + 字母(spec FR-001,优先于 M04 文档) | R-8 |
| DEC-9 | API 类型 = `openapi-typescript` 从 `/openapi.json` 生成,repository 方法签名直接用 | R-9 |
| DEC-10 | WS 客户端 = Phase 1 落地骨架 + 单测,无业务 | R-10 |
| DEC-11 | Docker 镜像 = api/worker 共享 image,启动命令不同 | R-11 |
| DEC-12 | 显式禁止引入项(见 R-12) | R-12 |

## 6. Open Questions(Phase 1 之后,不在本阶段解决)

下列 spec §8 的问题在 Phase 1 内**不需要解决**,已在对应 phase plan 中分配:

- **Q1** Ability Dimension 6 维度定义 → Phase 2(M09 plan)
- **Q2** LangSmith 启用 → Phase 4(M14 plan)
- **Q3** LLM 模型族选择 → Phase 4(M14 plan)
- **Q4** Resources 内容策略 → Phase 5(M19 plan)
- **Q5** 错题状态机阈值 → Phase 2 / Phase 5(M08 + M17 plan)

**Phase 1 内部不存在遗留的 NEEDS CLARIFICATION**。

## 7. References

- [RFC 9562 — Universally Unique IDentifiers (UUID)](https://www.rfc-editor.org/rfc/rfc9562) §5.7 UUIDv7
- [RFC 6902 — JavaScript Object Notation (JSON) Patch](https://www.rfc-editor.org/rfc/rfc6902)
- [fastapi-users sqlalchemy adapter docs](https://fastapi-users.github.io/fastapi-users/13.0/configuration/databases/sqlalchemy/)
- [fractional-indexing (npm)](https://www.npmjs.com/package/fractional-indexing)
- [python-fractional-indexing (PyPI)](https://pypi.org/project/python-fractional-indexing/)
- [fast-json-patch (npm)](https://www.npmjs.com/package/fast-json-patch)
- [python-jsonpatch (PyPI)](https://pypi.org/project/jsonpatch/)
- [PyJWT](https://pyjwt.readthedocs.io/en/stable/)
- [openapi-typescript](https://openapi-ts.dev/)
- [MSW (Mock Service Worker)](https://mswjs.io/)
- [Playwright](https://playwright.dev/)
- 模块文档:`docs/modules/{01..07,23}-*.md`
- 宪法:`.specify/memory/constitution.md` v1.0.0
