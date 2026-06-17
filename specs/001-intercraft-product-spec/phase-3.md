# Implementation Plan: InterCraft Phase 3 — 同步与离线打通

**Branch**: `001-intercraft-product-spec` | **Date**: 2026-06-13 | **Spec**: [spec.md](./spec.md) | **Phase 1 Plan**: [plan.md](./plan.md) | **Phase 2 Plan**: [phase-2.md](./phase-2.md) | **Phase 3 Research**: [research-phase-3.md](./research-phase-3.md) | **Phase 3 Data Model**: [data-model-phase-3.md](./data-model-phase-3.md) | **Phase 3 Quickstart**: [quickstart-phase-3.md](./quickstart-phase-3.md)

**Input**: Phase 3 范围来自 spec §5.3,叠加 2026-06-13 澄清 5 项决议,叠加 Phase 1/2 已就位的基础设施(账号/RLS/简历 CRUD/错题/Jobs/活动流/能力画像/面试只读)。

**Note**: 本 plan.md 是 Phase 3 增量计划;在 Phase 1 基础设施 + Phase 2 业务实体之上叠加 M12(锁 + WS 控制面)+ M13(IndexedDB Outbox)+ 前端 ResumeEditor 锁/Outbox 集成 + Dashboard 锁状态。

---

## Summary

落地 **Phase 3 — P1 同步与离线打通**:多端编辑悲观锁 + WS 实时推送锁状态 + 客户端 IndexedDB Outbox + 离线编辑自动回放 + diff 合并冲突解决。后端 2 模块(M12/M13)+ 前端 ResumeEditor + Dashboard 锁状态接入。**不**涉及 LangGraph(M14+)、Agent 子图(M16-M19)、Dashboard 数据聚合(Phase 5)。

**技术路径**(沿用 Phase 1/2 基础设施 + Phase 3 新增决议见 research-phase-3.md):
- 锁状态:Redis `SET lock:{type}:{id} <json> EX 300`,TTL 自动过期 + Pub/Sub 事件通知
- 锁审计:PostgreSQL `lock_audit_logs` append-only 表,异步写入
- WS 服务端:FastAPI 原生 WebSocket,单用户单连接,查询参数 JWT 鉴权
- 心跳:复用 WS 连接,60s 间隔发送 `lock.heartbeat`,90s 无心跳自动释放,TTL 300s 硬上限
- IndexedDB:Dexie.js ^4.x,单表 `outbox_entries`
- Outbox 范围:无锁资源(错题/活动流/个人设置/Jobs/tasks)
- Outbox 回放:批量 `POST /api/v1/outbox/replay`,服务端逐条顺序处理,独立冲突不阻塞
- 冲突检测:`updated_at` 比较,字段级 LWW + 人工审核 diff 合并
- 锁粒度:分支级(简历分支) + 错题级(单条错题强化 session)
- 一键回退:`VITE_USE_MOCK=true` 走 mock,默认 `false` 走真实 API

---

## Technical Context

**Language/Version**(沿用 Phase 1/2):
- 后端:Python 3.11+
- 前端:TypeScript 5.6 strict mode
- 数据库:PostgreSQL 15(持久化) + Redis 7(锁状态 + Pub/Sub)

**Primary Dependencies**(沿用 + Phase 3 新增):
- 后端(沿用):`fastapi / sqlalchemy[asyncio] / asyncpg / alembic / pydantic-settings / structlog / arq / redis / pytest`
- 后端(Phase 3 新增):`redis.asyncio` 已就位(Phase 1 `app/core/redis.py`);FastAPI WebSocket 原生支持,无新 pip 依赖
- 前端(沿用):`react / react-router-dom / zustand / @tanstack/react-query / openapi-typescript / vitest / @testing-library/react / msw / @playwright/test`
- 前端(Phase 3 新增):`dexie@^4.0` (IndexedDB 封装,R3-3 决议)

**Storage**:
- 主库:PostgreSQL 15(沿用 Phase 1 T008b 在线 DB)
- 缓存/Pub-Sub:Redis 7(活跃锁状态 + lock:* channel pub/sub)
- 客户端:IndexedDB `intercraft_outbox` 数据库(Dexie.js 管理)
- Alembic 迁移:`0003_phase3_lock_audit.py`(仅创建 `lock_audit_logs` 表)

