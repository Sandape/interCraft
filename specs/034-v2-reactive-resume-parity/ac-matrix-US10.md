---
req_id: REQ-034-US10
title: Production hardening (error boundaries / retry / telemetry / RLS audit / rate limit)
status: locked
round: 1
locked_at: 260629 2530
locked_by: negotiation
negotiation_rounds: 1
parent_spec: specs/034-v2-reactive-resume-parity/spec.md
scope_cast: "US10 = 5 axis cross-cutting hardening (error boundary / retry / telemetry / RLS audit / rate limit); production minimum, 不做 enterprise-grade (避免 scope creep); 不做 CSP/CORS/CSRF 强化 (v1 已有 FastAPI 默认); 不做 SSE 客户端重连 (deferred 035)"
source_grep: "Step 3 4 grep: (1) slowapi/RateLimit → backend/app/core/rate_limit.py 已 ship (token bucket + 429); v2 endpoints 未 wire. (2) ErrorBoundary → 0 hit. (3) retry/backoff → src/api/client.ts 已 ship (5xx GET-only, 2 retries); POST/PUT/DELETE 不重试. (4) telemetry → 0 hit"
moderation_log: "Round 1 (negotiation): tester 15 反例 (1 BLOCKER / 6 MAJOR / 8 MINOR) → main-agent 15/15 接受 (R7/R10/R12 部分接受含范围 cast) → 跳过 dev round 2 直接锁定 (L007 token 风险 + US5/6/7/8/9 precedent) → 15 修订编码 Phase 2 Implementation Spec 段"
---

# Acceptance Matrix for REQ-034-US10 — Production Hardening

## SC Gaps

- spec.md US10 段（行 44）仅列 5 axis 名称，未定义每个 axis 的 success criteria 阈值（重试次数 / 限流值 / telemetry 事件清单）
- **范围澄清（避免 US8/US9 陷阱）**：
  - US10 = 5 axis cross-cutting hardening，**每 axis 仅 production minimum**
  - **不**重写现有 `enforce_rate_limit` / `client.ts` retry，**不**做大规模 refactor
  - **不**做 granular per-component ErrorBoundary / **不**做 SSE-WS retry / **不**做 OTel / **不**做 IP rate limit / **不**做 per-endpoint 自定义 limit
- **范围 cast（5 axis × 5 AC = 25 项）**：
  - Axis 1 ErrorBoundary: 1 顶层 + 1 test
  - Axis 2 Retry: 扩 POST/PUT/DELETE 重试 + 1 test（GET 已 ship）
  - Axis 3 Telemetry: 1 client + 1 backend endpoint + 1 test
  - Axis 4 RLS audit: 1 audit script + 1 test (4 表)
  - Axis 5 Rate limit: wire 60/min 到 v2 hot 3 endpoints + 1 test
- **关键阻塞（dev Phase 2 必须解决）**：
  - **Axis 2 retry 已 ship GET-only**：client.ts SAFE_RETRY_METHODS = GET；需扩到 PUT/POST/DELETE (幂等取决于后端，需 dev 评估：resume_create 是 idempotent via slug unique，resume_update 用 If-Match version，duplicate 幂等)
  - **Axis 5 rate limit 已 ship 600/min**：config.py `rate_limit_business_per_min=600`；US10 spec 要 60/min，dev 需新建 `rate_limit_v2_hot_per_min=60` + 在 v2 hot 3 endpoint 显式 `Depends(enforce_rate_limit(scope="v2_hot", per_minute=60))`
  - **Axis 4 RLS audit 无现成 script**：spec 引用 033 badcase 已用 CTE set_config 配方，需 dev 新建 `backend/tests/integration/test_034_rls_audit.py`

## AC 矩阵

### Axis 1: Error Boundary (React)

| AC-ID | 类型 | 描述 | 验证方式 | 期望结果 | 来源 |
|-------|------|------|----------|----------|------|
| AC-01 | static | **顶层 ErrorBoundary class 实现 + wrap 位置** — 新建 `src/components/ErrorBoundary.tsx` (React class component with `componentDidCatch` + `getDerivedStateFromError`)；在 `src/App.tsx` 顶层 wrap（覆盖所有 lazy routes）；fallback UI 含 "Something went wrong" 文案 + reload 按钮 (calls `window.location.reload()`) | (1) `ls src/components/ErrorBoundary.tsx` 期望 1 hit；(2) `git grep -c 'ErrorBoundary' src/App.tsx` 期望 ≥ 1 hit (import + wrap)；(3) `git grep -c 'componentDidCatch\|getDerivedStateFromError' src/components/ErrorBoundary.tsx` 期望 ≥ 2 hits | 1 文件 + App.tsx wrap | SC-US10-A1 + Axis 1 范围 cast |
| AC-02 | static | **telemetry 上报（联动 Axis 3）** — ErrorBoundary 捕获 error 时调用 `telemetryClient.error({event:'react_error', message, stack, requestId})`；不阻塞 render | `git grep -c 'telemetry\|track' src/components/ErrorBoundary.tsx` 期望 ≥ 1 hit；具体函数名 Axis 3 锁定后定 | ErrorBoundary 上报 | Axis 1 + Axis 3 联动 |
| AC-03 | happy | **ErrorBoundary 触发 fallback** — 测试故意 throw 的子组件 → ErrorBoundary 接住 → 显示 fallback UI ("Something went wrong" + reload 按钮)；不白屏 | 单测：`render(<ErrorBoundary><ThrowError /></ErrorBoundary>)` → 期望 `screen.getByText(/Something went wrong/i)` 存在 + reload 按钮存在 | Fallback UI 触发 | Axis 1 happy |
| AC-04 | happy | **ErrorBoundary 不影响正常子组件** — 子组件正常 render 时不显示 fallback UI | 单测：render children 无 throw → 期望 children 内容存在 + fallback 文本不存在 | 不误触发 | Axis 1 happy |
| AC-05 | boundary | **ErrorBoundary 仅 1 顶层实例** — 不在每组件 mount per-component boundary（避免 100+ boundaries） | `git grep -rl 'ErrorBoundary' src/` 期望 ≤ 2 hits (ErrorBoundary.tsx + App.tsx) | 仅 1 顶层 | Axis 1 排除项 |

