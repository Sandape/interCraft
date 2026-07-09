# Feature Specification: Interview Intelligence Engine

**Feature Branch**: `053-interview-intelligence`

**Created**: 2026-07-07

**Status**: Draft

**Input**: User description: "求职追踪每个岗位状态：已投递、笔试中、一面中、二面中、三面中、已失败、已通过。用户将岗位设置为笔试中/一面中/二面中/三面中时需要选择对应的面试时间。在面试时间前5小时，进行深度websearch调研（面试经验+常见考察点+公司/产品调研+用户薄弱点），整理成面试前报告发送给用户微信。"

## Clarifications

### Session 2026-07-09

- Q: FR-009 调研调度器使用 ARQ cron 还是独立 scheduler？ → A: 使用现有 ARQ cron（`backend/app/workers/`），复用已有调度基础设施，不引入新组件。
- Q: Web Search 搜索语言范围（中英双语 or 仅中文）？ → A: 仅中文搜索。外企/英文岗位场景下，由 LLM 在报告汇总时标注"该岗位中文面经信息有限，建议自行搜索英文资料"。
- Q: 报告质量校验（FR-018）失败时用户如何感知？ → A: 自动重试一次完整调研流程（重新搜索 + 重新生成），两次都失败后仅通知管理员，不推送给用户。
- Q: 多用户面试时间集中于同一时段时，调研并发如何控制？ → A: 不做额外限流，依赖 10 分钟扫描窗口自然分散 + ARQ 队列 FIFO 消化。通过 FR-023 指标监控，必要时后续加限流。
- Q: 新用户无能力画像数据（ability_dimensions / error_questions 为空）时，薄弱环节章节如何处理？ → A: 保留章节但标注"你还没有足够的面试数据，完成一次模拟面试后可生成个性化薄弱点分析"，引导用户去完善画像。
- Q: FR-012 公司产品调研搜索 query 中的 `{业务关键词}` 如何获取？ → A: 调研时由 LLM 从 job 的 `position` + `notes` 字段自动提取 2-3 个业务关键词，不增加用户输入负担，不新增数据库字段。

## Background

InterCraft 当前求职追踪模块（`specs/014-job-tracking`）使用 7 状态模型（applied/test/oa/hr/offer/rejected/withdrawn），缺少"面试时间"概念。用户无法记录每一轮的面试时间，系统也无法在面试前主动帮助用户准备。

本规范是"Personal AI Career Agent"三大 REQ 中的**第二个**，聚焦于：

1. **状态模型重构**：将求职状态从抽象的"笔试/OA/HR面/Offer"替换为用户实际认知的"笔试中/一面中/二面中/三面中/已失败/已通过"
2. **面试时间追踪**：在推进到面试轮次状态时，强制用户设定面试时间
3. **面试前智能调研**：在面试前 5 小时，Agent 自动执行深度 Web Search，将面试经验、公司产品调研、用户薄弱点整合为结构化备战报告
4. **报告推送**：通过微信渠道（REQ-052）将报告在面试前送达用户

### 前置依赖

- **REQ-052（Personal Agent + WeChat Channel）**: 微信通道与消息发送能力。本规范的报告推送依赖 REQ-052 的 Agent 消息发送接口。
- **现有能力复用**: Web Search（`backend/app/agents/tools/tavily_search.py`）、能力画像（`ability_dimensions`）、错题本（`error_questions`）、ARQ 调度器（`backend/app/workers/`）。

### REQ 路线图

```
REQ-052: Personal Agent + WeChat Channel ✅ 已建立
  └── Agent 实体、iLink 微信接入、QR 绑定、消息收发

REQ-053 (本规范): Interview Intelligence Engine
  └── 新状态模型、面试时间、定时调度、深度调研、报告生成与推送

REQ-054: WeChat Conversational Agent (待建立)
  └── NL 意图解析、工具调用、微信文字模拟面试、对话管理
```

## User Scenarios & Testing *(mandatory)*

### User Story 1 — 新状态模型下的求职追踪 (Priority: P1)

用户在求职追踪模块中看到的新状态选项为：已投递、笔试中、一面中、二面中、三面中、已失败、已通过。从任一非终态状态，用户可以推进到后续状态，状态流转符合逻辑（不能从"已通过"回退，但允许从"三面中"直接到"已通过"即跳过某些轮次）。

当用户将岗位状态推进到「笔试中」「一面中」「二面中」或「三面中」时，系统**要求**用户选择对应的面试/笔试时间（日期+时间，精确到分钟）。面试时间必须是将来的时间。非面试状态（已投递、已失败、已通过）变更时不显示时间选择器。

**Why this priority**: 状态模型是所有下游能力的数据基础。没有面试时间字段，定时调研调度器（US2）就没有触发条件。这是整个 REQ 的入口数据。

**Independent Test**: 创建一个 applied 状态的 job → 推进到 interview_1 → 强制选择面试时间 → 保存成功 → 状态徽章和时间线正确显示。推进到 failed/passed 时不显示时间选择器。

**Acceptance Scenarios**:

1. **Given** 用户在 `/jobs` 列表且系统中存在旧状态模型的存量数据（如 `status=oa`），**When** 数据迁移执行后，**Then** 旧状态被映射到新模型（`oa` → `interview_1`、`hr` → `interview_2`、`offer` → `passed`、`rejected` → `failed`、`withdrawn` → `failed`），且 `status_history` 中的历史记录同步转换。
2. **Given** 用户打开详情抽屉查看一个 `applied` 状态的 job，**When** 点击「推进状态」，**Then** 下拉选项显示允许的目标（笔试中/一面中/二面中/三面中/已失败/已通过），不含当前状态和非法跳转（如 applied → applied）。
3. **Given** 用户选择目标状态为「一面中」，**When** 状态选择器展开下一栏，**Then** 显示面试时间选择器（日期 + 时间，精确到分钟），标注必填。用户必须选择将来时间才能提交。
4. **Given** 用户选择目标状态为「已失败」或「已通过」，**When** 状态确认弹窗出现，**Then** 不显示面试时间选择器，仅显示可选的备注字段（≤ 500 字符）。
5. **Given** 用户尝试设置一个过去的时间作为面试时间，**When** 提交，**Then** UI 内联校验阻止提交，提示"面试时间必须是将来时间"。
6. **Given** 一个处于 `applied` 状态的 job，**When** 用户直接推进到 `interview_3`（跳过 1 和 2），**Then** 系统允许（状态机不强制顺序经过每一轮），但 `status_history` 中正确记录 `applied → interview_3` 的跳转。
7. **Given** 一个处于 `failed` 或 `passed`（终态）的 job，**When** 用户尝试推进状态，**Then** 「推进状态」按钮置灰不可点击，提示"已终结的岗位无法推进"。

**状态转换矩阵**:

| 当前状态 | 允许推进到 |
|---------|-----------|
| applied（已投递） | test, interview_1, interview_2, interview_3, failed, passed |
| test（笔试中） | interview_1, interview_2, interview_3, failed, passed |
| interview_1（一面中） | interview_2, interview_3, failed, passed |
| interview_2（二面中） | interview_3, failed, passed |
| interview_3（三面中） | failed, passed |
| failed（已失败） | (终态，不可推进) |
| passed（已通过） | (终态，不可推进) |

---

### User Story 2 — 定时调研调度 (Priority: P1)

系统每 10 分钟扫描一次所有用户的 `jobs` 表，找出 `interview_time` 在未来 5 小时 ± 5 分钟窗口内、且尚未生成过报告的岗位。对每个匹配的岗位，系统触发一个"面试前调研"任务。该任务异步执行，通过 Deep Web Search 完成调研，生成报告，并通过微信推送给用户。

同一岗位的同一面试时间只触发一次调研（通过报告生成记录去重）。若用户修改了面试时间，系统取消原时间的调研任务，为新时间重新调度。

**Why this priority**: 这是本规范的核心价值——"主动智能"。没有调度器，Agent 只是被动的消息通道，失去了"在面试前帮你准备"的独特定位。

**Independent Test**: 创建一个 job 并设置 interview_time = now + 5h → 等待调度器扫描 → 验证调研任务被触发 → 验证报告生成 → 验证微信收到报告。

**Acceptance Scenarios**:

1. **Given** 用户有一个岗位，`interview_time = 2026-07-08 14:00`（北京时间），**When** 系统在 2026-07-08 09:00 ± 5 分钟执行扫描，**Then** 该岗位被匹配，系统创建一条 `interview_research_task` 记录（状态=`pending`），入队执行。
2. **Given** 同一个岗位的同一个面试时间已经触发过一次调研，**When** 系统再次扫描到该岗位，**Then** 不会重复触发（通过 `interview_research_task` 表中 `job_id + interview_time` 唯一约束去重）。
3. **Given** 用户将面试时间从 14:00 修改为 16:00，**When** 修改保存后，**Then** 系统取消原 09:00 的调研任务（若尚未执行），为 11:00（16:00 - 5h）重新调度。
4. **Given** 用户删除一个有待调度调研任务的岗位，**When** 删除成功，**Then** 关联的 pending 调研任务被取消（状态=`cancelled`）。
5. **Given** 用户的面试时间在 5 小时内（如 3 小时后），**When** 系统扫描时发现该岗位未生成报告，**Then** 仍然触发调研（补触发机制），但在报告开头追加说明"⚠️ 距离面试仅 3 小时，调研时间有限"。
6. **Given** 系统扫描周期为每 10 分钟一次，**When** 某次扫描因 Redis 锁未释放而跳过，**Then** 下一次扫描（10 分钟后）可以正常执行，不会因为一次跳过而永久错过。

---

### User Story 3 — 深度 Web Search 调研 (Priority: P1)

调研任务启动后，系统执行多路并行的深度 Web Search，覆盖以下维度：

