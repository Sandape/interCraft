---
description: "Phase 3 (P1 sync & offline) 任务列表 — M12 锁 + WS 控制面 + M13 IndexedDB Outbox + 前端集成"
---

# Tasks: InterCraft Phase 3 — 同步与离线打通

**Input**: Design documents from `/specs/001-intercraft-product-spec/`
- Plan: [phase-3.md](./phase-3.md)
- Spec: [spec.md](./spec.md)
- Research: [research-phase-3.md](./research-phase-3.md)
- Data Model: [data-model-phase-3.md](./data-model-phase-3.md)
- Contracts: [contracts/locks.md](./contracts/locks.md), [contracts/outbox.md](./contracts/outbox.md)
- Quickstart: [quickstart-phase-3.md](./quickstart-phase-3.md)
- Phase 1 baseline: [tasks.md](./tasks.md)(T001-T156 全部完成)
- Phase 2 baseline: [phase-2-tasks.md](./phase-2-tasks.md)(T001-T075 全部完成)

**Scope**: Phase 3 only (US9 — 多端同步与离线编辑);M12(锁 + WS) + M13(IndexedDB Outbox)+ 前端 5 页面集成。
**Phase 3 User Story**: US9 (多端同步与离线编辑) — P1.

**Tests**: TDD 强制(Constitution III NON-NEGOTIABLE);**所有** user story 任务都先写测试 → 看红 → 签收 → 最小实现 → 重构。

**Local Environment Constraints** (inherited from Phase 1):
- Redis 7: ✅ 本机已起 `localhost:6379`
- PostgreSQL 15: ✅ 在线 DB `81.71.152.210:5432/interCraft`
- Node/npm: ✅
- Python/uv: ✅

## Format: `[ID] [P?] [Story] Description`

- **[P]**: 不同文件 / 无依赖 / 可并行
- **[Story]**: 任务归属 user story(US9);Setup/Foundational/Polish 阶段无标签
- 路径:后端在 `backend/app/...`、前端在 `src/...`、测试在 `backend/tests/...` / `tests/e2e/...`

---

## Phase 1: Setup (Phase 3 基础设施)

**Purpose**: Phase 3 特有基础设施(沿用 Phase 1/2 基础设施,只扩不改)

- [X] T001 Create Alembic migration `backend/migrations/versions/0003_phase3_lock_audit.py` 创建 `lock_audit_logs` 表(id uuidv7 PK, resource_type, resource_id, user_id, device_id, session_id, action(acquired/released/expired/heartbeat), metadata_json JSONB, occurred_at TIMESTAMPTZ)+ 索引 `idx_lock_audit_resource(resource_type, resource_id, occurred_at DESC)` + `idx_lock_audit_user(user_id, occurred_at DESC)`;不启用 RLS,见 phase-3.md Complexity Tracking
- [X] T002 [P] Create `backend/app/core/ws.py` — `ConnectionManager` 类:`{user_id: dict[str, WebSocket]}` 连接池;`async connect(user_id, device_id, ws)` / `async disconnect(user_id, device_id)` / `async send_to_user(user_id, message)` / `async broadcast_to_resource(resource_id, message)` / `get_online_users()` 方法;structlog 记录 connect/disconnect 事件
- [X] T003 [P] Extend `backend/app/core/redis.py` — 新增 `async publish(channel, message_json)` + `async subscribe(channel)` 异步生成器方法(复用现有 `redis.asyncio.from_url` 客户端)
- [X] T004 [P] Create `backend/app/api/deps.py` — 新增 `async get_current_user_ws(websocket: WebSocket) -> str` 依赖:从 `websocket.query_params.get("token")` 提取 JWT → `decode_token(token, "access")` → 验证 session alive → 返回 user_id;token 在日志中脱敏(`***`替换)
- [X] T005 [P] Install frontend dependency: `npm install dexie@^4.0` + create `src/lib/outbox/db.ts` — Dexie 实例 `intercraft_outbox` v1,`outbox_entries` 表 schema:`++id, entity_type, status, client_timestamp`;export `OutboxEntry` TypeScript interface(见 data-model-phase-3.md §3.3)
- [X] T006 [P] Create `backend/app/workers/tasks/lock_audit.py` — `async def write_lock_audit(ctx, record: dict) -> dict`:异步 fire-and-forget 写入 `lock_audit_logs` 表;失败记录 `lock_audit_log.write_failed` error log + Prometheus counter 告警;不阻塞主流程
- [X] T007 Modify `backend/app/api/v1/__init__.py` — 挂载 locks 路由 + outbox 路由 + WS 端点 `/api/v1/ws/locks`;更新 OpenAPI schema

