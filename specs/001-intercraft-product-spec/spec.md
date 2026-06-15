# Feature Specification: InterCraft · 面试工坊

**Feature Branch**: `001-intercraft-product-spec`
**Created**: 2026-06-12
**Status**: Draft
**Input**: 基于已完成的前端 UI-UX 样板(12 个页面、10 个 UI 组件、`src/data/mockData.ts` 静态数据)生成覆盖整个 InterCraft 产品的需求文档,作为 6 阶段分批开发的基线。
**Spec Kit 范围**: 整个 InterCraft 产品(对齐 `docs/modules/01-infrastructure.md` ~ `23-frontend-migration.md` 的 23 个后端模块)
**主要读者**: 全栈工程师(后端 + 前端)、架构师;PM 可读场景与验收章节

---

## 1. 产品定位与用户角色

InterCraft 是面向求职中/转岗中工程师的**结构化面试准备平台**,核心做法是「**简历 → 模拟面试 → 能力画像 → 错题强化 → 简历迭代**」的闭环工作流。

| 角色 | 描述 | 关键诉求 |
|---|---|---|
| **求职工程师**(主要) | 3-8 年经验,在职看机会,自我驱动 | 多公司简历分支管理、AI 模拟面试即时反馈、能力短板可视化 |
| **转岗学习者**(次要) | 跨方向/跨栈,需补强基础 | 错题本 + 通用 Coach 指导,无业务锚点的开放问答 |
| **HR / 面试官**(暂未支持) | — | 明确**不在 MVP 范围**,预留接口 |

---

## Clarifications

### Session 2026-06-13

- Q: `monthly_token_quota` 重置机制选哪个? → A: A — UTC cron 每月 1 日 00:00 批量重置(ARQ 定时任务);简单、跨用户统一,Phase 2 落地 cron 占位,Phase 4 M14 LLM 限流直接消费
- Q: A12 任务自动触发器幂等键方案? → A: A — DB 唯一约束 `(user_id, type, related_entity_id)` + 应用层 `find_or_create`;双保险,outbox 重放安全
- Q: M11 面试历史"纯 CRUD" 在 Phase 2 的范围? → A: A — 最小化(只 list + get,无 CUD);表落地 + 读 API 完整;Phase 4 Agent 启动 session 时补 create/update;前端 InterviewList 留 mock
- Q: M08 错题本 Phase 2 数据源(无 interview,FR-040 不触发)? → A: A — 仅手动创建(FR-042),无 seed/示例数据;新用户空态 + 「新建错题」CTA;Phase 4 FR-040 自动提取再叠加
- Q: Settings 基础部分范围(Phase 2 前端迁移)? → A: A — 仅「资料」tab(read + edit,User.name/title/target_role/years_of_experience);设备/订阅/安全/导出/注销 tab 全部 Phase 6 迁移
- Q: Phase 3 锁粒度 — 简历编辑时锁住整个分支还是单个 block? → A: A — 分支级锁;编辑任意 block 锁住整个分支,其他用户看到完整只读模式;分支级实现简单,简历编辑本质单用户,block 级锁无比例价值
- Q: Phase 3 Outbox 写入范围 — 哪些写操作进入离线 Outbox? → A: B — 仅无锁资源(错题/活动流/个人设置/Jobs/tasks);锁资源(简历分支)走独立的 diff-merge 重连流程(E2/FR-063);避免 outbox 回放与锁状态协调的复杂度
- Q: Phase 3 Outbox 冲突 diff 合并策略(409 时)? → A: B — 字段级 last-write-wins + 人工审核;用户逐字段选择保留本地版或服务端版;无需在 outbox 存储 base 快照,复用 Phase 1 版本 diff UI 模式
- Q: Phase 3 锁自动释放的时间链(心跳 60s / TTL 300s / Tab 关闭 30s)? → A: A — 客户端每 60s 心跳续期;服务端 90s 无心跳(1.5 个间隔)自动释放;TTL 300s 为硬上限(即使心跳活跃也强制重新获取);Tab 关闭的 30s 是 WS 断线检测窗口
- Q: Phase 3 WS 连接模型(锁事件推送)? → A: A — 单用户单 WS 连接;所有资源的锁事件复用到同一连接,客户端按 resource_id 过滤;复用 Phase 1 WS 客户端骨架,锁事件量低无需多通道

---

## 2. User Scenarios & Testing *(mandatory)*

> 故事按优先级 P1 → P3 排序;每条故事**独立可测试、可独立部署、可独立演示**。
> 每条故事对应 1 个或多个后端模块(参见 `docs/modules/`),优先级由「用户价值 × 关键路径位置」决定,而非实现难易。

### User Story 1 — 注册与登录(账号体系) (Priority: P1)

新用户访问产品,完成注册并登录,登录后看到自己的工作台。

**Why this priority**: 任何业务功能(简历、面试、错题)都需要 user_id 隔离(RLS);账号体系是 M04/M05 的「零号卡口」,未完成则所有下游模块无法联通。

**Independent Test**: 在浏览器完成「邮箱注册 → 收不到邮件时的二次校验 → 登录 → 拿到 JWT → 调用 `/api/v1/users/me` 返回 200」端到端;在 5 个浏览器登录同一账号,验证第 6 个登录踢出最早设备。

**Acceptance Scenarios**:
1. **Given** 未注册用户访问 `/dashboard`, **When** 输入合法邮箱 + 强密码 + 提交注册, **Then** 系统创建账号、返回 201,自动登录并跳转到 `/dashboard`
2. **Given** 已登录用户在第 6 个浏览器输入凭据登录, **When** 提交, **Then** 系统踢出最早活跃设备并发送邮件/Toast 提示
3. **Given** access token 过期但 refresh token 有效, **When** 用户访问任意受保护页面, **Then** 客户端静默续签并继续渲染,**用户无感知**
4. **Given** 任何已登录用户用伪造的 `user_id` 请求 `/api/v1/users/{他人_id}/resumes`, **When** 后端校验 RLS, **Then** 返回 403/空集(其他用户数据不可见)

---

### User Story 2 — 简历分支与块管理(Notion 式简历) (Priority: P1)

用户在工作台进入「简历中心」,管理多个针对不同公司/岗位的简历分支,每个分支由 7 类块(heading / summary / experience / project / skill / education)组成,支持拖拽排序、折叠、即时编辑。

**Why this priority**: 简历是产品的「业务起点」,所有下游(模拟面试、错题、岗位匹配)都依赖简历内容。Phase 1 必须有真实可写的简历 CRUD。