1. **面试经验**：搜索"{公司名} {岗位名} 面试经验"、"{公司名} 面经"，整理该岗位/公司的常见面试流程、典型面试题、候选人评价
2. **公司产品调研**：搜索"{公司名} 核心产品"、"{公司名} {业务方向} 最新动态"，了解该公司在 JD 方向上的有名产品/服务（如投递 Qwen 团队的 AI 应用开发，需检索千问 APP 相关信息）
3. **常见考察点**：搜索"{岗位名} 面试知识点"、"{技术栈关键词} 面试题"，整理该岗位方向的高频考察知识点
4. **用户薄弱点关联**：从用户的 `ability_dimensions`（6 维度中得分最低的 2 个）和 `error_questions`（最近 20 条错题）中提取薄弱环节

搜索结果汇总后，由 LLM 对内容进行去重、提炼、组织，生成结构化调研摘要。

**Why this priority**: 调研是报告质量的决定性因素。没有高质量的信息源，报告沦为空洞的模板。并行搜索 + LLM 提炼是本规范区别于竞品（仅有固定题库）的核心竞争力。

**Independent Test**: 创建一个测试 job（如：公司="阿里巴巴"、岗位="Java 开发工程师"）→ 手动触发调研 → 验证 4 个维度的搜索结果均包含相关内容 → 验证 LLM 提炼后的摘要不包含原始 HTML 残留或无关广告内容。

**Acceptance Scenarios**:

1. **Given** 调研任务启动，job 信息为 `{company: "字节跳动", position: "AI 应用开发工程师"}`，**When** 系统执行面试经验搜索，**Then** 搜索结果包含至少 3 条来自不同来源（如牛客网、知乎、CSDN）的面经内容，每条包含面试流程描述和至少一道具体面试题。
2. **Given** 同一个调研任务，**When** 系统执行公司产品调研，**Then** 搜索结果包含该公司在 AI 应用方向的产品/服务信息（如豆包、Coze 等），且信息时效性在最近 6 个月内。
3. **Given** 同一个调研任务，**When** 系统执行常见考察点搜索，**Then** 搜索结果按技术栈分类（如 Python/RAG/LLM 应用），每类至少列出一个具体考察点。
4. **Given** 用户在该岗位方向上有 2 个低分能力维度（如 `tech_depth=3.5`、`algorithm=4.0`）和 5 条活跃错题，**When** 调研任务读取用户薄弱点，**Then** 薄弱点分析准确反映这 2 个维度和 5 条错题的知识点标签。
5. **Given** 某个搜索维度返回 0 条结果（如非常冷门的公司），**When** LLM 汇总阶段处理，**Then** 该维度在报告中标记为"暂无相关公开信息"，不影响其他维度的正常输出。
6. **Given** 单次搜索的 Web Search API 调用失败（超时/限流），**When** 系统重试 2 次（共 3 次尝试）后仍失败，**Then** 该维度使用降级策略——从已成功的维度中提取可关联信息，并在报告中标注"以下信息基于有限搜索结果生成"。

---

### User Story 4 — 面试前报告生成 (Priority: P1)

LLM 将调研结果整合为一份 2000-3000 字符的结构化面试备战报告。报告结构固定，包含以下章节：

1. **📋 面试概览**：公司名、岗位名、面试时间、面试轮次、倒计时
2. **🏢 公司与产品速览**：公司核心业务简介、与岗位方向相关的有名产品/服务
3. **📝 面经汇总**：互联网上该岗位/公司的典型面试流程、常见面试题（3-8 道，含简要答案方向）
4. **🎯 高频考察点**：该岗位方向的核心知识点（按重要性排列，5-10 个）
5. **⚠️ 你的薄弱环节**：基于用户能力画像和错题本的个性化提醒，每个薄弱点附带一条速成建议
6. **💡 最后建议**：3 条面试前可立即执行的行动建议（如"复习 XX 知识点"、"准备好自我介绍"、"了解公司 YY 产品最新版本"）

报告以 Markdown 格式生成，通过微信发送时转换为适合纯文本阅读的格式（保留章节标题符号，代码/表格做扁平化处理）。

**Why this priority**: 报告是用户直接看到的价值输出。调研做得再好，如果报告组织混乱、重点不突出，用户不会觉得有用。结构化的报告是用户对 Agent 能力的直接感知。

**Independent Test**: 完成一次完整调研 → 生成报告 → 验证报告包含全部 6 个章节 → 验证字符数在 2000-3000 范围内 → 验证薄弱点分析引用了真实的能力维度数据 → 在微信中查看报告格式是否可读。

**Acceptance Scenarios**:

1. **Given** 调研任务完成，4 个维度的搜索结果均可用，**When** LLM 生成报告，**Then** 报告包含全部 6 个章节，总字符数在 2000-3000 之间（中文字符计入 1，英文字母计入 0.5），不包含大段重复内容。
2. **Given** 报告生成完成，**When** 系统检查内容质量，**Then** 面经汇总章节至少包含 3 道具体面试题、公司产品速览章节至少提到 1 个具体产品/服务名称、薄弱环节章节至少包含 2 个具体维度的针对性建议。
3. **Given** 用户有 2 个低分能力维度（tech_depth 和 algorithm）和 5 条错题，**When** 报告生成薄弱环节章节，**Then** 该章节引用了具体维度名称和得分，每条错题的知识点被合并归类（不是简单罗列 5 条）。
4. **Given** 调研结果中某个维度信息较少（如面经仅有 2 条），**When** LLM 生成报告，**Then** 面经汇总章节如实反映信息量，不以编造或过度泛化的内容填充。报告开头标注"⚠️ 该岗位面经信息较少，建议多渠道补充"。
5. **Given** 报告以 Markdown 格式生成（含 `**加粗**`、`- 列表`、`### 标题`），**When** 通过微信通道发送，**Then** Markdown 语法被转换为纯文本可读格式：`**text**` → `【text】`、`### 标题` → `▎标题`、列表保留 `- ` 前缀。转换后总字符数增幅不超过 10%。
6. **Given** 用户过去 7 天内已有至少一场同公司的面试报告，**When** 生成新报告，**Then** 报告末尾追加"📊 历史对比"小节，对比上次面试前的薄弱点与本次的变化（进步/退步/持平），帮助用户看到自己的成长轨迹。

---

### User Story 5 — 微信报告推送 (Priority: P1)

报告生成后，系统通过 REQ-052 的消息发送接口将报告推送到用户微信。报告按章节自动分段（每段约 500 字符），标注 `(1/6)` `(2/6)` 等序号。用户在微信中收到一系列来自 Agent 的消息，构成完整的面试备战报告。

若发送时用户处于免打扰时段（REQ-052 偏好配置），报告延迟到免打扰结束后发送。若微信发送失败，报告内容持久化保存在 `interview_reports` 表中，用户可在 Web 端查看，系统通过站内通知告知用户"面试备战报告已生成，微信发送失败，请在 Web 端查看"。

**Why this priority**: 推送是报告触达用户的最后一公里。如果报告生成了但用户没看到，整个调研流程的价值为零。但技术上这是 REQ-052 发送能力的简单调用，排在报告生成之后。

**Independent Test**: 报告生成完成 → 检查微信是否收到分段消息 → 验证每段内容完整性和顺序 → 模拟发送失败 → 验证站内通知和 Web 端可用性。

**Acceptance Scenarios**:

1. **Given** 一份 2500 字的报告，**When** 系统通过微信通道发送，**Then** 用户在微信中收到约 5 条消息，每条约 500 字，段间序号 `(1/5)` `(2/5)` 等连续正确，内容按报告章节顺序组织。
2. **Given** 用户设置了免打扰时段 22:00-08:00，当前时间为 23:00，**When** 报告生成完成，**Then** 报告暂存发送队列，在次日 08:00 后自动发送。微信中收到的消息附带原始生成时间"报告生成于 07/07 23:00"。
3. **Given** 微信发送过程中第 3 段发送失败（iLink API 返回错误），**When** 系统检测到失败，**Then** 剩余段落暂停发送，系统重试第 3 段（最多 3 次），3 次全部失败后：(a) 完整报告写入 `interview_reports` 表 (b) 创建站内通知"面试备战报告已生成，微信发送失败，点击查看" (c) 用户可在 Web 端 Report 页查看完整报告。
4. **Given** 用户尚未绑定微信（Agent 状态为 dormant），**When** 报告生成完成，**Then** 报告保存到数据库，创建站内通知"面试备战报告已生成（微信未绑定，无法推送），点击查看"，用户可在 Web 端查看。

---

### User Story 6 — Web 端报告查看与历史 (Priority: P2)

用户在 InterCraft Web 端可以查看所有已生成的面试备战报告。在求职追踪的岗位详情面板中，若该岗位有面试时间和对应的报告，显示"查看备战报告"入口。点击进入报告详情页，展示完整的结构化报告（6 个章节），支持浏览器原生阅读体验（Markdown 渲染）。

**Why this priority**: Web 端查看是微信推送的补充渠道。用户在桌面端准备面试时，Web 端的阅读体验更好（更大的屏幕、更丰富的排版）。但核心价值通过微信推送已实现，排在 P1 之后。

**Independent Test**: 生成一份报告 → 在岗位详情面板点击"查看备战报告"→ 跳转报告页 → 验证 6 个章节完整显示 → 验证 Markdown 正确渲染。

**Acceptance Scenarios**:

1. **Given** 岗位已生成过至少一份面试备战报告，**When** 用户打开该岗位的详情抽屉，**Then** 在面试时间信息旁显示「查看备战报告」入口按钮。
2. **Given** 用户点击「查看备战报告」，**When** 跳转到报告详情页，**Then** 页面展示完整报告（Markdown 渲染），包含 6 个章节，排版清晰可读。
3. **Given** 该岗位经历过多轮面试（如一面 + 二面），每轮都生成了报告，**When** 用户查看报告历史，**Then** 按面试时间倒序排列，每份报告标注面试轮次和时间，可分别查看。
4. **Given** 报告中的"历史对比"小节（US4-AC6），**When** 在 Web 端渲染，**Then** 薄弱点变化以简洁的对比表格呈现（维度/上次得分/本次得分/趋势箭头）。

---

### User Story 7 — 存量数据迁移 (Priority: P1)

