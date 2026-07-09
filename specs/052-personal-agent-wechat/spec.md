# Feature Specification: Personal Agent + WeChat Channel

**Feature Branch**: `052-personal-agent-wechat`

**Created**: 2026-07-07

**Status**: Draft

**Input**: User description: "设计一个Agent，每个用户有一个Agent，该Agent有关于该用户所有信息的权限。接入微信（参考CoPaw接入微信iLink的方式）。"

## Clarifications

### Session 2026-07-07

- Q: iLink API 申请未获批或不可用时如何处理？是否需要微信公众号 fallback？ → A: iLink 完全可用，不做 fallback。重点放在多用户长轮询架构的资源效率和进程隔离上。微信通信凭证需要专门的持久化表，确保应用重启后自动恢复联通。
- Q: QR 码端点如何防止恶意遍历 qrcode token？ → A: 生成 qrcode 时绑定当前登录用户的 user_id，轮询 `/qrcode/status` 时校验 user_id 一致性。未登录请求拒绝。qrcode 5 分钟过期自动失效。
- Q: 离线消息队列的持久化策略？Redis 重启是否会导致消息丢失？ → A: PG 为主存储 + Redis 为热队列。outbound 消息先 INSERT 到 `agent_messages` 表（status=pending），再 push 到 Redis 队列。发送成功后 UPDATE status=sent。Redis 重启后从 PG 中 status=pending 的记录重建队列，消息零丢失。
- Q: 首期并发 Agent 规模目标是多少？是否需要水平扩展？ → A: 首期目标 1000 绑定用户，单机设计上限 10000。连接池按 10000 协程并发设计，不引入分布式。水平扩展作为后续优化。
- Q: 单个用户长轮询崩溃是否会影响连接池中其他用户？ → A: 独立 asyncio.Task + per-user 指数退避重试 + 熔断机制。连续失败 10 次/5min 触发熔断，暂停该用户长轮询，状态标记 degraded，发送站内通知。5 分钟后半开探测。其他用户完全不受影响。

## Background

InterCraft 当前是一个 Web-only 平台。用户必须打开浏览器、登录、手动操作才能管理求职进度或进行模拟面试。在微信作为中国求职者核心沟通工具的背景下，缺少微信触达能力意味着：

- 用户错过面试时间（无主动提醒）
- 用户无法在移动端便捷管理求职状态
- 模拟面试等 AI 能力被局限在桌面端

本规范是"Personal AI Career Agent"三大 REQ 中的**第一个**，确立 Agent 基础设施与微信渠道，为后续的面试智能引擎（REQ-053）和对话式求职管理（REQ-054）提供底座。

### 竞品格局

2026 年 3 月微信发布 iLink/ClawBot API 后，首次出现官方合法的个人微信 Bot 通道。目前市场上**尚无任何产品**将完整 AI 求职 Agent 原生集成到微信中。多面鹅、智面星等竞品提供独立 App/小程序的 AI 面试功能，但不具备：(1) 微信原生对话体验 (2) 跨模块持久用户画像 (3) 自主 Agent 行为（主动提醒、主动调研）。

CoPaw（`D:\Project\CoPaw`）已成功实现 iLink 集成，为本规范提供了经过验证的技术参考架构：HTTP 长轮询、QR 码认证、Bearer Token 会话管理。

### REQ 路线图

```
REQ-052 (本规范): Personal Agent + WeChat Channel
  └── Agent 实体、iLink 微信接入、QR 绑定、消息收发
       |
       ├──> REQ-053: Interview Intelligence Engine
       |     └── 新状态模型、面试时间、定时调度、深度调研、报告生成与推送
       |
       └──> REQ-054: WeChat Conversational Agent
             └── NL 意图解析、工具调用、微信文字模拟面试、对话管理
```

## User Scenarios & Testing *(mandatory)*

### User Story 1 — 扫码绑定微信 (Priority: P1)

用户在 InterCraft Web 端进入 Agent 设置页，看到"绑定微信"入口。点击后系统展示一个二维码，用户使用微信扫码，在微信中确认绑定。绑定成功后，Web 端显示"已绑定"状态及绑定的微信昵称。用户的 InterCraft 账号与其个人微信账号建立一对一绑定关系。