**Testing**:
- 后端单元:`backend/app/modules/locks/tests/test_lock_service.py`(mock Redis)
- 后端集成:`tests/integration/test_lock_acquire_release.py`(真实 Redis + PostgreSQL)
- 后端契约:OpenAPI 自动扩展(lock + outbox 端点)
- 前端单元:`src/hooks/__tests__/useLock.test.tsx`(MSW + WS mock)
- 前端 E2E:`tests/e2e/phase3/`(Playwright,双浏览器上下文模拟多端)

**Target Platform**:
- 后端:Linux 容器(本地开发 Windows + WSL2)
- 前端:现代桌面浏览器(Chrome/Edge/Firefox 最近 2 大版本)

**Performance Goals**:
- 锁 acquire P95 ≤ 100ms(Redis SET + PUBLISH)
- 锁心跳 P95 ≤ 50ms(Redis EXPIRE)
- WS 事件推送延迟 P95 ≤ 200ms(同区域,对齐 SC-011)
- Outbox 回放 30 条 P95 ≤ 2s(含冲突检测)
- IndexedDB 写入 ≤ 50ms(本地,非阻塞主线程)

**Constraints**:
- 离线 Outbox 仅覆盖无锁资源(错题/活动流/设置/Jobs/tasks)
- 锁资源(简历分支/错题强化)走独立 diff-merge 流程,不进入 Outbox
- WS 推送仅锁事件(Phase 4 才加入 AI token streaming)
- 移动端离线不专门优化(延续 OOS-3)
- Dexie.js 首次引入前端依赖;Phase 1 禁止,Phase 3 合理引入点

**Scale/Scope**(Phase 3 范围):
- 并发锁:≤ 50 个活跃锁(开发期,生产预期 ≤ 500)
- WS 并发连接:≤ 50(开发期)
- Outbox 条目:≤ 100/用户(离线期积累上限)
- Diff 合并:逐字段手动选择,单次 ≤ 20 个冲突字段
- 前端接入:ResumeEditor + Dashboard 两页面;其他页面不感知锁
- 新增后端端点:5 个(locks acquire/release/status + outbox replay/status)
- 新增 WS 端点:1 个(`/api/v1/ws/locks`)

---

## Constitution Check

*GATE: Must pass before Phase 3 design. Re-check after Phase 3 design.*

依据 `.specify/memory/constitution.md` v1.0.0 的 5 大原则 + 技术约束 + 工作流,逐条校验:

### 原则 I — Library-First

| 检查点 | Phase 3 落点 | 状态 |
|---|---|---|
| 后端每个模块自包含(M12/M13),有 README + 公开 API | `backend/app/modules/locks/` + `backend/app/modules/outbox/` 各有 README/CLI/API | ✅ |
| AI 编排子图是「库」 | Phase 3 不涉及 | N/A |
| 前端特性模块是「库」 | `src/lib/outbox/` + `src/lib/lock/` 自包含,有独立接口与测试 | ✅ |

### 原则 II — CLI Interface

| 检查点 | Phase 3 落点 | 状态 |
|---|---|---|
| 文本 I/O,`--json` 模式 | `uv run python -m app.modules.locks.cli acquire/release/status --json` | ✅ |
| 退出码文档化 | README 中列出 | ✅ |
| 前端核心逻辑可被 CLI 验证 | `scripts/check-outbox-replay.mjs` 验证 Dexie replay 逻辑 | ✅ |

### 原则 III — Test-First(NON-NEGOTIABLE)

| 检查点 | Phase 3 落点 | 状态 |
|---|---|---|
| 写测试 → 看红 → 最小实现 → 重构 | tasks.md 中先列 test 任务再列 impl 任务 | ✅ |
| UI 任务:组件/hook/E2E 先于组件 | useLock / useOutbox / OutboxReplay 组件先写测试 | ✅ |
| 任务只有在测试就位且为绿时才视为「完成」 | ✅ |

### 原则 IV — Integration & Synchronization Testing