**Checkpoint**: `alembic upgrade head` 创建 lock_audit_logs 表;Redis pub/sub + WS 连接管理器可独立 import;Dexie db 可实例化

---

## Phase 2: Foundational (US9 前置验证)

**Purpose**: 跨 US9 后端/前端的契约与工具验证,完成后可并行推进锁 + Outbox

- [X] T008 [P] Write lock service unit test at `backend/app/modules/locks/tests/test_lock_service.py` — mock Redis,验证 acquire(首次成功 / 同用户另一设备 409 / 不同用户 409) / release(正常 / 无权限 403 / 锁不存在 404) / heartbeat(续期 / 锁不存在 error) / get_status(locked / unlocked)
- [X] T009 [P] Write lock API contract test at `backend/tests/contract/test_lock_api.py` — `POST /locks/acquire` → 201 / 409 resource_locked / 409 already_held_by_you / 422 invalid_resource_type;`DELETE /locks/{id}` → 200 / 404 / 403;`GET /locks/{type}/{id}` → 200 locked=true / 200 locked=false
- [X] T010 [P] Write outbox API contract test at `backend/tests/contract/test_outbox_api.py` — `POST /outbox/replay` batch ok(create/update/delete 混合) / conflict 检测(updated_at 比较) / limit 30 → 422 too_many_entries / invalid entity_type → 422 / entity not found on delete → 404;`GET /outbox/status` → 200
- [X] T011 [P] Write frontend Dexie OutboxRepository test at `src/lib/outbox/__tests__/OutboxRepository.test.ts` — vitest + fake-indexeddb:add entry / list pending / update status(pending→syncing→synced/conflict/failed) / delete synced / retry_count 递增 / 排序 by client_timestamp ASC
- [X] T012 [P] Write frontend useLock hook test at `src/lib/lock/__tests__/useLock.test.tsx` — React Testing Library + MSW + WS mock:acquire → status="locked" + holder / acquire 409 → status="readonly" + holder 信息 / release → status="idle" / WS lock.lost → status="readonly" + alert / heartbeat 定时器 60s 发送

**Checkpoint**: 所有 foundational 测试已写,**当前应全部 RED**(待实现)

---

## Phase 3: M12 Lock Service + WS (US9 Backend Lock)

**Goal**: 后端悲观锁服务完整上线 — Redis 锁状态 + REST API + WS 推送 + 心跳管理 + 审计日志

**Independent Test**: `curl` 获取锁 → 另一用户获取被拒(409) → 主动释放 → WS 收到 lock.released → 锁状态查询返回 unlocked

### Tests for M12 (write FIRST, ensure FAIL)

> 以上 T008/T009 已覆盖 unit + contract;本阶段写集成测试

- [X] T013 [P] [US9] Write lock integration test at `backend/tests/integration/test_lock_acquire_release.py` — 真实 Redis:2 用户并发 acquire / 释放后另一用户成功获取 / 同用户另一设备 409 / 锁不存在 404 / WS 推送验证(httpx AsyncClient + WebSocket)
- [X] T014 [P] [US9] Write lock heartbeat integration test at `backend/tests/integration/test_lock_heartbeat.py` — 真实 Redis:心跳续期验证 EXPIRE / 90s 无心跳 → lock.lost 推送 / TTL 300s 硬上限验证(手动 SET 短 TTL)

### Implementation for M12

