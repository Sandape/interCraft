# Feature Specification: 性能与可观测性增强

**Feature Branch**: `022-perf-observability-enhancement`

**Created**: 2026-06-22

**Status**: Draft

**Input**: User description: "Feature 022 — 性能与可观测性增强。补齐 v1 在可观测性和性能方面的短板，范围聚焦在六项高/中严重度 gap：LLM 日志 request_id 关联、Resume 列表 N+1 查询、errors 表复合索引、前端路由懒加载、Vite manualChunks、metrics 覆盖补全。不改业务逻辑，不改 API 契约。"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - 排障工程师通过 request_id 关联 LLM 调用 (Priority: P1)

作为线上排障工程师，当用户反馈某次 AI 面试或错题强化结果异常时，我需要通过 HTTP 请求 ID 追溯到该请求触发的所有 LLM 调用日志，从而定位是评分逻辑还是模型响应问题。当前每次 LLM 调用日志生成的新 UUID 无法回溯到原始 HTTP 请求，排障只能靠时间戳模糊匹配。

**Why this priority**: 可观测性是 v1 上线后的首要短板。线上事故无法快速定位直接拖累运营效率；request_id 是所有分布式追踪的基础，不修复则后续 metrics 和 trace 都失去关联锚点。

**Independent Test**: 在 `/api/v1/agents/error-coach/{thread_id}/messages` 请求头中注入 `X-Request-ID`，触发一轮 evaluate 调用后，grep LLM 日志应能按同一 request_id 找到对应 `llm.invoke` 事件。

**Acceptance Scenarios**:

1. **Given** 后端收到带 `X-Request-ID: abc-123` 的面试请求，**When** 该请求触发 evaluate 节点 LLM 调用，**Then** `llm.invoke` 结构化日志的 `request_id` 字段值为 `abc-123`。
2. **Given** 后端收到未带 `X-Request-ID` 的请求，**When** 中间件生成 UUID 并注入响应头 `X-Request-ID`，**Then** 该请求触发的 LLM 调用日志使用此生成值。
3. **Given** 一次 HTTP 请求触发 3 次 LLM 调用（fetch_question / hint / evaluate），**When** 在日志系统中按 `request_id=abc-123` 过滤，**Then** 3 条 `llm.invoke` 日志按时间顺序排列，均包含同一 `request_id`。

---

### User Story 2 - 用户快速加载简历列表页 (Priority: P1)

作为求职者，在打开简历列表页时，我期望页面在 500ms 内展示所有简历分支及各自的版本数和块数。当前后端列表查询返回分支列表后，前端对每个分支单独查询版本数和块数，10 个分支意味着 11 次数据库往返，首屏延迟可达 2-3 秒。

**Why this priority**: 简历列表是高频访问页面（用户登录后默认落地页之一），性能直接影响用户留存。N+1 是数据库性能反模式，修复后单页可支撑更多分支而无延迟退化。

**Independent Test**: 创建 1 个用户 + 10 个分支（每分支 3 版本 + 5 块），访问 `GET /api/v1/resume-branches`，断言后端 SQL 查询计数 ≤ 2（1 次列表 + 1 次聚合 COUNT），断言响应耗时 P95 ≤ 300ms。

**Acceptance Scenarios**:

1. **Given** 用户有 10 个简历分支，每分支有 3 版本 + 5 块，**When** 调用 `GET /api/v1/resume-branches`，**Then** 响应包含 10 个分支，每个分支携带 `version_count=3` 和 `block_count=5` 字段。
2. **Given** 同一用户同一数据，**When** 后端处理此请求，**Then** 数据库连接上执行的 SQL 语句数量 ≤ 2（通过 `pg_stat_statements` 或 SQL 日志计数验证）。
3. **Given** 用户无任何分支，**When** 调用列表接口，**Then** 响应为空数组 `[]`，且仅执行 1 次 SQL。

---