**Independent Test**: 创建核心简历 → 创建「应聘 A 公司」分支 → 修改块 → 保存 → 刷新页面仍能看到改动。

**Acceptance Scenarios**:
1. **Given** 用户已登录, **When** 进入「简历中心」并点击「新建分支」, **Then** 系统从核心简历浅拷贝生成新分支(块内容共享,分支状态独立),用户可重命名
2. **Given** 用户在编辑简历块, **When** 修改某块内容后 5 秒内不操作, **Then** 系统自动保存并显示「已保存 · 2 秒前」提示
3. **Given** 用户拖拽块改变顺序, **When** 拖拽完成, **Then** 块顺序持久化,刷新后保持
4. **Given** 用户点击「重置/回滚」, **When** 选择历史版本, **Then** 系统生成新分支指向该版本状态(不破坏现有分支)
5. **Given** 用户在分支编辑器中,A 端进入编辑,B 端同时打开, **When** A 提交修改, **Then** B 端 WS 收到 `lock.acquired` 事件,UI 切换为「只读」并提示「XX 正在编辑」

---

### User Story 3 — 简历版本快照与回滚 (Priority: P1)

用户在编辑过程中可手动/自动保存版本,版本以「完整快照 + diff(自上次完整版本起)」混合方式存储,可对比、还原。

**Why this priority**: 简历迭代频繁,误改后回滚是核心需求;A9(版本字段缺失)已在 ANALYSIS_REPORT 中标出,本 Phase 必须落地。

**Independent Test**: 修改 3 次 → 手动保存版本 v2 → 再改 2 次 → 选 v2 「回滚到此版本」→ 创建新分支指向 v2 状态,可在新分支上继续修改。

**Acceptance Scenarios**:
1. **Given** 用户点击「保存版本」, **When** 输入版本备注(如「投递字节前定稿」), **Then** 系统创建 `is_full_snapshot=true` 的版本,带备注、时间、作者类型(manual/auto/ai)
2. **Given** 用户编辑后离开编辑器超过 10 分钟未操作, **When** 返回编辑器, **Then** 系统自动创建 `diff` 版本(以最近完整版本为基线)
3. **Given** 用户选 v3 并点击「回滚」, **When** 确认, **Then** 系统**不修改当前分支**,而是创建新分支继承 v3 内容
4. **Given** 用户查看版本历史, **When** 选两个版本对比, **Then** UI 高亮显示差异(块级 / 内容级)

---

### User Story 4 — 启动 AI 模拟面试(5 轮对话 + 报告) (Priority: P1)

用户从「模拟面试」入口选择目标岗位,启动一场文字/语音面试,AI 面试官(Interview Agent)按 LangGraph 节点产出问题、接收回答、生成报告。

**Why this priority**: 这是产品的「核心 AI 能力展示」,技术风险最高(LangGraph 编排、WS 流式、双源持久化),但必须 Phase 4 落地以解锁后续 Agent 扩展。

**Independent Test**: 启动面试 → 收到 `node.started(intake)` → 收到流式 `token.delta` → 用户答完 5 题 → 收到报告页(可读可分享)。

**Acceptance Scenarios**:
1. **Given** 用户选择「字节跳动 · 高级前端工程师」, **When** 点击「开始模拟面试」, **Then** 系统创建 `interview_sessions` 记录、初始化 LangGraph thread、推 WS `node.started(intake)`
2. **Given** Interview Agent 正在问第 3 题, **When** 用户回答并提交, **Then** 评分节点在 1.5s 内反馈,继续推下一题
3. **Given** 用户在 5 轮对话中途中断(关闭 Tab), **When** 重新进入「面试历史」, **Then** 看到「进行中」标记,可恢复(若 lock 仍有效)或查看已生成的部分报告
4. **Given** 用户完成 5 轮, **When** 报告节点结束, **Then** 系统同步写 `interview_reports`、异步触发 ability_diagnose 子图,UI 立即显示报告并标注「能力画像更新中…」

---

### User Story 5 — 能力画像与成长轨迹 (Priority: P1)

用户在「个人画像」页看到 6 维度(技术深度/架构能力/工程实践/沟通表达/算法能力/业务理解)雷达图、与目标差距、月度成长曲线、改进建议清单。

**Why this priority**: 能力画像是产品的「价值证明」,用户回访的核心驱动力;数据源是 M09 + M18(异步聚合),技术实现依赖 Phase 4 的 Agent 触发。

**Independent Test**: 完成 1 场面试后等待 10 秒,刷新个人画像页,看到该面试对应维度的分数更新;切换时间范围(1m/3m/6m/1y)看到曲线变化。

**Acceptance Scenarios**:
1. **Given** 用户首次进入个人画像, **When** 未完成任何面试, **Then** 雷达图显示「空状态」+ 引导文案「完成首场模拟面试,启动你的能力追踪」
2. **Given** 用户完成 3 场面试, **When** 等待异步诊断完成(WS `ability.updated`), **Then** 6 维度分数被刷新,UI 显示「+5 本周」动画
3. **Given** 用户点击「改进建议」标签, **When** 选中某维度, **Then** 系统列出 3-5 条具体可执行建议,关联到错题本/学习资源/Coach
4. **Given** 用户切换时间范围为 6 个月, **When** 曲线渲染, **Then** 每月取样点 + 趋势线,跨度数据来自 `ability_dimensions_history`

---

### User Story 6 — 错题本与错题强化 Agent (Priority: P2)

用户在面试/练习中答错的题自动沉淀到「错题本」,可启动 Error Coach Agent 进行 3 轮强化练习,通过后 frequency 减 1。

**Why this priority**: 错题本是闭环关键,但功能边界依赖 M15(面试打分)的数据,故排在 Phase 2。Agent 子图(Phase 5)上才有 AI 强化。

**Independent Test**: 完成 1 场面试 → 报告页有 2 道错题 → 错题本看到记录 → 启动 Error Coach → 答对 3 轮 → frequency 减 1 → 状态变「已掌握」。

**Acceptance Scenarios**:
1. **Given** 面试报告中某题得分 < 6, **When** 报告写入完成, **Then** 系统自动创建 `error_questions` 记录,`frequency=3, status=fresh`
2. **Given** 用户在错题本选中某题, **When** 点击「启动错题强化」, **Then** Error Coach 子图启动,首轮给出题目原文 + 标答要点,等待用户复述思路
3. **Given** 用户连续 3 轮答对(每轮 ≥ 8 分), **When** 第 3 轮结束, **Then** frequency 减 1,`status=mastered`(frequency=0 时)
4. **Given** 用户答错强化题, **When** 评分节点判定, **Then** frequency 回到 3,本轮入 `error_coach` 子图,生成新 thread 留痕

