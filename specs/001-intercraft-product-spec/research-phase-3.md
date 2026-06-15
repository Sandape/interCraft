# Phase 3 Research: 同步与离线打通

**Status**: Phase 0 output · **Date**: 2026-06-13 · **Spec**: [spec.md](./spec.md) | **Phase 1 Research**: [research.md](./research.md) | **Phase 2 Research**: [research-phase-2.md](./research-phase-2.md) | **Phase 3 Plan**: [phase-3.md](./phase-3.md)

> 本文档记录 Phase 3 (M12 悲观锁 + WS 控制面 + M13 IndexedDB Outbox)中需要拍板的技术决策。所有决议在 2026-06-13 澄清 5 项 + spec §5.3 范围内,不违反 Constitution。

## 0. 上下文

Phase 3 目标(参见 spec §5.3):「多端编辑触发悲观锁,离线编辑 → 联网后自动回放,WS 实时推送锁状态」。澄清 5 项(2026-06-13)已拍板:锁粒度 = 分支级、Outbox = 无锁资源、diff 合并 = 字段级 LWW、锁时间链 = 60s/90s/300s、WS = 单用户单连接。

需要落地的能力:后端 M12(锁服务 + WS 控制面)+ M13(客户端 IndexedDB Outbox);前端 ResumeEditor 接入锁 + Outbox、Dashboard 接入 lock 状态;WS 客户端完整版(锁事件推送)。

**Phase 3 不涉及**:LangGraph(M14+)、Agent 子图(M16-M19)、错题强化、面试报告、Dashboard 数据聚合。

## 1. 已知决策(从 spec §6 + Phase 1/2 research 继承)

| # | 决策 | 来源 | Phase 3 是否需要进一步研究 |
|---|---|---|---|
| D-1 | 后端 = FastAPI (Python 3.11+) + SQLAlchemy 2.0 async + asyncpg | Phase 1 | 否 |
| D-2 | DB = PostgreSQL 15 (在线托管) | Phase 1 | 否 |
| D-3 | 缓存/Pub-Sub = Redis 7 (本机 localhost:6379) | Phase 1 | **是**:锁状态存储 + 锁事件 pub/sub |
| D-4 | 鉴权 = JWT (access 15min + refresh 7d) | Phase 1 | **是**:WS 鉴权方案 |
| D-5 | RLS = `SET LOCAL app.user_id` | Phase 1 | 否(Lock 表由锁服务自管,可选 RLS) |
| D-6 | 前端 = TS strict + React 18 + Vite + Zustand + React Query | Phase 1 | 否 |
| D-7 | 锁粒度 = 分支级(简历) + 错题级(错题强化) | 澄清 2026-06-13 | 否 |
| D-8 | Outbox 范围 = 无锁资源(错题/活动流/个人设置/Jobs/tasks) | 澄清 2026-06-13 | 否 |
| D-9 | Diff 合并 = 字段级 LWW + 人工审核 | 澄清 2026-06-13 | 否 |
| D-10 | 锁时间链 = 心跳 60s / 自动释放 90s / TTL 300s / WS 断线 30s | 澄清 2026-06-13 | 否 |
| D-11 | WS 连接 = 单用户单连接 | 澄清 2026-06-13 | 否 |
| D-12 | 队列 = ARQ | Phase 1 | 否(Phase 3 无新 cron 需求) |
| D-13 | Constitution III Test-First | Constitution | 否 |

## 2. Phase 3 需要研究的不确定点

### R-1: 锁状态存储 — Redis vs PostgreSQL

**问题**:锁是高频读写(心跳每 60s)、需要自动过期(TTL)、需要变更通知(pub/sub)。Redis 天然支持这三者,PostgreSQL 需要额外机制(LISTEN/NOTIFY + pg_cron 清理过期行)。

**评估**:

| 维度 | Redis | PostgreSQL |
|---|---|---|
| TTL 自动过期 | `SET resource lock:xxx EX 300` 原生支持 | 需 pg_cron 定期 DELETE expired |
| 变更通知 | `PUBLISH lock:acquired {...}` 原生 pub/sub | `NOTIFY` + `LISTEN`,需额外连接 |
| 心跳性能 | 单次 O(1) `SET ... EX 300` | UPDATE + 索引,开销更大 |
| 持久化 | 重启丢失(可接受 — 锁本质临时) | 持久,但锁不需要 |
| 审计追溯 | 需额外写 PostgreSQL | 原生 |
| 运维复杂度 | 已有 Redis,无新增 | 无新增 |

**结论 — Redis 为主,PostgreSQL 为辅**:
- **活跃锁**:Redis `SET lock:{resource_type}:{resource_id} <json> EX 300`,利用 TTL 自动过期
- **心跳续期**:Redis `EXPIRE lock:{resource_type}:{resource_id} 300`(续 TTL)
- **锁事件**:Redis `PUBLISH lock:<resource_id> <event_json>`,所有在线客户端 SUBSCRIBE
- **审计日志**:PostgreSQL `lock_audit_logs` 表(append-only),记录 acquire/release/expire 事件,供调试与可观测性
- **锁状态查询**:`GET /locks/{resource_type}/{resource_id}` 读 Redis

**决策**:R3-1 — Redis 为主存储 + PostgreSQL audit_logs 为辅助审计。

---

### R-2: WS 服务端 — FastAPI 原生 WebSocket vs 第三方库

**问题**:Phase 3 需要 WS 端点推送锁事件。FastAPI 原生支持 WebSocket,无需引入 Socket.IO 或 Django Channels。

**评估**:

| 维度 | FastAPI 原生 WS | Socket.IO (python-socketio) |
|---|---|---|
| 依赖 | 无新增 | `python-socketio` + `python-engineio` |
| 鉴权 | 查询参数或首消息传 JWT | socket.io auth 握手 |
| 重连 | 手动实现(已有 Phase 1 前端骨架) | 内置自动重连 |
| 房间/频道 | 需手动管理 `dict[user_id, list[ws]]` | 内置 room 机制 |
| 复杂度 | 低,完全受控 | 中,引入新协议层 |
| 与前端匹配 | 前端 `WebSocket` 原生 API | 前端需 `socket.io-client` |

**结论 — FastAPI 原生 WebSocket**:
- Phase 3 仅需推送 3 种锁事件,不需要 Socket.IO 的房间/命名空间等高级特性
- 前端 WS 客户端骨架(Phase 1)已基于原生 WebSocket,无需引入 `socket.io-client`
- 连接管理用内存 dict + Redis pub/sub 桥接:每个 WS 连接订阅 Redis 频道,收到消息推送到对应前端

**决策**:R3-2 — FastAPI 原生 WebSocket,服务端维护 `dict[user_id, WebSocket]` 连接池,Redis pub/sub 做跨进程桥接(单进程 dev 阶段可省 Redis pub/sub,直接内存推送)。

---

### R-3: IndexedDB 封装库 — Dexie.js vs idb vs 原生 API

**问题**:Phase 3 需要在客户端浏览器中操作 IndexedDB(Outbox 队列)。IndexedDB 原生 API 是回调风格,不友好。需要选择一个轻量封装。

**评估**:

| 维度 | Dexie.js | idb | 原生 IndexedDB |
|---|---|---|---|
| API 风格 | Promise-based,链式 | Promise-based,接近原生 | 回调 + 事务手动管理 |
| TS 支持 | 一流(泛型 `Table<T>`) | 良好(`IDBPDatabase<T>`) | 需手写类型 |
| 包大小 | ~15KB gzip | ~2KB gzip | 0 |
| 生态 | 成熟,文档丰富 | 轻量,Google 官方 | — |
| Constitution 合规 | Phase 1 显式禁止引入(当时无 Outbox 需求),Phase 3 是合理引入点 | 同左 | 无合规问题 |
| 学习曲线 | 低 | 中 | 高 |