### User Story 3 - 错题本列表在万级数据下流畅滚动 (Priority: P2)

作为面试备考用户，当错题本积累到 500+ 条时，列表按状态/频率/创建时间排序应保持秒级响应。当前 `error_questions` 表无复合索引，排序走全表扫描，500 条数据下 P95 延迟可达 800ms。

**Why this priority**: 错题本是长期使用型功能，数据量随时间累积。索引缺失是渐进性性能衰退的典型，不修复会导致用户使用越久体验越差。

**Independent Test**: 在测试数据库插入 500 条错题，调用 `GET /api/v1/error-questions?source=all`，用 `EXPLAIN` 验证查询计划使用 `Index Scan` 而非 `Seq Scan`，P95 延迟 ≤ 200ms。

**Acceptance Scenarios**:

1. **Given** 用户有 500 条错题，状态分布 fresh/practicing/mastered，**When** 调用 `GET /api/v1/error-questions`，**Then** 响应 P95 延迟 ≤ 200ms。
2. **Given** 同一数据集，**When** 通过 `EXPLAIN ANALYZE` 查看查询计划，**Then** 主排序路径使用 `Index Scan`，而非 `Seq Scan`。
3. **Given** 用户查询 `?source=auto` 过滤，**When** 执行查询，**Then** 查询计划使用索引下推过滤，而非全表扫后再过滤。

---

### User Story 4 - 访客首屏快速看到登录页 (Priority: P2)

作为首次访问站点的访客，我期望登录页在 1.5 秒内完成加载并交互。当前所有 17 个页面（含 ResumeEditor、InterviewLive、InterviewReport 等重组件）被 eager import 进首屏 bundle，导致首屏 JS 体积膨胀，即便访问 `/login` 也要下载全部页面代码。

**Why this priority**: 首屏加载速度直接影响新用户转化率。SEO 和广告投放的落地页多为登录页，加载慢导致跳出率高。路由懒加载是前端性能的基线优化。

**Independent Test**: 运行 `npm run build` 后，用 `vite-bundle-visualizer` 或 rollup-plugin-visualizer 分析 `dist/`，断言登录页对应的 chunk 体积 ≤ 500KB（不含 vendor chunk），且 ResumeEditor / InterviewLive / InterviewReport 出现在独立 chunk 文件中。

**Acceptance Scenarios**:

1. **Given** 生产构建产物 `dist/`，**When** 打开 `dist/index.html` 查看首屏引用的 JS 文件，**Then** 首屏 JS 体积（gzip 后）≤ 500KB。
2. **Given** 访问 `/login` 路由，**When** 浏览器 Network 面板观察 JS 下载，**Then** 仅下载 `index` + `vendor` + `Login` chunk，不下载 `ResumeEditor` / `InterviewLive` 等重组件 chunk。
3. **Given** 用户在 `/login` 页面点击「进入控制台」导航到 `/resume`，**When** 浏览器请求新页面，**Then** 额外下载 `ResumeEditor` chunk，Suspense fallback 显示 ≤ 500ms。

---

### User Story 5 - 运维通过 metrics 监控 LLM 配额与 checkpointer 健康 (Priority: P2)

作为运维工程师，我需要通过 Prometheus `/metrics` 端点监控 LLM 配额耗尽事件、checkpointer 重连次数、WebSocket 并发连接数、ARQ 任务积压量四类指标，以便在配额接近上限或 checkpointer 频繁断连时主动告警。当前 metrics 仅覆盖 HTTP/auth/resume/lock/outbox 五类，AI 与异步任务的可观测性盲区。

**Why this priority**: v1 已上线 4 个 LangGraph agent + 2 个 ARQ worker，但运维对 AI 和异步层的可观测性几乎为零。配额耗尽会导致用户 AI 功能静默失败，checkpointer 断连会导致面试卡顿，均需主动监控。