---

### User Story 7 — 简历优化 Agent(人类介入 interrupt) (Priority: P2)

用户对某简历分支点击「AI 优化」,Resume Optimize Agent 分析后生成 patch,推 WS `interrupt` 等待用户在编辑器中 review 决定「应用 / 丢弃 / 部分采纳」。

**Why this priority**: 唯一启用 `interrupt` 的子图,价值显著但交互复杂,放在 Phase 5。

**Independent Test**: 在分支上点击「AI 优化」 → 收到 patch → 编辑器内联高亮改动 → 用户选择「应用」 → 落盘新版本(标记 `trigger=ai`)。

**Acceptance Scenarios**:
1. **Given** 用户在分支编辑器, **When** 点击「AI 优化」, **Then** Resume Optimize 子图启动,首节点读取分支内容 → 调 LLM 生成 patch
2. **Given** Agent 节点产出 patch, **When** 节点结束, **Then** 系统推 WS `interrupt` 事件,前端进入「Review」态,块上内联显示 before/after
3. **Given** 用户选「应用」, **When** 确认, **Then** 节点恢复,patch 落盘,创建新版本(`trigger=ai`,备注「AI 优化:…」)
4. **Given** 用户选「丢弃」, **When** 确认, **Then** 节点恢复但 patch 不落盘,GraphState 标记 `discarded`

---

### User Story 8 — 求职追踪(Jobs) (Priority: P2)

用户在「求职追踪」页管理投递的公司/岗位/状态(投递/笔试/一面/二面/HR/Offer/拒信),可关联到简历分支,统计漏斗。

**Why this priority**: 工具型页面,价值中等,数据模型简单(M10 中的 jobs 部分),排在 Phase 2。

**Independent Test**: 创建一条「字节 · 高级前端 · 已投递」记录 → 关联到「字节 · 高级前端」简历分支 → 状态推进到「一面」→ Dashboard 看到漏斗更新。

**Acceptance Scenarios**:
1. **Given** 用户在 Jobs 页, **When** 点击「新建投递」, **Then** 表单含公司、岗位、JD 链接、关联简历分支(可空),提交后写入 `jobs` 表
2. **Given** 用户推进某条记录状态, **When** 选「一面」, **Then** 记录时间线写入 `activities`,Dashboard 的「求职漏斗」实时更新
3. **Given** 用户标记状态为「submitted」, **When** 提交, **Then** 系统自动创建「准备 X 公司面试」任务(M10 联动)

---

### User Story 9 — 多端同步与离线编辑 (Priority: P2)

用户在断网情况下仍可编辑错题/活动流/个人设置等无锁资源,联网后 outbox 自动回放;简历等锁资源在断网超 60s 时显式告警。

**Why this priority**: 用户体验提升项;依赖 M12(锁)与 M13(Outbox),故排在 Phase 3。

**Independent Test**: 浏览器 A 编辑错题 → 断网 → 继续编辑 3 条 → 联网 → outbox 回放成功 → 后端确认 200。

**Acceptance Scenarios**:
1. **Given** 浏览器断网, **When** 用户编辑错题标签, **Then** UI 显示「离线 · 已暂存 3 条」,本地 IndexedDB 落盘
2. **Given** 网络恢复, **When** outbox 自动重放, **Then** 3 条记录按时间顺序提交,服务端 200 后从 outbox 删除
3. **Given** 用户离线 60s 后尝试编辑锁资源(简历分支), **When** 系统检测心跳超时, **Then** 显式告警「锁可能已被他人抢占」,联网后强制走 diff 合并视图(参见 A3)
4. **Given** 用户在多端同时编辑不同错题, **When** 联网, **Then** 各自提交,无冲突(错题无悲观锁)

---

### User Story 10 — 通用 Coach 对话(无业务锚点) (Priority: P2)

用户在「通用 Coach」中发起开放问答(如「如何准备系统设计面试」「React Server Components 是什么」),Agent 给出处方式回答并可关联错题/资源。

**Why this priority**: 增值功能,数据轻,排在 Phase 5。

**Independent Test**: 进入通用 Coach → 提问「解释一下 React 的 useEffect 依赖数组」→ 收到流式回答 → 点击「保存为学习资源」→ Resources 页看到。

**Acceptance Scenarios**:
1. **Given** 用户在通用 Coach, **When** 提问, **Then** 新建 `general_coach` thread,推 WS 流式 token
2. **Given** Agent 回答中引用了某外部资源, **When** 渲染完成, **Then** 资源卡片可点击,关联到 Resources
3. **Given** 用户对回答点「👍」/「👎」, **When** 提交反馈, **Then** 反馈写入 GraphState(可后续用于 prompt 优化)

---

### User Story 11 — 设置 / 设备 / 安全 / 订阅 (Priority: P2)

用户在「设置」中管理个人资料、设备列表(最多 5 个活跃)、订阅档位、订阅周期重置、通知偏好、数据导出/导入/注销。

**Why this priority**: 工具型页面,涉及 M04/M05/M20/M21,跨多个阶段;UI 已就绪,数据后置。

**Independent Test**: 在设置页踢出指定设备 → 该设备下次访问被强制登出;订阅档位变更后,AI 配额按新档生效。

**Acceptance Scenarios**:
1. **Given** 用户在「设备」标签, **When** 点击「踢出此设备」, **Then** `auth_sessions.trusted_at=NULL`、JWT 失效,目标设备 5 分钟内自动登出
2. **Given** 用户在「订阅」, **When** 从 Pro 降级到 Free, **Then** 下个计费周期生效,`monthly_token_quota` 调整
3. **Given** 用户点击「导出全部数据」, **When** 二次确认身份, **Then** 系统生成 24h 签名 URL,zip 含明文敏感字段(参见 A10)
4. **Given** 用户点击「注销账号」, **When** 二次确认 + 等待 7 天冷静期, **Then** 账号进入 `soft_deleted`,30 天后物理清除(参见 M20)

---

### User Story 12 — 学习资源与帮助中心 (Priority: P3)

Resources 页汇总公开学习资源(文章/视频/课程),按标签分类;Help 页提供产品使用引导与 FAQ。

**Why this priority**: 增值页面,内容可手动维护,排在 Phase 6 收尾。

**Independent Test**: 进入 Resources → 选「系统设计」标签 → 看到 5 个资源卡片 → 点击进入详情;Help 页搜「如何创建简历分支」看到图文步骤。