| 检查点 | Phase 3 落点 | 状态 |
|---|---|---|
| 跨服务通信(WS、REST)在真实适配器上端到端跑通 | `tests/integration/` 真实 Redis + PostgreSQL;Playwright 双浏览器上下文 | ✅ |
| 同步与离线路径:冲突解决、断线重连 MUST 在模拟网络故障场景下测试 | Playwright `page.route()` 模拟离线 → 联网切换;WS 断线 + 重连 | ✅ |
| 不允许「全部 mock 的快乐路径」 | 锁测试 = 真实 Redis;Outbox 测试 = 真实 IndexedDB(Playwright) | ✅ |

### 原则 V — Observability

| 检查点 | Phase 3 落点 | 状态 |
|---|---|---|
| 结构化日志(request_id/user_id/action) | 锁服务所有操作:acquire/release/expire/heartbeat/replay 走 structlog | ✅ |
| 指标 | 新增:`lock_acquire_attempts_total{result}`, `lock_heartbeat_latency_seconds`, `outbox_replay_total{result}`, `outbox_conflict_total` | ✅ |
| 错误上下文含足够复现信息 | lock_id/resource_type/resource_id/user_id 全部入日志 + 错误响应 | ✅ |
| CLI 即可观测:从保存输入夹具重放失败场景 | `app.modules.locks.cli replay <fixture.json>` | ✅ |

### Technology & Stack Constraints

| 检查点 | Phase 3 落点 | 状态 |
|---|---|---|
| 前端 TS strict + React 18 + Vite + TailwindCSS | 沿用 | ✅ |
| 后端 MUST 暴露 HTTP 契约 + 机器可读 schema | lock/outbox 端点进入 OpenAPI | ✅ |
| 持久层 MUST 用项目标准 ORM + 迁移工具 | `lock_audit_logs` 走 SQLAlchemy + Alembic | ✅ |
| 同步与离线:MUST 幂等且可重放(Constitution) | Outbox replay 设计为幂等(entity_id 已存在 → ok);updated_at 冲突检测 | ✅ |
| 安全与隐私:用户数据加密 + RLS 唯一通道 | 锁不存用户业务数据;lock_audit_logs 不走 RLS(全局审计,运维视角) | ✅ |

### Development Workflow

| 检查点 | Phase 3 落点 | 状态 |
|---|---|---|
| 分支命名 `[###-feature-name]` | 沿用 `001-intercraft-product-spec` | ✅ |
| 质量门禁:lint/typecheck/单测/集成/契约 | 沿用 Phase 1 CI | ✅ |
| Constitution Check 门禁 | 本节 + 设计后 Re-evaluation | ✅ |

### 治理

- 原则/约束如需偏离,必须在 Complexity Tracking 中给出理由。
- 锁审计表不走 RLS 是**有意的偏离**:审计日志需运维全局视角;`user_id` 列保留用于筛选,但不强制 TenantScoped。此偏离记录在 Complexity Tracking。
- 本 plan 与宪法 v1.0.0 兼容;1 项偏离已记录。

### Constitution Check 结论

**PASS — 1 项有记录的偏离(lock_audit_logs 不走 RLS),其余完全合规。**

---

## Project Structure

### Documentation (this feature)

```text
specs/001-intercraft-product-spec/
├── plan.md                    # Phase 1 plan(已存在)
├── phase-2.md                 # Phase 2 plan(已存在)
├── phase-3.md                 # 本文件
├── research.md                # Phase 1 research(已存在)
├── research-phase-2.md        # Phase 2 research(已存在)
├── research-phase-3.md        # Phase 3 research(本次新增)
├── data-model.md              # Phase 1 data model(已存在)
├── data-model-phase-2.md      # Phase 2 data model(已存在)
├── data-model-phase-3.md      # Phase 3 data model(本次新增)
├── quickstart.md              # Phase 1 quickstart(已存在)
├── quickstart-phase-2.md      # Phase 2 quickstart(已存在)
├── quickstart-phase-3.md      # Phase 3 quickstart(本次新增)
├── contracts/
│   ├── README.md              # 总览(更新:追加 Phase 3 端点)
│   ├── ...                    # Phase 1/2 contracts
│   ├── locks.md               # 锁 API(M12)— 本次新增
│   └── outbox.md              # Outbox API(M13)— 本次新增
└── spec.md                    # 全产品 spec(已存在,Phase 3 澄清已写入)
```