**Why this priority**: 微信绑定是所有微信触达能力的前置条件。没有绑定，Agent 无法向用户发送任何消息，后续 REQ-053/054 全部无法运作。

**Independent Test**: 在 Agent 设置页点击"绑定微信"→ 扫描二维码 → 微信确认 → Web 端显示已绑定状态。解绑后重新绑定同样流程可走通。

**Acceptance Scenarios**:

1. **Given** 用户已登录 InterCraft 且未绑定微信，**When** 进入 Agent 设置页点击「绑定微信」，**Then** 系统返回 iLink 扫描链接（`qrcode_url`）和浏览器可渲染的二维码图片链接（`qrcode_image_url`），页面展示该二维码图片并开始轮询扫码状态。
2. **Given** 二维码已展示，**When** 用户使用微信扫码并在微信中确认，**Then** Web 端 3 秒内收到绑定成功通知，显示微信昵称和头像，二维码区域替换为「已绑定」状态卡片。
3. **Given** 二维码已展示但超过 5 分钟未被扫码，**When** 二维码过期，**Then** 系统提示「二维码已过期，点击刷新」，用户可点击重新获取。
4. **Given** 用户已绑定微信，**When** 点击「解除绑定」，**Then** 弹出确认「解除后 Agent 将无法通过微信联系你」，确认后绑定关系清除，bot_token 失效。
5. **Given** 一个微信账号已绑定用户 A，**When** 用户 B 尝试用同一微信账号扫码绑定，**Then** 系统拒绝并提示「该微信账号已绑定其他用户」。

---

### User Story 2 — Agent 发送消息到微信 (Priority: P1)

系统（Agent）通过已绑定的微信渠道，向用户个人微信发送文本消息。消息以 InterCraft Agent 身份发送，在用户微信中显示为来自该 Agent 的聊天消息。支持长文本自动分段（每段约 500 字符），保留 Markdown 格式在纯文本环境中的可读性。

**Why this priority**: 消息发送是 Agent 主动触达用户的基础能力。面试提醒报告（REQ-053）、状态变更确认（REQ-054）都依赖此能力。

**Independent Test**: 通过后端 CLI 或管理接口触发一条测试消息 → 用户在微信中 5 秒内收到该消息 → 验证文本完整性和格式正确性。

**Acceptance Scenarios**:

1. **Given** 用户已绑定微信且 Agent 在线，**When** 系统调用发送接口向该用户发送一条文本消息，**Then** 用户在微信中 10 秒内收到消息，消息来源显示为 InterCraft Agent。
2. **Given** 系统需要发送一条 2000 字的报告，**When** 调用发送接口，**Then** 微信中收到 4 条分段消息，每段约 500 字，段间有 `(1/4)` `(2/4)` 等序号标识，Markdown 代码块在分段时不被打断。
3. **Given** 用户已绑定微信但 Agent 未在线（iLink 长轮询连接断开），**When** 系统尝试发送消息，**Then** 消息进入发送队列，Agent 重连后自动发送，且消息保留时间戳说明"消息产生于 XX:XX，于 XX:XX 送达"。
4. **Given** 用户 A 和用户 B 各有一条待发送消息，**When** Agent 同时处理，**Then** 两条消息分别发送到对应用户的微信，不会串号。

---

### User Story 3 — 接收用户微信消息 (Priority: P1)

Agent 通过 iLink 长轮询持续监听用户在微信中发送的消息。当用户向 Agent 的微信对话发送文本消息时，系统接收、记录并确认收到。消息在 InterCraft 后端以结构化事件形式入站，携带发送者身份（绑定的 user_id）、消息内容、时间戳。

**Why this priority**: 消息接收是双向通信的另一半。REQ-054 的对话式求职管理完全依赖此能力。即使暂无 NL 处理逻辑，接收能力本身即可用于"确认收到"等基础 ACK。

**Independent Test**: 用户在微信中向 Agent 发送一条消息 → 后端日志和数据库中记录该消息 → 发送者可被正确识别为对应用户。

**Acceptance Scenarios**:

1. **Given** 用户已绑定微信且向 Agent 发送文本消息，**When** Agent 的长轮询收到该消息，**Then** 系统在 30 秒内（长轮询周期）将该消息写入 `agent_messages` 表，字段包含 `user_id`、`content`、`direction=inbound`、`received_at`。
2. **Given** 用户在微信中发送图片消息，**When** Agent 收到，**Then** 系统下载图片并存储，消息记录标记 `message_type=image`，内容字段填入 CDN 下载 URL。若下载失败（CDN 过期），记录错误日志但不丢失消息元数据。
3. **Given** 用户在微信中发送语音消息，**When** Agent 收到，**Then** 系统提取 iLink 提供的 ASR 文本转录（如有），记录为文本消息附带 `source=voice_asr` 标记。若 ASR 不可用，记录为 `message_type=voice` 并附注"语音消息（无文本转录）"。
4. **Given** Agent 长轮询连接断开（网络故障），**When** 连接在 60 秒内恢复，**Then** 断开期间用户发送的消息不丢失，重连后通过 cursor 机制补拉。
5. **Given** 用户未绑定微信或绑定已解除，**When** 微信端向 Agent 发送消息，**Then** Agent 回复友好提示"你尚未绑定 InterCraft 账号，请先在 InterCraft 中完成绑定"，不记录为有效用户消息。

---

### User Story 4 — Agent 在线状态与生命周期 (Priority: P2)

Agent 作为 per-user 的后台进程运行（逻辑层面，非 OS 进程），在用户绑定微信后自动激活，在用户解绑后进入休眠。Agent 的在线状态（在线 / 离线 / 休眠）在管理后台可见，用户可在 Web 端查看 Agent 状态。Agent 异常离线时系统自动尝试重连。

**Why this priority**: Agent 生命周期管理保障服务可靠性。无此能力时，Agent 静默离线会导致消息丢失和用户体验降级，但 P1 的绑定和收发能力可以先跑通。

**Independent Test**: 绑定微信 → Agent 状态变为 Online → 解绑 → Agent 状态变为 Dormant → 在管理后台可看到状态变化时间线。

**Acceptance Scenarios**:

1. **Given** 用户完成微信绑定，**When** 绑定成功，**Then** Agent 自动激活，状态变为 `active`，iLink 长轮询启动。
2. **Given** Agent 处于 `active` 状态，**When** iLink 长轮询连续 3 次失败（约 2 分钟），**Then** Agent 状态变为 `degraded`，触发重连逻辑（指数退避：5s → 10s → 20s → 30s...），系统日志记录告警。
3. **Given** 用户解除微信绑定，**When** 解绑操作完成，**Then** Agent 状态变为 `dormant`，iLink 长轮询停止，bot_token 失效，已入队的未发送消息被标记为 `cancelled` 并通知用户（站内通知）。
4. **Given** Agent 在 `degraded` 状态下重连成功，**When** 长轮询恢复，**Then** Agent 状态恢复为 `active`，重连期间未送达的消息自动补发，系统日志记录恢复事件。
5. **Given** 管理员在管理后台查看 Agent 状态列表，**When** 打开 Agent 监控面板，**Then** 看到每个已绑定用户的 Agent 状态（active/degraded/dormant）、最后心跳时间、绑定微信昵称、累计发送/接收消息数。

---

### User Story 5 — Agent 全量数据访问权限 (Priority: P2)

Agent 以用户身份拥有对该用户在 InterCraft 中所有数据的只读权限——包括求职追踪（jobs）、模拟面试记录（interview_sessions + interview_reports）、能力画像（ability_dimensions + ability_profile）、错题本（error_questions）、简历（resume_branches）、任务（tasks）、活动流（activities）。Agent 的数据访问通过现有 RLS 机制，使用关联用户的 `user_id` 进行数据隔离。

**Why this priority**: 全量数据访问是 Agent "了解用户"的前提。REQ-053 的薄弱点分析需要读能力画像和错题本，REQ-054 的对话管理需要读求职追踪。但 P1 的微信通道本身不依赖此能力。

**Independent Test**: 通过 Agent 上下文调用各模块的读取接口 → 验证返回数据与对应用户直接调用结果一致 → 验证 Agent 无法读取其他用户数据。

**Acceptance Scenarios**:

1. **Given** Agent 以用户 U 的身份运行，**When** Agent 调用 `GET /jobs` 读取求职追踪列表，**Then** 返回结果与用户 U 直接在 Web 端看到的数据一致，且不包含其他用户的 job。
2. **Given** Agent 需要生成用户能力摘要，**When** Agent 读取 `ability_dimensions`（6 维度得分）、`error_questions`（薄弱知识点）、`interview_reports`（最近 5 场面试报告），**Then** 三个数据源均通过 RLS 正确隔离，返回仅限该用户的数据。
3. **Given** Agent 尝试通过修改 `user_id` 参数访问其他用户数据，**When** 后端 RLS 策略执行，**Then** 返回空结果集（0 rows）或 403 拒绝，Agent 日志记录可疑访问尝试。
4. **Given** 用户 U 的新数据写入（如新增一个 job），**When** Agent 在下一次读取时，**Then** 新数据在 5 秒内（缓存 TTL）对 Agent 可见。

---

### User Story 6 — Agent 配置与偏好 (Priority: P3)

用户在 InterCraft Web 端可配置 Agent 的基本偏好：Agent 显示名称（默认"我的求职助手"）、免打扰时间段（如 22:00-08:00 不发送消息）、消息推送频率偏好（实时 / 整点汇总）。配置持久化存储，Agent 行为遵循用户偏好。

**Why this priority**: 用户体验优化。P1/P2 能力跑通后再加入偏好控制是合理的优先级排序。

**Independent Test**: 设置免打扰时间为当前时间 ± 5 分钟 → 触发一条 Agent 消息 → 在免打扰时段内消息被延迟，时段结束后自动发送。

**Acceptance Scenarios**:

1. **Given** 用户打开 Agent 设置页，**When** 修改 Agent 显示名称为"小助手"，**Then** Agent 在微信中发送消息时署名变为「小助手」。
2. **Given** 用户设置了免打扰时间段 22:00-08:00，**When** 系统在 23:00 生成一条面试提醒，**Then** 消息被暂存，在次日 08:00 后自动发送，微信消息中附带原始生成时间说明。
3. **Given** 用户设置了"整点汇总"模式，**When** 一小时内产生 3 条 Agent 消息，**Then** 3 条消息被合并为一条汇总消息在整点发送，而非 3 条独立消息。

---

### Edge Cases

- **同一微信账号绑定多个 InterCraft 账号**：拒绝。一个微信账号只能绑定一个 InterCraft 账号。后绑者收到"该微信已绑定用户 XXX"提示。
- **用户在微信端删除了 Agent 对话**：Agent 不感知。下次发送消息时，微信会创建新的对话会话。不影响绑定关系。但 context_token 可能失效——此时 Agent 使用 `sendmessage` 不带 `context_token`（iLink 允许首次发送不带 context_token）。
- **bot_token 过期**：iLink bot_token 有过期时间（具体由 iLink 服务端决定）。Token 过期后 Agent 状态变为 `degraded`，系统向用户发送站内通知"微信绑定已过期，请重新扫码绑定"。用户重新扫码后获取新 token，无需重新绑定用户关系（WeChat UIN 不变）。
- **长轮询 cursor 丢失**：cursor 是长轮询的断点续传指针。若 Agent 重启导致 cursor 丢失（内存状态），使用空 cursor 重新开始轮询——iLink 服务端可能重放部分消息。Agent 通过 `context_token` 或 `msg_id` 去重（参考 CoPaw 的 `OrderedDict` 去重池）。
- **用户同时使用 Web 端和微信端操作同一 job**：两个通道的写操作通过现有 outbox + 后端状态机保障一致性。Web 端的变更不会实时推送到微信端（v1 不做双向同步通知）。微信端发起的状态变更在 Web 端刷新后可见。
- **微信消息中包含特殊字符 / emoji**：系统按 UTF-8 原样存储。文本分割时不在 emoji 序列中间截断（检查 Unicode 代理对）。
- **iLink API 限流或服务不可用**：Agent 实现指数退避重试（5s/10s/20s/30s/60s...最大间隔 5 分钟），重试超过 30 分钟后状态变为 `degraded`，发送站内通知提醒用户。

## Requirements *(mandatory)*

### Functional Requirements