**Acceptance Scenarios**:
1. **Given** 用户在 Resources, **When** 选标签筛选, **Then** 客户端按 `tag` 过滤(无后端依赖时)或调 `GET /api/v1/resources?tag=…`(有后端时)
2. **Given** 用户在 Help, **When** 搜索关键词, **Then** 返回匹配的 FAQ 列表,无结果时给出兜底「联系支持」

---

### Edge Cases *(mandatory)*

| # | 场景 | 预期行为 |
|---|---|---|
| E1 | AI 流式响应中途 WS 断线 | 前端丢弃当前节点 `token.delta`,重连后携带 `last_seen_checkpoint_id`,服务端从下一节点重放(参见 A4) |
| E2 | 离线编辑锁资源超过 60s | UI 显式告警「锁可能已失效」,联网后强制走 diff 合并而非覆盖(参见 A3) |
| E3 | 5 设备限制 | 第 6 个登录踢出最早活跃设备,目标设备 WS 收到 `account.lifecycle_changed` 事件 |
| E4 | 简历分支「submitted」后修改 | 允许编辑(可能「撤回后修改」),但生成新版本(`trigger=manual`),原 submitted 状态保留 |
| E5 | ability_diagnose 异步任务失败 | 报告页立即可用,画像页显示「更新失败,5 分钟后重试」,ARQ 重试 3 次后人工介入 |
| E6 | 用户主动降级订阅但当月已超 Free 配额 | 当月允许继续使用(不阻断),下个计费周期严格按新档 |
| E7 | 简历版本回滚时源版本已被删除 | 回滚失败提示「原版本已失效」,引导创建新版本 |
| E8 | LangGraph 节点在 LLM 限流时失败 | 节点捕获 `QuotaExceededError`,推 WS `error`,前端引导订阅升级 |
| E9 | Outbox 回放时服务端返回 409 冲突 | 前端展示字段级 diff 合并视图,逐字段标记「本地版」vs「服务端版」,用户逐字段选择保留哪版(字段级 last-write-wins);不支持全量三路合并 |
| E10 | 用户在多端同时启动面试 | 面试会话无锁(每次启动新 thread),但同端多 Tab 锁定「进行中」防误开 |

---

## 3. Requirements *(mandatory)*

### 3.1 Functional Requirements

#### 账号与权限(对应 M04/M05)
- **FR-001**: System MUST 支持邮箱 + 密码注册,密码强度规则可在 `config/auth.yaml` 配置(默认 8 位 + 数字 + 字母)
- **FR-002**: System MUST 颁发 access token(15 分钟有效) + refresh token(7 天有效),refresh 静默续签
- **FR-003**: System MUST 限制单账号同时 5 个活跃设备,超限踢出最早设备
- **FR-004**: System MUST 对所有业务表启用 RLS,任何 user 不可访问他人数据
- **FR-005**: System MUST 记录设备指纹(UA + 屏幕 + 时区),支持「信任设备」标记(免 MFA)
- **FR-006**: System MUST 通过 ARQ cron 任务在每月 1 日 00:00 UTC 批量重置 `users.monthly_token_used = 0` 并刷新 `quota_reset_at = now()`;任务在 M04 启用时落地,Phase 2 实现 cron 占位,Phase 4 M14 LLM 限流直接消费该字段(决策日 2026-06-13)

#### 简历中心(对应 M06/M07)
- **FR-010**: System MUST 支持核心简历 + N 个分支(派生自核心),分支支持浅拷贝 → 块级深拷贝
- **FR-011**: System MUST 支持 7 类块(heading / summary / experience / project / skill / education / custom),块可折叠、拖拽、即时编辑
- **FR-012**: System MUST 实现「手动保存版本」+「自动保存版本(>10 分钟未操作)」双触发
- **FR-013**: System MUST 存储版本以「完整快照 + diff(JSON Patch RFC 6902)」混合(参见 A9)
- **FR-014**: System MUST 支持版本回滚,回滚创建新分支而非破坏原分支

#### 模拟面试(对应 M11/M14/M15)
- **FR-020**: System MUST 支持文字 + 语音两种模式(语音通过浏览器 Web Speech API,文本走 WS)
- **FR-021**: System MUST 在每场面试的 5 轮对话中,每轮评分 0-10,产出 `per_question_score` 数组
- **FR-022**: System MUST 在面试结束同步写 `interview_reports`,异步触发 ability_diagnose 子图
- **FR-023**: System MUST 通过 WS 推送 `node.started` / `token.delta` / `node.completed` / `interrupt` / `error` 事件
- **FR-024**: System MUST 携带 `last_seen_checkpoint_id` 支持断线重连,丢弃断线节点的 partial tokens(参见 A4)
- **FR-025**: System MUST 在节点执行前预扣 token,超 `monthly_token_quota` 抛 `QuotaExceededError`
- **FR-026**: System MUST 在 Phase 2 落地 `interview_sessions` 表与 list/get 读 API(只读,无 create/update/delete),为 Phase 4 Agent 启动 session 的 CUD 留 schema 与路由占位;前端 InterviewList 暂留 mock,Phase 4 迁移(决策日 2026-06-13)

#### 能力画像(对应 M09/M18)
- **FR-030**: System MUST 维护 6 个固定维度(技术深度 / 架构能力 / 工程实践 / 沟通表达 / 算法能力 / 业务理解),每个维度包含 3-5 个子项
- **FR-031**: System MUST 聚合多源(面试报告 / 错题 / Coach)生成维度分数,异步更新不阻塞报告展示
- **FR-032**: System MUST 存储历史快照 `ability_dimensions_history(aggregate=month/day)`,支撑成长曲线
- **FR-033**: System MUST 在画像更新时推 WS `ability.updated` 事件,触发前端缓存失效

#### 错题本(对应 M08/M17)
- **FR-040**: System MUST 自动从面试报告中提取 `score < 6` 的题写入错题本(Phase 4 启用)
- **FR-041**: System MUST 维护错题状态 `fresh / practicing / mastered` + 频次 `frequency (0-3)`
- **FR-042**: System MUST 支持用户手动新增/编辑/归档错题
- **FR-043**: System MUST 在 Error Coach 子图完成 3 轮强化后自动减 frequency
- **FR-044**: System MUST 在 Phase 2 阶段(无 interview 数据源时)错题入库**仅**走用户手动创建;不预置 seed/示例数据,新用户空态展示;Phase 4 启动后 FR-040 自动提取叠加(决策日 2026-06-13)

