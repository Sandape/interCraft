# Feature Specification: 登录会话稳定性

**Feature Branch**: `050-login-session-stability`

**Created**: 2026-07-07

**Status**: Draft

**Input**: User description: "针对当前应用的登录方式，提出一个合适的迭代方案，现在时不时登录状态就掉了，很不稳定。"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - 会话在单标签页内持续保持（P1）

作为一名活跃用户，我在单个标签页内操作应用时，不应该被意外登出。即使我在某段时间内没有操作（后台挂起），回到应用时仍然处于登录状态。

**Why this priority**: 这是"登录状态掉了"最直接的体验——用户正在使用却被弹回登录页，严重中断工作流。

**Independent Test**: 用户在单个标签页登录后，等待比 access_token TTL 更长的时间（20 分钟），期间有零星的 API 调用；回来时页面仍保持正常可用，不会被重定向到 /login。

**Acceptance Scenarios**:

1. **Given** 用户已登录且页面处于活跃使用状态，**When** 后台发生 silent refresh（access_token 过期后自动刷新），**Then** 用户无感知，页面状态不受影响，不触发任何重定向
2. **Given** 用户已登录且停留在页面内（有操作或无操作），**When** 访问任何受保护页面，**Then** 返回 HTTP 200 而非 401
3. **Given** access_token 已过期但 refresh_token 有效，**When** 应用发起 API 调用，**Then** silent refresh 成功执行，原请求自动重放并返回正确结果

### User Story 2 - 多标签页共存不互相踢出（P1）

作为一名习惯打开多个标签页的用户，我在不同标签页中使用同一个应用时，不应该因为第二个标签页的登录导致第一个标签页掉线。

**Why this priority**: 多标签页是现代浏览器的核心用法。当前设备指纹设计导致同设备多标签页的 session 互相覆盖，是最可能的"频繁掉线"根因。

**Independent Test**: 用户在标签页 A 登录，然后新开标签页 B 并登录（使用相同浏览器，同一设备），标签页 A 和 B 在未来 30 分钟内都能正常使用，不会有任一个被踢出。

**Acceptance Scenarios**:

1. **Given** 用户已在标签页 A 登录，**When** 用户在相同设备的新标签页 B 中再次登录，**Then** 标签页 A 不掉线，两标签页的 session 各自独立
2. **Given** 用户已在标签页 A 和 B 中登录，**When** 用户在标签页 A 操作 30 分钟，**Then** 标签页 B 的 API 调用仍正常（refresh_token 能独立刷新）

### User Story 3 - 设备间 session 有合理上限且优雅降级（P2）

作为一名在多设备上使用应用的用户，当我的活跃 session 超过限制时，最旧的设备会被踢出，但我应当收到明确提示，而不是静默掉线。

**Why this priority**: 5 设备上限在当前阶段合理，但被踢出时的体验需要从"静默掉线"改善为"明确通知"。

**Independent Test**: 用户在 6 台设备上依次登录。第 6 台成功登录，第 1 台在第 1 台的下一次 API 调用或 refresh 时收到明确提示"您的账号已在其他设备登录，当前设备已被登出"。

**Acceptance Scenarios**:

1. **Given** 用户已有 5 个活跃 session，**When** 用户在新设备上登录，**Then** 第 6 个 session 创建成功，最旧的 session 被标记为 evicted
2. **Given** 某个 session 被 evicted，**When** 该设备的 access_token 过期且尝试 refresh，**Then** 服务器返回明确的"session evicted"错误码，前端展示友好提示而非静默跳登录

### User Story 4 - 网络抖动或短时后端不可用不导致掉线（P2）

作为一名网络条件可能不稳定的用户，当后端短暂不可用或网络瞬断时，恢复后我应当仍处于登录状态，而不是被登出。

**Why this priority**: 瞬时的 401（如后端重启、网络闪断）不应触发清除 token 的动作，减少因误判导致的"掉线"。

**Independent Test**: 使用浏览器开发者工具模拟一次 API 请求返回 401 后 2 秒内恢复，访问受保护页面应正常。

**Acceptance Scenarios**:

1. **Given** 用户已登录，**When** 某次 API 调用因网络问题返回 401，**Then** 前端不立即清除 token，而是尝试至少一次 refresh
2. **Given** refresh 失败（因网络问题），**When** 应用发起下一次 API 调用，**Then** 应再次尝试 refresh（而非直接认定为未登录）

### Edge Cases