- [X] T015 [P] [US9] Create `backend/app/modules/locks/models.py` — `LockAuditLog` SQLAlchemy model(uuidv7 PK, resource_type VARCHAR(64), resource_id UUID, user_id UUID, device_id VARCHAR(128), session_id UUID, action VARCHAR(16), metadata_json JSONB, occurred_at TIMESTAMPTZ);no RLS;indexes as T001
- [X] T016 [P] [US9] Create `backend/app/modules/locks/schemas.py` — `AcquireInput(resource_type: Literal["resume_branch","error_question"], resource_id: UUID)` / `LockStatus(locked: bool, lock_id?, resource_type, resource_id, user_id?, user_name?, device_id?, acquired_at?, expires_at?)` / `LockEvent(type: str, resource_type, resource_id, ...)` / `ReleaseResponse(lock_id, resource_type, resource_id, released_at)` / `HeartbeatMessage(type="lock.heartbeat", lock_id, resource_type, resource_id)` Pydantic v2 models
- [X] T017 [US9] Create `backend/app/modules/locks/redis_store.py` — `async acquire(resource_type, resource_id, lock_data_json) -> bool`(SET NX EX 300) / `async release(lock_key) -> bool`(DEL) / `async heartbeat(lock_key) -> bool`(EXPIRE 300,返回 True 若 key 存在) / `async get(lock_key) -> dict | None` / `async publish_event(resource_id, event_json)` / `async scan_stale()`(SCAN lock:* keys,检查 heartbeat_at 与 now 差值 > 90s);key 格式 `lock:{resource_type}:{resource_id}`
- [X] T018 [US9] Create `backend/app/modules/locks/service.py` — `LockService` 类:依赖 `RedisStore` + `ConnectionManager` + `write_lock_audit`;`async acquire(user_id, device_id, session_id, input) -> LockStatus`(验证 resource 存在 → Redis acquire → audit log fire-and-forget → WS broadcast lock.acquired → 返回 LockStatus) / `async release(lock_id, user_id) -> ReleaseResponse`(验证归属 → Redis release → audit log → WS broadcast lock.released) / `async heartbeat(lock_id, user_id) -> bool`(验证归属 → Redis EXPIRE → audit log action=heartbeat) / `async get_status(resource_type, resource_id) -> LockStatus`(Redis get → 附带 user_name 查 User 表) / `async auto_release_stale()`(Redis scan_stale → release each → audit log action=expired → WS push lock.lost to holder + broadcast lock.released)
- [X] T019 [US9] Create `backend/app/modules/locks/api.py` — REST endpoints:`POST /api/v1/locks/acquire`(body AcquireInput → LockService.acquire → 201/409) / `DELETE /api/v1/locks/{lock_id}`(→ ReleaseResponse 200/404/403) / `GET /api/v1/locks/{resource_type}/{resource_id}`(→ LockStatus 200);所有端点通过 `get_current_user` 依赖注入 user_id;错误响应遵循 events.md schema
- [X] T020 [US9] Create `backend/app/modules/locks/ws_handler.py` — WS endpoint `/api/v1/ws/locks`:`websocket.accept()` → `get_current_user_ws(websocket)` 验证 JWT → `ConnectionManager.connect(user_id, device_id, ws)` → 循环接收消息:`lock.heartbeat` → LockService.heartbeat / 其他 → error frame / 断线 → `ConnectionManager.disconnect` + 30s 后触发 auto_release_stale 检查
- [X] T021 [P] [US9] Create `backend/app/modules/locks/cli.py` — typer CLI:`acquire --resource-type --resource-id --json` / `release --lock-id --json` / `status --resource-type --resource-id --json` / `list-stale`(扫描过期锁) / `replay <fixture.json>`(重放锁操作序列)
- [X] T022 [P] [US9] Create `backend/app/modules/locks/README.md` — 用途/公开 API/配置项/CLI 示例/退出码/WS 事件参考

**Checkpoint**: M12 锁服务完整可用。Curl 可 acquire → release → status;WS 可收到 lock.acquired / lock.released;心跳 90s 自动释放

---

## Phase 4: M13 Outbox (US9 Backend + Frontend Outbox)

**Goal**: 服务端 Outbox 回放端点 + 客户端 IndexedDB Outbox 完整链路

**Independent Test**: 浏览器离线编辑 3 个错题 → 联网 → Outbox 自动回放 → 刷新页面确认持久化

### Tests for M13 (write FIRST, ensure FAIL)

> T010/T011 已覆盖 contract + Dexie unit;本阶段写集成测试

- [X] T023 [P] [US9] Write outbox replay integration test at `backend/tests/integration/test_outbox_replay.py` — 真实 PostgreSQL + 种子数据:batch replay 全部 ok(create/update/delete) / 部分 conflict(updated_at 冲突) / 幂等 create(entity_id 已存在) / entity_type 路由正确 / limit 30 rejected / 独立条目冲突不阻塞其余
- [X] T024 [P] [US9] Write OutboxReplayService frontend test at `src/lib/outbox/__tests__/OutboxReplayService.test.ts` — vitest + MSW:检测 `navigator.onLine` → 取 pending entries(limit 30) → POST `/outbox/replay` → 处理 results(ok → synced / conflict → conflict + store server_entity / failed → retry_count++ or failed) → 循环至无 pending / 清理 synced 条目(保留 ≤ 50)
- [X] T025 [P] [US9] Write ConflictResolver component test at `src/components/outbox/__tests__/ConflictResolver.test.tsx` — React Testing Library:渲染 server_entity vs local payload 逐字段 diff / 用户逐字段选择保留版 / 提交合并 → 调用对应 PATCH API / 成功后 outbox entry → synced

### Implementation for M13