#### 任务 & 活动流(对应 M10)
- **FR-050**: System MUST 自动创建任务(简历 submitted → 准备 X 公司面试)
- **FR-051**: System MUST 维护统一活动流 `activities`,支持游标分页 + 类型过滤
- **FR-052**: System MUST 支持任务状态 `todo / doing / done / archived`,手动与自动均可
- **FR-053**: System MUST 在 `tasks` 表加 `UNIQUE (user_id, type, related_entity_id)` 约束,任务自动创建走 `find_or_create` 模式;outbox 重放与重试多次触发同一事件时任务不重复(决策日 2026-06-13)

#### 同步与离线(对应 M12/M13)
- **FR-060**: System MUST 对锁资源实现悲观锁 + 心跳续期(60s 间隔,客户端主动发送) + 自动释放(服务端 90s 无心跳即释放,1.5 个间隔容忍网络抖动) + TTL 300s 硬上限(即使心跳活跃也强制重新获取);锁粒度为**分支级**(简历分支任一 block 被编辑时锁住整个分支,其他用户看到完整只读模式)和**错题级**(单条错题强化 session 独立锁);WS 断线 30s 内为 disconnect 检测窗口
- **FR-061**: System MUST 通过单用户单 WS 连接推送 `lock.acquired` / `lock.released` / `lock.lost` 事件(所有资源的锁事件复用到同一连接,客户端按 `resource_id` 过滤),前端 UI 同步只读/编辑状态
- **FR-062**: System MUST 客户端在网络不可用时将**无锁资源**(错题/活动流/个人设置/Jobs/tasks)的写操作入 IndexedDB Outbox,联网后批量回放;锁资源(简历分支)走独立 diff-merge 重连流程(FR-063)
- **FR-063**: System MUST 离线超 60s 编辑锁资源时显式告警,联网后强制走 diff 合并视图(字段级 last-write-wins:逐字段展示本地版 vs 服务端版,用户逐字段选择保留哪版;不采用全量三路合并)

#### 简历优化 Agent(对应 M16)
- **FR-070**: System MUST 启动 Resume Optimize 子图,LLM 生成 JSON Patch
- **FR-071**: System MUST 在产出 patch 后 `interrupt`,等待用户选择「应用 / 丢弃 / 部分采纳」
- **FR-072**: System MUST 应用的 patch 落盘并创建新版本(`trigger=ai`,备注由 LLM 摘要生成)

#### 通用 Coach(对应 M19)
- **FR-080**: System MUST 支持无业务锚点的开放问答,每次启动新建 thread
- **FR-081**: System MUST 允许用户对回答「👍/👎」反馈,反馈入 GraphState 供 prompt 优化
- **FR-082**: System MUST 允许将回答中引用的资源「保存到 Resources」

#### 求职追踪(对应 M10 jobs 部分)
- **FR-090**: System MUST 维护投递记录(公司/岗位/JD/状态/关联简历分支/时间线)
- **FR-091**: System MUST 在状态变更时自动写 `activities` + 推进漏斗统计

#### 全局能力(对应 M20/M21/M22)
- **FR-100**: System MUST 实现软删除(30 天回收站)+ 注销(90 天物理清除)+ 7 天冷静期
- **FR-101**: System MUST 支持全量数据导出(zip,明文敏感字段)+ 24h 一次性签名 URL
- **FR-102**: System MUST 支持跨账号导入,字段映射 + 二次确认
- **FR-103**: System MUST 维护 `audit_logs`,记录敏感字段读写 + 上下文,字段含 `request_id / endpoint / changed_fields / result / duration_ms`(参见 A16)
- **FR-104**: System MUST 每天对账 `ai_messages` ↔ `checkpoints`,不一致时发告警

#### 前端架构(对应 M23)
- **FR-110**: System MUST 实现 Repository 模式 + Zustand 状态 + React Query 缓存三层架构
- **FR-111**: System MUST 通过 `VITE_USE_MOCK` 一键在 mock 与真实 API 间切换
- **FR-112**: System MUST 实现 WS 客户端:自动重连 + 指数退避 + `last_seen_checkpoint_id` 携带
- **FR-113**: System MUST 页面迁移按依赖关系分批(参见 §4 阶段划分),每个页面 PR 独立可回滚
- **FR-114**: System MUST 在 Phase 2 阶段仅迁移 Settings 的「资料」tab(读 + 改 name/title/target_role/years_of_experience);设备/订阅/安全/导出/注销 tab 留 mock,Phase 6(M20/M21)再迁移(决策日 2026-06-13)

#### AI 编排通用(对应 M14)
- **FR-120**: System MUST 基于 LangGraph 编排所有 Agent 子图,每个子图视为一个独立库(Constitution I)
- **FR-121**: System MUST 通过统一 LLM 客户端集中处理限流 / 重试 / 结构化日志(Constitution V)
- **FR-122**: System MUST 集中化处理 token 用量 / prompt 缓存命中率 / 模型失败率指标

### 3.2 Key Entities

> 业务表均含隐含字段:`id (uuid)` + `user_id` + `created_at` + `updated_at` + `deleted_at`(参见 A13)
> 提供 SQLAlchemy Mixin:`TimestampedMixin` / `SoftDeletableMixin` / `TenantScopedMixin`