### Axis 2: Retry Logic (API client)

| AC-ID | 类型 | 描述 | 验证方式 | 期望结果 | 来源 |
|-------|------|------|----------|----------|------|
| AC-06 | static | **现有 retry 已 ship（GET-only）** — `src/api/client.ts` 已 ship 5xx retry max 2 (3 attempts)，backoff `200 * 3^attempt + jitter`；仅 GET；401 不重试；429 surfaced as `RateLimitError`（不重试） | (1) `git grep -c 'backoffMs\|SAFE_RETRY_METHODS' src/api/client.ts` 期望 ≥ 3 hits；(2) `SAFE_RETRY_METHODS` 含 GET；不重试 401/422/429 | GET 已有重试 | client.ts 现状盘点 |
| AC-07 | static | **dev 扩 SAFE_RETRY_METHODS 到 PUT/POST/DELETE** — Axis 2 spec 要"5xx / 网络错误 / 408 / 429"全重试（含非幂等）；dev 需评估：v2 hot endpoints (create/update/duplicate) 在网络层重试是否安全（PUT 含 If-Match version → 重试用旧 version 会失败 412；POST duplicate 用 slug unique → 重试第二次返 409）。dev 必须：(a) 把 `SAFE_RETRY_METHODS` 扩到 PUT/POST/DELETE；(b) 保留 401 不重试 + 422 不重试；(c) 在 retry 循环里读 `Retry-After` header 优先 backoff（429 路径） | (1) `SAFE_RETRY_METHODS` 期望含 GET+PUT+POST+DELETE；(2) `client.ts` retry 循环读 `Retry-After` header 期望 ≥ 1 hit；(3) PUT 第二次重试带相同 `If-Match: <old_version>` 时服务端期望返 412（含 `version_mismatch` code）— dev 必加 client 路径：若响 412 + 旧 version → 重 fetch GET 拿新 version → 再 PUT 一次 | PUT/POST/DELETE 可重试 + 429 backoff | Axis 2 spec + v2 hot endpoints 幂等性 |
| AC-08 | happy | **5xx GET 重试后成功** — mock 第一次 500 + 第二次 200 → client 期望 retry 成功 + 返回正常 body | vitest：mock fetch sequence `[500, 200]` → `request('GET', '/foo')` → 期望结果 `ok` + fetch 被调 2 次 | 5xx GET 重试 | Axis 2 happy |
| AC-09 | happy | **4xx 不重试** — mock 404 → client 期望立即抛 `ApiError`（不重试） | vitest：mock fetch returns 404 → `request('GET', '/foo')` → 期望 `expect(fetch).toHaveBeenCalledTimes(1)` + throws | 4xx 不重试 | Axis 2 happy |
| AC-10 | boundary | **最多 3 attempts** — mock 连续 500 × 5 → client 期望 fetch 调用 ≤ 3 次 | vitest：mock fetch returns 500 → `request('GET', '/foo')` → 期望 fetch count == 3 | Max 3 attempts | Axis 2 边界 |

### Axis 3: Telemetry Hooks

| AC-ID | 类型 | 描述 | 验证方式 | 期望结果 | 来源 |
|-------|------|------|----------|----------|------|
| AC-11 | static | **新建 telemetry client（前端）** — `src/lib/telemetry.ts` 暴露 `telemetryClient.{page_view, api_error, dialog_open, dialog_close, resume_save, resume_update_v2_sse}(payload)`；底层用 `navigator.sendBeacon` (fallback `fetch keepalive:true`) 上报到 `POST /api/v1/telemetry/events`；payload 必含 `event_name, request_id (X-Request-ID), ts, user_id (if logged in)`；失败静默（不阻塞 UI） | (1) `ls src/lib/telemetry.ts` 期望 1 hit；(2) `git grep -c 'sendBeacon\|keepalive' src/lib/telemetry.ts` 期望 ≥ 1 hit；(3) 导出 6 个方法名期望 ≥ 6 hits | 1 client + 6 events | SC-US10-A3 + L004 不引 LangSmith |
| AC-12 | static | **新建 backend telemetry endpoint** — `POST /api/v1/telemetry/events` 接收 `{event_name, payload, ts, request_id}`；schema: `TelemetryEventIn` (pydantic)；handler 写 `backend/logs/telemetry.jsonl` (append-only, file lock) — **不**入库（避免 schema migration）；返回 204；不要求 auth（公开 endpoint 但限频 100/min per IP） | (1) `git grep -rn 'POST.*telemetry' backend/app/` 期望 ≥ 1 hit；(2) `git grep -c 'telemetry.jsonl' backend/app/modules/telemetry/` 期望 ≥ 1 hit；(3) `enforce_rate_limit(scope="telemetry")` 应用 ≥ 1 hit | endpoint + file sink | Axis 3 spec + 033 badcase file pattern |
| AC-13 | happy | **page_view 触发** — 路由切换时自动 `telemetryClient.page_view({path})`；可由 `useLocation` hook 触发 | 单测：render with MemoryRouter navigate '/foo' → 期望 mock fetch 'POST /api/v1/telemetry/events' called with `event_name='page_view'` | page_view 上报 | Axis 3 happy |
| AC-14 | happy | **api_error 触发** — `client.ts` 5xx/4xx 路径调 `telemetryClient.api_error({status, path, requestId})` | 单测：mock fetch 500 → request → 期望 telemetry 上报 + body `event_name=='api_error'` | api_error 上报 | Axis 3 happy |
| AC-15 | boundary | **telemetry 失败不阻塞 UI** — 后端 500 返错时 client 不抛错（catch 内静默）；UI 仍正常 | 单测：mock telemetry endpoint 抛错 → expect 后续 UI action 正常执行 + 不 console.error | 静默失败 | Axis 3 边界 |