#### Agent 实体与生命周期
- **FR-001**: System MUST 为每个注册用户自动创建一个 Personal Agent 实体（用户注册时隐式创建，无需用户手动操作）。Agent 以用户身份拥有数据访问权限。
- **FR-002**: System MUST 支持 Agent 的三种核心状态：`active`（微信已绑定且长轮询正常）、`degraded`（微信已绑定但连接异常，正在重试）、`dormant`（微信未绑定）。状态变更记录在 `agent_status_history` 中。
- **FR-003**: System MUST 在 Agent 状态变更时发出结构化日志事件（`agent.status_changed`），包含 `user_id`、`old_status`、`new_status`、`reason`、`timestamp`。

#### 微信 iLink 集成
- **FR-004**: System MUST 实现 iLink HTTP 客户端（参考 CoPaw `ILinkClient`），调用 iLink API（base URL: `https://ilinkai.weixin.qq.com`）完成以下操作：
  - `get_bot_qrcode()` — 获取绑定二维码
  - `get_qrcode_status()` — 轮询扫码状态
  - `getupdates()` — 长轮询接收消息（35s 超时）
  - `sendmessage()` — 发送文本消息
- **FR-005**: System MUST 通过统一的 `ILinkConnectionPool` 管理所有用户的长轮询连接，而非为每个用户启动独立 OS 线程。连接池：(a) 以协程方式并发管理所有活跃绑定用户的 `getupdates()` 长轮询，每个用户跑在独立 `asyncio.Task` 中 (b) 在服务启动时自动从 `wechat_credentials` 表加载所有 `status=active` 的凭证并恢复连接 (c) 在用户绑定时动态添加连接、解绑时动态移除 (d) 确保用户 A 的长轮询收到的消息不会被路由到用户 B 的回调（user_id 级别的严格隔离）(e) 连接池使用 HTTP/2 或连接复用，将数千个长轮询映射到少量 TCP 连接上 (f) 单个用户 Task 崩溃不影响其他用户——外层 try/catch 兜底，per-user 指数退避重试（5s→10s→20s→30s…最大 60s）(g) 连续失败 ≥ 10 次/5 分钟窗口触发熔断——暂停该用户长轮询，状态标记 `degraded`，发送站内通知；5 分钟后自动半开探测，成功则恢复 `active`。
- **FR-006**: System MUST 为每个已绑定的微信账号维护通信凭证，持久化存储于 `wechat_credentials` 表（独立于 `wechat_bindings` 表，解绑不物理删除——仅标记失效）。凭证字段包含：`bot_token`（AES-256-GCM 加密存储）、`cursor`（长轮询断点续传指针，每次 `getupdates` 返回后更新）、`context_token`（最近入站消息的会话 token，用于发送消息时关联会话）。应用重启时，Agent 连接池从 `wechat_credentials` 表读取所有 `status=active` 的凭证，自动恢复长轮询连接，无需用户重新扫码。
- **FR-007**: System MUST 在 iLink API 请求头中携带 `AuthorizationType: ilink_bot_token` 和 `Authorization: Bearer <bot_token>`，每个请求生成随机 `X-WECHAT-UIN` 用于防重放。

#### QR 码绑定流程
- **FR-008**: System MUST 提供 `GET /api/v1/agent/wechat/qrcode` 端点（需登录），生成 qrcode 时绑定当前登录用户的 `user_id`。返回 base64 编码的 PNG 二维码图片和 `qrcode_token`（opaque token，有效 300 秒）。同一用户最多同时持有 1 个未使用的 qrcode——再次请求时使旧 qrcode 失效。
- **FR-009**: System MUST 提供 `GET /api/v1/agent/wechat/qrcode/status?qrcode_token=<token>` 端点（需登录），校验请求者的 `user_id` 与 qrcode 创建者一致，不一致时返回 403。一致时轮询返回当前扫码状态：`waiting`（等待扫码）、`scanned`（已扫码待确认）、`confirmed`（已确认，此时触发绑定操作并返回成功）、`expired`（已过期）。
- **FR-010**: System MUST 在用户微信扫码确认后，自动完成以下绑定操作：(a) 保存 bot_token（加密存储）(b) 关联当前 InterCraft user_id <-> 微信 UIN (c) 将 Agent 状态从 `dormant` 切换为 `active` (d) 启动 iLink 长轮询 (e) 向用户微信发送欢迎消息"绑定成功！我是你的 InterCraft 求职助手…"。
- **FR-011**: System MUST 支持用户主动解除微信绑定（`DELETE /api/v1/agent/wechat/binding`），解绑后：(a) bot_token 标记为失效 (b) Agent 状态切换为 `dormant` (c) 长轮询停止 (d) 未发送消息队列被取消并站内通知用户。