**Independent Test**: 触发一次 LLM 配额不足场景（mock quota used > quota），访问 `/metrics` 应能找到 `llm_quota_exhausted_total` 指标且值 ≥ 1；触发一次 WS 连接，应能找到 `ws_connections_active` 指标且值 ≥ 1。

**Acceptance Scenarios**:

1. **Given** LLM 配额已耗尽，**When** 用户尝试调用 AI 接口，**Then** `/metrics` 中 `llm_quota_exhausted_total` 指标值 +1。
2. **Given** checkpointer 因 idle 断连后重连成功，**When** 查询 `/metrics`，**Then** `checkpointer_reconnect_total` 指标值 ≥ 1。
3. **Given** 3 个用户同时连接 WebSocket，**When** 查询 `/metrics`，**Then** `ws_connections_active` 指标值 = 3。
4. **Given** ARQ 队列中有 5 个未处理任务，**When** 查询 `/metrics`，**Then** `arq_jobs_queued` 指标值 = 5。
5. **Given** 运维抓取 `/metrics` 端点，**When** 解析 Prometheus 格式输出，**Then** 至少暴露 15 个不同指标名（含既有 5 类 + 新增 4 类）。

---

### User Story 6 - 构建产物 vendor 分包稳定 (Priority: P3)

作为前端开发者，我期望 `npm run build` 产出的 vendor chunk（react / react-router / tanstack 等）与业务代码分离，使得依赖升级时浏览器缓存命中率提升，用户无需重新下载未变更的第三方库。当前所有代码混打成一个 bundle，任何业务改动都会让用户重新下载全部 vendor 代码。

**Why this priority**: 缓存优化是长期收益项，单次构建影响不大，但日常发版累积的带宽节省和加载加速显著。优先级低于功能性 story，但作为性能基线必须落地。

**Independent Test**: `npm run build` 后检查 `dist/assets/` 目录，应存在独立的 `vendor-*.js` 文件，体积占比 ≥ 40% 总 JS 体积，且 hash 在依赖未变时保持稳定。

**Acceptance Scenarios**:

1. **Given** 生产构建产物，**When** 列出 `dist/assets/` 目录，**Then** 存在 `vendor-*.js` 独立文件，体积 ≥ 总 JS 体积的 40%。
2. **Given** 仅修改业务代码（如 `src/pages/Login.tsx`），**When** 重新 `npm run build`，**Then** `vendor-*.js` 文件名 hash 保持不变。
3. **Given** 升级 `react` 版本，**When** 重新 `npm run build`，**Then** `vendor-*.js` 文件名 hash 改变，但业务 chunk hash 保持不变。

---

### Edge Cases

- 当 HTTP 请求未携带 `X-Request-ID` 头时，中间件生成 UUID 后必须同步注入响应头 `X-Request-ID`，否则前端无法关联。
- 当 LLM 调用在后台任务（ARQ worker）中触发而非 HTTP 请求上下文时，request_id 应使用任务 ID 或显式传递的 trace ID，不得为空。
- 当用户删除所有简历分支后访问列表接口，返回 `[]` 且查询计数应为 1（空列表也需执行 1 次查询）。
- 当 `error_questions` 表数据量为 0 时，索引不应被查询计划器跳过（需 `SET enable_seqscan = off` 验证索引可用）。
- 当用户在 `/login` 页面直接刷新（非导航），浏览器不应重复下载已缓存的 vendor chunk。
- 当 Suspense fallback 渲染期间用户再次导航，应取消上一个懒加载 chunk 的下载，避免内存泄漏。
- 当 `/metrics` 端点被高频抓取（如每 5 秒一次 Prometheus scrape）时，指标采集本身不得引入 > 5ms 的请求延迟。
- 当 LLM 配额从耗尽状态恢复（管理员重置）后，`llm_quota_exhausted_total` 为 Counter 类型不重置，但 `llm_quota_available` 为 Gauge 类型应立即反映新配额。

## Requirements *(mandatory)*

### Functional Requirements

#### US1 — LLM 日志 request_id 关联