- [X] T026 [P] [US9] Create `backend/app/modules/outbox/schemas.py` — `ReplayEntry(client_entry_id: int, entity_type, operation, entity_id, payload: dict, entity_updated_at: datetime, client_timestamp: int)` / `ReplayInput(entries: list[ReplayEntry])` / `ReplayResult(client_entry_id, status: "ok"|"conflict"|"failed", server_entity?, conflict_fields?)` / `ReplayResponse(results: list[ReplayResult], summary: {total, ok, conflict, failed})` Pydantic v2 models;`entity_type` validator ∈ `["error_question","activity","user_profile","job","task"]`
- [X] T027 [US9] Create `backend/app/modules/outbox/service.py` — `OutboxService` 类;`async replay_batch(input: ReplayInput, user_id) -> ReplayResponse`:逐条遍历 entries → 根据 entity_type 路由到对应 replay_* 方法(`_replay_error_question` / `_replay_activity` / `_replay_user_profile` / `_replay_job` / `_replay_task`) → 每条比较 `server.updated_at` vs `entry.entity_updated_at`(R3-5) → ok(执行操作 + 返回 server_entity) / conflict(返回 server_entity + conflict_fields) / failed(exception,返回 error);create 操作幂等(entity_id 已存在 → ok 不重复创建);各 replay_* 方法调用对应 Module Service
- [X] T028 [US9] Create `backend/app/modules/outbox/api.py` — REST endpoints:`POST /api/v1/outbox/replay`(body ReplayInput → OutboxService.replay_batch → 200 with ReplayResponse / 422 too_many_entries / 422 invalid_entity_type) / `GET /api/v1/outbox/status`(→ healthy + recent_replays stats)
- [X] T029 [P] [US9] Create `backend/app/modules/outbox/cli.py` — typer CLI:`replay <fixture.json>`(从 JSON 文件读取 ReplayInput,输出 ReplayResponse) / `status --json` / `validate-schema <entry.json>`(校验单条 entry 合法性)
- [X] T030 [P] [US9] Create `backend/app/modules/outbox/README.md` — 用途/公开 API/entity 路由表/冲突检测逻辑/CLI 示例
- [X] T031 [P] [US9] Create `src/lib/outbox/OutboxRepository.ts` — Dexie CRUD 封装:`async add(entry: OutboxEntry) -> number` / `async getPending(limit=30): OutboxEntry[](sort by client_timestamp ASC)` / `async markSyncing(ids: number[])` / `async markSynced(ids: number[])` / `async markConflict(id, serverEntity)` / `async markFailed(id, error)` / `async incrementRetry(id)` / `async countPending(): number` / `async cleanup(retain=50)`(delete old synced entries);export `outboxRepo` singleton
- [X] T032 [US9] Create `src/lib/outbox/OutboxReplayService.ts` — `class OutboxReplayService`:依赖 `outboxRepo` + `LockRepository`(HTTP);`async replay()`:检测 `navigator.onLine` → `getPending()` → `POST /outbox/replay` → 遍历 results 更新状态 → 若有 conflict 存入待处理队列 → 循环至无 pending → 触发 `onConflict` 回调(通知 UI);`startWatching()` 监听 `window.addEventListener('online')` + 每 30s 定时检查;`onConflict` 回调注册供 React 组件消费
- [X] T033 [P] [US9] Create `src/repositories/OutboxRepository.ts` — HTTP Repository 接口:`replay(entries: ReplayEntry[]): Promise<ReplayResponse>` / `getStatus(): Promise<{status, ...}>`;HTTP impl 调用 `src/api/client.ts`;Mock impl 用于 VITE_USE_MOCK

**Checkpoint**: M13 Outbox 完整链路可用。后端 replay 端点正确路由 + 冲突检测;前端 Dexie 增删改查 + 自动回放 + 冲突回调

---

## Phase 5: Frontend Page Integration (US9 UI Integration)

**Goal**: 前端 5 页面接入锁 + Outbox + OfflineBanner + ConflictResolver

**Independent Test**: ResumeEditor 锁获取/释放 UI 正确;Dashboard 显示活跃锁;ErrorBook 离线编辑横幅 + Outbox 回放

### Tests for Frontend Integration (write FIRST, ensure FAIL)

