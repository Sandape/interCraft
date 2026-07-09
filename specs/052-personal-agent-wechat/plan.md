# Implementation Plan: Personal Agent + WeChat Channel

**Branch**: `052-personal-agent-wechat` | **Date**: 2026-07-07 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/052-personal-agent-wechat/spec.md`

## Summary

为每个 InterCraft 用户建立 Personal AI Agent，通过 iLink API 接入个人微信，实现：
1. 微信扫码绑定 → Agent 激活 → 长轮询连接建立
2. 系统通过微信向用户发送文本消息（含长文本分段）
3. 接收用户在微信中发送的消息并持久化
4. Agent 生命周期管理（active/degraded/dormant）+ 连接池故障隔离

核心技术路径：**CoPaw 的 iLink 协议层（Python/httpx） + Bote 的多用户连接管理架构（Adapter-Map + DB 持久化凭证）**，适配为 Python asyncio Task Pool 模式。

## Technical Context

**Language/Version**: Python 3.12+
**Primary Dependencies**: FastAPI, httpx (with HTTP/2), SQLAlchemy (async), Redis (redis-py), pycryptodome (AES)
**Storage**: PostgreSQL (credentials, messages, bindings, preferences), Redis (dedup, send queue hot cache)
**Testing**: pytest (with pytest-asyncio), Playwright (E2E, mock iLink API)
**Target Platform**: Linux server (Windows dev), single-instance v1
**Project Type**: Web service (FastAPI backend module) + Frontend settings page (React)
**Performance Goals**: P95 send latency < 15s, 1000 concurrent long-polls, CPU ≤ 50%, memory ≤ 1GB
**Constraints**: No new message middleware (Redis + PG only), text-only send (iLink limitation), single-machine v1
**Scale/Scope**: 1000 active users (design cap 10000), 6 new DB tables, ~2000 LOC backend + ~500 LOC frontend

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| **I. Library-First** | ✅ PASS | Agent module as self-contained `backend/app/modules/agent/` with own models/repository/service/api/cli |
| **II. CLI Interface** | ✅ PASS | FR-025: `python -m app.modules.agent.cli` — send-test-message, agent-status, list-bindings |
| **III. Test-First** | ✅ PASS | Each US has independent test scenarios. E2E spec covers 4 US flows. Unit tests for ILinkClient, connection pool, message split |
| **IV. Integration Testing** | ✅ PASS | Contracts defined in `contracts/agent-api.yaml`. VS-1~VS-8 in quickstart.md cover integration. Mock iLink API for CI |
| **V. Observability** | ✅ PASS | FR-023/024: Prometheus metrics (6 counters/histograms) + structured logging per message |

**Post-Phase-1 Re-check**: No violations introduced. All design artifacts (data-model, contracts, quickstart) maintain constitution compliance.

## Project Structure

### Documentation (this feature)

```text
specs/052-personal-agent-wechat/
├── plan.md              # This file
├── research.md          # Phase 0: iLink architecture research
├── data-model.md        # Phase 1: 6 new tables design
├── quickstart.md        # Phase 1: 8 validation scenarios
├── contracts/           # Phase 1: agent-api.yaml
└── tasks.md             # Phase 2: /speckit-tasks output
```

### Source Code (repository root)

```text
backend/
├── app/
│   ├── modules/
│   │   └── agent/                    # NEW: Agent module
│   │       ├── __init__.py
│   │       ├── models.py             # Agent, WeChatCredential, WeChatBinding, AgentMessage, AgentPreference, AgentStatusHistory
│   │       ├── schemas.py            # Pydantic request/response schemas
│   │       ├── repository.py         # Data access layer
│   │       ├── service.py            # Agent lifecycle, binding, preferences
│   │       ├── api.py                # FastAPI router: /api/v1/agent/*
│   │       ├── cli.py                # CLI: send-test-message, agent-status, list-bindings
│   │       └── README.md
│   │
│   ├── channels/                     # NEW: WeChat channel layer
│   │   ├── __init__.py
│   │   ├── ilink_client.py           # ILink HTTP client (adapted from CoPaw)
│   │   ├── ilink_pool.py             # ILinkConnectionPool: multi-user asyncio Task management
│   │   ├── ilink_utils.py            # Headers, AES decryption, split_text (adapted from CoPaw)
│   │   ├── circuit_breaker.py        # Per-user circuit breaker (熔断)
│   │   └── message_handler.py        # Inbound message parser + dispatcher
│   │
│   ├── workers/
│   │   └── tasks/
│   │       └── agent_health_check.py # ARQ cron: scan stale connections (30s)
│   │
│   └── api/v1/
│       └── __init__.py               # Register agent router
│
├── migrations/
│   └── versions/
│       └── 0023_agent_tables.py      # Alembic migration: 6 new tables
│
└── tests/
    ├── unit/
    │   ├── test_ilink_client.py       # ILinkClient unit tests (mock HTTP)
    │   ├── test_ilink_pool.py         # Connection pool unit tests
    │   ├── test_message_handler.py    # Message parsing tests
    │   └── test_circuit_breaker.py    # Circuit breaker state machine tests
    │
    └── integration/
        ├── test_agent_api.py          # Agent REST API integration tests
        └── test_agent_lifecycle.py    # Agent lifecycle integration tests

