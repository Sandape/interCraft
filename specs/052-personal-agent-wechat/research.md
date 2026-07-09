# Research Report: Personal Agent + WeChat Channel

**Feature**: REQ-052 | **Date**: 2026-07-07

## Research Topics

### 1. iLink Protocol — Multi-User Architecture Pattern

**Decision**: 采用 **Adapter-Map + asyncio Task Pool** 模式（融合 CoPaw 协议实现 + Bote 多用户管理）

**Rationale**:
- **CoPaw** 已验证 iLink 协议的全部细节（长轮询、QR 认证、消息格式、AES 解密），可直接复用 `ILinkClient` 的核心逻辑
- **Bote** 的 `ConcurrentHashMap<String, PlatformAdapter>` 模式证明了"per-user adapter + 集中管理"架构在生产环境可承载 1000+ 并发连接
- Python asyncio 协程比 Java 虚拟线程更轻量：一个协程 ≈ 数 KB 内存 vs 虚拟线程 ≈ 数百 KB，单机 10000 协程完全可行
- CoPaw 的单线程模型无法直接用于多用户——每个长轮询需要独立的 `getupdates()` 协程和独立的 `bot_token`/`cursor`

**Alternatives considered**:
- **每用户一个 OS 线程**（CoPaw 模式扩展）：1000 用户 = 1000 线程 = ~1GB 栈空间，不可行
- **共享单个长轮询连接**：iLink 不支持——每个 bot_token 是独立的微信账号，必须独立轮询
- **外部消息队列聚合**：引入 Kafka/RabbitMQ 增加运维复杂度，v1 不需要

### 2. Credential Persistence — DB vs File

**Decision**: **PostgreSQL `wechat_credentials` 表**（Bote 模式），非文件（CoPaw 模式）

**Rationale**:
- CoPaw 的文件持久化（`~/.copaw/weixin_bot_token`）仅适用于单用户单机场景
- Bote 的 `bt_resource_publish_record.publish_params` JSON 字段模式适合多租户——每个用户一行，`bot_token`/`cursor`/`base_url` 序列化为 JSONB
- 数据库持久化支持：(a) 服务重启自动恢复 (b) 多实例部署（未来水平扩展）(c) 加密存储 bot_token
- `cursor` 必须在每次 `getupdates()` 返回后立即更新到数据库——Bote 的 `persistPublishParams()` 模式保证了重启后不丢消息

**Alternatives considered**:
- Redis 持久化：快但 RDB/AOF 模式下仍可能丢失最近的 cursor 更新
- 加密文件：CoPaw 模式，不支持多实例

### 3. Connection Pool Architecture — asyncio vs Threads

**Decision**: **asyncio Task Pool + 连接复用**（Python 原生方案）

**Rationale**:
- Python asyncio 原生支持数千并发协程，无需引入线程池
- httpx.AsyncClient 支持 HTTP/2 多路复用和连接池——少量 TCP 连接承载数千个长轮询
- 参考 Bote 的 `ThreadPools.getPublish().submit(pollLoop)` 模式：每个用户一个独立 `asyncio.Task`，外层 try/catch 兜底
- 连接池生命周期：启动时从 DB 加载所有 active 凭证 → 逐一创建 Task → 运行时动态 add/remove

**Architecture**:
```python
class ILinkConnectionPool:
    _tasks: dict[str, asyncio.Task]        # callback_code → poll task
    _clients: dict[str, ILinkClient]       # callback_code → HTTP client
    _circuit_breakers: dict[str, CircuitBreaker]  # per-user 熔断状态

    async def start_all(self) -> None: ...
    async def add(self, user_id: str, cred: WeChatCredential) -> None: ...
    async def remove(self, user_id: str) -> None: ...
    async def _poll_loop(self, user_id: str, client: ILinkClient) -> None: ...
```

**Alternatives considered**:
- `asyncio.TaskGroup`（Python 3.11+）：更优雅的错误传播，但一个 task 崩溃会取消整个 group——不适合需要独立故障隔离的场景
- `anyio` / `trio`：结构化并发更好，但引入新依赖，项目已使用 asyncio

### 4. Health Check & Recovery

**Decision**: **内置健康检查 + ARQ cron 辅助**（融合 Bote 多层恢复模式）