### Source Code (repository root,Phase 3 增量)

```text
D:\Project\eGGG\
├── backend/
│   ├── migrations/
│   │   └── versions/
│   │       └── 0003_phase3_lock_audit.py     # lock_audit_logs 表
│   ├── app/
│   │   ├── core/
│   │   │   ├── redis.py                       # 扩:pub/sub subscribe + listen
│   │   │   └── ws.py                          # 新:WS 连接管理器(dict[user_id, WS])
│   │   ├── modules/
│   │   │   ├── locks/                         # 新(M12)
│   │   │   │   ├── README.md
│   │   │   │   ├── models.py                  # LockAuditLog(SQLAlchemy)
│   │   │   │   ├── schemas.py                 # AcquireInput / LockStatus / LockEvent
│   │   │   │   ├── service.py                 # acquire / release / heartbeat / get_status
│   │   │   │   ├── redis_store.py             # Redis SET/GET/EXPIRE/DEL + PUBLISH
│   │   │   │   ├── api.py                     # REST: POST acquire / DELETE release / GET status
│   │   │   │   ├── ws_handler.py              # WS: /api/v1/ws/locks 连接处理
│   │   │   │   ├── cli.py
│   │   │   │   └── tests/
│   │   │   │       ├── test_lock_service.py
│   │   │   │       ├── test_lock_api.py
│   │   │   │       └── test_lock_ws.py
│   │   │   └── outbox/                        # 新(M13 服务端回放处理)
│   │   │       ├── README.md
│   │   │       ├── schemas.py                 # ReplayInput / ReplayResult / ReplayEntry
│   │   │       ├── service.py                 # replay_batch: 逐条路由 → 冲突检测 → 结果汇总
│   │   │       ├── api.py                     # POST /outbox/replay / GET /outbox/status
│   │   │       ├── cli.py
│   │   │       └── tests/
│   │   │           └── test_outbox_replay.py
│   │   ├── api/
│   │   │   ├── v1/
│   │   │   │   └── __init__.py                # 修改:挂载 locks/outbox 路由 + WS 端点
│   │   │   └── deps.py                        # 扩:get_current_user_ws(WS 版 JWT 验证)
│   │   └── workers/
│   │       └── tasks/
│   │           └── lock_audit.py               # 新:异步写 lock_audit_logs(fire-and-forget)
│   └── tests/
│       ├── contract/
│       │   ├── test_lock_api.py               # lock REST contract
│       │   └── test_outbox_api.py             # outbox REST contract
│       └── integration/
│           ├── test_lock_acquire_release.py   # Redis 锁全生命周期
│           ├── test_lock_heartbeat.py          # 心跳 + 超时自动释放
│           ├── test_lock_ws_events.py          # WS 推送 lock.* 事件
│           ├── test_outbox_replay.py           # outbox 回放 + 冲突检测
│           └── test_rls_isolation_phase3.py   # lock_audit_logs 跨用户可读性验证
│
├── src/                                        # 前端
│   ├── api/
│   │   ├── client.ts                           # 沿用
│   │   ├── ws.ts                               # 扩:lock 事件监听 + 心跳发送 + 重连
│   │   └── schema.d.ts                         # openapi-typescript 重建(含 lock/outbox)
│   ├── lib/
│   │   ├── outbox/
│   │   │   ├── db.ts                           # Dexie 实例 + outbox_entries schema
│   │   │   ├── OutboxRepository.ts             # add/pending/count/markSyncing/markSynced/markConflict
│   │   │   ├── OutboxReplayService.ts          # 检测联网 → 取 pending → POST replay → 处理结果
│   │   │   └── __tests__/
│   │   │       ├── OutboxRepository.test.ts
│   │   │       └── OutboxReplayService.test.ts
│   │   └── lock/
│   │       ├── LockClient.ts                   # WS 锁事件订阅 + 心跳管理 + 状态缓存
│   │       ├── useLock.ts                      # React hook: {status, acquire, release}
│   │       └── __tests__/
│   │           └── useLock.test.tsx
│   ├── repositories/
│   │   ├── LockRepository.ts                   # HTTP: acquire / release / getStatus
│   │   └── OutboxRepository.ts                 # HTTP: replay / getStatus
│   ├── hooks/
│   │   ├── queries/
│   │   │   └── useLockStatus.ts                # GET /locks/{type}/{id} 轮询(WS 降级)
│   │   └── mutations/
│   │       ├── useAcquireLock.ts
│   │       ├── useReleaseLock.ts
│   │       └── useOutboxReplay.ts
│   ├── components/
│   │   ├── lock/
│   │   │   ├── LockIndicator.tsx               # "🔒 只读 · 张三正在编辑" 状态栏
│   │   │   └── OfflineBanner.tsx               # "离线 · 已暂存 N 条" 横幅
│   │   └── outbox/
│   │       ├── ConflictResolver.tsx            # diff 合并视图(字段级 LWW)
│   │       └── __tests__/
│   │           └── ConflictResolver.test.tsx
│   ├── pages/
│   │   ├── ResumeEditor.tsx                    # 修改:接入 useLock + OfflineBanner
│   │   ├── Dashboard.tsx                       # 修改:接入 LockIndicator(显示活跃锁)
│   │   ├── ErrorBook.tsx                       # 修改:接入 OfflineBanner(离线编辑提示)
│   │   ├── Jobs.tsx                            # 修改:接入 OfflineBanner
│   │   └── Profile.tsx                         # 修改:接入 OfflineBanner
│   └── data/
│       └── mockData.ts                         # 保留(留 mock 仓库用)
│
└── tests/
    └── tests/e2e/
        └── phase3/
            ├── lock-acquire-release.spec.ts    # 双浏览器上下文:锁获取/释放/WS 推送
            ├── outbox-offline-replay.spec.ts   # 离线编辑 → 联网回放
            ├── outbox-conflict-merge.spec.ts   # 409 冲突 → diff 合并视图
            └── lock-auto-expire.spec.ts        # 心跳超时 → 自动释放 + WS 通知
```