### Axis 4: RLS Audit

| AC-ID | 类型 | 描述 | 验证方式 | 期望结果 | 来源 |
|-------|------|------|----------|----------|------|
| AC-16 | static | **新建 RLS audit 测试 (4 表)** — `backend/tests/integration/test_034_rls_audit.py` 含 4 个 test cases，覆盖 RLS 表 `resumes_v2 / sharing / public_resume / statistics`；每个 case：(a) 用 user_A session 插入 row；(b) 用 user_B session `SET LOCAL app.user_id = user_B_id`；(c) SELECT * from table 期望 0 rows（user_A row 不可见） | (1) `ls backend/tests/integration/test_034_rls_audit.py` 期望 1 hit；(2) `git grep -c 'def test_' backend/tests/integration/test_034_rls_audit.py` 期望 ≥ 4 hits（4 表）；(3) `git grep -c 'app.user_id\|set_config' backend/tests/integration/test_034_rls_audit.py` 期望 ≥ 4 hits | 1 file + 4 tests | SC-US10-A4 + CTE set_config 配方 |
| AC-17 | happy | **resumes_v2 越权返 0 rows** — user_B SELECT resumes_v2 期望 0 rows (user_A 创建的 row 不可见)；同理 sharing/public_resume/statistics | 跑 `pytest backend/tests/integration/test_034_rls_audit.py -v` 期望 4 passed | 4 表全过 | Axis 4 happy |
| AC-18 | boundary | **同 user 仍可见自己 row** — user_A SELECT 期望 ≥ 1 row（自己创建）；防 RLS 误锁 self | test 含 `test_self_can_see_own_row` 期望 ≥ 1 row | self 可见 | Axis 4 边界 |
| AC-19 | boundary | **service role / SET LOCAL row_security=OFF** 仍可读所有 row（admin 调试用）— 不影响业务 RLS | 不需新 test，依赖 033 badcase 已 ship 的 admin path；本 US10 不要求新 admin path | 不阻塞 admin | Axis 4 边界 |
| AC-20 | static | **RLS policy 不升级 + 不做 column-level** — 本 US10 不改 migration / 不加 column-level GRANT；仅 audit 现有 policy | `git diff backend/alembic/versions/` 期望 0 hits (本 US 不引入新 migration) | 不动 policy | Axis 4 排除项 |

### Axis 5: Rate Limiting (hot endpoints)

| AC-ID | 类型 | 描述 | 验证方式 | 期望结果 | 来源 |
|-------|------|------|----------|----------|------|
| AC-21 | static | **新增 v2 hot scope + config** — `backend/app/core/config.py` 加 `rate_limit_v2_hot_per_min: int = 60`；`rate_limit.py` `enforce_rate_limit` 已支持任意 scope + per_minute，不需重写 | (1) `git grep -n 'rate_limit_v2_hot_per_min' backend/app/core/config.py` 期望 ≥ 1 hit；(2) 现有 `enforce_rate_limit(scope=..., per_minute=...)` signature 不变（dev 不改 rate_limit.py） | config 加一项 | SC-US10-A5 + 现有 token bucket |
| AC-22 | static | **v2 hot 3 endpoint 显式 Depends** — `backend/app/modules/resumes_v2/api.py` 在 `POST /api/v1/v2/resumes` + `PUT /api/v1/v2/resumes/{id}` + `POST /api/v1/v2/resumes/{id}/duplicate` 3 个 route 加 `dependencies=[Depends(enforce_rate_limit_to_response)]` 或 `await enforce_rate_limit(request, scope="v2_hot", per_minute=60)`；per-user-id (user_id from JWT) | (1) `git grep -c 'enforce_rate_limit' backend/app/modules/resumes_v2/api.py` 期望 ≥ 3 hits；(2) `git grep -c 'scope="v2_hot"' backend/app/modules/resumes_v2/api.py` 期望 ≥ 3 hits | 3 endpoints wired | Axis 5 spec + v2 hot endpoints 列表 |
| AC-23 | happy | **60/min 触发 429** — 模拟同一 user 连续 61 次 POST → 第 61 次返 429 + `Retry-After` header；GET list 不受限（不在 hot scope） | 集成测试：`backend/tests/integration/test_034_rate_limit_v2.py` 含 `test_v2_create_429_after_60` 期望第 61 次 status_code == 429 | 429 触发 | Axis 5 happy |
| AC-24 | happy | **per-user 隔离** — user_A 触限不影响 user_B（user_B 同 endpoint 仍 200） | test 含 `test_v2_rate_limit_per_user_isolation`：user_A 触发 429 同时 user_B 调同 endpoint 期望 200 | per-user 隔离 | Axis 5 happy |
| AC-25 | boundary | **不做 IP-based 限流 + 不做 per-endpoint 自定义** — 60/min 统一适用 3 个 hot endpoint；proxy 后 IP 失真不算 US10 范围；config 不引入 `RATE_LIMIT_V2_CREATE_PER_MIN` 等细分 | (1) `git grep -c 'rate_limit_v2_hot_per_min' backend/app/core/config.py` 期望 == 1 hit（仅 1 个 config key，不细分）；(2) `git grep -c '_client_ip' backend/app/modules/resumes_v2/api.py` 期望 == 0 hits（v2 hot 走 user_id，不走 IP） | 1 config + per-user | Axis 5 排除项 |

## 跨 axis 关联

- **Axis 1 ↔ Axis 3**: ErrorBoundary catch → telemetry.api_error (AC-02 + AC-14 联动)
- **Axis 2 ↔ Axis 3**: client.ts 5xx 路径 → telemetry.api_error (AC-07 + AC-14 联动)
- **Axis 5 ↔ Axis 3**: 429 触发 → telemetry.api_error (status=429) (AC-22 + AC-14 联动)
- **Axis 4 与其他独立**: 仅 audit，不改 runtime 行为