#### 消息发送
- **FR-012**: System MUST 提供消息发送接口，支持系统内部组件（CLI、ARQ Worker、管理后台）向指定用户的微信发送文本消息。接口接受 `user_id`、`content`（Markdown 文本）、`priority`（normal/high）。
- **FR-013**: System MUST 在发送超过 500 字符的消息时自动分段。分段策略：(a) 优先在段落边界（`\n\n`）处分割 (b) 其次在句子边界（`。`、`！`、`？`）处分割 (c) 避免在 Markdown 代码块中间切断 (d) 每段标注序号 `(n/total)`。
- **FR-014**: System MUST 为每个发送任务生成唯一的 `client_id`（UUID），并在 iLink `sendmessage` 请求中携带，用于客户端去重和发送状态追踪。
- **FR-015**: System MUST 采用双存储策略保证消息不丢失：(a) outbound 消息先 INSERT 到 `agent_messages` 表（`direction=outbound, status=pending`）作为持久化主存储 (b) 同时 push 到 Redis 发送队列作为热缓存，供连接池快速出队发送 (c) 发送成功后 UPDATE `agent_messages.status=sent` (d) Agent 离线时消息留在 PG（status=pending），Agent 重连后从 PG 批量加载 pending 消息到 Redis 队列 (e) Redis 重启或清空时，从 PG 中 `status=pending AND created_at > NOW() - INTERVAL '24 hours'` 的记录重建队列 (f) 超过 24 小时的 pending 消息自动标记为 `status=expired`，不再发送。

#### 消息接收
- **FR-016**: System MUST 将接收到的微信消息持久化到 `agent_messages` 表，字段包含：`id`、`user_id`（关联 InterCraft 用户）、`direction`（inbound/outbound）、`content`（文本内容）、`message_type`（text/image/voice/file）、`wechat_msg_id`（微信消息 ID 用于去重）、`context_token`（iLink 会话 token）、`received_at`、`created_at`。
- **FR-017**: System MUST 通过 `context_token`（或 `wechat_msg_id` 作为 fallback）对入站消息去重，去重池保留最近 2000 条（参考 CoPaw `OrderedDict` 模式），防止长轮询 cursor 重置导致消息重复处理。
- **FR-018**: System MUST 支持接收以下微信消息类型：(a) 文本消息——提取 `text_item.text` (b) 图片消息——下载 CDN 图片（AES-128-ECB 解密），存储到本地或对象存储 (c) 语音消息——提取 iLink 提供的 ASR 转录文本。

#### Agent 数据访问
- **FR-019**: System MUST 让 Agent 以关联用户的身份执行所有数据读取操作，通过后端 RLS（`SET app.user_id`）确保数据隔离。Agent 不得拥有任何超出绑定用户权限范围的数据访问能力。
- **FR-020**: System MUST 提供 Agent 数据访问的统一上下文接口 `AgentContext`，封装对以下模块的只读访问：`jobs`、`interview_sessions`、`interview_reports`、`ability_dimensions`、`ability_profile`、`error_questions`、`resume_branches`、`tasks`、`activities`。每个模块的访问方法返回与该用户 `user_id` 绑定的数据。

#### 用户偏好配置
- **FR-021**: System MUST 持久化存储以下 Agent 用户偏好：(a) `display_name`（默认"我的求职助手"，上限 20 字符）(b) `quiet_hours_start` / `quiet_hours_end`（默认 null = 不限）(c) `notification_mode`（`realtime` / `hourly_digest`，默认 `realtime`）。
- **FR-022**: System MUST 在 Agent 发送消息前检查用户偏好：(a) 若当前时间在免打扰时段内，消息延迟到免打扰结束后发送 (b) 若通知模式为 `hourly_digest`，消息进入小时汇总队列，整点统一发送。

