# Feature Specification: Phase 6 — 全局能力收尾

**Feature Branch**: `005-phase6-global-capabilities`

**Created**: 2026-06-15

**Status**: Draft

**Input**: User description: "Phase 6 — 全局能力收尾。在 Phase 1-5 全部 Agent 子图基础上,补齐产品全局能力:用户生命周期管理(M20)、数据导入导出(M21)、审计可观测完整版(M22)、Settings 全部 tab 迁移、Resources/Help 真实内容、订阅管理。Phase 6 是 P1 开发的最终阶段,交付后产品达到完整可用状态。语音模式 deferred 到后续阶段,前端先注释掉避免误导用户。"

## Clarifications

### Session 2026-06-15

- Q: M20 物理清除的 90 天从哪个时间点算起? → A: 从用户发起注销请求算总共 90 天。`scheduled_purge_at = NOW() + 90d`,无中间 `purged` 等待期。
- Q: 审计日志的访问控制范围? → A: 用户只能看到自己的操作日志;另提供 admin 端点 `GET /api/v1/admin/audit-logs` 返回全量日志(Phase 6 范围)。
- Q: 导出 ZIP 的存储后端? → A: 使用本地文件系统(`/tmp/exports/`),生产环境通过环境变量 `EXPORT_STORAGE_PATH` 配置;不上 S3。
- Q: 邮件发送失败时的降级策略? → A: 邮件发送失败时静默降级 — 前端站内通知 + 日志告警,不阻止业务流程;用户可在 Settings 内查看通知中心。
- Q: 语音面试并发限制? → A: 语音模式从 Phase 6 范围移除(deferred),前端注释掉语音相关入口避免误导用户。`interview_sessions.mode` 字段保留但仅 `text` 模式有效。

## User Scenarios & Testing *(mandatory)*

### User Story 1 — 账号生命周期:注销、冷静期、物理清除 (Priority: P1)

用户在 Settings 的「安全」tab 发起账号注销,经过 7 天冷静期后可确认物理删除。冷静期内可取消注销重新激活。系统在 90 天后自动物理清除已确认注销的账号及关联数据。

**Why this priority**: 账号生命周期是用户数据主权的基础保障,也是 GDPR/合规硬性要求。M04 已有 `status/subscription` 字段但无状态流转逻辑,Phase 6 完整落地。

**Independent Test**: Settings → 安全 → 点击「注销账号」→ 二次确认 → 账号进入 `soft_deleted`,收到邮件 → 7 天内登录 → 看到「您已发起注销,点击取消」→ 取消成功 → 账号恢复正常。

**Acceptance Scenarios**:

1. **Given** 用户点击「注销账号」, **When** 二次确认并提交, **Then** `User.status` 变更为 `soft_deleted`, `scheduled_purge_at` 设为 90 天后, `cancellation_deadline` 设为 7 天后,系统发送注销确认邮件
2. **Given** 账号处于 `soft_deleted` 状态, **When** 用户登录, **Then** 首页展示横幅「您的账号注销正在处理中,还有 X 天可取消,90 天后将物理清除」,除取消注销外所有写操作被阻止
3. **Given** 用户在 7 天冷静期内点击「取消注销」, **When** 确认, **Then** `User.status` 恢复为 `active`, `scheduled_purge_at` 和 `cancellation_deadline` 清空,系统发送恢复通知邮件
4. **Given** 7 天冷静期结束(`cancellation_deadline` 已过), **When** 用户尝试取消注销, **Then** 返回「冷静期已过,无法取消」
5. **Given** `scheduled_purge_at` 已到, **When** ARQ cron `purge_expired_accounts` 巡检, **Then** `User.status` 变更为 `purged`,关联数据开始物理删除
6. **Given** 账号已 `purged`, **When** 任何人尝试登录该账号, **Then** 返回「账号不存在」
7. **Given** 账号已 `purged`, **When** M20 `physical_cleanup` cron 运行, **Then** 物理删除 `purged` 超过 7 天的所有用户数据(预留缓冲期),按 `user_id` 分批(每批 100 条)

---

### User Story 2 — 数据导入导出:用户数据可携带 (Priority: P2)

用户在 Settings 的「导出」tab 发起全量数据导出,系统异步打包用户简历、面试记录、错题本、能力画像等数据为 ZIP 文件,通过邮件或站内信发送下载链接。同时支持从 JSON/Markdown 格式导入简历数据。