## Tester 反驳日志

### R1 — Axis 4 RLS Audit — scope_mismatch — AC-16 引用 4 表但只 1 表 RLS
**反例**: AC-16/AC-17 声称审计 4 表 `resumes_v2 / sharing / public_resume / statistics`，但读 `backend/migrations/versions/0022_032_resumes_v2.py` 行 52-57 显示**只有 `resumes_v2` 有 ENABLE+FORCE ROW LEVEL SECURITY + `resumes_v2_user_isolation` policy**；`resume_statistics_v2` (行 155) 与 `resume_analysis_v2` (行 22 注释明确说 "Statistics and analysis rows are reached only via the parent") 故意未建 RLS policy（父行 RLS 拦 access）。`sharing` 表名不匹配实际（migration 无 `sharing` 表，ac 凭空）；`public_resume` 是 `resumes_v2.is_public=true` 的 partial index（行 126-129），非独立表。
**风险**: dev 若按 AC-16 字面新建 4 个 test，会写 `git grep 'ENABLE ROW LEVEL' sharing` → 0 hit → 失败；或写 `audit public_resume` 找不到表 → 测无法跑；按 plan 锁定 AC-16 必然 deliver 错。
**建议**: AC-16 改为 1 表（`resumes_v2` 唯一 RLS-enabled） + 跨边界测 (parent-gated access 走 `resume_statistics_v2` 必须经 `resumes_v2` 父行 join 才能 SELECT 出来)；删除 `sharing` / `public_resume` 引用；或明确新增 RLS policy 后再 audit（与 AC-20 "不动 policy" 矛盾 → 选一边）。

### R2 — Axis 4 RLS Audit — coverage_gap — AC-16 缺 system 路径与 8 policy 全覆盖
**反例**: AC-16 仅测 user_A → user_B 横向越权（4 表 × SELECT=0 rows），但 spec.md SC-US10-A4 要求"audit RLS"，memory `mcp_pg_rls_caveat` 指出 RLS 默认对 superuser/table owner **不生效**（需 FORCE RLS 才拦 owner）。当前 migration `resumes_v2` **已加 FORCE ROW LEVEL SECURITY**（行 54），但 AC-17 未测：(a) postgres role 直连（bypassing app 鉴权）能否 SELECT；(b) `SET LOCAL row_security=OFF` 是否被拦截；(c) service role 通过 `app.domain.rls.set_user_context` 后是否被父行策略放行；(d) UPDATE/DELETE 而非 SELECT 的越权。
**风险**: dev 上线后若 postgres 误配只读 role 给某个 worker，FE/BE 都通过 RLS 但 worker 直查泄漏 PII；AC-17 happy pass 不代表 production 安全。
**建议**: AC-17 扩为 ≥ 8 case（4 表 × {SELECT/UPDATE/DELETE} 越权 + 1 个 system-bypass test 用 `psycopg2.connect(user='postgres')` 验证 RLS 在 table owner 下仍生效）。

### R3 — Axis 3 Telemetry — single_point_of_failure — AC-12/AC-15 端点挂掉全卡
**反例**: AC-12 把 telemetry endpoint 设为 `POST /api/v1/telemetry/events` 单一 sink（jsonl append-only），前端 AC-15 强调"失败静默不阻塞 UI"。但：(a) 后端若 `backend/logs/` 目录无写权限（Docker volume 未挂）→ 端点返 500；(b) 单一端点无降级：AC-11 sendBeacon 失败重试 fallback 到 fetch keepalive 仍打到同一后端 → 整条链路瘫；(c) AC-02 + AC-07 + AC-22 三处均报 `api_error` 到同一端点，限流 100/min per IP 触发后所有 telemetry 全部丢失。
**风险**: dev 上线 production 1 周后若 disk 满 / 权限错 / 限流打爆 → 监控全盲；盲区 + 限流串扰。
**建议**: AC-12 加 disk-full 降级 (catch OSError → 返 204 + stderr 记一行) + buffer-and-retry（in-memory ring buffer，重启丢失可接受）；AC-15 加"端点 3 次失败后 client 切 console.warn 模式"防静默丢数据。

### R4 — Axis 3 Telemetry — PII_泄漏 — AC-11/AC-14 `resume_save` payload 含 PII
**反例**: AC-11 列出事件 `resume_save / resume_update_v2_sse / api_error`，payload 必含 `user_id` (JWT) + `request_id` + 路径参数。dev Phase 2 实现必然把 `user_id` (UUID) 写入 jsonl → 等于行为日志记 user 行为轨迹；`api_error` 事件 `path` 字段可能含 query string 中的 email/token（如 `PUT /api/v1/v2/resumes/{id}?invite=email@x.com`）→ jsonl 中明文 PII/凭据。
**风险**: spec.md US10 是 ship-readiness，没 GDPR/合规扫描；jsonl 文件若不加密 + 留 30 天 = 监管风险（EU 用户）+ log 平台泄漏。
**建议**: AC-11 强约束 (a) payload 白名单（user_id 仅 hash 不明文 / path 仅路径模板不存 query string / 不带 token 字段）；(b) jsonl 60 天滚动删除；(c) dev 必加 unit test 验证 `telemetry.api_error` 不带 `Authorization` header / cookie / `email`/`phone` field。