| 实体 | 关键属性 | 关系 |
|---|---|---|
| **User** | email(unique), password_hash, name, title, years_ofExperience, target_role, subscription(enum), monthly_token_quota, monthly_token_used, quota_reset_at | 1:N 全部业务实体 |
| **AuthSession** | user_id, device_id, refresh_token_hash, expires_at, last_seen_at, device_name, device_fingerprint, last_seen_ip, trusted_at | N:1 User |
| **ResumeBranch** | user_id, name, company, position, status(enum: draft/optimizing/ready/submitted/archived), match_score, parent_id, is_main, is_pinned, last_edited_at | N:1 User, 自引用 parent |
| **ResumeBlock** | branch_id, type(enum), title, content, meta, position, collapsed | N:1 Branch |
| **ResumeVersion** | branch_id, version_no, is_full_snapshot, base_version_id, snapshot_json, diff_patch(JSONB), trigger(enum: manual/auto/ai), author_type, note, created_at | N:1 Branch, 自引用 base_version |
| **InterviewSession** | user_id, branch_id(optional), position, company, mode(text/voice), status(enum), thread_id(text), checkpoint_ns(text), started_at, ended_at, duration_sec | N:1 User, 1:N Report, 1:N Message |
| **InterviewMessage** | session_id, role(interviewer/candidate), content, dimension, score(0-10), feedback_json, sequence_no, occurred_at | N:1 Session |
| **InterviewReport** | session_id, overall_score, per_question_score(JSONB), dimension_scores(JSONB), strengths(JSONB), improvements(JSONB), summary_md, generated_at | 1:1 Session |
| **AiMessage**(原文 ai_messages) | thread_id, checkpoint_ns, role, content, tool_calls, model, prompt_tokens, completion_tokens, cache_hit, occurred_at, checkpoint_id | 由 LangGraph checkpointer 同步 |
| **AbilityDimension** | user_id, dimension_key, sub_key, actual_score, ideal_score, last_updated_at, source(enum: interview/error/coach/manual) | N:1 User, 自引用 sub |
| **AbilityDimensionHistory** | user_id, dimension_key, snapshot_date, actual_score, aggregate(month/day) | N:1 User |
| **ErrorQuestion** | user_id, source_session_id, question_text, answer_text, dimension, score, status(enum), frequency(int 0-3), last_practiced_at | N:1 User, N:1 Session |
| **Task** | user_id, type(enum), title, related_entity_type, related_entity_id, status(enum), due_at, completed_at | N:1 User, 多态关联 |
| **Activity** | user_id, type(enum), actor_type, payload_json, occurred_at, request_id | N:1 User, 游标分页 |
| **Job** | user_id, company, position, jd_url, status(enum: applied/test/oa/hr/offer/rejected), branch_id(optional), last_status_changed_at | N:1 User |
| **Lock** | resource_type, resource_id, user_id, device_id, acquired_at, heartbeat_at, expires_at | 由锁服务自管,可选 RLS |
| **AuditLog** | user_id, request_id, actor_id, action, target_type, target_id, endpoint, changed_fields(JSONB), result(enum: success/failed/forbidden), duration_ms, ip, ua, occurred_at | N:1 User, append-only |
| **AiConversation** | thread_id, checkpoint_ns(unique 组合), user_id, graph_name, created_at, last_active_at | 逻辑引用 LangGraph checkpoints |

---

## 4. Success Criteria *(mandatory)*

> 全部为可测量、技术无关的指标;不涉及具体框架 / 库 / 数据库选型。

### 功能性(每个 Phase 必过)
- **SC-001**: Phase 1 演示可在 5 分钟内完成「注册新用户 → 登录 → 创建 1 个简历分支 → 编辑 3 个块 → 手动保存版本 → 刷新页面验证」
- **SC-002**: Phase 4 演示可在 10 分钟内完成「启动 1 场面试 → 完成 5 轮对话 → 收到报告页 → 个人画像维度分数刷新」
- **SC-006**: 全 6 阶段完成后,产品覆盖 12 个 UI 页面(Login / Dashboard / Resume List / Resume Editor / Interview List / Interview Live / Interview Report / Profile / Jobs / Resources / Settings / Help),每页从 mock 切到真实 API

### 性能
- **SC-010**: 关键 REST API P95 ≤ 500ms(冷启动除外)
- **SC-011**: WS 推送延迟 P95 ≤ 200ms(同区域)
- **SC-012**: LangGraph 单节点执行 P95 ≤ 1.5s
- **SC-013**: Dashboard 首屏 LCP ≤ 2s(在 4G 网络下)

### 可靠性
- **SC-020**: RLS 实测不可越权(2 个测试账号互相访问对方数据全部 403/空集)
- **SC-021**: 关键路径单元测试覆盖率 ≥ 70%,集成测试 ≥ 50%
- **SC-022**: 双源对账日报 0 缺失告警
- **SC-023**: 离线编辑联网后 outbox 100% 成功回放(无丢失)

### 可用性
- **SC-030**: 关键用户路径(注册 → 创简历 → 跑面试)首次成功率 ≥ 90%
- **SC-031**: 用户支持工单(账号 / 锁 / 同步相关)≤ 5% 总量
- **SC-032**: 暗色模式在所有页面与组件下与浅色一致(无对比度 < 4.5:1 的文本)

### 业务
- **SC-040**: 用户完成首场模拟面试的中位时长 ≤ 25 分钟(含思考时间)
- **SC-041**: 完成 1 场面试后 7 日内回访率 ≥ 40%
- **SC-042**: 用户平均创建 ≥ 2 个简历分支(产品核心用法)

---

## 5. 6 阶段分批开发计划(每个阶段独立可演示)

> **设计原则**:
> 1. 每个 Phase 端到端可演示(可上线可回滚)
> 2. 关键路径串行(用户故事 P1),非关键并行(P2/P3)
> 3. 单 Phase 工作量适中(2-3 周,1-2 人)
> 4. 后端就绪一部分,前端就迁移一部分(避免大批量 mock 切换)
> 5. 阻塞性问题(A1-A5,见 `docs/ANALYSIS_REPORT.md`)在进入相关 Phase 前必须修订

### Phase 1 — P0 基线(账号 + 简历 CRUD + 前端基础设施) **2-3 周**

**目标**: 用户可注册 → 登录 → 创建/编辑/查看/删除简历分支 → 保存版本。**首个端到端可演示版本**。

**后端模块**: M01 项目骨架 → M02 数据库 ORM → M03 缓存/队列/加密 → M04 账号认证 → M05 会话设备 RLS → M06 简历分支块 → M07 简历版本

**前端模块**: M23 基础设施(Repository 骨架 / React Query 骨架 / WS 客户端骨架 / 拦截器 / 错误边界 / VITE_USE_MOCK)

**演示场景**:
- `curl /healthz` → 200
- 注册新用户 A,登录拿到 JWT
- 创建核心简历 + 1 个分支「字节 · 高级前端」
- 编辑 3 个块,自动保存 + 手动保存版本
- 刷新页面验证持久化
- 5 设备限制触发,第 6 个登录踢出最早

**关键风险**: A1(三源消息流)、A2(checkpoints RLS,在 Phase 4 之前需冻结方案)、A13(软删除 Mixin 全模块统一)

**依赖修订**:
- A1 修订(删 `interview_messages` 或改 VIEW)在 Phase 4 启动前完成
- A13 修订(显式标注 `deleted_at` 等字段)在 Phase 1 启动前完成

**入口验收**: SC-001 可在 5 分钟内走通

---

### Phase 2 — P1 业务实体上线(错题 / 能力 / 任务 / 面试历史纯 CRUD) **2-3 周**

**目标**: Profile / Jobs / 错题本(无 Agent)的纯 CRUD 部分上线,前端 mock 切换到真实 API。

**后端模块**: M08 错题本(CRUD 部分)→ M09 能力画像(数据模型)→ M10 任务活动流(含 M10 jobs 部分)→ M11 面试历史(纯 CRUD)