**Why this priority**: 数据可携带性是用户信任的基础,也是差异化竞争点。导出功能让用户感到数据「属于自己」,降低转换成本。

**Independent Test**: Settings → 导出 → 点击「导出我的数据」→ 等待 1-5 分钟 → 收到邮件含下载链接 → 下载 ZIP → 内含 JSON + Markdown 格式的简历/面试/错题数据。

**Acceptance Scenarios**:

1. **Given** 用户在 Settings「导出」tab 点击「导出我的数据」, **When** 确认, **Then** ARQ 任务 `export_user_data(user_id)` 入队,前端显示「正在准备导出,预计 1-5 分钟」
2. **Given** 导出任务执行, **When** 读取用户数据(简历分支及版本、面试记录及报告、错题本、能力维度、活动流、设置), **Then** 打包为 ZIP(`/tmp/exports/{user_id}_{timestamp}.zip`),内含 JSON 数据文件 + Markdown 格式简历
3. **Given** ZIP 打包完成, **When** 上传至临时存储(72 小时过期), **Then** 系统发送邮件+站内通知含下载链接,前端状态更新为「导出完成,点击下载」
4. **Given** 用户在「导入」页面上传 JSON/Markdown 简历文件, **When** 提交, **Then** 系统解析文件,创建新的简历分支,提示「导入完成,请检查简历内容」

---

### User Story 3 — 审计可观测完整版:全量审计 & LangSmith (Priority: P2)

系统启用完整的审计日志记录(audit_logs 表),覆盖所有写操作及 Agent 子图关键事件。同时提供可选的 LangSmith 链路追踪,帮助开发者在调试阶段可视化 LangGraph 执行流程。

**Why this priority**: 审计是安全运营的基础,Phase 1 已有结构化日志但无持久化审计表。LangSmith 为 Agent 子图调试提供可视化手段,Phase 4 明确 deferred 到 Phase 6 法务评审。

**Independent Test**: 创建简历分支 → 后台 `audit_logs` 表出现对应记录 → 接口返回 200 → (可选)配置 LangSmith API key → 执行一次面试 → LangSmith 项目中出现对应 trace。

**Acceptance Scenarios**:

1. **Given** 用户执行任意写操作(创建/更新/删除简历、启动面试、提交回答等), **When** 操作完成, **Then** 系统写入 `audit_logs` 表,包含 actor_id / action / resource_type / resource_id / old_values / new_values / ip_address / user_agent
2. **Given** Agent 子图执行关键节点(interrupt / score / diagnose / suggest), **When** 节点完成, **Then** 写入审计日志,记录节点输入/输出摘要(token 用量、耗时、结果)
3. **Given** 管理员(或用户自己)查看操作历史, **When** 请求 `GET /api/v1/audit-logs`, **Then** 返回按时间倒序的审计记录,支持按资源类型/操作类型/时间范围筛选
4. **Given** 开发者在 `backend/.env` 配置 `LANGCHAIN_API_KEY` + `LANGCHAIN_PROJECT`, **When** 执行任意 LangGraph 子图, **Then** LangSmith 项目中出现完整的 trace,含节点执行时间、输入/输出、LLM 调用明细
5. **Given** 未配置 LangSmith, **When** Agent 子图执行, **Then** 系统正常通过结构化日志记录,不依赖 LangSmith

---

### User Story 4 — Settings 全部 tab 迁移 (Priority: P2)

Settings 页面除已迁移的「资料」tab 外,其余 tab(设备、订阅、安全、导出)全部从 mock 切换到真实 API,实现完整可用的设置中心。

**Why this priority**: Settings 是用户管理账号的唯一入口。Phase 2 仅迁移了「资料」tab,其余 tab 显示「Phase 6 上线」占位。Phase 6 完成全部迁移,消除 mock。

**Independent Test**: 进入 Settings → 逐个访问设备/订阅/安全/导出 tab → 每个 tab 展示真实数据(或合理空态) → 可执行对应操作(如修改密码、查看登录设备)。

**Acceptance Scenarios**:

1. **Given** 用户进入 Settings「设备」tab, **When** 页面加载, **Then** 展示当前登录的设备列表(设备名称、浏览器、IP、最后活跃时间),支持「下线其他设备」操作
2. **Given** 用户进入 Settings「订阅」tab, **When** 页面加载, **Then** 展示当前订阅方案(free/pro/enterprise)、月度 token 用量(已用/总量)、重置日期,支持「升级方案」CTA(跳转定价页)
3. **Given** 用户进入 Settings「安全」tab, **When** 页面加载, **Then** 展示修改密码表单、最近登录活动列表(时间/IP/设备)、「注销账号」入口(参见 User Story 2)
4. **Given** 用户进入 Settings「导出」tab, **When** 页面加载, **Then** 展示「导出我的数据」按钮及上次导出时间(如有),支持发起新导出(参见 User Story 3)

---

### User Story 5 — Resources & Help 真实内容 (Priority: P3)

Resources 和 Help 页面从占位 mock 替换为真实内容,Resources 展示面试准备资源(文章/视频/模板),Help 展示 FAQ、使用指南和联系支持。

**Why this priority**: 非关键路径页面,但真实内容有助于用户自助解决常见问题,减轻支持负担。

**Independent Test**: 访问 Resources 页 → 看到分类资源列表(文章/视频/模板) → 点击可查看详情 → 访问 Help 页 → 看到 FAQ + 搜索框 → 关键词搜索返回相关结果。

**Acceptance Scenarios**:

1. **Given** 用户进入 Resources 页, **When** 页面加载, **Then** 展示分类资源(面试技巧 / 简历指南 / 技术准备),每条含标题/摘要/阅读时长/标签,支持按标签筛选
2. **Given** 用户点击某资源, **When** 跳转详情, **Then** 展示完整内容(Markdown 渲染),含相关资源推荐
3. **Given** 用户进入 Help 页, **When** 页面加载, **Then** 展示 FAQ 分类(账号 / 面试 / 简历 / 订阅 / 技术),可展开查看答案
4. **Given** 用户在 Help 页搜索框输入关键词, **When** 提交, **Then** 返回匹配的 FAQ 和资源文章,支持模糊搜索

---

### Edge Cases

| # | 场景 | 预期行为 |
|---|---|---|
| E1 | 注销冷静期(7 天)过后用户还想取消 | 返回「冷静期已过,无法取消」 |
| E2 | 同一用户在不同设备同时发起注销和取消注销 | 最终状态以最后一次操作时间为准 |
| E3 | 数据导出任务超过 5 分钟 | 导出任务后台继续,完成后发通知;前端可查看进度 |
| E4 | 用户导入格式不合法 | 返回具体错误(JSON 字段缺失 / Markdown 结构无法解析) |
| E5 | M20 物理清除时部分数据删除失败 | 记录失败项到 dead_letter,继续下一批,告警人工介入 |
| E6 | 审计日志表数据量过大(> 1000 万行) | 按 `created_at` 月分区,保留 12 个月后自动归档 |
| E7 | LangSmith 配置后但 API key 无效 | 静默降级为结构化日志,日志告警「LangSmith 配置无效」 |
| E8 | 订阅 token 配额在月内用尽 | 前端显示配额用尽提示,阻止新面试启动,现有面试不受影响 |
| E9 | 免费用户升级 Pro 后立即生效 | 订阅变更即时生效,月度配额按剩余天数比例计算 |

## Requirements *(mandatory)*

### Functional Requirements

#### M20 · 用户生命周期管理

- **FR-001**: System MUST 支持 `User.status` 状态流转: `active` → `soft_deleted`(用户发起注销,设置 `scheduled_purge_at = NOW() + 90d`) → 物理清除(by ARQ cron after `scheduled_purge_at`)
- **FR-002**: System MUST 在用户发起注销时设置 `scheduled_purge_at = NOW() + 90 days`, `cancellation_deadline = NOW() + 7 days`,发送注销确认邮件
- **FR-003**: System MUST 提供 `POST /api/v1/account/cancel-deletion` 端点,7 天冷静期内可取消注销,恢复 `active` 状态,清空 `scheduled_purge_at`
- **FR-004**: System MUST 在用户处于 `soft_deleted` 状态时,阻止所有写操作(读操作正常),前端展示恢复引导
- **FR-005**: System MUST 实现 ARQ cron 任务 `purge_expired_accounts`:每日巡检,将 `scheduled_purge_at < NOW() AND status = 'soft_deleted'` 的用户标记为 `purged` 并开始物理清除
- **FR-006**: System MUST 实现 ARQ cron 任务 `physical_cleanup`:每周巡检,物理删除 `purged` 超过 7 天的用户及其关联数据(预留缓冲期),按 `user_id` 分批(每批 100 条)
- **FR-007**: System MUST 提供 `GET /api/v1/account/deletion-status` 端点,返回当前注销状态、剩余冷静期天数及计划物理清除日期