### R5 — Axis 2 Retry — idempotency_violation — AC-07 PUT 412 循环 + 客户端 3x retry → 9x 流量
**反例**: AC-07 已识别 PUT `If-Match: <old_version>` 重试风险（写"必加 client 路径"），但未给硬约束：(a) client 读 412 后 fetch GET 拿新 version → 再 PUT — 此时如 server 中间版本又被别人改了 → 第二次 PUT 又 412 → AC-10 说"max 3 attempts"但**这 3 attempts 包含 412 retry 路径**，可能 1 次业务重试 + 2 次 412 refresh 全耗尽仍失败；(b) AC-07 同时说"429 backoff 读 Retry-After" — 但 `Retry-After` 是 60s 整，3 次重试堆叠 180s → 用户卡 3 分钟；(c) spec "PUT/POST/DELETE 全重试" 实际是 9x 流量（3 client × 3 attempts）— 与 AC-25 rate limit 60/min 冲突：单个 user 1 次 PUT 失败 → 触发 9x requests → 立即被限流。
**风险**: AC-07 看似周到但执行起来 PUT 走 1 次业务 + 2 次 412 refresh = 3 attempts 全部消耗；与限流 60/min 互踩：v2 hot endpoint 限流是 60/min 但 PUT 单次失败可消耗 9 quota，6 次失败就用完当日 quota。
**建议**: AC-07 拆为 (a) 业务重试 max 1 次（2 attempts），(b) 412 走 refresh path 不计入 retry 预算，(c) `Retry-After` 期间禁二次 retry。

### R6 — Axis 1 ErrorBoundary — info_disclosure — AC-01 fallback UI 暴露 stack trace
**反例**: AC-03 fallback UI "Something went wrong" + reload 按钮，AC-01 没约束是否显示 stack trace。dev 常见做法：fallback 里 `console.error(error)` + UI 显示 error.message。`error.message` 经常含 API path + stack 前几行（如 `TypeError: Cannot read property 'id' of undefined at ResumeList (ResumeList.tsx:42)`）— 在生产是 **PII 泄露**（用户名/路径/内部组件名）+ 给攻击者 recon。
**风险**: dev 上线后攻击者触发 XSS/异常路径 → 从 fallback UI 读源码结构。
**建议**: AC-01 硬约束 fallback UI **不**显示 error.message / stack（仅 generic "Something went wrong" + reload + "Report ID: {requestId}" 按钮）；console.error 可保留；AC-03 单测断言 `screen.queryByText(/TypeError/)` 为 null。

### R7 — Axis 1 ErrorBoundary — coverage_gap — AC-05 "仅 1 顶层" 漏 BuilderShell 单点挂掉
**反例**: AC-05 grep ≤ 2 hits = "仅 1 顶层"，但 v2 editor = 3 面板（左 Section / 中 Builder / 右 Design），范围 cast "不做 granular per-component"。若 BuilderShell 内某个 react-three-fiber canvas（PDF 预览）抛 `WebGL context lost` → 整棵 App.tsx ErrorBoundary 接住 → 用户**所有 v2 编辑丢失**（含未保存 draft）。spec cast "不 granular" → 单点 = 整 app 挂。
**风险**: 1 个 PDF 预览组件崩 = 用户丢所有编辑（含非该组件数据）；与"production minimum" 相悖 — 1 个组件不能毁整 app。
**建议**: AC-05 改"1 顶层 + 1 panel boundary" (PDF/Canvas 单独 boundary，fallback 显示 "PDF renderer failed - editing safe")；或 AC-01 显式排除 react-three-fiber 路径 (lazy import try/catch)。

### R8 — Axis 5 Rate Limit — spec_mismatch — AC-22 缺 `duplicate` 是否独立 quota
**反例**: AC-22 列 `POST /api/v1/v2/resumes` + `PUT /api/v1/v2/resumes/{id}` + `POST /api/v1/v2/resumes/{id}/duplicate` 3 endpoint 共用 `scope="v2_hot"`, 60/min 统一配额。问题：(a) duplicate 创建新 resume 业务上是独立 resume → 配额应独立？(b) 60/min 是 per user 但 dev 实际 verify 用同 1 user 连续 61 次 POST → **测的是 create 而非 duplicate** — AC-23 happy test 只测 create 触发 429，duplicate 行为未测；(c) AC-24 per-user 隔离只测 create，duplicate 行为同样未测。
**风险**: production duplicate endpoint 可能有不同幂等性问题（如重试产生 2 份 resume），单独 audit 后才能定 quota；混在一起测不出。
**建议**: AC-22 把 duplicate 列为单独 scope `scope="v2_duplicate"`, 配额独立（如 30/min）; AC-23/AC-24 必含 duplicate path 测试。

### R9 — Axis 5 Rate Limit — conflict — AC-25 60/min vs 600/min 业务限流冲突
**反例**: AC-21 加 `rate_limit_v2_hot_per_min=60`, 但 config.py 行 82 已有 `rate_limit_business_per_min=600`。`enforce_rate_limit` 用 scope 区分 token bucket，但 v2 hot endpoint 不在 business scope → 60/min 是新 key。问题：(a) AC-25 grep `rate_limit_v2_hot_per_min == 1 hit` 只能验 config 写 1 次，但 enforce_rate_limit 内部可能 fallback 到 `rate_limit_business_per_min=600`（如 scope key 不在 config 时）— dev 必保 60 优先生效；(b) 前端 AC-07 retry 3x 把 60/min 实际打穿到 180/min → backend 仍按 60 计数 → 第 31 次业务成功但第 31+ 次 429，但前端 retry 把"成功"那次也算 retry → 配额计数混乱。
**风险**: spec 没明说 token bucket 是 fixed window 还是 sliding window；60 vs 600 实际是 1:10 关系，1 个 v2 hot 调用 = 10 业务额度？or 独立 counter？dev 不明就可能 ship 错。
**建议**: AC-21 补充 scope→bucket 映射断言 (e.g., `git grep 'v2_hot.*60' backend/app/core/rate_limit.py` 期望 ≥ 1 hit) + AC-25 加 "scope key 不在 config 时不 fallback 到 business" 单元测试。