**前端模块**: M23 Phase 1.5 迁移:Profile / Jobs / ErrorBook 三个页面 + Settings 基础部分

**演示场景**:
- 调 `/api/v1/error-questions` → 返回列表
- 调 `/api/v1/ability-dimensions` → 6 维度
- 调 `/api/v1/ability-dimensions/history?aggregate=month` → 时序数据
- 调 `/api/v1/tasks` → 任务列表
- 调 `/api/v1/activities?cursor=&limit=20` → 游标分页
- 前端 Profile / Jobs / ErrorBook 三个页面从 mock 切到真实 API

**关键风险**: A12(任务自动触发器位置与幂等)

**依赖修订**: A6(thread_id 派生规则)、A8(月度配额重置)、A12(任务触发)在 Phase 2 设计阶段拍板

**入口验收**: 三个页面在 `VITE_USE_MOCK=false` 下完全可用,所有列表/详情数据来自真实后端

---

### Phase 3 — P1 同步与离线打通 **2-3 周**

**目标**: 多端编辑触发悲观锁,离线编辑 → 联网后自动回放,WS 实时推送锁状态。

**后端模块**: M12 锁 + WS 控制面 → M13 客户端 IndexedDB + Outbox

**前端模块**: M23 Phase 2 迁移:ResumeEditor 接入锁 + Outbox、Dashboard 接入 lock 状态

**演示场景**:
- 浏览器 A 进入 ResumeEditor → 后端发锁 → 浏览器 B 看到「只读」UI
- 浏览器 A 关 Tab 30s → 后端自动释放锁 → B 端 WS 收到 `lock.released`
- 浏览器 A 断网 → 编辑 3 个错题 → 联网 → outbox 回放 → 服务端确认
- 断网 60s 编辑 ResumeEditor → 显式告警 → 联网后走 diff 合并视图

**关键风险**: A3(离线 + 锁语义)

**依赖修订**: A3 必须在 Phase 3 启动前完成 v0.3 修订

**入口验收**: 多端编辑、断网编辑两条核心路径在演示中稳定通过

---

### Phase 4 — P1 Interview Agent 跑通(超核心) **3-4 周**

**目标**: 全流程面试(start → 5 轮对话 → 生成报告),WS 流式 token,双源持久化 + 对账。**产品核心 AI 能力首次完整展示**。

**后端模块**: M14 LangGraph 基础设施 → M15 Interview 子图 → M22 审计可观测对账(初版)

**前端模块**: M23 Phase 3 迁移:InterviewList / InterviewLive / InterviewReport + WS 流式客户端完整版

**演示场景**:
- 启动面试 → 收到 `node.started(intake)` → 后续 `node.started(question_gen)` → 流式 `token.delta`
- 用户回答 → 节点循环 → 5 题后触发 `report` 节点
- 查 `ai_messages` ↔ `checkpoints` 配对一致
- 模拟 WS 断线 → 重连携带 `last_seen_checkpoint_id` → 服务端从下一节点开始
- 报告写 `interview_reports` 同步,异步触发 ability_diagnose,UI 立即看到报告,画像页 5 秒后刷新

**关键风险**: A1(三源消息流)、A2(checkpoints RLS)、A4(流式 token 重放)、A5(子图间数据传递)、A15(报告时序竞争)

**依赖修订**: A1 / A2 / A4 / A5 / A15 在 Phase 4 启动前完成 v0.3 修订

**入口验收**: SC-002 可在 10 分钟内走通,断线重连无重复 token

---

### Phase 5 — P2 Agent 子图扩展开 + Dashboard 聚合 **3-4 周**

**目标**: 简历优化(含 interrupt)/ 错题强化 / 能力诊断(异步)/ 通用辅导 四子图上线,Dashboard 切换为真实 API 聚合数据。

**后端模块**: M16 Resume Optimize → M17 Error Coach → M18 Ability Diagnose(异步)→ M19 General Coach → M22 对账日报完整版

**前端模块**: M23 Phase 4 迁移:Dashboard 聚合(8 维度数据) + Resume Optimize Review UI + Error Coach 对话 UI + General Coach

**演示场景**:
- 简历优化:运行子图 → 节点暂停在 `apply_or_discard` → 前端收到 `interrupt` → 用户确认 → 落盘新版本
- 错题强化:启动子图 → 三次答对结束 → frequency 减 1
- 能力诊断:Phase 4 面试结束后,自动触发 → 几秒后 `ability_dimensions` 更新
- 通用 Coach:无业务锚点的问答 + 👍/👎 反馈
- Dashboard:`VITE_USE_MOCK=false` 下所有指标从真实 API 聚合

**关键风险**: 子图间数据传递(A5)、工具共享时的 schema 冻结

**依赖修订**: A6 修订(thread_id 派生规则)在 Phase 5 启动前确认

**入口验收**: 4 个 Agent 子图均可在演示中跑通,Dashboard 真实数据全亮

---

### Phase 6 — P2 全局能力 + 收尾 + 学习资源/帮助 **2-3 周**

**目标**: 软删除 30 天 / 注销 90 天清除,全量导出/导入,审计 + 双源对账日报,Resources/Help 上线,前端从 mock 完全切到真实 API。

**后端模块**: M20 生命周期 / 注销 / 保留期 → M21 导入导出 → M22 审计可观测对账(完整版,含 LangSmith 可选)

**前端模块**: M23 Phase 5 迁移:Settings(数据导出/导入/注销/设备管理) + Resources + Help + Login(从 mock 切到真实)

**演示场景**:
- 软删除一份简历 → 进回收站 → 30 天后(模拟时间)物理删除
- 一键导出 → 拿到 zip 签名 URL → 24h 后过期
- 跑对账 job → 收到 0 缺失告警(健康)
- 注销账号 → 7 天冷静期 → 90 天物理清除
- 前端 `VITE_USE_MOCK=false` → 所有页面正常工作
- Resources / Help 上线并可访问

**关键风险**: A10(加密字段在导入导出中的处理)、A16(audit_logs 字段粒度)、A17(LangSmith 启用决策)

**依赖修订**: A10 / A16 在 Phase 6 设计阶段拍板,A17 决策项在 Phase 6 启动前确认

**入口验收**: SC-006 全 12 页全部从 mock 切到真实 API,全功能无 mock 残留

---

### 阶段依赖图