- **access_token 和 refresh_token 同时过期**：用户离线超过 7 天，回到应用时需要重新登录，这是预期的安全行为
- **refresh_token 被重用检测**：两个 API 同时触发 refresh（竞态条件），其中一个成功、另一个触发"reuse detection"；后端应仅拒绝而非吊销所有 session
- **后端全部重启**：部署期间可能会短时 502/503，恢复后客户端应重试而非清 token
- **多标签页同 device_id 的 refresh 竞争**：两个标签页几乎同时触发 refresh，后一个的旧 session 已被前一个标记删除，是否导致连锁吊销？

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001（多标签页 Session 隔离）**: 后端在创建 session 时，不因相同 device_id 而删除其他活跃 session。在注册和 refresh 时跳过 device_id 去重逻辑，允许同一 device_id 存在多个活跃 session。
- **FR-002（Session 上限提升）**: max_active_sessions 从 5 提升到 10，以适应用户多设备+多标签页的常见使用模式。
- **FR-003（Session 过期自动清理）**: `list_active` 查询需要同时过滤 `deleted_at IS NULL` AND `expires_at > now()`（或 `expires_at IS NULL` 以防宽限期）。确保过期 session 不占用上限配额。
- **FR-004（Session Evicted 明确错误码 + Toast 通知）**: 当 session 因 eviction 而被删除时，refresh 和受保护 API 返回专用的错误码（如 `auth.session_evicted`）；前端检测到后展示 Toast 通知"当前设备已被其他登录踢出"，不自动清除 token 也不跳转，让用户确认后再处理。
- **FR-005（前端 refresh 容错增强）**: `tryRefresh()` 在 refresh 端点返回非 200 时，如果是因为网络错误（fetch 抛异常）或服务器 5xx，不立即清除 token；保留 token 并在下次 API 调用时再次尝试 refresh。仅在收到明确认证错误（401/403 + 特定 code）时才清除。
- **FR-006（前端启动时 /users/me 重试）**: `useCurrentUser` 查询的 `retry` 从 `false` 改为 `retry: 2`（或使用指数退避重试），避免单次 401 立即导致登出。在重试间隔期间，页面保持在"校验中"状态而非重定向到 /login。
- **FR-007（前台心跳保活）**: 在 `useCurrentUser` 的 `staleTime`（当前 60s）和 `refetchInterval` 之上，增加一个隐式保活机制：当页面可见（document.visibilityState === 'visible'）时，若距离上次成功认证超过 access_token TTL 的一半（7.5 分钟），发起一次静默 `/users/me` 调用触发 refresh 链。
- **FR-008（Refresh 竞态保护 - 后端）**: 当 refresh_token 重用检测被触发时，仅拒绝本次 refresh 请求，抛出 `REFRESH_REUSE` 错误，不得吊销所有活跃 session（当前行为是将该用户的所有 session 标记为 deleted）。安全上，这仍能阻止攻击者使用窃取的 refresh token，同时不惩罚合法用户因并发刷新触发误报。
- **FR-009（Session 轮转策略优化）**: 在 session 轮转（rotate_refresh）时，保持原 session_id 不变（更新 refresh_token_hash 和 expires_at 而不是创建新行），消除 session 数量因 refresh 而无限增长的风险。同时解决旧 session 在并发场景下被查找不到的问题。
- **FR-010（Refresh 可观测性）**: 后端对每次 refresh 请求记录：结果（成功/失败）、失败原因（expired / evicted / reuse_detected / invalid）、user_id（脱敏）。暴露 refresh 成功率指标，用于监控和告警。
- **FR-011（Session 事件审计日志）**: 每次 session 创建、eviction、吊销均记录结构化审计日志，包含事件类型、actor、target_session_id、cause，支持事后排查"为什么掉线"。

### Key Entities *(include if feature involves data)*

- **UserSession（后端 auth_sessions 表）**: 代表用户的登录会话，绑定 user_id、device_fingerprint、refresh_token_hash。此迭代移除 `UNIQUE(user_id, device_id)` 约束以支持多标签页共存；修改轮转策略为原地更新（而非软删除+新建）；增加明确的 eviction 原因追踪。
- **SessionEvictionEvent（新增概念）**: 当一个 session 被 eviction 时记录的事件，包含 evicted_session_id、cause（max_devices_exceeded / admin_revoke 等）、evicted_at。前端据此展示友好的"被踢出"原因。

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 用户在单个标签页内连续工作 2 小时（含 pass ive 时段），中途不会因认证原因被重定向到登录页
- **SC-002**: 用户在相同浏览器的 3 个不同标签页中同时登录，30 分钟内无任一个标签页被意外登出
- **SC-003**: 模拟后端瞬时不可用（2 秒 502），恢复后用户的登录状态维持不变，前端不清除 token
- **SC-004**: 当 session 被 evict 时，用户侧看到明确的错误提示（"当前设备已被其他登录踢出"），而不是静默跳转到登录页
- **SC-005**: 并发 refresh 场景（同一瞬间 3 个 API 同时触发 refresh），最多 2 个成功，失败的收到明确错误但不影响其他已登录的 session
- **SC-006**: 用户离线上线交替场景（WiFi 断连 30 秒后恢复），恢复后 5 秒内回到认证状态，无需手动重新登录

## Assumptions

- **sessionStorage 标签页隔离策略保留**：当前设计选择（每个标签页独立存储 token）是有意的安全策略，不在本迭代修改。多标签页体验问题通过后端 FR-001 和 FR-009 解决，而非共享 token 存储。
- **OAuth/SSO 不在本迭代范围**：OAuth 集成已有 placeholder（501 Not Implemented），将在独立特性中规划。
- **用户大多数情况下使用单一浏览器**：本迭代优化主要针对单浏览器多标签页场景。跨浏览器 session 管理是正常行为（各自独立登录）。
- **后端部署重启不频繁**：短时 502 在部署期间发生，FR-005 的保留 token + 下次重试策略已为此 Cover。
- **依赖现有 auth API 路由**：不新增 API 端点（除可能的 eviction 事件查询外），仅修改现有端点的行为。

## Clarifications

### Session 2026-07-07

- **Q: 同一 (user_id, device_id) 多行共存的数据库策略？** → **A**: 移除 `UNIQUE(user_id, device_id)` 约束，允许多行共存；同一设备多标签页通过唯一 `session_id` 区分，不再依赖 device_id 去重
- **Q: Session 上限 10 后，驱逐策略的排序依据？** → **A**: 按 `last_seen_at` 升序，驱逐最久未活跃的 session（保持当前行为）
- **Q: Evicted session 前台通知采用什么交互模式？** → **A**: Toast 通知（"当前设备已被其他登录踢出"），不清除 token，让用户确认后再处理
- **Q: 可观测性具体需要哪些信号？** → **A**: 三个核心：① refresh 成功率/失败原因分布（metrics）；② session 创建/eviction 事件（logs）；③ 多标签页冲突/重用检测触发（audit logs）
- **Q: Refresh 接口是否需要额外限速？** → **A**: 共享现有 auth 限速池（10 次/分钟），不做额外限制