#### 可观测性
- **FR-023**: System MUST 为 Agent 和微信通道暴露以下指标：(a) `agent_status`（按用户和状态分组的 Gauge）(b) `wechat_messages_sent_total`（Counter）(c) `wechat_messages_received_total`（Counter）(d) `wechat_poll_latency_ms`（Histogram，长轮询返回延迟）(e) `wechat_send_latency_ms`（Histogram，消息发送延迟）(f) `wechat_connection_errors_total`（Counter，按错误类型分组）。
- **FR-024**: System MUST 为 Agent 发出/收到的每条消息记录结构化日志，包含 `request_id`、`user_id`、`direction`、`message_type`、`content_length`、`wechat_msg_id`、`latency_ms`。

#### CLI 接口（Constitution 原则 II）
- **FR-025**: System MUST 提供 CLI 命令 `python -m app.modules.agent.cli` 支持：(a) `send-test-message <user_id> <text>` — 向指定用户发送测试消息 (b) `agent-status <user_id>` — 查看 Agent 运行状态 (c) `list-bindings` — 列出所有微信绑定关系（管理用）。

### Key Entities *(include if feature involves data)*

- **Agent（Personal Agent）**: 每个用户一个的 AI Agent 实体。关键属性：`user_id`（一对一关联用户）、`status`（active/degraded/dormant）、`wechat_uin`（绑定的微信 UIN，nullable）、`bot_token_encrypted`（加密存储的 iLink bearer token，nullable）、`last_heartbeat_at`、`status_changed_at`、`created_at`、`updated_at`。Agent 本身不存储业务数据——它通过 AgentContext 实时读取关联用户的数据。

- **AgentMessage（微信消息记录）**: 微信通道的消息持久化记录。关键属性：`user_id`、`direction`（inbound/outbound）、`content`、`message_type`（text/image/voice/file）、`wechat_msg_id`（iLink 消息 ID）、`context_token`（iLink 会话 token）、`client_id`（发送端去重 ID，仅 outbound）、`segments_total`（分段总数，仅 outbound 长消息）、`segment_index`（当前段序号）、`received_at`、`created_at`。

- **AgentPreference（Agent 偏好配置）**: 用户对 Agent 行为的偏好设置。关键属性：`user_id`（一对一）、`display_name`、`quiet_hours_start`/`quiet_hours_end`（time 类型，nullable）、`notification_mode`（realtime/hourly_digest）。

- **WeChatBinding（微信绑定关系）**: InterCraft 用户与微信账号的绑定记录。关键属性：`user_id`（唯一约束——一个 InterCraft 账号只能绑一个微信）、`wechat_uin`（唯一约束——一个微信账号只能绑一个 InterCraft 账号）、`bound_at`、`unbound_at`（nullable）、`last_qrcode_login_at`。绑定关系是 1:1 的。绑定的**通信凭证**（bot_token、cursor、context_token）不存于此表——见 `WeChatCredential`。