**Structure Decision**: 沿用 Phase 1/2 web-application 布局。Phase 3 在 backend 新增 2 个模块(M12 locks / M13 outbox 服务端),前端新增 `src/lib/lock/` + `src/lib/outbox/` 两个自包含库。Dexie.js 封装在 `src/lib/outbox/db.ts`,不污染全局。

---

## Implementation Strategy

> Phase 3 实施按 M12(锁 + WS)→ M13(Outbox)顺序推进,前端的锁集成先于 Outbox 集成。每个模块 Test-First。

### 阶段 1:基础设施(共 0.5 周)

| # | 任务 | 产出 | 测试 |
|---|---|---|---|
| 1.1 | Alembic 迁移 `0003_phase3_lock_audit.py`:创建 `lock_audit_logs` 表 + 索引 | 迁移 | `alembic upgrade head` 成功 |
| 1.2 | `app/core/ws.py`:WS 连接管理器 `ConnectionManager`(dict[user_id, list[WebSocket]],connect/disconnect/send_to_user/send_to_all) | 工具模块 | pytest unit |
| 1.3 | `app/core/redis.py` 扩:pub/sub subscribe(listen to lock:* channels) | Redis 扩展 | pytest unit |
| 1.4 | `app/api/deps.py` 扩:`get_current_user_ws(websocket)` — 从查询参数提取 JWT,验证,返回 user_id | Auth 扩展 | pytest unit |
| 1.5 | 前端 `npm install dexie@^4.0` + `src/lib/outbox/db.ts`(Dexie schema) | 依赖 + 基础设施 | vitest |

### 阶段 2:M12 锁服务 + WS(共 1 周)

**Test-First 顺序**:test_service → test_api → test_ws → impl_redis_store → impl_service → impl_api → impl_ws_handler → impl_cli