### R10 — Axis 2 Retry — SSE 重连盲区 — 范围 cast "不做 SSE-WS retry" 误判
**反例**: 范围 cast 行 73 "不做 SSE / WebSocket retry（SSE 已有 pg_notify + reconnect）"。memory `req_034_us8_test` 验证 SSE pg_notify 修好（test_sse.py 6/6），但 SSE **客户端重连** 不是后端责任。AC-02 写 "ErrorBoundary → telemetry.api_error"，但 SSE 断线不在 ErrorBoundary 捕获路径（不 throw）— 用户 5 分钟前看到 v2 editor live update，5 分钟后因网络抖动静默无更新，且无任何提示。
**风险**: spec cast 写"SSE 已有 reconnect"但实测只验后端，前端 EventSource 无重连逻辑 = production 静默丢更新（用户改 resume 后看不到 live preview，误以为改坏了）。
**建议**: AC-06/AC-07 扩一个"SSE EventSource auto-reconnect with backoff" AC（如 `new EventSource(url, {withCredentials: true})` + onerror 触发重连 1/2/4/8s）；或范围 cast 显式补 "前端 SSE 客户端重连 deferred 到 035"。

### R11 — Axis 3 Telemetry — observability_gap — "production minimum" 模糊
**反例**: AC-11/AC-12/AC-13/AC-14 用具体方法名（`page_view` / `api_error` / `dialog_open` 等），但**没说 telemetry 事件 schema 是否包含 `app_version` / `git_sha`**。dev 上线 production 后 jsonl 文件查到 `event_name='api_error'` 但**不知道哪个 build 出的错** — 等于上线后 50% 调试能力损失。
**风险**: spec 用 "production minimum" 模糊词（行 7 scope_cast）但实际 ship-readiness 应含 build identifier。
**建议**: AC-11 payload 必含 `app_version` (frontend vite env `VITE_APP_VERSION` 或 build hash) + `git_sha` (CI 注入)，dev 必加 `import.meta.env.VITE_GIT_SHA` 注入；AC-12 接收后存 jsonl 必保留字段。

### R12 — 跨 Axis 4 surface — scope_creep — 未覆盖 CSRF/CORS/CSP/security headers
**反例**: scope_cast 行 7 写 "不做 enterprise-grade (避免 scope creep)"，但**v2 ship 公开 endpoint** `POST /api/v1/v2/resumes/{id}/duplicate` + telemetry `POST /api/v1/telemetry/events` 公开（AC-12 "不要求 auth"） = 攻击面。telemetry 公开 + 后端无 CSP/CORS 限制 = 跨站 telemetry 投毒（attacker 站点发 fake event 污染 jsonl）。CSRF 同理（cookie 鉴权时）。
**风险**: spec "production minimum" 隐式含"可上线", 但 security headers 缺失 = 实际上线后有 XSS/CSRF/clickjacking 风险。
**建议**: scope_cast 加 1 行 "**不**做 CSP / CORS / CSRF token 强化（v1 已有 FastAPI 默认）"，让 ship-readiness 的"readiness"边界清晰；或加 1 个 AC-26 验 `response.headers['X-Content-Type-Options'] == 'nosniff'` + CORS 限定 origin。

### R13 — 跨 Axis 4 surface — dev_machine_blindspot — AC-16 缺 prod deploy 验证
**反例**: AC-16 在 dev machine 跑（`pytest backend/tests/integration/test_034_rls_audit.py`）通过不代表 production 通过。memory `mcp_pg_rls_caveat` 提到 `mcp__postgres__query` 查 RLS 表返 0 rows (3 种 workaround)，但**dev machine 通常 RLS OFF 或 policy 不全** — 4 表 audit 在 dev 跑过即认为 ship-ready 不可靠。
**风险**: production Postgres 配 RLS 时若 alembic 没跑全 → 4 表全 bypass；dev machine 测过 → ship 后越权。
**建议**: AC-16 加 1 个 gate: CI step "verify production RLS policy 数量 ≥ 4 by `mcp__postgres__query` direct probe" — 即在 prod-like env 跑 1 次 sanity check，4 表 policy 都在 → 才认为 AC-17 通过。

### R14 — 跨 Axis 2 surface — 不可测断言 — "Max 3 attempts" 数字未量化吞吐影响
**反例**: AC-10 "最多 3 attempts" 数字硬编码，但缺 (a) P99 5xx 触发率 (3 attempts 把 P99 200ms 拉成 P99 600ms — production 不可接受)；(b) 重试占 server load 比例 (3x 网络流量 + 3x server CPU)；(c) "成功 retry" 率指标 (dev 上线后如何 know retry 帮了多少忙)。无 P50/P99 阈值 = AC-10 是单元测通过即过，但 production 性能 / 成本不可知。
**风险**: spec "production minimum" 必须含可观测 SLA，否则 ship 后 dev 无 visibility。
**建议**: AC-10 加 SLO (a) retry 路径 P99 latency < 1s；(b) telemetry 上报 `retry_count` 字段，dev 在 1 周后从 jsonl 统计 "5xx 中 retry 后成功 %"。

### R15 — 跨 Axis 3 surface — 集成点 4 联动仅声明未测 — AC-02/AC-14/AC-22 串行路径无 e2e
**反例**: 跨 axis 关联段 83-87 写 4 联动 (Axis1↔3 / Axis2↔3 / Axis5↔3)，但**联动**本身无 e2e test。例如：用户 PUT 失败 → 5xx → client 重试 3x 全失败 → 抛 ApiError → ErrorBoundary 接住 → 上报 telemetry `api_error` → 后端 jsonl 写入 → 前端无感静默 — 这条链路过 5 个 AC (AC-07 + AC-10 + AC-02 + AC-14 + AC-15)，**全链路 happy path 无 1 个 e2e**。
**风险**: 单 AC 都过 = 5 个齿轮都好，但**装配一起可能齿轮不咬合** (e.g., AC-14 `api_error` payload 字段 AC-02 `react_error` 字段不兼容)。
**建议**: AC-26 (新) 写 1 个 e2e test: 模拟 network failure → PUT 失败 → 触发 ErrorBoundary → 验证 telemetry.jsonl 出现 `event_name='react_error'` 行 + 行 payload 含 `requestId` 字段与 AC-02 一致。