- **WeChatCredential（微信通信凭证）**: iLink 通道的运行时凭证，独立于绑定关系表以支持凭证轮换和连接恢复。关键属性：`user_id`（FK → users.id）、`bot_token_encrypted`（AES-256-GCM 加密）、`cursor`（长轮询断点续传指针，每次 `getupdates` 返回后更新）、`context_token`（最近入站消息的会话 token）、`status`（active/expired/revoked）、`last_polled_at`、`created_at`、`updated_at`。服务重启时，连接池从此表读取所有 `status=active` 的凭证自动恢复长轮询。解绑时将 status 标记为 `revoked` 但不物理删除（保留审计轨迹）。

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 用户可以在 3 分钟内完成微信扫码绑定全流程（从点击"绑定微信"到 Web 端显示"已绑定"），流程中无需手动输入任何信息。
- **SC-002**: Agent 发送的文本消息在 30 秒内到达用户微信（端到端：从系统发送调用到微信新消息通知），P95 延迟不超过 15 秒。
- **SC-003**: 用户通过微信发送的文本消息在 60 秒内（含最长 35 秒长轮询等待 + 25 秒处理缓冲）被系统接收并持久化。
- **SC-004**: Agent 在 iLink 连接断开后 5 分钟内自动恢复（重连成功率 > 95%），断开期间的用户消息零丢失（通过 cursor 补拉）。
- **SC-005**: 长文本（2000+ 字符）分段发送时，0% 的消息在 Markdown 代码块、emoji 序列或 URL 中间被截断。
- **SC-006**: Agent 发送的 100% 消息正确路由到绑定用户——0 次消息串号事故（用户 A 的消息发送到用户 B）。
- **SC-007**: 同一微信消息（相同 `wechat_msg_id` / `context_token`）不会被重复处理超过 1 次（去重有效性 100%）。
- **SC-008**: Agent 数据访问在所有场景下正确进行用户隔离——Agent 以用户 U 的身份运行时，无法读取任何其他用户的数据（RLS 零泄漏）。
- **SC-009**: 单机支持 1000 个活跃 Agent 同时维持 iLink 长轮询连接，CPU 使用率 ≤ 50%，内存使用 ≤ 1GB。连接池创建/销毁连接时无内存泄漏（连续运行 72 小时内存增长 ≤ 5%）。
- **SC-010**: 管理后台 Agent 监控面板可实时查看所有已绑定用户的 Agent 状态，状态数据延迟不超过 60 秒。
- **SC-011**: Playwright E2E 测试覆盖：US1（扫码绑定完整流程，模拟 iLink API 响应）、US2（消息发送与分段）、US3（消息接收与持久化）、US4（Agent 状态生命周期）。

## Assumptions

- **iLink API 可用性**: iLink API (`https://ilinkai.weixin.qq.com`) 完全可用，已通过 CoPaw 验证。本规范不做微信公众号 fallback——所有微信通信走 iLink 通道。
- **多用户长轮询架构**: 每个绑定用户对应一个 iLink 长轮询连接（HTTP hold 35s）。所有连接由统一的 `ILinkConnectionPool` 管理，而非每用户一个独立 OS 线程/进程。连接池复用 HTTP 连接（HTTP/2 multiplexing），内存开销控制在每用户 < 100KB。服务重启后连接池自动从 `wechat_credentials` 表恢复所有活跃绑定用户的 token 和 cursor，逐一重建长轮询。
- **参考实现**: CoPaw 的 `ILinkClient` + `WeixinChannel` 实现（`D:\Project\CoPaw\src\copaw\app\channels\weixin\`）是本规范微信集成的主要技术参考。iLink 协议细节（消息格式、加密方式、长轮询行为）以 CoPaw 已验证的实现为准。
- **每用户一个 Agent**: Agent 是 1:1 绑定用户的，不存在跨用户共享 Agent 的场景。首期规模：1000 绑定用户，单机设计上限 10000。每个 Agent 的长轮询在连接池中以协程方式管理（非 OS 线程），每连接内存开销 < 100KB，10000 连接约需 1GB 内存 + 少量 CPU。水平扩展作为后续优化（非 v1 需求）。
- **不引入消息中间件**: 当前规模下（预计初期 < 1000 个绑定用户），Redis 队列 + ARQ worker 足够处理消息发送。不引入 RabbitMQ/Kafka 等独立消息中间件。规模扩大后可升级。
- **微信发送仅支持文本**: iLink 目前不支持通过 API 发送图片、文件、语音（仅接收支持）。本规范 v1 只做文本消息发送。媒体发送留待 iLink API 能力更新后扩展。
- **Agent 生命周期受限于用户状态**: 用户账号被禁用/删除时，Agent 自动进入 `dormant`，bot_token 失效，微信绑定解除。该逻辑复用现有账户生命周期系统（Phase 6）。
- **安全性**: bot_token 使用 AES-256-GCM 加密存储于数据库。Agent 数据访问复用现有 PostgreSQL RLS。微信消息内容不在日志中完整记录（仅记录长度和元数据）。
- **国际化**: 所有 Agent 消息和 UI 文案使用简体中文。不引入 i18n 框架。
- **状态模型变更**: 求职追踪的新状态模型（applied/test/interview_1/interview_2/interview_3/failed/passed）和 `interview_time` 字段将在 REQ-053 中实现。本规范保持现有 jobs 模块不变。