**结论 — Dexie.js**:
- Phase 3 是 Outbox 的首个合理引入点;Phase 1 禁止 Dexie 是因为无离线需求
- Dexie 的 `Table<T>` 泛型与前端 Repository 模式自然对齐
- Outbox 表结构简单(~1 张表),Dexie 的 migration/schema 管理能力足够且不过度

**决策**:R3-3 — Dexie.js ^4.x,引入为 `package.json` dependency;仅用于 Outbox(单表 `outbox_entries`);若未来扩展离线能力(多表同步),Dexie schema 可增量演进。

---

### R-4: Outbox 回放策略 — 顺序 vs 并行 vs 批量

**问题**:离线期间可能积累 N 条操作,联网后如何回放?spec US9 scenario 2 提到"按时间顺序提交"。

**评估**:

| 维度 | 顺序回放 | 并行回放 | 批量端点 |
|---|---|---|---|
| 冲突处理 | 简单 — 第一条冲突可阻塞后续 | 复杂 — 需处理跨条目依赖 | 中等 — 服务端逐条处理 |
| 性能 | N 次 HTTP 往返 | 快,但有竞态 | 1 次 HTTP 往返 |
| 部分成功 | 自然支持 | 需额外追踪 | 需逐条结果返回 |
| 实现复杂度 | 低 | 高 | 中 |

**结论 — 批量端点 + 服务端顺序处理**:
- 前端一次 `POST /api/v1/outbox/replay` 发送全部待回放条目
- 服务端逐条处理,每条返回 `{entry_index, status: "ok"|"conflict", server_entity?}`
- 前端根据返回结果逐条更新 Outbox 状态(删除成功的,标记冲突的)
- 冲突的条目不阻塞后续条目(每条独立,错题/活动流/设置/Jobs/tasks 之间无依赖)

**决策**:R3-4 — 批量端点 `POST /api/v1/outbox/replay`,服务端逐条顺序处理,独立条目冲突不阻塞其余。

---

### R-5: 冲突检测机制 — updated_at vs ETag/If-Match

**问题**:Outbox 回放时如何判断服务端数据是否被其他端修改过?

**评估**:

| 维度 | updated_at 比较 | ETag/If-Match |
|---|---|---|
| 实现 | 客户端存储 `updated_at`,回放时发送,服务端比较 | HTTP 标准头 `If-Match: <etag>` |
| 精度 | 毫秒级(Phase 1 TimestampedMixin 已就位) | 通常为 hash/version_no |
| 复杂度 | 低 — 直接比较时间戳 | 中 — 需要 etag 生成规则 |
| 风险 | 同毫秒并发写可能漏检 | 更精确 |

**结论 — updated_at 比较**:
- Phase 1 `TimestampedMixin` 已为所有业务表提供 `updated_at`
- Outbox 条目存储离线编辑时的 `entity_updated_at`,回放时服务端比较 `server.updated_at > client.entity_updated_at` → 409
- 同毫秒并发写窗口极窄(离线场景下更难发生),接受此风险

**决策**:R3-5 — 客户端在 Outbox 条目中存储编辑时的 `updated_at`,回放时服务端比较;若 `server.updated_at > client.updated_at` 返回 409 conflict + `server_entity` 供 diff 合并。

---

### R-6: 锁心跳传输通道 — WS 复用 vs 独立 HTTP 轮询

**问题**:客户端需要每 60s 发送心跳续期。可以用现有 WS 连接发送心跳消息,或者独立 HTTP POST。

**评估**:

| 维度 | WS 复用 | HTTP POST |
|---|---|---|
| 连接数 | 1 | 1 WS + 1 HTTP/60s |
| 实现 | WS 消息 `{type: "lock.heartbeat"}` | `POST /locks/{id}/heartbeat` |
| 可靠性 | WS 断开 = 心跳中断 → 锁释放(预期行为) | HTTP 独立,WS 断开仍可续期(不合理) |
| 复杂度 | 低 | 中 |

**结论 — WS 复用**:
- WS 断线本身应该触发锁释放(客户端已离线),心跳走 WS 天然绑定连接状态
- 无需额外 HTTP 端点,前端 WS 客户端一次性处理所有锁消息(acquire/heartbeat/release/lost)