- [X] T034 [P] [US9] Write LockIndicator component test at `src/components/lock/__tests__/LockIndicator.test.tsx` — React Testing Library:`status="locked"` → "正在编辑" 标签 / `status="readonly"` → "只读 · {name} 正在编辑" / `status="idle"` → 不渲染 / `holder` prop 显示用户名
- [X] T035 [P] [US9] Write OfflineBanner component test at `src/components/lock/__tests__/OfflineBanner.test.tsx` — React Testing Library:`isOffline=true + pendingCount=5` → "离线 · 已暂存 5 条" / `isOffline=false` → 不渲染 / `isSyncing=true` → "同步中..."
- [X] T036 [P] [US9] Write Dashboard lock status integration test at `src/components/__tests__/DashboardLockStatus.test.tsx` — MSW + WS mock:渲染 Dashboard → 模拟 WS `lock.acquired` 事件 → 活跃锁列表出现 / 模拟 `lock.released` → 列表移除 / 用户自己持有的锁显示「释放」按钮

### Implementation for Frontend Integration

- [X] T037 [P] [US9] Create `src/lib/lock/LockClient.ts` — `LockClient` 单例类:构造函数(`token`, `deviceId`) → `connect()` 建立 WS `/api/v1/ws/locks?token=...` → `onEvent(callback: (event: LockEvent) => void)` 注册事件监听 → `sendHeartbeat(lockId, resourceType, resourceId)` 通过 WS 发送 → `disconnect()`;自动重连(指数退避 1s/2s/4s/8s max 30s);断线时通知 `onDisconnect` 回调;`lock.acquired` / `lock.released` / `lock.lost` 事件解析 + 分发
- [X] T038 [US9] Create `src/lib/lock/useLock.ts` — React hook:`useLock(resourceType, resourceId)` → `{status: 'idle'|'acquiring'|'locked'|'readonly'|'conflict', holder: {userId, userName}?, acquire, release, error}`;`acquire()` 调用 LockRepository.acquire → on success status="locked" + 启动 WS 心跳 60s interval → on 409 status="readonly" + holder 信息;`release()` 调用 LockRepository.release → status="idle" + clear heartbeat interval;监听 WS `lock.lost` 事件 → status="readonly" + toast 告警;cleanup on unmount(release if locked)
- [X] T039 [P] [US9] Create `src/repositories/LockRepository.ts` — HTTP Repository 接口:`acquire(resourceType, resourceId): Promise<LockStatus>` / `release(lockId): Promise<ReleaseResponse>` / `getStatus(resourceType, resourceId): Promise<LockStatus>`;HTTP impl 调用 `src/api/client.ts`;Mock impl 用于 VITE_USE_MOCK(toggle 用 localStorage 模拟锁状态)
- [X] T040 [P] [US9] Create `src/hooks/mutations/useAcquireLock.ts` + `src/hooks/mutations/useReleaseLock.ts` + `src/hooks/queries/useLockStatus.ts` — React Query hooks 包装 LockRepository 方法
- [X] T041 [P] [US9] Create `src/components/lock/LockIndicator.tsx` — 展示锁状态:locked → badge "🔒 正在编辑" / readonly → badge "🔒 只读 · {holder_name} 正在编辑" / idle → null;支持 `onRelease` callback;小型组件,可嵌入 Topbar 或编辑器工具栏
- [X] T042 [P] [US9] Create `src/components/lock/OfflineBanner.tsx` — 监听 `navigator.onLine` + `OutboxReplayService.pendingCount`:离线 → 固定底部 banner "📡 离线 · 已暂存 {count} 条" / 同步中 → "🔄 同步中..." / 冲突 → "⚠ {count} 条冲突需处理" 可点击展开 ConflictResolver;在线无待处理 → null
- [X] T043 [P] [US9] Create `src/components/outbox/ConflictResolver.tsx` — Dialog 组件:展示冲突条目列表;选中单条 → 字段级 diff(本地版 left / 服务端版 right);逐字段 radio:"保留本地" / "采用服务端";"应用合并" button → 调用对应 PATCH API → outbox entry → synced;支持 "全部采用本地" / "全部采用服务端" 批量操作;"稍后处理" 跳过
- [X] T044 [US9] Integrate lock into `src/pages/ResumeEditor.tsx` — 进入编辑器:若 `VITE_USE_MOCK=false` → `useLock("resume_branch", branchId)` → acquire on mount → status="locked" 时编辑器可编辑 + LockIndicator 显示 + 每 60s WS heartbeat → status="readonly" 时编辑器只读(disabled) + LockIndicator 显示持锁者 → on unmount(when tab close) release;离线超 60s → OfflineBanner "锁可能已失效" 告警;联网后若锁丢失 → diff 合并视图(本地 unsaved changes vs 服务端最新版)
- [X] T045 [US9] Integrate lock into `src/pages/Dashboard.tsx` — 展示 "活跃锁" widget:我持有的锁列表(可主动释放) + 我关注的资源的锁状态(ResumeBranch 列表每条显示是否被他人锁定);WS 事件实时更新
- [X] T046 [P] [US9] Integrate OfflineBanner into `src/pages/ErrorBook.tsx` — 挂载 OfflineBanner + 初始化 OutboxReplayService.startWatching();编辑错题时若离线 → `outboxRepo.add({entity_type: "error_question", operation: "update", ...})`
- [X] T047 [P] [US9] Integrate OfflineBanner into `src/pages/Jobs.tsx` — 同 T046,entity_type = "job"
- [X] T048 [P] [US9] Integrate OfflineBanner into `src/pages/Profile.tsx` — 同 T046,entity_type = "user_profile"
- [X] T049 [P] [US9] Create `src/lib/lock/__tests__/LockClient.test.ts` — vitest + MSW WS mock:connect → 鉴权成功 / token 无效 → error / 收到 lock.acquired → callback 触发 / 自动重连指数退避 / heartbeat 每 60s 发送 / 断线 → onDisconnect 回调
- [X] T050 [P] [US9] Register LockRepository + OutboxRepository in `src/repositories/index.ts` — factory 导出 `getLockRepository()` / `getOutboxRepository()`;Mock impl 利用 localStorage 模拟锁状态 + 内存数组模拟 Outbox