- **FR-001**: 系统 MUST 在 HTTP 入口中间件读取 `X-Request-ID` 请求头；若不存在则生成 UUID 并注入响应头 `X-Request-ID`。
- **FR-002**: 系统 MUST 将 request_id 存入请求级 ContextVar，供同一请求内的所有日志调用读取。
- **FR-003**: LLM 客户端的 `invoke` / `invoke_stream` / `retry` 日志 MUST 从 ContextVar 读取 request_id 并写入结构化日志字段，不得现场生成新 UUID。
- **FR-004**: 当 LLM 调用发生在非 HTTP 上下文（如 ARQ worker）时，系统 MUST 使用任务 ID 或显式 trace ID 作为 request_id，不得为空字符串。
- **FR-005**: 所有现有的 `llm.invoke` / `llm.retry` / `llm.mock_invoke` 日志事件 MUST 携带 request_id 字段。

#### US2 — Resume 列表 N+1 修复

- **FR-010**: `GET /api/v1/resume-branches` 响应 MUST 为每个分支携带 `version_count` 和 `block_count` 字段。
- **FR-011**: 后端列表查询 MUST 在单次数据库往返内获取所有分支及其聚合计数（通过聚合子查询或 selectinload + 内存聚合）。
- **FR-012**: 前端列表组件 MUST 直接使用响应中的 `version_count` / `block_count`，不得再对每个分支单独发起 COUNT 请求。
- **FR-013**: 系统 MUST 保持响应字段名与既有契约一致（若既有字段为 `versions_count` 则沿用，不擅自改名）。

#### US3 — errors 表复合索引

- **FR-020**: 系统 MUST 为 `error_questions` 表添加覆盖排序字段 `(user_id, status, frequency, created_at)` 的复合索引。
- **FR-021**: 索引 MUST 通过 Alembic 迁移创建，不得依赖手动 DDL。
- **FR-022**: 索引 MUST 是部分索引或包含 `WHERE deleted_at IS NULL` 的过滤条件（仅索引未软删的行）。
- **FR-023**: 系统 MUST 在迁移中包含 `CONCURRENTLY` 选项（若数据库支持）以避免长锁表。

#### US4 — 前端路由懒加载

- **FR-030**: `src/App.tsx` MUST 使用 `React.lazy` 懒加载所有非首屏页面组件（登录页除外，首屏直接 eager）。
- **FR-031**: 懒加载组件 MUST 包裹在 `<Suspense>` 中，fallback 为骨架屏或 loading spinner。
- **FR-032**: 路由配置 MUST 保持现有路径结构不变，仅改为动态 import 形式。
- **FR-033**: 懒加载 MUST 覆盖 ResumeEditor、InterviewLive、InterviewReport、ErrorBook、Profile、Jobs、Settings 等重组件页。

#### US5 — metrics 覆盖补全

- **FR-040**: 系统 MUST 新增 `llm_quota_exhausted_total` Counter 指标，按 `user_id` 维度记录配额耗尽事件。
- **FR-041**: 系统 MUST 新增 `llm_quota_available` Gauge 指标，按 `user_id` 维度反映当前可用配额。
- **FR-042**: 系统 MUST 新增 `checkpointer_reconnect_total` Counter 指标，记录 checkpointer 重连次数。
- **FR-043**: 系统 MUST 新增 `ws_connections_active` Gauge 指标，反映当前活跃 WebSocket 连接数。
- **FR-044**: 系统 MUST 新增 `arq_jobs_queued` Gauge 指标，反映 ARQ 队列中待处理任务数。
- **FR-045**: 系统 MUST 新增 `arq_jobs_failed_total` Counter 指标，记录 ARQ 任务失败次数。
- **FR-046**: `/metrics` 端点 MUST 暴露至少 15 个不同指标名（既有 5 类 + 新增 6 类）。

#### US6 — Vite manualChunks