#### M21 · 数据导入导出

- **FR-010**: System MUST 提供 `POST /api/v1/account/export` 端点,将导出任务入队(ARQ),返回任务 ID
- **FR-011**: System MUST 实现 ARQ 任务 `export_user_data`:读取用户全量数据(简历分支及版本/面试记录及报告/错题本/能力维度/活动流/设置),打包为 ZIP,上传至临时存储(过期时间 72 小时)
- **FR-012**: System MUST 在导出完成后通过邮件 + 站内通知发送下载链接,链接有效期 72 小时
- **FR-013**: System MUST 提供 `GET /api/v1/account/export/{task_id}/status` 端点,返回导出进度(pending/processing/completed/failed)和下载 URL(完成后)
- **FR-014**: System MUST 提供 `POST /api/v1/resumes/import` 端点,接收 JSON 或 Markdown 格式文件,解析后创建新简历分支
- **FR-015**: System MUST 支持 JSON 导入格式:与导出格式对称,支持字段映射和校验
- **FR-016**: System MUST 支持 Markdown 导入:按 heading 级别识别简历块结构(heading → block_type),正文为 content

#### M22 · 审计可观测完整版

- **FR-020**: System MUST 在写操作(create/update/delete)时写入 `audit_logs` 表,包含 actor_id / action / resource_type / resource_id / old_values(JSONB) / new_values(JSONB) / ip_address / user_agent / created_at
- **FR-021**: System MUST 在 Agent 子图关键节点(interrupt / score / diagnose / suggest / end)执行时写入审计日志,含节点输入摘要 / 输出摘要 / token 用量 / 耗时
- **FR-022**: System MUST 提供 `GET /api/v1/audit-logs` 端点,返回当前用户的操作日志(RLS 过滤 actor_id = current user),支持 `resource_type` / `action` / `date_from` / `date_to` 筛选,按 `created_at DESC` 排序,支持分页
- **FR-023**: System MUST 提供 `GET /api/v1/admin/audit-logs` 端点,返回全量用户的审计日志(需要 admin 角色),支持 `user_id` / `resource_type` / `action` / `date_from` / `date_to` 筛选
- **FR-025**: System MUST 支持 LangSmith 可选配置:当 `backend/.env` 中存在 `LANGCHAIN_API_KEY` + `LANGCHAIN_PROJECT` 时,自动启用 LangSmith tracing
- **FR-026**: System MUST 在 LangSmith 不可用(API key 无效/网络不可达)时静默降级为结构化日志,不影响业务逻辑
- **FR-027**: System MUST `audit_logs` 表按 `created_at` 月分区,保留 12 个月后自动归档

#### 前端迁移 — Settings & Resources

- **FR-040**: System MUST 将 Settings「设备」tab 从 mock 切换到真实 API:展示登录设备列表,支持「下线其他设备」
- **FR-041**: System MUST 将 Settings「订阅」tab 从 mock 切换到真实 API:展示订阅方案/token 用量/重置日期,含「升级方案」入口
- **FR-042**: System MUST 将 Settings「安全」tab 从 mock 切换到真实 API:修改密码/最近登录活动/注销入口
- **FR-043**: System MUST 将 Settings「导出」tab 从 mock 切换到真实 API:发起导出/查看进度/下载(参见 FR-010~FR-013)
- **FR-044**: System MUST 将 Resources 页从占位替换为真实内容(文章/视频/模板),支持标签筛选和 Markdown 渲染
- **FR-045**: System MUST 将 Help 页从占位替换为真实内容(FAQ/使用指南),支持模糊搜索

#### 订阅管理