系统必须将现有所有 `jobs` 表中的存量数据从旧状态模型迁移到新状态模型。迁移在数据库层面执行（Alembic migration），映射规则清晰、可逆（通过事务回滚）。迁移后，前端的状态 Tab、状态徽章、推进菜单全部切换到新状态模型。

**Why this priority**: 不迁移存量数据，新旧状态并存会导致前端显示混乱、状态机校验异常。这是本规范的基础设施变更，必须在功能上线前完成。

**Independent Test**: 在测试数据库上执行迁移 → 验证所有存量 job 状态被正确映射 → 验证 `status_history` JSONB 中的历史记录也被转换 → 验证迁移脚本的 `downgrade()` 可回滚。

**Acceptance Scenarios**:

1. **Given** 生产数据库中有一条 `status=oa` 的 job，**When** 迁移执行，**Then** 该 job 的 `status` 被更新为 `interview_1`，`status_history` 中所有出现 `oa` 的 `from`/`to` 值被替换为 `interview_1`。
2. **Given** 生产数据库中有一条 `status=offer` 的 job，**When** 迁移执行，**Then** 该 job 的 `status` 被更新为 `passed`，`status_history` 中的 `offer` 同步替换。注：原 `offer` 状态代表"拿到 Offer"，映射到 `passed`（已通过）语义最接近。
3. **Given** 原 `rejected` 和 `withdrawn` 状态的 job，**When** 迁移执行，**Then** 统一映射为 `failed`（已失败），`status_history` 中的旧值同步替换为 `failed`，但原始状态文本保留在 history 的 `note` 字段中（如"原状态: rejected"）。
4. **Given** 迁移脚本执行完成后，**When** 执行 `downgrade()` 回滚，**Then** 所有状态值恢复到迁移前，`status_history` 中的值也完整恢复。
5. **Given** 迁移脚本执行完成，**When** 通过 `GET /api/v1/jobs/transitions` 查询状态转换矩阵，**Then** 返回新 7 状态的转换关系（test/interview_1/interview_2/interview_3 替代了 oa/hr），前端无需手动维护状态列表。

**旧→新状态映射表**:

| 旧状态 | 新状态 | 说明 |
|--------|--------|------|
| applied | applied | 一致，无需变更 |
| test | test | 笔试→笔试中，保持一致 |
| oa | interview_1 | OA→一面中 |
| hr | interview_2 | HR面→二面中 |
| offer | passed | Offer→已通过 |
| rejected | failed | 已拒→已失败 |
| withdrawn | failed | 已撤回→已失败 |

---

### Edge Cases

- **面试时间晚于当前时间但早于 5 小时**: 系统在下次扫描时发现并立即触发调研（补触发），报告中追加时间紧迫提示。调研不需要完整 5 小时提前量——有总比没有好。
- **用户对同一个 job 频繁修改面试时间**: 每次修改面试时间时，取消前一个调研任务（如未执行），创建新任务。若前一个任务正在执行中（无法取消），允许两个任务都完成生成报告——用户会收到两份报告，但最新时间的报告在微信中置顶（后发送），且附带说明"面试时间已更新至 XX:XX"。
- **用户在面试时间过后仍处于同一面试状态**: 系统不自动推进状态（Agent 不替用户做决定），但 24 小时后若状态未变，Agent 发送一条微信消息提醒"你的 XX 公司面试（原定于 XX 时间）是否已完成？可以在 InterCraft 中更新状态哦"。
- **Web Search API 月度配额用尽**: 调研任务检测到配额不足时，使用降级策略：(a) 减少搜索维度（仅执行面经和公司产品 2 个维度）(b) 报告中标注"本月调研配额已用尽，以下为精简版报告" (c) 系统发送配额告警给管理员。
- **面试时间跨越多日**: 用户设置面试时间后，系统每天扫描仍会命中这个 job。去重机制通过 `interview_research_task` 的唯一约束防止重复调研。若用户将面试时间推迟到数周后，调研在面试前 5 小时才触发，不会提前数周就开始搜索。
- **多个用户的面试时间集中在同一时间段**: 扫描器发现大量匹配项时，逐个入队（ARQ 任务队列）。不做额外并发限制，依赖 10 分钟扫描窗口自然分散 + ARQ 队列 FIFO 消化。通过 FR-023 指标监控 `interview_research_tasks_total` 的 pending 积压量，若 pending 持续 > 20 则告警，后续版本按需加 `max_concurrency` 限流。
- **离职/已删除用户的 job**: Agent 生命周期管理（REQ-052 FR-002）确保已删除用户的 Agent 进入 `dormant` 状态，其 job 的面试调研任务不再触发。数据迁移时 `deleted_at IS NOT NULL` 的记录仍迁移状态值但跳过调研调度。
- **岗位没有设置面试时间**: 处于 applied 或 failed/passed 状态的岗位没有 interview_time（null），调度器扫描时自动跳过。不生成调研报告。
- **新用户无能力画像数据**: `ability_dimensions` 为空（从未完成模拟面试）时，薄弱环节章节填入引导文案，质量校验 FR-018(d) 跳过。其他 5 个章节正常生成。报告仍为有效报告（FR-018 的 (a)(b)(c) 仍需通过）。
- **外企/英文岗位的中文信息不足**: 仅执行中文搜索。若 Web Search 返回的中文结果数量少或质量低（如 Tavily score < 0.5），由 LLM 在报告"面经汇总"章节开头标注"⚠️ 该岗位中文面经信息有限，建议自行搜索英文资料（如 Glassdoor、LeetCode Discuss）"，不改变报告结构和其他章节。