- 2.1 [T] `test_lock_service.py`:acquire/release/heartbeat/get_status 单元测试(mock Redis)
- 2.2 [T] `test_lock_api.py`(contract):POST acquire → 201 + 409 冲突 / DELETE release → 200 / GET status → 200
- 2.3 [T] `test_lock_ws.py`:WS 连接鉴权 / lock.acquired 推送 / lock.released 推送 / lock.lost 推送 / heartbeat 续期
- 2.4 [I] `locks/redis_store.py`:SET key EX 300 / GET / EXPIRE / DEL / PUBLISH
- 2.5 [I] `locks/service.py`:acquire(user_id, device_id, resource) / release(lock_id, user_id) / heartbeat(lock_id, user_id) / get_status(resource_type, resource_id) / auto_release_stale()(ARQ 定时 30s 检查无心跳 90s)
- 2.6 [I] `locks/api.py`:REST 端点(POST acquire / DELETE release / GET status)
- 2.7 [I] `locks/ws_handler.py`:WS `/api/v1/ws/locks` — 鉴权 → 注册连接 → Redis 订阅 → 消息转发 → 心跳处理 → 断线清理
- 2.8 [I] `locks/cli.py` + `locks/README.md`

### 阶段 3:M13 Outbox 服务端 + 客户端(共 1 周)

- 3.1 [T] `test_outbox_replay.py`:batch replay ok / conflict 检测 / entity_type 路由 / limit 30 / 幂等 create
- 3.2 [T] 前端 `OutboxRepository.test.ts`:add/pending/syncing/synced/conflict 状态机
- 3.3 [T] 前端 `OutboxReplayService.test.ts`:检测联网 → 取 pending → POST → 处理结果
- 3.4 [T] 前端 `ConflictResolver.test.tsx`:diff 展示 local vs server / 逐字段选择 / 提交合并
- 3.5 [I] `outbox/service.py`:replay_batch(entries, user_id) — 逐条路由到对应 service,updated_at 冲突检测,汇总结果
- 3.6 [I] `outbox/api.py`:POST `/api/v1/outbox/replay` + GET `/api/v1/outbox/status`
- 3.7 [I] 前端 `src/lib/outbox/OutboxRepository.ts`(Dexie CRUD 封装)
- 3.8 [I] 前端 `src/lib/outbox/OutboxReplayService.ts`(联网检测 + 批量回放 + 冲突触发)

### 阶段 4:前端页面集成(共 1 周)

- 4.1 [T] `useLock.test.tsx`:acquire → UI 切换编辑模式 / release → UI 切换只读 / lock.lost → 告警
- 4.2 [I] `src/lib/lock/LockClient.ts`:WS 连接管理 + 心跳定时器(60s) + 锁状态缓存 + 事件分发
- 4.3 [I] `src/lib/lock/useLock.ts`:React hook — `{status: 'idle'|'acquiring'|'locked'|'readonly'|'conflict', acquire, release, holder}`
- 4.4 [I] `ResumeEditor.tsx` 集成:进入编辑器 → acquire lock → 编辑中每 60s 心跳 → 退出 release → 展示 OfflineBanner(离线告警)
- 4.5 [I] `Dashboard.tsx` 集成:展示活跃锁列表(我持有的 + 他人持有的我关注的资源)
- 4.6 [I] `ErrorBook.tsx` / `Jobs.tsx` / `Profile.tsx` 集成:接入 OfflineBanner(离线编辑提示 + Outbox 待回放计数)
- 4.7 [I] `ConflictResolver.tsx` 组件:字段级 diff 合并视图(复用 Phase 1 版本 diff UI 模式)

### 阶段 5:集成测试 + E2E(共 0.5 周)

- 5.1 [T] `tests/integration/test_lock_acquire_release.py`:真实 Redis lock 生命周期
- 5.2 [T] `tests/integration/test_lock_heartbeat.py`:心跳续期 → 90s 无心跳自动释放
- 5.3 [T] `tests/integration/test_lock_ws_events.py`:WS 推送 lock.acquired/released/lost
- 5.4 [T] `tests/e2e/phase3/lock-acquire-release.spec.ts`:Playwright 双浏览器上下文
- 5.5 [T] `tests/e2e/phase3/outbox-offline-replay.spec.ts`:Playwright `page.route()` 模拟离线
- 5.6 [T] `tests/e2e/phase3/outbox-conflict-merge.spec.ts`:双浏览器制造冲突 → diff 合并
- 5.7 [T] `tests/e2e/phase3/lock-auto-expire.spec.ts`:模拟心跳超时 → 自动释放
- 5.8 更新 contracts README + 走 quickstart-phase-3.md 全部场景