frontend/
├── src/
│   ├── pages/
│   │   └── AgentSettings.tsx         # NEW: Agent settings page (QR bind, preferences, status)
│   ├── components/
│   │   └── agent/
│   │       ├── QRBindCard.tsx         # QR code display + polling status
│   │       ├── AgentStatusCard.tsx    # Agent status display
│   │       └── AgentPreferencesForm.tsx # Preferences form
│   ├── hooks/
│   │   └── queries/
│   │       └── useAgent.ts           # React Query hooks for agent API
│   └── repositories/
│       └── AgentRepository.ts        # Frontend data layer for agent API

tests/e2e/
└── agent-wechat/
    ├── agent-binding.spec.ts         # E2E: QR bind flow (mock iLink)
    ├── agent-messaging.spec.ts       # E2E: send/receive messages
    ├── agent-lifecycle.spec.ts       # E2E: agent status transitions
    └── agent-preferences.spec.ts     # E2E: preferences CRUD
```

**Structure Decision**: 两层分离——`backend/app/modules/agent/` 处理 Agent 业务逻辑（数据模型、API、偏好），`backend/app/channels/` 处理微信通道技术实现（iLink 协议、连接池、消息处理）。通道层可被未来其他消息渠道（如 Discord、Telegram）复用。前端新增单个设置页面 `AgentSettings.tsx`，与现有 `/jobs`、`/interviews` 等页面模式一致。

## Complexity Tracking

> No constitution violations. No entries required.

## Implementation Phases

### Phase 0 — Foundation (Research Complete ✅)

- [x] iLink protocol research (CoPaw + Bote reference implementations)
- [x] Multi-user architecture decision: asyncio Task Pool + DB credential persistence
- [x] Technology choices documented in [research.md](./research.md)

### Phase 1 — Design (Complete ✅)

- [x] Data model: 6 new tables in [data-model.md](./data-model.md)
- [x] API contracts: [contracts/agent-api.yaml](./contracts/agent-api.yaml)
- [x] Validation guide: [quickstart.md](./quickstart.md)

### Phase 2 — Tasks (Pending: `/speckit-tasks`)

Task breakdown by User Story, ordered by priority:

**US1 (P1) — 扫码绑定微信**:
- T001: Alembic migration for 6 tables
- T002: `ILinkClient` (QR code + status polling)
- T003: `WeChatBinding` repository + service (bind/unbind)
- T004: `WeChatCredential` repository (encrypted token persistence)
- T005: `AgentService` (auto-create on user registration, activate on bind)
- T006: Agent API endpoints: QR code, binding, status
- T007: Frontend `AgentSettings.tsx` + `QRBindCard.tsx`

**US2 (P1) — Agent 发送消息**:
- T008: `ILinkClient.send_text()` (CoPaw-adapted)
- T009: `split_text()` utility (Markdown-fence-aware, 500-char segments)
- T010: `AgentMessage` repository (outbound path: INSERT pending → Redis → UPDATE sent)
- T011: Agent internal send-message API endpoint

**US3 (P1) — 接收微信消息**:
- T012: `ILinkClient.getupdates()` (long-poll, 35s hold)
- T013: `ILinkConnectionPool` (asyncio Task per user, startup recovery from DB)
- T014: Inbound message parser (`message_handler.py`: text/image/voice/ASR)
- T015: Redis-backed message dedup (SET with TTL)
- T016: `AgentMessage` repository (inbound path: INSERT received)

**US4 (P2) — Agent 生命周期**:
- T017: `CircuitBreaker` (consecutive failures → degraded → half-open probe)
- T018: `AgentStatusHistory` repository (append-only transitions)
- T019: `agent_health_check.py` ARQ cron task (30s scan)
- T020: Admin agent monitoring endpoints + frontend panel

**US5 (P2) — Agent 数据访问**:
- T021: `AgentContext` class (RLS-enforced read access to 9 modules)
- T022: RLS verification tests (Agent cannot read other users' data)

**US6 (P3) — Agent 配置与偏好**:
- T023: `AgentPreference` repository + service
- T024: Quiet hours message delay logic
- T025: Hourly digest aggregation logic
- T026: Frontend `AgentPreferencesForm.tsx`

**E2E Testing**:
- T027: Playwright E2E: QR bind flow (mock iLink API)
- T028: Playwright E2E: messaging + lifecycle + preferences

## Key Architectural Decisions

### 1. ILinkConnectionPool: Centralized asyncio Task Management

参考 Bote `SdkConnectionManagerImpl` 的 `ConcurrentHashMap<String, PlatformAdapter>` 模式，实现为：

```python
class ILinkConnectionPool:
    """Central registry of per-user long-poll tasks."""
    _tasks: dict[str, asyncio.Task]
    _breakers: dict[str, CircuitBreaker]

    async def startup(self):
        """Load all active credentials from DB, create poll tasks."""
        creds = await wechat_credential_repo.list_active()
        for cred in creds:
            await self._spawn_poll_task(cred)

    async def add(self, user_id: str):
        """Called after successful QR binding."""

    async def remove(self, user_id: str):
        """Called after unbind. Cancel task, clean up."""

    async def _poll_loop(self, user_id: str, client: ILinkClient):
        """Per-user long-poll: getupdates() → dispatch → repeat."""