## Requirements *(mandatory)*

### Functional Requirements

#### 状态模型重构
- **FR-001**: System MUST 将求职追踪状态模型从旧 7 状态（applied/test/oa/hr/offer/rejected/withdrawn）替换为新 7 状态（applied/test/interview_1/interview_2/interview_3/failed/passed），中文标签对应为：已投递/笔试中/一面中/二面中/三面中/已失败/已通过。
- **FR-002**: System MUST 实现新的状态转换矩阵（见 US1 状态转换矩阵表），`interview_1 → interview_2 → interview_3` 是推荐路径，但允许跳过中间轮次（如 `applied → interview_3`）。终态（failed/passed）不可推进。
- **FR-003**: System MUST 在状态推进到 test/interview_1/interview_2/interview_3 时，**强制要求**用户设置 `interview_time`（TIMESTAMPTZ，精确到分钟），interview_time 必须是未来时间。推进到 applied/failed/passed 时不要求 interview_time。
- **FR-004**: System MUST 提供数据库迁移脚本（Alembic），将存量数据的旧状态映射为新状态（详见旧→新状态映射表），同时更新 `status_history` JSONB 数组中的 `from`/`to` 值。迁移脚本必须支持 `downgrade()` 回滚。
- **FR-005**: System MUST 将 `jobs` 表新增 `interview_time` 列（TIMESTAMPTZ，nullable），默认 NULL（存量数据不回溯填充）。索引 `idx_jobs_interview_time` 用于调度器扫描。
- **FR-006**: System MUST 更新 `GET /api/v1/jobs/transitions` 端点返回新的状态集和转换矩阵，前端通过此端点获取可用的状态选项和推进菜单。

#### 面试时间管理
- **FR-007**: System MUST 在 `PatchJobInput` schema 中新增 `interview_time` 字段（可选，ISO 8601 datetime）。单独修改 interview_time 时（不改变状态），取消旧的调研任务并为新时间重新调度。
- **FR-008**: System MUST 在修改 interview_time 时进行校验：(a) 必须是 ISO 8601 格式 (b) 必须是未来时间（允许 5 分钟容差以处理时钟偏差）(c) 必须有对应的面试轮次状态（test/interview_1/interview_2/interview_3），否则拒绝并提示"请先将岗位状态推进到面试轮次"。

#### 调度器
- **FR-009**: System MUST 实现定时扫描任务（ARQ cron，复用现有 `backend/app/workers/` 调度基础设施），每 10 分钟扫描 `jobs` 表，查找满足以下条件的岗位：(a) `status IN ('test', 'interview_1', 'interview_2', 'interview_3')` (b) `interview_time BETWEEN NOW() + INTERVAL '4h 55m' AND NOW() + INTERVAL '5h 5m'` (c) 尚未在 `interview_research_tasks` 中存在 `status != 'cancelled'` 的记录（同 job_id + 同 interview_time）。
- **FR-010**: System MUST 对扫描到的每个岗位创建一个 `interview_research_task` 记录（状态=`pending`），并 enqueue 到 ARQ 执行。`interview_research_tasks` 表通过 `(job_id, interview_time)` 唯一约束保证不重复调度。
- **FR-011**: System MUST 在用户修改或删除 interview_time、修改 job 状态为非面试轮次、或删除 job 时，将对应的 pending 调研任务标记为 `cancelled`。正在执行中的任务（`running`）不强制中断（允许完成），但报告生成后追加备注"面试时间已于 XX:XX 更新"。

#### 深度调研
- **FR-012**: System MUST 执行 4 路并行的中文 Web Search：(1) 面试经验（query="{company} {position} 面试经验 面经"）(2) 公司产品调研（query="{company} {业务关键词} 产品 最新"，其中 `{业务关键词}` 由 LLM 在调研时从 job 的 `position` + `notes` 字段自动提取 2-3 个关键词）(3) 常见考察点（query="{position} 面试知识点 考察点"）(4) 用户薄弱点查询（从 ability_dimensions 和 error_questions 本地读取）。所有搜索使用中文 query，不做英文搜索。每路搜索使用 Tavily Search API（已有集成 `backend/app/agents/tools/tavily_search.py`），最多返回 5 条结果。若公司/岗位为外企且中文信息不足，LLM 在报告汇总时标注"该岗位中文面经信息有限，建议自行搜索英文资料"。
- **FR-013**: System MUST 为每路搜索实现重试策略：最多 3 次尝试，指数退避（2s/4s/8s）。3 次全部失败时该维度标记为 `failed`，不影响其他维度和整体报告生成。
- **FR-014**: System MUST 将原始搜索结果（标题、URL、摘要、发布日期）持久化到 `interview_research_results` 表，按维度分组存储（JSONB），用于：(a) 报告生成质量审计 (b) 用户反馈"信息不准确"时回溯来源 (c) 后续同公司岗位复用搜索结果（24 小时内同公司的搜索结果可复用，减少 API 调用）。