**Checkpoint**: 前端 5 页面全部接入锁/离线/Outbox。VITE_USE_MOCK=false 下 ResumeEditor 锁获取 + Dashboard 锁列表 + ErrorBook/Jobs/Profile 离线编辑横幅均可演示

---

## Phase 6: Integration Tests + E2E

**Purpose**: 真实 Redis/PostgreSQL/浏览器端到端验证

- [X] T051 [P] [US9] Write Lock WS events integration test at `backend/tests/integration/test_lock_ws_events.py` — 真实 Redis + WebSocket:acquire → WS 收到 lock.acquired / release → WS 收到 lock.released / 90s 无心跳 → WS 收到 lock.lost / 跨用户广播正确
- [X] T052 [P] [US9] Write lock acquire serializable test at `backend/tests/integration/test_lock_concurrent.py` — 2 协程并发 acquire 同一资源 → 仅 1 个成功,另 1 个 409(验证 SET NX 原子性)
- [X] T053 [P] [US9] Write RLS isolation test at `backend/tests/integration/test_rls_isolation_phase3.py` — lock_audit_logs 不走 RLS:任意认证用户可读 `lock_audit_logs WHERE user_id = ANY`;验证跨用户可读性 + user_id 筛选功能
- [X] T054 [P] [US9] Write lock auto-release test at `backend/tests/integration/test_lock_auto_release.py` — 创建锁 → 手动设置 heartbeat_at = now-120s → 调用 auto_release_stale() → 锁已释放 → audit log 写入 expired → WS 收到 lock.lost
- [X] T055 [P] [US9] Create Playwright E2E `tests/e2e/phase3/lock-acquire-release.spec.ts` — 双浏览器上下文(browserContext A + B):A 登录进入 ResumeEditor → 验证可编辑 + LockIndicator "正在编辑" / B 访问同一分支 → 验证只读 + LockIndicator 显示 A 用户名 / A 关闭 Tab → B WS 收到 lock.released → UI 切换可编辑
- [X] T056 [P] [US9] Create Playwright E2E `tests/e2e/phase3/outbox-offline-replay.spec.ts` — 单浏览器:A 登录 → 进入 ErrorBook → `page.route()` 切断网络 → 编辑 2 条错题(navigator.onLine=false 触发 OfflineBanner) → 恢复网络 → 验证 Outbox 回放成功 → 刷新页面验证持久化
- [X] T057 [P] [US9] Create Playwright E2E `tests/e2e/phase3/outbox-conflict-merge.spec.ts` — 双浏览器:A 离线编辑错题 X tags=["A","B"] / B 在线编辑同一错题 X tags=["A","C"] / A 联网 → Outbox 回放 → ConflictResolver 弹出 → A 选择"保留本地" → 验证 tags=["A","B"] / B 选择"采用服务端" → 验证 tags=["A","C"]
- [X] T058 [P] [US9] Create Playwright E2E `tests/e2e/phase3/lock-auto-expire.spec.ts` — 单浏览器:A 获取锁 → 强制关闭 browserContext(模拟崩溃) → B 等待 90s → 轮询 GET /locks/{type}/{id} 直到 locked=false → B 成功获取锁
- [X] T059 [P] [US9] Create Playwright E2E `tests/e2e/phase3/offline-resume-warning.spec.ts` — A 获取锁进入 ResumeEditor → `page.route()` offline → 等待 60s → 验证 OfflineBanner "锁可能已失效" 告警 / 联网 → diff 合并视图
- [X] T060 [P] [US9] Create Playwright E2E `tests/e2e/phase3/dashboard-lock-status.spec.ts` — Dashboard 页:初始化 → 无活跃锁 / A 在另一 Tab 获取 ResumeEditor 锁 → Dashboard WS 推送 → 活跃锁列表出现 A 的锁 / A 释放 → Dashboard 列表移除