```

关键设计点：
- 每个用户一个独立 `asyncio.Task`（非线程），内存占用 < 100KB
- 连接池启动时从 `wechat_credentials` 表加载所有 `status=active` 的凭证
- Per-user `CircuitBreaker` 独立熔断（连续 10 次失败/5min → 熔断）
- 用户 Task 崩溃不影响其他用户

### 2. Credential Persistence: DB-First, Not File-Based

CoPaw 用文件存储 token（`~/.copaw/weixin_bot_token`），不适用于多用户。InterCraft 采用 Bote 的 DB 持久化模式：

- `wechat_credentials` 表存储 `bot_token_encrypted`（AES-256-GCM）+ `cursor` + `context_token`
- 每次 `getupdates()` 返回后立即 `UPDATE wechat_credentials SET cursor = $1, last_polled_at = NOW()`
- 服务重启时，连接池从 DB 读取所有 active 凭证，逐一恢复长轮询
- `cursor` 为空时从头开始（CoPaw 模式），避免 cursor 过期导致的消息丢失

### 3. Message Send: PG + Redis Dual Storage

```
send(user_id, content)
  │
  ├─ 1. INSERT agent_messages (status='pending')    ← PG (source of truth)
  ├─ 2. LPUSH wechat:send_queue:{user_id} content    ← Redis (hot queue)
  │
  └─ ConnectionPool picks up:
       ├─ RPOP wechat:send_queue:{user_id}
       ├─ iLink send_text()
       ├─ UPDATE agent_messages SET status='sent'
       └─ On failure: status='failed', retry 3x, then dead-letter
```

### 4. iLink Protocol: Direct CoPaw Adaptation

CoPaw 已验证的 iLink 协议实现直接复用：
- `make_headers()` → `ilink_utils.py`（AuthorizationType + X-WECHAT-UIN + Bearer token）
- `ILinkClient` API methods → `ilink_client.py`（getupdates, sendmessage, get_bot_qrcode, get_qrcode_status）
- `split_text()` → `ilink_utils.py`（max 500 chars, Markdown fence-aware）
- AES-128-ECB 解密 → `ilink_utils.py`（pycryptodome, 3 key formats）

适配点：
- CoPaw 单 bot_token → InterCraft per-user bot_token（从连接池获取）
- CoPaw thread-based → InterCraft asyncio Task-based
- CoPaw 文件持久化 → InterCraft DB 持久化
- CoPaw 无熔断 → InterCraft 添加 CircuitBreaker

## Dependencies

| Dependency | Purpose | Risk |
|------------|---------|------|
| iLink API (`ilinkai.weixin.qq.com`) | WeChat messaging | iLink 服务可用性——通过 health check + 站内通知缓解 |
| httpx 0.27+ (HTTP/2) | iLink HTTP client | 版本兼容——`uv add httpx[http2]` |
| pycryptodome | AES media decryption | 纯 Python 实现，Windows 需 MSVC 编译——预编译 wheel 可用 |
| Existing ARQ worker | Health check cron | 已有基础设施，仅新增 task |
| Existing RLS infrastructure | Agent data access | 已验证的 `SET app.user_id` 模式 |