---

## Risks & Mitigations

| # | 风险 | 等级 | 缓解 |
|---|---|---|---|
| R-3.1 | Redis 重启丢失活跃锁状态,用户编辑中断 | 中 | WS 断线 30s 窗口内客户端自动重连 + 重新获取锁;锁丢失推送 `lock.lost` 通知前端 |
| R-3.2 | WS 断线时 heartbeat 无法发送,但客户端可能仍在本地编辑(锁资源) | 中 | 60s 离线告警(FR-063) + 重连后强制 diff 合并;Outbox 不存锁资源编辑 |
| R-3.3 | Dexie.js 引入增加前端包体积 | 低 | Dexie ~15KB gzip,tree-shaking 按需引入;仅 `src/lib/outbox/` 内部使用 |
| R-3.4 | Outbox 回放时 entity 已被其他端删除(delete 操作) | 低 | 404 标记 `outbox.entity_not_found`,客户端丢弃该条目 |
| R-3.5 | 锁 audit_logs 异步写入失败导致审计缺失 | 低 | Fire-and-forget 失败记录 error log + 计数器告警;不阻塞锁操作 |
| R-3.6 | WS pub/sub 跨进程时 Redis pub/sub 桥接延迟 | 低 | 单进程 dev 阶段直接内存推送;生产多 worker 时 Redis pub/sub 桥接,延迟 < 50ms |
| R-3.7 | Outbox 条目在回放前用户清除浏览器数据 | 低 | 提示 "离线数据未同步,清除将丢失" (浏览器 beforeunload 事件) |

---

## Out of Scope (Phase 3 明确不做)

- ❌ LangGraph(M14) / 子图(Interview/ResumeOpt/ErrorCoach/AbilityDiag/General Coach)
- ❌ AI token streaming WS(Phase 4)
- ❌ 错题强化 Agent(Phase 5 M17)
- ❌ Dashboard 数据聚合切真实 API(Phase 5)
- ❌ 简历优化 Agent interrupt(Phase 5 M16)
- ❌ Interview Session 写入(Phase 4)
- ❌ 资源/帮助/数据导出/导入/注销/订阅(Phase 6)
- ❌ Settings 其余 tab(设备/订阅/安全)(Phase 6)
- ❌ 移动端离线优化(OOS-3)
- ❌ 多人协作/团队空间(OOS-1)
- ❌ WebRTC 实时音视频(OOS-5)

---

## Phase 3 vs Phase 2 差异速查

| 维度 | Phase 2 | Phase 3 |
|---|---|---|
| 后端模块 | M08-M11(4) + scheduler | M12-M13(2) |
| 前端页面 | Profile + Jobs + ErrorBook + Settings tab(4)| ResumeEditor 锁 + Dashboard 锁 + Outbox 集成(扩 5 页) |
| 新增表(PostgreSQL) | 7 张业务表 | 1 张(`lock_audit_logs` append-only) |
| 新增存储 | — | Redis 锁状态 + IndexedDB Outbox |
| 新增依赖 | 无 | 前端:`dexie@^4.0`;后端:无新 pip 依赖 |
| 新增 WS 端点 | 0 | 1 (`/api/v1/ws/locks`) |
| 新增 REST 端点 | 23+ | 5 (locks × 3 + outbox × 2) |
| Alembic 迁移 | `0002_phase2_entities.py`(7 张表) | `0003_phase3_lock_audit.py`(1 张表) |
| 前端新文件 | ~20 (Repository + hooks) | ~15 (lib/lock + lib/outbox + components) |
| Constitution Check | PASS | PASS(1 项偏离记录) |

---

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|---|---|---|
| `lock_audit_logs` 不走 RLS(TenantScoped) | 审计日志需要运维/管理员全局视角可查;`user_id` 列保留用于筛选 | 若走 RLS,管理员排查锁冲突需登录对应用户账号,不可操作 |

**Constitution v1.0.0 几乎完全对齐,1 项有记录的偏离。**