- **FR-050**: `vite.config.ts` MUST 配置 `build.rollupOptions.output.manualChunks`，将 `react`、`react-dom`、`react-router-dom`、`@tanstack/react-query` 等第三方依赖分入 `vendor` chunk。
- **FR-051**: manualChunks 配置 MUST 使用函数形式（按模块路径匹配），不得使用对象形式（对象形式在动态 import 时有坑）。
- **FR-052**: 业务代码 MUST 与 vendor 代码分离，业务 chunk 的 hash 在仅改业务代码时变化，vendor chunk hash 保持稳定。

#### 跨切面

- **FR-060**: 本 feature MUST 不改动任何 API 请求/响应契约（除新增 `version_count` / `block_count` 字段外）。
- **FR-061**: 本 feature MUST 不改动任何业务逻辑（仅优化、观测、索引）。
- **FR-062**: 本 feature MUST 保持所有现有 E2E 和单元测试通过（回归零退化）。
- **FR-063**: 本 feature MUST 不引入新的运行时依赖（除非 metrics / observability 必需）。

### Key Entities *(include if feature involves data)*

- **error_questions**: 增加复合索引 `(user_id, status, frequency, created_at) WHERE deleted_at IS NULL`，不改字段。
- **resume_branches**: 响应扩展 `version_count` / `block_count` 虚拟字段（不落库），由查询聚合得出。
- **ai_messages**: 不改表结构，仅日志关联 request_id（ai_messages 表本身已有 request_id 字段，本次确保写入）。

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 任何 HTTP 请求触发的 LLM 调用日志均可通过同一 request_id 在日志系统中检索到对应 HTTP 请求日志（覆盖率 100%）。
- **SC-002**: 用户访问简历列表页（10 分支）首屏 P95 延迟从当前 ≥ 1.5 秒降至 ≤ 300ms。
- **SC-003**: 错题本列表在 500 条数据下 P95 延迟从当前 ≥ 800ms 降至 ≤ 200ms。
- **SC-004**: 访客首次访问登录页首屏 JS 下载体积（gzip）≤ 500KB，Lighthouse Performance 评分 ≥ 90。
- **SC-005**: `/metrics` 端点暴露 ≥ 15 个指标名，覆盖 HTTP / auth / resume / lock / outbox / LLM quota / checkpointer / WS / ARQ 九类。
- **SC-006**: 生产构建产物存在独立 `vendor-*.js` chunk，体积占比 ≥ 40% 总 JS 体积；依赖未变时 vendor chunk hash 稳定。
- **SC-007**: 既有 round-1 + round-2 E2E 测试套件 100% 通过，无回归。

## Assumptions

- 用户使用现代浏览器（Chrome 90+ / Firefox 88+ / Safari 14+），支持原生 ES modules 和动态 import。
- 后端日志通过 structlog 输出 JSON 到 stdout，由外部日志收集器（如 Loki / Elasticsearch）聚合检索。
- Prometheus 抓取间隔默认 15 秒，`/metrics` 端点响应时间 < 50ms。
- 数据库为 PostgreSQL 15+，支持 `CREATE INDEX CONCURRENTLY` 和部分索引。
- 前端构建使用 Vite 5+，支持 `manualChunks` 函数形式配置。
- 本 feature 不引入 OpenTelemetry 分布式追踪（留待 v2.0），仅做 request_id 关联。
- Resume 列表的 `version_count` / `block_count` 字段为响应虚拟字段，不写入数据库 schema。
- errors 表索引迁移在生产环境通过 `CONCURRENTLY` 执行，避免锁表；本地开发可普通 `CREATE INDEX`。
- ARQ 指标通过 `on_startup` / `on_job` / `on_failure` 钩子采集，不依赖 ARQ 内部 API。
- 本 feature 不改动既有 4 个 LangGraph agent 的业务逻辑；checkpointer 重连指标的埋点仅在 `checkpointer.py` 公共层，不侵入各 graph。