**Rationale**:
- Bote 的 `ConnectionHealthCheckService` 采用 `@Scheduled` 定时扫描 disconnected 连接并重连
- InterCraft 采用两层恢复：
  1. **内层（连接池内）**：每个 Task 自身带指数退避重试 + 熔断。与 spec FR-005 一致
  2. **外层（ARQ cron 每 30s）**：扫描 `wechat_credentials` 表中 `status=active` 但连接池中缺失的凭证，重新 add
- Bote 的指数退避策略直接采纳：1min → 2min → 4min → 8min → … → 2h cap
- 健康检查监控指标暴露给 Prometheus（`wechat_connection_errors_total`）

**Alternatives considered**:
- 仅依赖 Task 内部重试：若 Task 静默死亡（如 asyncio.CancelledError 被误吞），无外层恢复机制
- 使用外部 watchdog（supervisor/k8s liveness）：太重，且无法做到 per-user 粒度

### 5. Message Routing & Dedup

**Decision**: **Redis-backed dedup + PG 持久化消息**（结合 CoPaw 去重逻辑 + Bote 消息持久化）

**Rationale**:
- CoPaw 的 `OrderedDict` 去重（max 2000 条）适用于单用户，多用户需要 per-user 隔离
- 改用 **Redis SET 的 `SISMEMBER` + TTL**：key = `wechat:dedup:{user_id}:{context_token}`，TTL=1h
- Redis 重启时 dedup 数据丢失的影响可控（最坏情况：重复处理一条消息，比漏处理更安全）
- 消息本身持久化到 PG `agent_messages` 表（spec FR-016）

**Alternatives considered**:
- PG-based dedup（`wechat_msg_id` UNIQUE 约束）：每次入站消息都要写 DB → 高延迟
- 内存 dict per user：重启丢失，且无法跨实例（未来水平扩展）

### 6. QR Code Binding Flow — Web-Based

**Decision**: **Web 端生成二维码 + 轮询确认**（CoPaw 流程 + Bote REST API 契约 + spec user_id 绑定）

**Rationale**:
- CoPaw 的 `wait_for_login()` 提供了完整的 polling 实现（1.5s 间隔，300s 超时）
- Bote 的 REST API 设计（`GET /qrcode` → `POST /confirm`）提供了清晰的 API 契约参考
- spec clarify 要求绑定 `user_id` → 生成 qrcode 时关联当前登录用户，轮询时校验
- 前端轮询 `/qrcode/status` → Web 端展示扫码状态变化（waiting → scanned → confirmed）

**Alternatives considered**:
- WebSocket 推送扫码状态：更实时但增加复杂度，v1 用 polling 足够（1.5s 间隔体验可接受）

## Technology Choices Summary

| Component | CoPaw Pattern | Bote Pattern | InterCraft Choice |
|-----------|--------------|--------------|-------------------|
| HTTP Client | httpx.AsyncClient (single) | RestTemplate (per adapter) | httpx.AsyncClient (per pool, with HTTP/2) |
| Concurrency | OS thread | Virtual threads | asyncio Tasks |
| Auth Persistence | File (~/.copaw/weixin_bot_token) | DB (publish_params JSON) | DB (wechat_credentials table, AES-256-GCM) |
| Cursor Persistence | Memory only | DB (every poll response) | DB (every poll response) |
| Dedup | OrderedDict (2000 cap) | Not implemented | Redis SET with TTL |
| Health Check | External (systemd) | @Scheduled (30s) | In-loop + ARQ cron (30s) |
| Retry Backoff | Fixed 5s sleep | Exponential (1m→2h cap) | Exponential (5s→60s cap) + Circuit Breaker |
| QR Binding | CLI flow | REST API | REST API + Web UI polling |
| Message Storage | In-memory only | Session DTO in DB | agent_messages table (PG) |

## Key Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| iLink API 限流 | 所有用户消息延迟 | per-user 退避 + 熔断隔离；单用户限流不影响其他用户 |
| bot_token 过期 | 用户失联 | `wechat_credentials.status=expired` → 站内通知用户重新扫码 |
| 1000 asyncio Task 内存压力 | OOM | 实测 per-task 内存 < 100KB（主要是 httpx 连接 buffer）；72h 压测验证无泄漏 |
| context_token 过期导致发送失败 | 消息丢失 | 发送失败时清空缓存的 context_token，等待下一条入站消息刷新；消息本身持久化在 PG 可补发 |