**决策**:R3-6 — 心跳通过 WS 消息 `{type: "lock.heartbeat", resource_type, resource_id}` 发送;WS 断开 θ 30s 后服务端自动释放锁。

---

### R-7: WS 鉴权方案 — JWT 传递方式

**问题**:WebSocket 连接不像 HTTP 有 Header,如何传递 JWT?

**评估**:

| 维度 | 查询参数 `?token=xxx` | 首消息 `{type: "auth", token}` | Cookie(SameSite) |
|---|---|---|---|
| 安全性 | token 出现在 URL(可能被日志记录) | token 仅在 WS 帧中 | 自动携带 |
| 实现复杂度 | FastAPI 原生支持 `websocket.query_params` | 需自定义握手逻辑 | 需配置 CORS + SameSite |
| 与现有 auth 集成 | 独立验证 | 独立验证 | 复用 HTTP auth middleware |

**结论 — 查询参数**:
- FastAPI WebSocket 原生支持从 `websocket.query_params.get("token")` 提取
- JWT access token 有效期仅 15min,URL 泄露窗口有限
- 重连时客户端自动从 token-storage 取最新 token 拼接到 URL
- 日志脱敏:WS 连接 URL 中的 token 参数在 structlog 中自动 `***` 遮蔽

**决策**:R3-7 — WS 鉴权通过查询参数 `?token=<access_token>`;服务端在 `websocket.accept()` 前验证 JWT;token 在日志中自动脱敏。

---

### R-8: Lock 审计表需求

**问题**:Redis 锁数据重启即丢失,是否需要 PostgreSQL 审计表用于调试与可观测性?

**评估**:
- Constitution V 要求可观测性:每个锁操作应有日志
- 生产排障(无法复现的锁冲突)需要追溯历史
- 审计表是 append-only,开销低(INSERT only,无 UPDATE/DELETE)

**结论 — 需要**:
- `lock_audit_logs` 表(PostgreSQL,append-only)
- 字段:`id, resource_type, resource_id, user_id, device_id, action(acquired/released/expired/heartbeat), occurred_at`
- 不在热路径上阻塞(异步写入,ARQ 任务或直接 `create_task`  fire-and-forget)

**决策**:R3-8 — 创建 `lock_audit_logs` 表(PostgreSQL),append-only,异步写入;不在锁 acquire/release 热路径上阻塞。

---

## 3. 决议汇总

| # | 决议 | 选择 | 理由 |
|---|---|---|---|
| R3-1 | 锁状态存储 | Redis 为主 + PostgreSQL audit_logs 为辅 | TTL 自动过期 + pub/sub 通知;PostgreSQL 兜底审计 |
| R3-2 | WS 服务端 | FastAPI 原生 WebSocket | 无新依赖,3 种事件足够,已有前端骨架 |
| R3-3 | IndexedDB 封装 | Dexie.js ^4.x | 最佳 TS 支持,Phase 3 是合理引入点 |
| R3-4 | Outbox 回放 | 批量端点 + 服务端顺序处理 | 单次往返,独立条目冲突不阻塞 |
| R3-5 | 冲突检测 | updated_at 比较 | TimestampedMixin 已就位,实现最简 |
| R3-6 | 心跳通道 | WS 复用 | WS 断开 = 锁应释放,天然绑定 |
| R3-7 | WS 鉴权 | 查询参数 `?token=` | FastAPI 原生支持,Token 日志脱敏 |
| R3-8 | Lock 审计表 | 需要,append-only | Constitution V 可观测性,异步写入不阻塞 |

## 4. 不需要研究的项(已由其他层级拍板)

- 锁粒度 / Outbox 范围 / Diff 合并 / 时间链 / WS 连接模型 → 2026-06-13 澄清已拍板
- 加密 / RLS / JWT / ARQ → Phase 1 已落地
- LangGraph / Agent / AI → Phase 3 不涉及
- 移动端离线(iOS/Android) → MVP 不涉及(OOS-3)