### 判定
**MAJOR** (1 BLOCKER 候选 R1 + 6 MAJOR + 8 MINOR) — R1 必 fix (4 表 mismatch 是 100% 错)，R2/R3/R4/R5/R7/R11 是 ship-readiness 关键；R6/R8/R9/R10/R12/R13/R14/R15 是 production polish 不阻塞但 dev Phase 2 顺手做。
**最关键 3 fix-or-die**: R1 (AC-16 4 表字面错)、R5 (AC-07 PUT 412 retry loop 与 60/min 限流冲突)、R7 (AC-05 漏 PDF/Canvas 边界 → 单点崩毁全 app)。
---

## Moderation Log (Main-agent 裁判, Round 1)

| # | axis | 类型 | 标题 | 裁判 | 编码为 Phase 2 硬约束 |
|---|------|------|------|------|---------------------|
| R1 | Axis 4 | scope_mismatch | AC-16 引用 4 表但只 1 表 RLS | **接受** | 修订 #1: AC-16 改 1 表 `resumes_v2` (唯一 RLS-enabled) + 跨边界 parent-gated 测; 删 `sharing` / `public_resume` 引用 |
| R2 | Axis 4 | coverage_gap | AC-16 缺 system 路径 + 8 policy 全覆盖 | **接受** | 修订 #2: AC-17 扩 ≥ 4 case (SELECT/UPDATE/DELETE 越权 + system-bypass test 用 `psycopg2.connect(user='postgres')` 验证 RLS 在 table owner 下仍生效) |
| R3 | Axis 3 | single_point_of_failure | AC-12 端点挂掉全卡 | **接受** | 修订 #3: AC-12 加 disk-full 降级 (catch OSError → 返 204 + stderr) + buffer-and-retry (in-memory ring buffer); AC-15 加"端点 3 次失败后 client 切 console.warn 模式" |
| R4 | Axis 3 | PII_泄漏 | AC-11/AC-14 `resume_save` payload 含 PII | **接受** | 修订 #4: AC-11 强约束 (a) payload 白名单 (user_id hash 不明文 / path 仅模板不带 query / 不带 token 字段); (b) jsonl 60 天滚动删除; (c) dev 必加 unit test 验证 telemetry 不带 Authorization/cookie/email/phone |
| R5 | Axis 2 | idempotency_violation | AC-07 PUT 412 循环 + 60/min 限流冲突 | **接受** | 修订 #5: AC-07 拆 (a) 业务重试 max 1 (2 attempts), (b) 412 走 refresh path 不计入 retry 预算, (c) `Retry-After` 期间禁二次 retry |
| R6 | Axis 1 | info_disclosure | AC-01 fallback UI 暴露 stack trace | **接受** | 修订 #6: AC-01 硬约束 fallback UI **不**显示 error.message / stack; 仅 generic "Something went wrong" + reload + "Report ID: {requestId}" 按钮; console.error 可保留; AC-03 单测断言 `screen.queryByText(/TypeError/)` 为 null |
| R7 | Axis 1 | coverage_gap | AC-05 漏 BuilderShell/PDF 单点挂掉 | **部分接受** | 修订 #7: AC-05 改"1 顶层 + 1 panel boundary" (PDF/Canvas 单独 boundary, fallback "PDF renderer failed - editing safe") |
| R8 | Axis 5 | spec_mismatch | AC-22 缺 `duplicate` 是否独立 quota | **接受** | 修订 #8: AC-22 duplicate 单独 scope `v2_duplicate` 配额 30/min; AC-23/AC-24 必含 duplicate path 测试 |
| R9 | Axis 5 | conflict | AC-25 60 vs 600 限流冲突 | **接受** | 修订 #9: AC-21 加 scope→bucket 映射断言 (`git grep 'v2_hot.*60' backend/app/core/rate_limit.py` ≥ 1 hit); AC-25 加 "scope key 不在 config 时不 fallback 到 business" 单元测试 |
| R10 | Axis 2 | SSE 重连盲区 | 范围 cast "不做 SSE-WS retry" 误判 | **部分接受** | 修订 #10: 范围 cast 显式补 "前端 SSE EventSource auto-reconnect **deferred 到 035**" — production minimum 不强制 |
| R11 | Axis 3 | observability_gap | AC-11 缺 app_version / git_sha | **接受** | 修订 #11: AC-11 payload 必含 `app_version` (vite env) + `git_sha` (CI 注入); dev 必加 `import.meta.env.VITE_GIT_SHA` 注入 |
| R12 | 跨 Axis 4 | scope_creep | 未覆盖 CSRF/CORS/CSP/security headers | **部分接受** | 修订 #12: scope_cast 加 1 行 "**不**做 CSP / CORS / CSRF 强化 (v1 已有 FastAPI 默认)" — readiness 边界清晰 |
| R13 | 跨 Axis 4 | dev_machine_blindspot | AC-16 缺 prod deploy 验证 | **接受** | 修订 #13: AC-16 加 CI gate: prod RLS policy 数量 ≥ 1 (因 R1 修订后只 1 表) by `mcp__postgres__query` direct probe |
| R14 | 跨 Axis 2 | 不可测断言 | "Max 3 attempts" 数字未量化 | **接受** | 修订 #14: AC-10 加 SLO (a) retry 路径 P99 latency < 1s; (b) telemetry 上报 `retry_count` 字段, dev 1 周后从 jsonl 统计 "5xx 中 retry 后成功 %" |
| R15 | 跨 Axis 3 | 集成点 4 联动 | 4 联动仅声明未测 | **接受** | 修订 #15: AC-26 (新) 写 1 个 e2e: 模拟 network failure → PUT 失败 → 触发 ErrorBoundary → 验证 telemetry.jsonl 出现 `event_name='react_error'` + payload 含 `requestId` 字段与 AC-02 一致 |

**裁判总览**: 15 反例全接受 (3 部分接受含范围 cast), 无驳回。**L007 token 风险 + US5/6/7/8/9 precedent → 跳过 dev round 2 文件修订直接锁定**, 15 修订编码为 Phase 2 Implementation Spec 硬约束。