#### 报告生成
- **FR-015**: System MUST 使用 LLM（DeepSeek V4 Pro，通过现有 `llm_client`）将调研结果合成为结构化报告。报告必须包含 6 个章节：📋 面试概览、🏢 公司与产品速览、📝 面经汇总、🎯 高频考察点、⚠️ 你的薄弱环节、💡 最后建议。Prompt 中明确要求输出字符数 2000-3000（中文字符），不得编造未经验证的信息。
- **FR-016**: System MUST 在报告生成后将完整内容（Markdown 格式）写入 `interview_reports` 表（复用现有 `interview_reports` 表，新增 `report_type='pre_interview_research'` 区分来源），关联 `job_id`、`interview_time`、`research_task_id`。
- **FR-017**: System MUST 在生成薄弱环节章节时，从 `ability_dimensions` 取最低 2 个维度的 `actual_score` 和 `improvements` 建议，从 `error_questions` 取最近 20 条 `status=fresh` 的错题知识点，由 LLM 合并归纳为不超过 3 个薄弱主题（而非逐一罗列 20 条）。若 `ability_dimensions` 为空（新用户无面试记录），保留该章节但填入引导文案"你还没有足够的面试数据，完成一次模拟面试后可生成个性化薄弱点分析"，质量校验 FR-018(d) 在此场景下不执行。
- **FR-018**: System MUST 在生成报告后进行内容质量校验：(a) 不为空或仅模板填充 (b) 至少包含 1 个具体公司/产品名称 (c) 至少包含 3 道具体面试题 (d) 薄弱环节章节至少引用 1 个具体能力维度。首次校验失败时，自动重试一次完整调研流程（重新执行 4 路搜索 + LLM 报告生成）。两次都失败后，报告状态标记为 `quality_failed`，通知管理员排查，不推送给用户。

#### 报告推送
- **FR-019**: System MUST 在报告生成并通过质量校验后，通过 REQ-052 的 Agent 消息发送接口（`Agent.send_message(user_id, content, priority='high')`）将报告推送到用户微信。发送前将 Markdown 转换为纯文本可读格式（参考 US4-AC5 的转换规则）。
- **FR-020**: System MUST 在微信发送失败（3 次重试后仍失败）或用户未绑定微信时，将完整报告保存到数据库，并通过现有站内通知系统（`NotificationService`）创建通知"面试备战报告已生成，点击查看"，附带报告查看链接。

#### Web 端报告查看
- **FR-021**: System MUST 在岗位详情面板中，若 `job.interview_time IS NOT NULL` 且存在对应的 `interview_report`（`report_type='pre_interview_research'`），显示「查看备战报告」入口按钮，链接到报告详情页。
- **FR-022**: System MUST 提供 `GET /api/v1/jobs/{id}/research-reports` 端点，返回该岗位所有面试备战报告列表（按 interview_time 倒序）。提供 `GET /api/v1/jobs/{id}/research-reports/{report_id}` 端点返回单份报告完整内容。

#### 可观测性与审计
- **FR-023**: System MUST 为调研调度和报告生成暴露以下指标：(a) `interview_research_tasks_total`（Counter，按状态 pending/running/completed/cancelled/failed）(b) `interview_research_duration_seconds`（Histogram，从任务入队到报告生成完成）(c) `interview_report_generation_tokens`（Counter，LLM token 消耗）(d) `web_search_api_calls_total`（Counter，按维度分组）。
- **FR-024**: System MUST 为每条调研任务记录结构化审计日志：`research_task_id`、`user_id`、`job_id`、`company`、`position`、`interview_time`、`triggered_at`、`completed_at`、`duration_ms`、`search_results_count`（每维度）、`report_length_chars`、`quality_check_passed`、`delivery_status`（sent/failed/delayed/cancelled）。

#### CLI 接口（Constitution 原则 II）
- **FR-025**: System MUST 提供 CLI 命令：(a) `python -m app.modules.jobs.cli migrate-status` — 执行状态模型迁移（dry-run 模式预览变更）(b) `python -m app.modules.agent.cli trigger-research <job_id>` — 手动触发面试调研（调试用）(c) `python -m app.modules.agent.cli research-stats` — 查看调研任务统计。

### Key Entities *(include if feature involves data)*

- **Job（更新）**: 求职追踪记录。本规范修改 `status` 列的有效值（新 7 状态）、新增 `interview_time` 列（TIMESTAMPTZ, nullable），`status_history` JSONB 中的 `from`/`to` 值同步使用新状态枚举。`last_status_changed_at` 行为不变。