**Checkpoint**: 所有集成测试 GREEN(真实 Redis + PostgreSQL);所有 E2E Playwright 通过(覆盖锁获取/释放/广播、离线回放、冲突合并、自动过期、Dashboard 状态)

---

## Phase 7: Polish & Quickstart Validation

**Purpose**: 可观测性收尾 + 文档 + quickstart 走通

- [X] T061 [P] [US9] Add Prometheus metrics at `backend/app/core/metrics.py` — 新增:`lock_acquire_attempts_total{result="ok"|"conflict"}` + `lock_heartbeat_latency_seconds`(Histogram) + `outbox_replay_total{result="ok"|"conflict"|"failed"}` + `outbox_conflict_total` + `lock_audit_write_failures_total`;在 LockService / OutboxService 中埋点
- [X] T062 [P] [US9] Wire auto-release scheduler at `backend/app/workers/main.py` — 注册 ARQ cron `auto_release_stale` 每 30s 执行(调用 `LockService.auto_release_stale()`);初始可以是 no-op placeholder(R3-8 审计写入验证)
- [X] T063 [P] [US9] Add structlog instrumentation in `backend/app/modules/locks/service.py` + `backend/app/modules/outbox/service.py` — 所有操作记录 `lock.acquired` / `lock.released` / `lock.heartbeat` / `lock.expired` / `outbox.replay_batch` 事件,字段含 `user_id / resource_type / resource_id / lock_id / result / duration_ms`
- [X] T064 [P] [US9] Update `backend/app/__init__.py` version → `"0.3.0"`
- [X] T065 [P] [US9] Run `openapi-typescript` regenerate → `src/api/schema.d.ts` 含 lock + outbox 类型
- [X] T066 [P] [US9] Verify `VITE_USE_MOCK=true` regression — Login/Register/ResumeList/ResumeEditor 在无后端时仍可用(锁/Outbox 走 Mock 降级);Mock LockRepository 返回 unlocked;Mock Outbox 不触发回放
- [X] T067 [P] [US9] Run quickstart-phase-3.md §1-§5 全部场景 — 锁获取/释放、WS 广播、离线回放、冲突合并、锁自动过期;记录通过/失败
- [X] T068 [P] [US9] Add `scripts/check-outbox-replay.mjs` — Node CLI 脚本:读取 Dexie outbox_entries → 模拟 batch replay → 验证 replay 逻辑与后端一致(Constitution II);`node scripts/check-outbox-replay.mjs --db ./test-outbox` 可独立运行
- [X] T069 [P] [US9] Update `backend/README.md` — 模块表追加 M12/M13 + 版本 0.3.0

**Checkpoint**: Phase 3 全量交付。所有测试绿,quickstart 全场景通过,VITE_USE_MOCK toggle 正常

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: 依赖 Phase 1 + Phase 2 基础设施就位 — 立即开始
- **Foundational (Phase 2)**: 依赖 Setup 完成 — BLOCKS US9 实现
- **M12 Lock (Phase 3)**: 依赖 Foundational tests 就位 — 后端锁服务独立于 Outbox
- **M13 Outbox (Phase 4)**: 依赖 M12 Lock 完成(LockRepository 供 Outbox 前端使用)+ 依赖 Outbox service 可独立
- **Frontend Integration (Phase 5)**: 依赖 M12 + M13 完成
- **Integration Tests (Phase 6)**: 依赖 Frontend Integration 完成(需要完整 UI)
- **Polish (Phase 7)**: 依赖所有实现完成

### User Story Dependencies

- **US9 (P1)**: 唯一 user story;依赖 Phase 1 + Phase 2 已有基础设施(账号+RLS+简历/错题/Jobs 业务表)

### Within US9

- Tests FIRST(Constitution III,NON-NEGOTIABLE)
- Backend:redis_store → service → api → ws_handler
- Frontend:Dexie db → OutboxRepository → OutboxReplayService → useLock → LockClient → 页面集成
- M12 可先于 M13 完成(锁是 Outbox 前端集成的前提)
- 所有 [P] 任务可并行(不同文件,无依赖)

### Parallel Opportunities