- **FR-050**: System MUST 支持 `free` / `pro` / `enterprise` 三级订阅方案,默认 `free`
- **FR-051**: System MUST `free` 方案月度 token 配额为 500K, `pro` 为 5000K, `enterprise` 为 50000K(可定制)
- **FR-052**: System MUST 在 `monthly_token_quota` 用尽时阻止新面试启动,返回 429 + 明确提示「本月配额已用尽」
- **FR-053**: System MUST 实现 ARQ cron `reset_monthly_quota`:每月 1 日 UTC 00:00 批量重置 `monthly_token_used = 0`
- **FR-054**: System MUST 在订阅变更时按剩余天数比例计算当月配额: `new_quota * (days_remaining / days_in_month)`

### Key Entities *(include if feature involves data)*

- **User.status**: Phase 1 已定义 `active` / `soft_deleted` / `purged`。Phase 6 实现完整状态流转与生命周期管理。
- **User.scheduled_purge_at**: 新增字段,记录计划物理清除时间(发起注销后 90 天)。Phase 1 预留,Phase 6 启用。
- **User.cancellation_deadline**: 新增字段,记录冷静期截止时间(发起注销后 7 天)。超过此期限不可取消注销。
- **audit_logs**: Phase 1 预留表结构,Phase 6 启用全量写入。字段: id(UUID), actor_id(UUID), action(TEXT), resource_type(TEXT), resource_id(UUID), old_values(JSONB), new_values(JSONB), ip_address(TEXT), user_agent(TEXT), created_at(TIMESTAMPTZ)。按月分区。
- **export_tasks**: 新增实体,跟踪数据导出任务。字段: id(UUID), user_id(UUID), status(enum: pending/processing/completed/failed), file_path(TEXT), expires_at(TIMESTAMPTZ), created_at(TIMESTAMPTZ)。
- **InterviewSession.mode**: Phase 2 已建字段(`text` / `voice`)。Phase 6 仅使用 `text` 模式,`voice` 模式 deferred。
- **login_devices**: 新增实体或通过已有 session 表派生,记录用户登录设备信息。
- **subscription_plans**: 新增实体或配置驱动,定义 `free` / `pro` / `enterprise` 方案的配额与特性。
- **resources**: 新增实体,存储 Resources 页面的文章/视频/模板内容。含 title/summary/category/tags/content/read_time。
- **help_faq**: 新增实体,存储 Help 页面的 FAQ 内容。含 question/answer/category/order。

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 账号注销全程:发起 → 7 天冷静期 → 90 天后物理清除,状态流转 100% 正确,无遗漏
- **SC-002**: 数据导出任务在 5 分钟内完成 95% 的导出请求(数据量 < 100MB)
- **SC-003**: 审计日志写入延迟 ≤ 1 秒(从操作完成到 audit_logs 记录可见),不影响主业务流程延迟
- **SC-004**: Settings 全部 tab 在 `VITE_USE_MOCK=false` 模式下完整可用,数据显示正确
- **SC-005**: Resources 和 Help 页面首屏加载 ≤ 2 秒,搜索响应 ≤ 1 秒
- **SC-006**: M20 物理清除任务执行时不影响在读用户正常操作(分批处理 + 低优先级)
- **SC-007**: 订阅配额检查在面试启动时 ≤ 50ms 完成,不影响启动延迟

## Assumptions

- 语音模式不在 Phase 6 范围(已 deferred),前端注释掉语音相关入口
- M20 物理清除采用「软删除标记 + 后台异步清理」模式,非同步删除
- M21 导出 ZIP 存储:本地文件系统,路径由 `EXPORT_STORAGE_PATH` 环境变量配置(开发默认 `/tmp/exports/`)
- M22 审计日志分区策略:按月分区,12 个月后自动归档(或删除);不提供审计日志自助删除
- LangSmith 为可选配置,默认不启用;配置方式为 `backend/.env` 环境变量
- 订阅管理仅做基础方案 + 配额控制,不涉及真实支付网关集成(支付走 Stripe/Paddle 等第三方,MVP 用后台手动开通)
- Resources 和 Help 内容初始为运营手动维护的 Markdown 文件,后续可迁移到 CMS
- Settings「设备」tab 数据从已有 session/user_agent 信息派生,不新增端设备注册表
- 「升级方案」CTA 仅跳转定价页或弹窗展示方案对比,不实现支付闭环
- 所有新端点沿用 Phase 1 的 RLS 策略(AuthMiddleware + `SET app.user_id`)
- Phase 6 完成后,产品前端保留的 mock 数据仅用于 VITE_USE_MOCK=true 开发模式