---

## Phase 2 Implementation Spec (dev 必须按此实施, locked)

> **dev Phase 2 实施 US10 时必须落实以下 15 修订**。每条对应原 AC 行号 + 修订动作 + 验证方式。

### 修订 #1 (R1): AC-16 改 1 表 resumes_v2
- 删除 `sharing` / `public_resume` 引用 (字面错)
- AC-16 仅 audit `resumes_v2` (唯一 RLS-enabled + FORCE ROW LEVEL SECURITY)
- 加跨边界测: parent-gated access 经 `resume_statistics_v2` 必须 join `resumes_v2` 父行才能 SELECT

### 修订 #2 (R2): AC-17 扩 ≥ 4 case
- (a) SELECT 越权: user_A 查 user_B resume → 0 row
- (b) UPDATE 越权: user_A UPDATE user_B resume → 0 row affected
- (c) DELETE 越权: user_A DELETE user_B resume → 0 row affected
- (d) system-bypass: `psycopg2.connect(user='postgres')` 验证 RLS 在 table owner 下仍生效 (FORCE RLS 已 ship)

### 修订 #3 (R3): AC-12 disk-full 降级 + buffer-and-retry
- 后端 catch OSError → 返 204 + stderr 记一行
- 前端 AC-15 加"端点 3 次失败后 client 切 console.warn 模式"防静默丢数据
- in-memory ring buffer: 重启丢失可接受

### 修订 #4 (R4): AC-11 PII 防护
- payload 白名单:
  - `user_id` 仅 hash (SHA-256 trunc 16 chars) 不明文
  - `path` 仅路径模板不存 query string
  - 不带 `Authorization` / cookie / `email` / `phone` field
- jsonl 60 天滚动删除 (backend script + cron)
- dev 必加 unit test 验证 telemetry.api_error 不含敏感字段

### 修订 #5 (R5): AC-07 retry 拆 3 段
- (a) 业务重试 max 1 次 (2 attempts 总)
- (b) 412 走 refresh path (GET 拿新 version) **不**计入 retry 预算
- (c) `Retry-After` 期间禁二次 retry (客户端硬阻塞)

### 修订 #6 (R6): AC-01 fallback UI 不暴露 stack
- fallback 仅显示 "Something went wrong" + reload 按钮 + "Report ID: {requestId}" 按钮
- console.error 可保留 (dev console)
- **不**显示 error.message / stack
- AC-03 单测断言 `screen.queryByText(/TypeError/)` 为 null

### 修订 #7 (R7): AC-05 加 1 panel boundary
- "1 顶层 + 1 panel boundary" (PDF/Canvas 单独 boundary)
- PDF boundary fallback: "PDF renderer failed - editing safe"
- 防止 WebGL context lost / PDF 渲染错误毁整 app

### 修订 #8 (R8): AC-22 duplicate 单独 scope
- `scope="v2_duplicate"` 配额 30/min (独立于 v2_hot 60/min)
- AC-23/AC-24 必含 duplicate path 测试
- 测 31 次 duplicate → 第 31 次 429

### 修订 #9 (R9): AC-21/AC-25 scope→bucket 映射
- AC-21 加: `git grep 'v2_hot.*60' backend/app/core/rate_limit.py` ≥ 1 hit
- AC-25 加: "scope key 不在 config 时不 fallback 到 business" 单元测试
- 显式声明 token bucket 是 fixed window (不混 business 600/min)

### 修订 #10 (R10): SSE EventSource reconnect deferred
- 范围 cast 显式补: "前端 SSE EventSource auto-reconnect **deferred 到 035**"
- production minimum 不强制
- US10 AC 不锁 SSE 客户端重连 (因属 react 客户端, 跨多 component)

### 修订 #11 (R11): AC-11 payload 必含 build identifier
- `app_version` (vite env `VITE_APP_VERSION` 或 build hash)
- `git_sha` (CI 注入 `import.meta.env.VITE_GIT_SHA`)
- AC-12 接收后存 jsonl 必保留字段

### 修订 #12 (R12): scope_cast 边界
- scope_cast 加 1 行: "**不**做 CSP / CORS / CSRF token 强化 (v1 已有 FastAPI 默认)"
- readiness 边界清晰: hardening 不含 security headers 重构

### 修订 #13 (R13): AC-16 CI gate
- dev machine 跑通后, 必须再加 CI step: `mcp__postgres__query` direct probe 验证 prod RLS policy 数量 ≥ 1 (因 R1 修订后只 1 表)
- 此 gate 失败 → ship-readiness FAIL

### 修订 #14 (R14): AC-10 SLO
- retry 路径 P99 latency < 1s (实测)
- telemetry 上报 `retry_count` 字段
- dev 1 周后从 jsonl 统计 "5xx 中 retry 后成功 %" 上报

### 修订 #15 (R15): AC-26 e2e 全链路
- 1 个 e2e test: 模拟 network failure → PUT 失败 → 触发 ErrorBoundary → 验证 telemetry.jsonl 出现 `event_name='react_error'` 行 + payload 含 `requestId` 字段与 AC-02 一致
- 跨 axis 联动验证 (Axis 1+2+3)

### 范围 cast 摘要 (locked)
- US10 = 5 axis cross-cutting hardening: ErrorBoundary + Retry + Telemetry + RLS audit + Rate limit
- "production minimum" = 足够 production 上线, 不做 enterprise-grade
- 不做 SSE 客户端重连 (deferred 035)
- 不做 CSP/CORS/CSRF 强化 (v1 已有 FastAPI 默认)
- 不做 OTel SDK 集成 (P2 升级)
- 不做 distributed tracing (P2 升级)
- 不做 column-level security
- 不做 IP-based rate limit (proxy 后失效)
- 不做 granular per-component ErrorBoundary (仅 1 顶层 + 1 PDF/Canvas panel)