```
Phase 1 ──► Phase 2 ──► Phase 3 ──► Phase 4 ──► Phase 5 ──► Phase 6
(M01-M07)  (M08-M11)   (M12-M13)   (M14-M15)   (M16-M19)   (M20-M22)
+ M23 基线  + M23 P1.5  + M23 P2    + M22 初版   + M23 P4    + M23 P5
                                                    + M23 P3    + M23 全切
```

**关键路径串行**: Phase 1 → 2 → 3 → 4 → 5 → 6,任何 Phase 延迟都推迟整体交付

**并行机会**:
- Phase 2 启动后,M20/M21(依赖 M05)可并行设计(不开发)
- Phase 4 启动后,M16/M17/M18/M19 四个 Agent 子图可在 Phase 5 内并行开发

---

## 6. Assumptions

> 记录 spec 中采用的默认选择;后续若与决策冲突,需在 plan.md 中显式覆盖。

### 用户与场景
- **A1**: 目标用户为有 3-8 年经验的工程师,具备基础计算机知识,不需要复杂 onboarding
- **A2**: 用户主要在桌面浏览器使用,移动端响应式为「可用但非主战场」
- **A3**: 求职者在一家公司投递周期平均 2-4 周,使用产品以「周」为单位
- **A4**: 用户平均同时投递 3-5 家公司,简历分支数 ≤ 10

### 技术与基础设施
- **A5**: 后端使用 FastAPI(Python 3.11+) + PostgreSQL 15 + Redis 7(沿用 M01 决策)
- **A6**: AI 编排使用 LangGraph(沿用 M14 决策)
- **A7**: LLM 首选 Anthropic Claude(参考原项目 `langchain-anthropic` 依赖)
- **A8**: 默认不启用 LangSmith(合规待评审,见 A17),所有链路走结构化日志
- **A9**: 鉴权使用 fastapi-users 起步(快速落地),后续可自研 JWT
- **A10**: 队列使用 ARQ(异步原生),非 Celery

### 数据与隐私
- **A11**: 敏感字段(身份证 / 真实姓名 / 薪资 / AI 对话)走 AES-256-GCM 加密,密钥从环境变量读
- **A12**: 用户数据保留期:软删除 30 天回收站,注销后 90 天物理清除
- **A13**: 不与第三方共享数据(HR/猎头场景不在 MVP)
- **A14**: 数据出境合规待评审(A17 同步处理),默认按「不出境」设计

### 范围
- **A15**: 多人协作 / 评论 / 团队空间 **不在 MVP 范围**
- **A16**: HR / 面试官视角 **不在 MVP 范围**(接口预留)
- **A17**: 移动 App **不在 MVP 范围**,仅 Web 响应式
- **A18**: 国际化(i18n) **不在 MVP 范围**,默认中文(zh-CN)
- **A19**: 实时音视频面试 **不在 MVP 范围**,语音通过 Web Speech API
- **A20**: 第三方 OAuth(GitHub/Google 登录)**不在 Phase 1**,预留 M04 扩展点

### 业务流程
- **A21**: 面试「进行中」状态无悲观锁(每次启动新 thread),但同端多 Tab 锁定防误开
- **A22**: Resume Optimize / Error Coach 完成后,业务侧不阻塞用户继续操作,失败可重试
- **A23**: 简历 submitted 后允许编辑(撤回再编辑),但生成新版本(保留原 submitted 状态)
- **A24**: 错误题自动入库门槛:`score < 6`,可在 Settings 中配置

---

## 7. Out of Scope(明确排除)

| # | 项 | 排除原因 | 后续可能性 |
|---|---|---|---|
| OOS-1 | 多人协作 / 团队空间 | 需重新设计权限模型,延后到 v2 | v2.0 评估 |
| OOS-2 | HR / 面试官视角 | 业务模式与求职者完全不同 | v2.0 评估 |
| OOS-3 | 移动 App(原生) | 资源限制,MVP 验证后评估 | v1.5 评估 |
| OOS-4 | 国际化(i18n) | MVP 聚焦中文用户 | v1.5 评估 |
| OOS-5 | 实时音视频面试 | 涉及 WebRTC + 录制 + 合规 | v2.0 评估 |
| OOS-6 | 第三方 SSO 登录 | 增加外部依赖,Phase 1 优先邮箱 | v1.x 增量 |
| OOS-7 | 公开简历托管(雇主可搜索) | 合规与隐私风险高 | v3.0 评估 |
| OOS-8 | 内部职位推荐 / 投递代理 | 商业逻辑复杂 | v2.0 评估 |
| OOS-9 | 简历模板市场 | 内容运营重投入 | v1.5 评估 |
| OOS-10 | 行业题库(非通用算法) | 需持续运营 | v1.x 增量 |

---

## 8. Open Questions(显式留待 plan 阶段解决)

> 这些问题**不阻塞** spec 通过,但**必须**在对应 Phase 的 `plan.md` 中明确决定。

- **Q1**: Ability Dimension 6 个维度的具体定义 / 子项划分,见 M09 §1(参考 `docs/PERSISTENCE_REQUIREMENTS.md`)
- **Q2**: LangSmith 启用决策(参见 A17),需法务介入
- **Q3**: LLM 模型族选择(Claude Opus / Sonnet / Haiku 按场景分层),需 M14 plan 阶段决定
- **Q4**: 资源(Resources)内容运营策略:是自建题库还是聚合外部,见 M19 plan 阶段
- **Q5**: 错题状态机(频率 / 掌握判定)的具体阈值,见 M08 / M17 plan 阶段

---

## 9. References

- **UI 样板**: `src/pages/*.tsx`(12 个页面)、`src/components/ui/`(10 个 UI 组件)、`src/components/layout/`(AppShell/Sidebar/Topbar)、`src/data/mockData.ts`(静态数据)
- **后端需求总览**: `docs/PERSISTENCE_REQUIREMENTS.md`(v0.2, 893 行,需 v0.3 修订)
- **一致性审视**: `docs/ANALYSIS_REPORT.md`(17 项问题,5 项阻塞 / 8 项重要 / 4 项建议)
- **开发路线图**: `docs/DEVELOPMENT_ROADMAP.md`(8 Sprint,本 spec 合并为 6 Phase)
- **23 模块文档**: `docs/modules/01-infrastructure.md` ~ `23-frontend-migration.md`
- **Constitution**: `.specify/memory/constitution.md`(5 大原则:Library-First / CLI / Test-First / Integration / Observability)

---

**Status**: Draft
**Next Step**: 等待用户审阅本 spec,通过后使用 `/speckit.clarify` 处理 Open Questions,或直接进入 `/speckit.plan` 对每个 Phase 生成 plan.md