- **Within Phase 1 (Setup)**: T001-T007 全部 [P],可并行
- **Within Phase 2 (Foundational)**: T008-T012 全部 [P],可并行(不同测试文件)
- **Within Phase 3 (M12)**: T015/T016/T021/T022 可并行(models/schemas/CLI/README 不同文件);T013/T014 可并行(不同集成测试)
- **Within Phase 4 (M13)**: T026/T029/T030/T031/T033 可并行;T023/T024/T025 可并行
- **Within Phase 5 (Frontend)**: T034-T036 可并行(测试);T037/T039/T040/T041/T042/T043 可并行(独立组件);T046-T049 页面集成可并行(不同页面文件)
- **Within Phase 6 (E2E)**: T051-T060 全部 [P],可并行
- **Within Phase 7 (Polish)**: T061-T069 全部 [P],可并行

---

## Parallel Example: US9 M12 Lock (Phase 3)

```bash
# Step 1: 所有测试并行(先写,必须红):
Task T008: "Lock service unit test in backend/app/modules/locks/tests/test_lock_service.py"
Task T009: "Lock API contract test in backend/tests/contract/test_lock_api.py"
Task T013: "Lock integration test in backend/tests/integration/test_lock_acquire_release.py"
Task T014: "Lock heartbeat integration test in backend/tests/integration/test_lock_heartbeat.py"

# Step 2: 后端实现并行(不同文件):
Task T015: "LockAuditLog model in backend/app/modules/locks/models.py"
Task T016: "Lock schemas in backend/app/modules/locks/schemas.py"
Task T021: "Lock CLI in backend/app/modules/locks/cli.py"
Task T022: "Lock README in backend/app/modules/locks/README.md"

# Step 3: 核心实现顺序(依赖上游):
Task T017: "Redis store in backend/app/modules/locks/redis_store.py" (depends on T016)
Task T018: "LockService in backend/app/modules/locks/service.py" (depends on T015, T016, T017)
Task T019: "Lock API routes in backend/app/modules/locks/api.py" (depends on T018)
Task T020: "WS handler in backend/app/modules/locks/ws_handler.py" (depends on T018)
```

---

## Implementation Strategy

### MVP First (Lock Only)

1. Complete Phase 1: Setup (T001-T007)
2. Complete Phase 2: Foundational (T008-T012)
3. Complete Phase 3: M12 Lock Service + WS (T013-T022) — **锁服务独立可演示**
4. **STOP and VALIDATE**: Curl acquire → WS lock.acquired → 另一用户 409 → release → WS lock.released
5. 此时锁已就位,ResumeEditor 可接入(无离线)

### Incremental Delivery

1. **Setup + Foundational** → 基础设施就位(T001-T012)
2. **+ M12 Lock** → 悲观锁 MVP;多端编辑互斥 + WS 实时推送;demo:"两浏览器同时编辑 → 锁保护"(T013-T022)
3. **+ M13 Outbox** → 离线编辑 + 自动回放;demo:"断网编辑 3 题 → 联网自动同步"(T023-T033)
4. **+ Frontend Integration** → 5 页面接入;demo: quickstart-phase-3.md 全场景(T034-T050)
5. **+ E2E + Polish** → 集成测试 + 可观测性 + quickstart 验收;Phase 3 release-ready(T051-T069)

### Parallel Team Strategy

- **Week 1**: Setup + Foundational(单人)
- **Week 2**: M12 Lock 后端(单人,后端优先)
- **Week 3**: M13 Outbox 后端 + 前端 Dexie(可并行:后端 Outbox API + 前端 Dexie CRUD)
- **Week 4**: 前端集成(ResumeEditor + Dashboard + ErrorBook/Jobs/Profile)
- **Week 5**: E2E + Polish + Quickstart 验收

---

## Notes

- `[P]` = 不同文件,无依赖,可并行
- `[US9]` = Phase 3 唯一 user story(多端同步与离线编辑)
- **Tests MUST fail before implementation**(Constitution III,NON-NEGOTIABLE)
- **RLS**:`lock_audit_logs` 不走 RLS(Constitution Complexity Tracking 已记录);其余所有查询走 `get_db_session(user_id=...)`
- **Redis 锁是临时的**:重启丢失是可接受的;WS 断线 30s 窗口内客户端可重连 + 重新获取
- **Outbox 不存锁资源编辑**:简历分支离线修改通过 diff 合并,不进入 IndexedDB
- Phase 3 不引入 LangGraph / Agent / AI;不修改 Phase 1/2 表结构(仅新增 lock_audit_logs)
- Commit cadence:每个 task 或逻辑组完成后 commit;PR 在 Phase 边界
- Stop at any checkpoint to validate story independently before proceeding
