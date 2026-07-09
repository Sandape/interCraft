# Implementation Plan: 登录会话稳定性

**Branch**: `050-login-session-stability` | **Date**: 2026-07-07 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/050-login-session-stability/spec.md`

## Summary

解决登录状态不稳定（"时不时掉线"）问题。根因链分析：

1. **同一设备多标签页 session 覆盖**（主因）：`UNIQUE(user_id, device_id)` 约束 + `register_session` 的 device_id 去重逻辑导致后登录的标签页覆盖前者的 session
2. **Refresh 重用检测过度惩罚**：并发 refresh 时 hash 不匹配触发所有 session 吊销
3. **前端容错不足**：`retry: false` + 网络错误立即清 token
4. **5 设备上限过紧 + 过期 session 未清理**：占用上限配额

技术方案：后端重构 session 轮转策略（原地更新 + 移除 UNIQUE 约束）+ 改进错误码体系 + 前端增强容错 + 新增观测性。

## Technical Context

**Language/Version**: Python 3.11+ (backend), TypeScript 5.5+ (frontend)

**Primary Dependencies**: 
- Backend: FastAPI 0.115+, SQLAlchemy 2.0+, asyncpg, PyJWT 2.x, bcrypt
- Frontend: React 18, TanStack React Query 5.x, Zustand 4.x, TypeScript

**Storage**: PostgreSQL 16 — `auth_sessions` table (RLS-scoped)

**Testing**: pytest + pytest-asyncio (backend), Vitest + Playwright (frontend)

**Target Platform**: Web (full-stack: FastAPI backend + React SPA)

**Project Type**: Web application (monorepo: `backend/` + `src/`)

**Performance Goals**: 
- Token refresh < 100ms p95 (single DB round-trip)
- Session eviction check < 5ms overhead per authenticated request
- No additional latency impact on existing auth flows

**Constraints**:
- Backward compatible: existing tokens remain valid until natural expiry
- No breaking API changes: same routes, same response schemas (add only fields)
- RLS must be preserved (auth_sessions is tenant-scoped)

**Scale/Scope**: Single-user sessions (RLS per user); max 10 active sessions per user is the new ceiling

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Library-First | ✅ PASS | Auth is `app/modules/auth/` — clear boundary. Session logic in `app/modules/sessions/`. No new module needed. |
| II. CLI Interface | ✅ PASS | Auth CLI exists at `backend/app/modules/auth/cli.py`. Adding session diagnostic commands is sufficient. |
| III. Test-First | ✅ PASS | All FRs have acceptance scenarios. Backend tests: test_auth_service.py, test_auth_flow.py. Frontend tests: client.test.ts, token-storage.test.ts. |
| IV. Integration & Sync Testing | ✅ PASS | Session rotation, eviction, multi-tab scenarios must be integration-tested against real or in-memory PG. Contract tests for error codes. |
| V. Observability | ✅ PASS | FR-010/FR-011 add structured logging + metrics for refresh/session events — directly mandated. |
| Overall | ✅ **PASS** | No violations. Complexity Tracking not required. |

## Project Structure

### Documentation (this feature)

```text
specs/050-login-session-stability/
├── plan.md              # This file
├── spec.md              # Feature spec (source input)
├── clarifications.md    # (not used — integrated into spec.md ## Clarifications)
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
│   └── auth-session-events.md
└── tasks.md             # Phase 2 output (/speckit-tasks)
```

### Source Code (repository root)

```text
backend/
├── app/
│   ├── modules/
│   │   ├── auth/service.py       # FR-008 refresh reuse behavior change
│   │   ├── auth/api.py            # FR-004 new error codes
│   │   ├── auth/schemas.py        # FR-004 response schema additions
│   │   ├── auth/models.py         # FR-001 remove UNIQUE constraint hint
│   │   ├── sessions/service.py    # FR-001 device_id dedup removal, FR-003 expires filter, FR-009 in-place rotation
│   │   └── sessions/repository.py # FR-003 list_active expires filter
│   ├── core/
│   │   ├── security.py            # No changes expected
│   │   ├── config.py              # FR-002 max_active_sessions=10
│   │   ├── exceptions.py          # FR-004 SessionEvictedError
│   │   └── metrics.py             # FR-010 refresh metrics
│   └── api/deps.py                # FR-004 eviction-aware error codes
│
├── tests/
│   ├── unit/test_auth_service.py       # FR-008/FR-009 behavior tests
│   ├── unit/test_auth_token_expired.py  # FR-005/FR-006 resilience
│   ├── integration/test_auth_flow.py    # Multi-tab, eviction scenarios
│   └── contract/test_auth_api.py        # Error code contracts

src/   # (frontend)
├── api/
│   ├── client.ts                   # FR-005 refresh retry logic enhancement
│   ├── token-storage.ts            # No changes expected
│   └── errors.ts                   # FR-004 eviction error handling
├── hooks/
│   ├── queries/useCurrentUser.ts   # FR-006 retry: false → retry: 2 + heartbeat (FR-007)
│   └── mutations/useLogin.ts       # No changes expected
├── stores/useAuthStore.ts          # FR-004 eviction Toast state
└── lib/requireAuth.ts              # FR-006 retry loading state handling
```

## Complexity Tracking

> No Constitution violations found. Complexity Tracking section is N/A.

## Phase 0 Output: Research

See [research.md](./research.md) — all NEEDS CLARIFICATION resolved during /speckit-clarify.

## Phase 1 Output: Design

See:
- [data-model.md](./data-model.md) — data model changes
- [contracts/auth-session-events.md](./contracts/auth-session-events.md) — error code contract
- [quickstart.md](./quickstart.md) — validation guide

## Phase 2: Tasks

To be generated by `/speckit-tasks`.

---

## Key Design Decisions

1. **移除 UNIQUE(user_id, device_id) 约束**（Clarification Q1）：允许多标签页共存，同一 device_id 多行通过 session_id 区分
2. **Session 轮转改为原地更新**（FR-009）：保持 session_id 不变，update refresh_token_hash + expires_at，避免软删除+新建导致的并发窗口问题
3. **Refresh 重用检测改为拒绝而非全量吊销**（FR-008）：安全性不变（拒绝即可阻止攻击者），但避免合法并发刷新触发误报
4. **前端口袋策略**（FR-005）：网络错误/5xx 时不立即清 token，保留 token 在下一次请求时再试；仅在收到明确认证错误时清
5. **Toast 通知 Eviction**（Clarification Q3）：不清 token 不跳转，用户确认后再处理