- **InterviewResearchTask（新增）**: 面试调研任务。关键属性：`id`（UUID PK）、`job_id`（FK → jobs.id）、`user_id`（FK → users.id）、`interview_time`（触发的面试时间）、`status`（pending/running/completed/cancelled/failed）、`search_dimensions`（JSONB，每维度 search 状态和结果数）、`report_id`（FK → interview_reports.id，nullable）、`triggered_at`、`started_at`、`completed_at`、`error_message`（nullable）。唯一约束：`(job_id, interview_time)`。

- **InterviewResearchResult（新增）**: 调研搜索结果。关键属性：`id`（UUID PK）、`task_id`（FK → interview_research_tasks.id）、`dimension`（enum: interview_experience/company_product/exam_points/user_weakness）、`query`（搜索查询字符串）、`results`（JSONB，Tavily API 原始返回的结构化数组）、`result_count`、`error`（nullable）、`searched_at`。

- **InterviewReport（复用并扩展）**: 现有 `interview_reports` 表。本规范新增 `report_type` 列（enum: `mock_interview` / `pre_interview_research`），`job_id` 列（FK → jobs.id，nullable——模拟面试报告已有此字段），`interview_time` 列（TIMESTAMPTZ，nullable——模拟面试报告为 NULL），`research_task_id`（FK → interview_research_tasks.id，nullable——模拟面试报告为 NULL）。现有字段（overall_score、per_question_score 等）对 research 类型报告均为 NULL。

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 存量数据迁移后，100% 的 job 状态被正确映射（抽样 200 条与迁移前对比，0 条映射错误），迁移 + 校验在 5 分钟内完成。
- **SC-002**: 用户推进状态到面试轮次时，3 步内完成面试时间设置（点击推进 → 选择目标状态 → 选择时间 → 确认），全过程不超过 30 秒。
- **SC-003**: 面试前 5 小时的调研任务在扫描窗口（±5 分钟）内的触发率达到 98% 以上（连续 50 个面试的调度记录中，≤ 1 个错过窗口）。
- **SC-004**: 从调研任务触发到报告生成完成的端到端时间中位数 ≤ 90 秒（含 4 路 Web Search + LLM 报告生成），P95 ≤ 180 秒。
- **SC-005**: 100% 的报告包含全部 6 个章节，且在内容质量校验中通过（至少 1 个公司产品名 + 至少 3 道面试题 + 至少 1 个能力维度引用——连续 50 份报告 0 份质量校验失败）。
- **SC-006**: 用户在微信中收到完整报告（所有分段）的时间 ≤ 报告生成完成后 2 分钟（P95），且 0% 出现段落丢失或乱序。
- **SC-007**: 同一面试时间不会生成重复报告——`interview_research_tasks` 唯一约束 100% 生效（连续 30 天日志中 0 条 `duplicate key` 告警）。
- **SC-008**: Web Search API 月度调用量在配额内的利用率 ≥ 80%（避免配额浪费或超额），配额用尽时自动降级而非静默失败。
- **SC-009**: 用户反馈（通过 Web 端"报告是否有用"评分）的平均满意度 ≥ 3.5/5（在报告查看页面提供 1-5 星评分按钮）。
- **SC-010**: Playwright E2E 测试覆盖：US1（新状态模型全流程：applied → interview_1 含时间设置 → interview_2 → passed）、US4（Web 端查看报告）、US7（迁移 dry-run 验证）。

## Assumptions

- **REQ-052 已就绪**: 微信通道和消息发送接口已实现。若 REQ-052 尚未完成，本规范的报告推送可通过站内通知降级，但微信触达能力缺失。
- **Tavily Search API 可用**: 现有 `backend/app/agents/tools/tavily_search.py` 集成可用。Web Search 配额充足（与现有面试调研共用配额，需评估增量）。若配额不足，需要升级 Tavily plan 或引入备选搜索 API。
- **LLM 配额**: DeepSeek V4 Pro 月度 500K token 配额中，每份面试备战报告消耗约 8K-15K token（含 search results context + report generation）。按日均 50 场面试计算，每月增量约 20K * 50 * 30 = 30M token——需要评估配额扩容需求。本规范假设配额可扩容或通过 prompt 优化压缩 token 消耗。
- **状态迁移不可逆业务影响**: `offer → passed` 和 `rejected/withdrawn → failed` 的映射会丢失"Offer 阶段附加信息"（薪资/HR 联系人/签约截止日）在前端展示的触发条件（原仅 `status=offer` 时展示）。迁移后 `status=passed` 时该信息保留在数据库但前端不再展示。本规范假定此行为可接受——用户可以在推进到 passed 前查看并保存 Offer 信息。
- **面试状态与面试轮次的关系**: 用户可能在"一面中"时实际经历了多轮一面（群面+单面），但系统层面只记录一个 interview_1 状态和一个 interview_time。多轮面试的精细管理（如一面有 3 个子轮次）超出本规范范围。
- **调研结果复用**: 24 小时内同一公司的搜索结果可跨岗位复用（减少 API 调用），但每个岗位独立生成报告（因为薄弱点是个性化的）。复用策略在 plan 阶段细化。
- **国际化**: 所有新增文案使用简体中文。
