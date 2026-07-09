# Feature Specification: WeChat Conversational Agent

**Feature Branch**: `054-wechat-conversational-agent`

**Created**: 2026-07-07

**Status**: Draft

**Input**: User description: "用户可以通过微信和Agent联络，能够让Agent进行各种工具调用和任务下发，能够通过直接跟Agent对话的方式，让Agent来完成一次求职追踪模块下新增一个新的岗位或调整旧的岗位的状态。另外还需要支持微信文字模拟面试、查看面试报告、查看能力画像。"

## Background

InterCraft 的求职追踪、模拟面试、能力画像等核心功能目前仅通过 Web 端访问。用户在移动场景下（如通勤路上收到面试通知、面试现场想快速记录结果）无法便捷地操作。微信作为中国用户最高频使用的应用，是触达用户的最佳渠道。

本规范是"Personal AI Career Agent"三大 REQ 中的**第三个**，在 REQ-052（微信通道）和 REQ-053（面试智能引擎）的基础上，赋予 Agent **理解用户自然语言并执行操作**的能力——用户通过微信聊天即可完成求职追踪管理和文字模拟面试，无需打开 InterCraft 网页。

### 前置依赖

- **REQ-052（Personal Agent + WeChat Channel）**: 微信消息收发能力。本规范的所有对话交互都通过 REQ-052 的微信通道进行。
- **REQ-053（Interview Intelligence Engine）**: 新状态模型（applied/test/interview_1/interview_2/interview_3/failed/passed）和 interview_time 字段。本规范的"修改状态"意图需要依赖新状态模型。
- **现有能力复用**: Jobs API（CRUD + 状态推进）、Interview Agent（LangGraph 模拟面试）、Interview Reports API、Ability Profile API。

### REQ 路线图

```
REQ-052: Personal Agent + WeChat Channel ✅ 已建立
  └── Agent 实体、iLink 微信接入、QR 绑定、消息收发

REQ-053: Interview Intelligence Engine ✅ 已建立
  └── 新状态模型、面试时间、定时调度、深度调研、报告生成与推送

REQ-054 (本规范): WeChat Conversational Agent
  └── NL 意图解析、工具调用、微信文字模拟面试、对话管理
```

## Clarifications

### Session 2026-07-09

- Q: 微信端 v1 写操作范围？ → A: 允许 create_job、update_job_status（含面试时间），以及改部分元数据（地点 / JD / 备注）；不含删除/归档与 Offer 填写（引导 Web）
- Q: 同一用户的面试会话互斥？ → A: 全局互斥——跨 Web/微信同一时间仅允许一场进行中面试；已有 in_progress/pending 时微信不新建，引导继续或结束现有场次
- Q: 跨渠道继续同一场面试？ → A: 允许跨渠道继续同一场（微信 ↔ Web 可互相续面）；session 与 checkpoint 共享，渠道仅作消息通道
- Q: 面试时间相对表达的时区与解析基准？ → A: 固定 Asia/Shanghai，忽略账号时区；「今天/明天/下周一」按处理时刻上海本地日历日解析，确认卡展示绝对时间
- Q: 意图解析 LLM 不可用时的行为？ → A: 自动重试 1 次；仍失败则友好降级文案 + 可观测性，不执行写操作，不降级到关键词规则擅自改数据

## User Scenarios & Testing *(mandatory)*

### User Story 1 — 通过微信新增岗位 (Priority: P1)

用户在微信中向 Agent 发送自然语言消息，表达想要添加一个新的求职追踪岗位。Agent 理解用户意图后，提取关键信息（公司名、岗位名、可选的工作地点、JD 链接等），若信息不完整则追问缺失必填字段（公司名、岗位名），确认信息无误后调用 Jobs API 创建岗位，并回复用户确认消息。

**Why this priority**: 新增岗位是求职追踪最高频的操作之一。用户在面试现场、招聘会、或看到 JD 时最自然的反应就是掏出微信记一笔。这是微信对话交互中 ROI 最高的场景。

**Independent Test**: 在微信中发送"帮我记一个字节跳动的AI应用开发工程师岗位"→ Agent 确认信息 → 用户确认 → Agent 回复"已创建" → 在 Web 端验证岗位已出现在列表中。

**Acceptance Scenarios**:

1. **Given** 用户在微信中发送"新增岗位：腾讯，后端开发工程师"，**When** Agent 收到消息，**Then** Agent 识别意图为 `create_job`，提取实体 `{company: "腾讯", position: "后端开发工程师"}`，回复确认卡片"即将新增岗位：📮 腾讯 · 后端开发工程师。确认创建吗？"，附带「确认」和「取消」按钮（以文字形式：回复"确认"或"取消"）。
2. **Given** 用户在微信中发送"加一个阿里的岗位"，**When** Agent 识别到 `company="阿里"` 但缺少 `position`，**Then** Agent 追问"好的，请问这个岗位的具体职位名称是什么？"，等待用户补充。
3. **Given** 用户在微信中发送"帮我记一下：公司=字节跳动，岗位=前端开发，地点=北京，JD链接=https://job.bytedance.com/xxx"，**When** Agent 解析消息，**Then** 提取全部 4 个字段，确认卡片显示完整信息，用户确认后创建成功。
4. **Given** 用户确认创建后，**When** 后端 Jobs API 创建成功，**Then** Agent 回复"✅ 已创建：字节跳动 · 前端开发（已投递）。你可以在 InterCraft 中查看详情或继续通过微信管理。"
5. **Given** 用户确认创建后，**When** 后端返回错误（如公司名超过 100 字符），**Then** Agent 回复"❌ 创建失败：公司名称过长（最多 100 字符）。请缩短后重试。"
6. **Given** 用户在等待 Agent 确认时发送了"取消"，**When** Agent 收到取消指令，**Then** 回复"已取消创建"，不调用 Jobs API。

---

### User Story 2 — 通过微信修改岗位状态 (Priority: P1)

用户通过微信告知 Agent 某个岗位的状态发生了变化（如"字节跳动的岗位进一面了，下周一 14:00 面试"）。Agent 识别出目标岗位和目标状态，若为面试轮次则提取面试时间，确认后调用 Jobs API 推进状态。

当用户有多个岗位时（如同时追踪了字节和腾讯），Agent 通过模糊匹配找到最可能的岗位。若匹配不明确（如用户只说"那个岗位进二面了"），Agent 列出候选岗位让用户选择。

**Why this priority**: 状态推进是求职追踪中最需要"随手记"的操作——用户在收到面试通知后，最自然的反应是打开微信告诉 Agent，而不是打开浏览器登录 Web 端。

**Independent Test**: 在微信中发送"字节跳动的岗位进一面了，下周三上午10点面试"→ Agent 找到字节的岗位 → 确认状态和一面的面试时间 → 推进成功 → Web 端验证状态和面试时间已更新。

**Acceptance Scenarios**:

1. **Given** 用户追踪了一个字节跳动的岗位（当前状态=applied），**When** 用户在微信中发送"字节进一面了，7月10号下午2点面试"，**Then** Agent 识别意图为 `update_status`，匹配到字节的 job，按 `Asia/Shanghai` 解析面试时间，确认："即将更新：字节跳动 · AI应用开发工程师 → 一面中，面试时间：7月10日 14:00。确认？"，用户确认后推进成功。
1a. **Given** 当前上海时间为 2026-07-09（周四），**When** 用户发送"字节进一面了，下周一 14:00 面试"，**Then** Agent 将面试时间解析为 2026-07-13 14:00（Asia/Shanghai），确认卡片展示该绝对时间。
2. **Given** 用户追踪了字节跳动和腾讯两个岗位，**When** 用户在微信中发送"那个岗位进二面了"，**Then** Agent 无法唯一确定目标岗位，回复"你目前追踪的岗位有：1. 字节跳动 · AI应用开发工程师（已投递）2. 腾讯 · 后端开发（笔试中）。请问是哪一个？回复序号或公司名即可。"
3. **Given** 用户回复"字节的挂了"，**When** Agent 识别意图为 `update_status` + `target=failed`，**Then** Agent 确认："即将更新：字节跳动 · AI应用开发工程师 → 已失败。建议填写失败原因（如：技术面没过/薪资谈不拢），方便后续复盘。要填写备注吗？"用户可选择填写或跳过。
4. **Given** 用户发送"字节三面过了！"，**When** Agent 识别 `target=passed`，**Then** Agent 确认推进到终态"已通过"，并提醒"🎉 恭喜！岗位已标记为已通过。记得在 InterCraft 中填写 Offer 信息（薪资、HR 联系方式等）。"
5. **Given** 用户尝试退回到上一个状态（如从 interview_2 退回到 interview_1），**When** Agent 检查状态机规则发现此转换非法，**Then** Agent 回复"❌ 无法从「二面中」退回到「一面中」。如需修改，请在 InterCraft Web 端操作。"（微信端只允许合法状态推进，不回退——回退是管理操作，需在 Web 端执行。）
6. **Given** 用户发送的状态描述模糊（如"字节有消息了"），**When** Agent 无法确定目标状态，**Then** Agent 回复"好的，请问具体是什么消息？可选：进笔试了 / 进一面了 / 进二面了 / 进三面了 / 挂了 / 过了。回复对应描述即可。"

---

### User Story 3 — 通过微信查询求职状态 (Priority: P2)

用户通过微信随时查询自己的求职追踪概况。Agent 理解查询意图后，从 Jobs API 读取数据，以简洁的摘要格式回复（如"你目前追踪了 5 个岗位：2 个已投递、1 个笔试中、1 个一面中、1 个已通过"）。用户可进一步查询具体岗位的详情或某个状态下的岗位列表。

**Why this priority**: 查询是仅次于 CRUD 的高频操作。用户在路上想快速了解"我还有几个面试 pending"时，微信查询比打开 Web 端快得多。但查询不产生新数据，排在写入操作之后。

**Independent Test**: 在微信中发送"我的求职进展怎么样"→ Agent 返回统计摘要 → 发送"有哪些岗位在面试阶段"→ Agent 列出面试中的岗位。

**Acceptance Scenarios**:

1. **Given** 用户追踪了 5 个岗位（状态分布：2 applied, 1 test, 1 interview_1, 1 passed），**When** 用户在微信中发送"我的求职进展"，**Then** Agent 回复"📊 求职概览：共追踪 5 个岗位。已投递 2 | 笔试中 1 | 一面中 1 | 已通过 1。最近更新：字节跳动 → 一面中（今天 10:30）。"
2. **Given** 用户发送"有哪些岗位在面试阶段"，**When** Agent 解析意图，**Then** 回复"当前在面试阶段的岗位：1. 字节跳动 · AI应用开发工程师 — 一面中，面试时间 7/10 14:00 2. 腾讯 · 后端开发 — 笔试中，笔试时间 7/9 10:00。共 2 个岗位待面试。"
3. **Given** 用户发送"字节跳动的岗位详情"，**When** Agent 匹配到字节的 job，**Then** 回复包含：公司/岗位/当前状态/面试时间（如有）/JD 链接（如有）/最近一条状态变更备注。
4. **Given** 用户发送"最近有没有面试"，**When** Agent 查询, **Then** 若 7 天内有面试时间，回复列表；若无，回复"未来 7 天内暂无面试安排。继续保持投递哦 💪"。
5. **Given** 用户查询时 Agent 后端 API 调用失败（如 Jobs API 超时），**When** Agent 重试 1 次后仍失败，**Then** 回复"抱歉，暂时无法获取求职数据（系统繁忙）。请稍后重试或前往 InterCraft 查看。"

---

### User Story 4 — 微信文字模拟面试 (Priority: P2)

用户通过微信启动一场文字模拟面试。Agent 调用现有的 LangGraph 面试 Agent，但将交互模式从 WebSocket 流式改为微信异步消息模式：Agent 发送面试题 → 用户文字作答 → Agent 评分并发送下一题 → 重复 5 轮 → Agent 发送简要面试报告。每轮之间有合理的等待时间（用户作答时间不限，Agent 评分后 10 秒内发送下一题）。

**Why this priority**: 微信中的模拟面试让用户可以在碎片时间练习（如排队、通勤）。但文字面试体验不如 Web 端的实时流式交互丰富，且微信的消息延迟使得面试节奏较慢。作为 Web 端面试的补充渠道而非替代，排在 P2。

**Independent Test**: 在微信中发送"开始模拟面试"→ Agent 发送第 1 题 → 用户作答 → Agent 评分 + 发送第 2 题 → ... → 5 轮后收到简要报告 → 在 Web 端可查看完整报告。

**Acceptance Scenarios**:

1. **Given** 用户在微信中发送"开始模拟面试"或"来一场面试"，**When** Agent 收到消息，**Then** Agent 回复"好的！请选择面试模式：A. 快速 Drill（5 道错题强化）B. 完整面试（5 轮综合面试）。另外，是针对某个岗位的定向面试，还是通用面试？"引导用户选择模式和岗位关联。
2. **Given** 用户选择了"完整面试 + 字节跳动岗位"，**When** Agent 创建 interview_session（通过 Interviews API），**Then** 回复"面试准备就绪！目标：字节跳动 · AI应用开发工程师。共 5 轮，每轮我会发送一道面试题，你通过文字作答。准备好了吗？回复「开始」启动面试。"
3. **Given** 面试进行中（第 2 轮），**When** Agent 发送面试题"请描述你在项目中遇到的最大的技术挑战，以及你是如何解决的"，**Then** 用户有无限时间作答（不设超时）。用户回复作答文本后，Agent 在 30 秒内完成评分并回复：评分 + 简要反馈（1-2 句优点 + 1 条改进建议）+ 第 3 轮面试题。
4. **Given** 用户在面试中途发送"暂停面试"或"不做了"，**When** Agent 收到暂停指令，**Then** 回复"面试已暂停。当前进度：2/5 轮。你可以稍后回复「继续面试」从中断处继续，或回复「结束面试」查看当前结果。"面试 session 状态保持为 `in_progress`，可在 Web 端继续。
5. **Given** 用户完成了全部 5 轮面试，**When** Agent 生成最终报告，**Then** 微信中收到面试摘要：总分、每轮得分、最强/最弱维度、1 条 actionable 建议。末尾附带"📎 完整报告可在 InterCraft 中查看"（因为微信中不适合展示完整的雷达图和维度详情）。
6. **Given** 用户在面试中使用语音消息作答，**When** Agent 收到语音消息，**Then** 通过 iLink ASR 转录为文本（REQ-052 FR-018c），按文本作答流程处理。评分反馈中备注"（基于语音转录评分）"以防 ASR 误差。
7. **Given** 用户尚未绑定岗位（没有 job 记录）但想进行通用面试，**When** 选择"通用面试"，**Then** Agent 使用默认面试配置（不关联 job_id），根据用户的能力画像（如有）和常见面试题生成题目。
8. **Given** 用户在 Web 端已有一场 `in_progress` 的模拟面试，**When** 在微信中发送"开始模拟面试"，**Then** Agent 不创建新 session，回复说明已有进行中的面试，并引导「继续面试」或「结束面试」后再开新场。
9. **Given** 用户在 Web 端完成了第 2 轮后离开，**When** 在微信中发送"继续面试"，**Then** Agent 从共享 checkpoint 恢复，通过微信发送第 3 轮题目（异步文字模式），不丢失已完成轮次。

---

### User Story 5 — 微信查看面试报告与能力画像 (Priority: P3)

用户通过微信查询历史面试报告摘要和能力画像概况。Agent 从 Interview Reports API 和 Ability Profile API 读取数据，以简洁的摘要格式回复。对于报告详情（完整 6 维度雷达图、每题详细反馈），Agent 引导用户前往 Web 端查看。

**Why this priority**: 查看报告是低频但有用的操作（用户可能在面试路上想快速回顾上次面试的反馈）。但报告的完整价值在 Web 端的丰富排版中才能体现，微信仅提供摘要。排在 P3。

**Independent Test**: 在微信中发送"我上次面试表现怎么样"→ Agent 返回最近一次面试的摘要 → 发送"能力画像"→ Agent 返回 6 维度得分概况。

**Acceptance Scenarios**:

1. **Given** 用户最近完成过一场模拟面试（总分 7.5），**When** 用户在微信中发送"上次面试报告"或"我面试表现怎么样"，**Then** Agent 回复最近一次面试摘要："📝 最近面试：字节跳动 · AI应用开发工程师（7/5）。总分 7.5/10。最强：工程实践(8.5)、沟通表达(8.0)。最弱：算法(6.0)、技术深度(6.5)。💡 建议：加强动态规划和树相关算法的练习。📎 完整报告：InterCraft → 面试记录。"
2. **Given** 用户在微信中发送"我的能力画像"，**When** Agent 从 Ability Profile API 读取数据，**Then** 回复 6 维度得分文字版："🎯 能力画像：技术深度 6.5 | 架构设计 7.0 | 工程实践 8.5 ↑ | 沟通表达 8.0 | 算法 6.0 ↓ | 业务理解 7.5。趋势：工程实践持续提升，算法略有下降。📎 完整雷达图：InterCraft → 能力画像。"
3. **Given** 用户没有完成过任何模拟面试（无报告数据），**When** 用户查询面试报告，**Then** Agent 回复"你还没有完成过模拟面试。回复「开始模拟面试」来试试你的第一场 AI 面试！"
4. **Given** 用户发送"有哪些面试报告"，**When** Agent 查询报告列表，**Then** 回复最近 5 场的列表（日期 + 岗位 + 得分），超过 5 场的引导到 Web 端查看完整历史。

---

### User Story 6 — 对话纠错与帮助 (Priority: P3)

当 Agent 无法理解用户消息时，提供友好的引导和帮助。用户可随时发送"帮助"查看 Agent 支持的所有指令。Agent 在意图不确定时主动列出可能的操作，而非静默失败或给出无关回复。

**Why this priority**: 对话体验的兜底保障。没有纠错和帮助时，用户遇到 Agent 不理解的消息会感到挫败。排在最后因为核心功能（CRUD + 面试）的意图识别已经能覆盖大部分用户消息。

**Independent Test**: 发送模糊消息"那个东西怎么样了"→ Agent 回复无法理解并列出选项 → 发送"帮助"→ Agent 列出所有支持的操作。

**Acceptance Scenarios**:

1. **Given** 用户发送了一条 Agent 无法识别意图的消息（如"今天天气怎么样"），**When** Agent 意图解析失败，**Then** Agent 回复"抱歉，我主要专注于求职相关的事务。我可以帮你：📝 新增/管理岗位 | 📊 查询求职进展 | 🎙️ 模拟面试 | 📋 查看报告。请告诉我你想做什么？"
2. **Given** 用户发送"帮助"或"你能做什么"，**When** Agent 收到帮助请求，**Then** 回复完整的能力列表和示例指令（格式清晰，3-4 条消息分段），包含：(a) 岗位管理示例 (b) 状态推进示例 (c) 模拟面试示例 (d) 查询示例。
3. **Given** Agent 连续两次无法理解用户消息，**When** 第三次仍无法理解，**Then** Agent 回复"我暂时无法理解你的需求。你可以：1. 回复「帮助」查看我能做什么 2. 前往 InterCraft Web 端操作 3. 换个方式描述你的需求。我会继续尝试理解！"
4. **Given** 用户发送的指令包含多个意图（如"帮我加一个腾讯的岗位，顺便看看我的求职进展"），**When** Agent 解析到复合意图，**Then** Agent 按顺序处理（先创建岗位，确认后自动查询进展），而非只处理第一个。
5. **Given** 意图解析 LLM 首次调用超时，**When** Agent 自动重试 1 次后仍失败，**Then** Agent 不执行写操作，回复友好降级文案（可稍后重试 / 「帮助」 / Web），并记录失败日志与指标。

---

### Edge Cases

- **快速连续发送多条消息**: Agent 按接收顺序处理，每条消息独立生成回复。若用户在 Agent 回复前又发了一条，Agent 先完成当前消息的处理再处理下一条。不丢失消息。同一意图的连续消息（如"字节"/"进一面"/"明天下午"）合并处理。
- **用户在 Web 端和微信端同时操作同一岗位**: 两个通道的写操作通过现有 outbox + 后端状态机保障一致性。微信端的操作结果不会实时推送到 Web 端（Web 端需刷新），但微信端操作后 Agent 的回复即是最新状态。
- **模拟面试中用户长时间不回复**: 不设超时。用户可以在面试中间间隔数小时甚至数天，通过"继续面试"恢复。Session 的 24 小时过期机制（现有 Interviews 模块）仍生效——过期后 Agent 引导用户开启新面试。
- **已有进行中面试时再次「开始模拟面试」**: 全局互斥生效。无论现有场次在 Web 还是微信创建，Agent 拒绝新建，提示继续或先结束现有场次。
- **跨渠道续面**: 允许。用户可在另一渠道「继续面试」同一 session；若两渠道几乎同时发送作答，按消息到达顺序串行处理，后到的作答在前一轮评分完成后再处理（不并行评分）。
- **模拟面试中 iLink 连接断开**: 用户的消息被暂存，Agent 重连后（REQ-052 长轮询恢复）通过 cursor 补拉消息，面试 session 不受影响。但 Agent 的评分和下一题发送可能延迟。
- **LLM 意图解析返回置信度低的结果**: 设置置信度阈值（如 0.6）。低于阈值时，Agent 不执行操作，转而列出最可能的 2-3 个意图让用户选择。避免误操作（如用户说"腾讯不行了"被误解为推进到 failed）。
- **意图解析 LLM 不可用**: 自动重试 1 次；仍失败则友好降级文案 + 可观测性，不执行写操作，不使用关键词规则擅自改数据。
- **用户在面试中发送与面试无关的消息**: Agent 识别后提示"当前正在进行模拟面试（第 3/5 轮）。如需中断面试，请回复「暂停面试」。否则请先完成当前题目作答。"非面试指令在面试中暂存，面试结束后再处理（或用户明确中断面试后处理）。
- **微信消息长度限制**: iLink 文本消息有长度上限（约 3000 字符，参考 CoPaw `split_text()`）。Agent 发送的面试题、评分反馈、报告摘要均不超过 500 字符。若确实需要发送长内容（如面试报告摘要），使用 REQ-052 的分段机制。
- **安全与权限**: Agent 仅响应绑定用户的微信消息。非绑定用户的消息返回友好提示（REQ-052 FR-017 的未绑定处理）。Agent 的写操作（创建岗位、推进状态、修改地点/JD/备注）必须经过用户确认——不执行"一句话自动完成"的隐式操作。
- **超出微信写范围的请求**: 用户请求删除/归档岗位或填写 Offer 时，Agent 不执行写操作，回复说明该操作需在 InterCraft Web 端完成，并可给出简短引导。

## Requirements *(mandatory)*

### Functional Requirements

#### 意图解析
- **FR-001**: System MUST 在收到用户微信消息后，通过 LLM（DeepSeek V4 Pro）进行意图解析。解析结果包含：`intent`（create_job / update_status / update_job_fields / query_jobs / query_reports / query_ability / start_interview / continue_interview / pause_interview / end_interview / help / unknown）、`entities`（提取的实体键值对）、`confidence`（0-1 浮点数）。
- **FR-002**: System MUST 定义意图解析的 Prompt，包含：(a) 新状态模型的完整状态列表和中文标签 (b) 每个意图的实体 schema（如 create_job 需要 company+position，update_status 需要 target_job+target_status+interview_time，update_job_fields 需要 target_job + 至少一个可改字段）(c) 中文口语表达的常见变体（如"挂了"="failed"、"过了"="passed"、"进一面"="interview_1"）(d) 要求 LLM 对不确定的实体标记 confidence。
- **FR-003**: System MUST 在意图置信度低于 0.6 时，不执行任何操作，而是回复列出最可能的 2-3 个意图让用户选择。用户选择后直接执行对应意图，无需重新解析。
- **FR-003a**: System MUST 在意图解析 LLM 调用失败（超时、5xx、网络错误等）时：自动重试 **1** 次；若仍失败，MUST NOT 执行任何写操作，MUST NOT 降级到关键词/规则引擎擅自推断并改数据；改为向用户回复友好降级文案（说明暂时无法理解，可稍后重试、回复「帮助」或前往 InterCraft Web），并记录结构化错误日志与失败指标（计入 FR-019 / FR-020）。
- **FR-004**: System MUST 支持复合意图处理：若用户一条消息中包含多个可独立执行的操作（如"加一个XX岗位，再查一下求职进展"），Agent 按顺序逐个执行，先完成后确认再执行下一个。

#### 岗位写操作工具调用
- **FR-005**: System MUST 实现 `create_job` 工具——调用 `POST /api/v1/jobs` 创建岗位。必填字段（company、position）缺失时，Agent 追问用户补充。可选字段（base_location、jd_url、branch_id、notes_md、employment_type、salary_range_text）在用户提及或首次创建后询问是否补充。
- **FR-006**: System MUST 实现 `update_job_status` 工具——调用后端状态推进接口推进岗位状态。工具执行前必须：(a) 模糊匹配找到目标岗位（详见 FR-007）(b) 确认目标状态合法（状态机校验）(c) 若推进到面试轮次，必须有 interview_time（追问用户）(d) 向用户展示确认卡片，等待用户明确确认（回复"确认"/"是"/"好的"等）后才执行。
- **FR-006b**: System MUST 将用户消息中的相对时间表达（如「明天」「下周一 14:00」「明天下午 2 点」）解析为绝对 `interview_time` 时，**一律使用固定时区 `Asia/Shanghai`**，忽略用户账号时区设置。「今天 / 明天 / 下周一」等相对日期以 Agent 处理该消息时的上海本地日历日为基准。确认卡片 MUST 展示解析后的绝对日期时间（如「7月10日 14:00」），便于用户核对。
- **FR-006a**: System MUST 实现 `update_job_fields` 工具——允许用户通过微信修改已有岗位的部分元数据，**仅限**：`base_location`（工作地点）、`jd_url`（JD 链接）、`notes_md`（备注）。工具执行前必须模糊匹配目标岗位并展示确认卡片。**明确不在微信端支持**：删除/归档岗位、填写或修改 Offer 信息（薪资、HR 联系方式等）——此类请求 MUST 回复引导用户前往 InterCraft Web 端操作。
- **FR-007**: System MUST 实现岗位模糊匹配：当用户未明确指定岗位 ID 时，Agent 从用户的所有活跃岗位中（`deleted_at IS NULL`），按以下优先级匹配：(a) 公司名 + 岗位名精确匹配 (b) 公司名包含匹配 (c) 岗位名包含匹配 (d) 最近更新的岗位。若匹配到多个候选，列出供用户选择（最多 5 个，超过 5 个时提示用户缩小范围）。
- **FR-008**: System MUST 所有写操作（create_job、update_job_status、update_job_fields）执行前向用户展示确认卡片，格式：操作类型 + 影响对象 + 关键参数 + "确认 / 取消"提示。用户确认后才执行 API 调用。确认等待无超时。

#### 微信文字模拟面试
- **FR-009**: System MUST 通过 `POST /api/v1/interview-sessions` 创建面试 session。用户可选择：(a) 关联已有岗位的定向面试 (b) 通用面试（不关联岗位）。面试模式支持 `full`（5 轮综合面试）和 `quick_drill`（5 道错题强化，需 ≥ 5 条活跃错题）。
- **FR-009a**: System MUST 对同一用户实行**全局面试会话互斥**（跨 Web 与微信）：若该用户已存在 `pending` 或 `in_progress` 的 interview session，微信端收到 `start_interview` 时 MUST NOT 创建新 session，而是回复说明当前已有进行中的面试（含渠道提示，如「Web 端」或「微信」），并引导用户回复「继续面试」从中断处恢复，或「结束面试」后再开新场。
- **FR-010**: System MUST 将 LangGraph 面试 Agent 的交互从 WebSocket 流式模式适配为微信异步消息模式：(a) Agent 调用 interview graph 的 `generate_question` 节点获取面试题 (b) 通过微信发送面试题文本 (c) 用户回复后，Agent 调用 interview graph 的 `score_answer` 节点评分 (d) 通过微信发送评分反馈 + 下一题 (e) 重复 5 轮后调用 `generate_report` 节点生成报告。
- **FR-011**: System MUST 支持面试中的中断与恢复：(a) 用户发送"暂停面试"→ Agent 保存当前进度，session 保持 `in_progress` (b) 用户发送"继续面试"→ Agent 从 LangGraph checkpoint 恢复，继续下一轮 (c) 用户发送"结束面试"→ 若已完成 ≥ 3 轮，生成部分报告；若 < 3 轮，session 标记为 `expired`，不生成报告。
- **FR-011a**: System MUST 允许**跨渠道继续同一场面试**：用户可在 Web 端开始的 session 上通过微信「继续面试」续面，也可在微信开始的 session 上于 Web 端续面。Session 与 LangGraph checkpoint 为渠道无关的共享状态；续面时按当前渠道的交互模式适配（微信用异步文字消息，Web 用既有流式/页面交互）。同一时刻仍受 FR-009a 全局互斥约束（不会并行两场）。
- **FR-012**: System MUST 在每轮面试评分反馈中保持简洁（微信消息格式）：`第 X/5 轮评分：X.X/10` + 1-2 句优点 + 1 条改进建议 + 下一题。单条消息不超过 500 字符。不发送原始的评分 JSON。

#### 信息查询
- **FR-013**: System MUST 实现 `query_jobs` 工具——调用 `GET /api/v1/jobs` 获取用户岗位列表，按状态聚合统计。回复格式简洁（摘要不超过 300 字符），包含状态分布和最近更新。
- **FR-014**: System MUST 实现 `query_reports` 工具——调用 `GET /api/v1/interview-sessions` 获取最近面试报告列表。单份报告摘要不超过 400 字符（总分 + 最强/最弱维度 + actionable 建议）。超过 5 份报告时，仅展示最近 5 份并引导到 Web 端查看完整历史。
- **FR-015**: System MUST 实现 `query_ability` 工具——调用 Ability Profile API 获取 6 维度得分。回复格式：维度名 + 得分 + 趋势箭头（↑↓→）。若用户没有能力画像数据（未完成过面试），引导用户完成首次模拟面试。

#### 对话管理
- **FR-016**: System MUST 为每个用户的微信对话维护会话上下文（Redis 存储，TTL=24 小时），跟踪：(a) 当前对话状态（idle / awaiting_confirmation / in_interview）(b) 待确认的操作（操作类型 + 参数）(c) 当前面试 session_id 和 round_number（如在面试中）。上下文在用户 24 小时无交互后自动清除。
- **FR-017**: System MUST 在 `awaiting_confirmation` 状态下，仅接受确认/取消类消息（"确认"/"好的"/"是"/"行"/"可以"/"取消"/"算了"/"不要了"），其他消息回复"请先确认或取消当前操作：[显示待确认内容]"。用户在等待确认期间发送的新任务指令在确认/取消当前操作后处理。
- **FR-018**: System MUST 实现 `help` 意图——当用户发送"帮助"、"你能做什么"、"功能"等消息时，回复结构化的能力列表（分 4 类：岗位管理、状态推进、模拟面试、信息查询），每类附带 1-2 个示例指令。帮助消息若超过 500 字符，分 2-3 段发送。

#### 可观测性
- **FR-019**: System MUST 为对话交互暴露以下指标：(a) `conversation_turns_total`（Counter，按 intent 分组）(b) `intent_confidence_histogram`（Histogram，LLM 意图置信度分布）(c) `tool_call_success_rate`（按 tool 名称分组的成功率 Gauge）(d) `interview_via_wechat_total`（Counter，按 status completed/expired 分组）(e) `conversation_duration_seconds`（Histogram，从用户首条消息到会话结束的时长）。
- **FR-020**: System MUST 记录每条对话交互的结构化日志：`user_id`、`intent`、`confidence`、`tool_calls`（工具名称 + 参数摘要 + 执行结果 + latency_ms）、`response_length`、`conversation_state`。消息内容本身不记录（隐私），仅记录意图和参数摘要。

#### CLI 接口（Constitution 原则 II）
- **FR-021**: System MUST 提供 CLI 命令：(a) `python -m app.modules.agent.cli parse-intent "<message>"` — 测试意图解析（给定自然语言，输出解析结果 JSON）(b) `python -m app.modules.agent.cli simulate-chat <user_id>` — 启动交互式对话模拟终端（用于调试对话流程，非微信环境）。

### Key Entities *(include if feature involves data)*

- **ConversationContext（会话上下文）**: Redis 中的临时数据结构，TTL=24 小时。关键属性：`user_id`、`state`（idle/awaiting_confirmation/in_interview）、`pending_action`（操作类型 + 参数 JSON）、`interview_session_id`（如在面试中）、`interview_round`（当前轮次）、`last_active_at`。此数据不持久化到 PostgreSQL——它是纯运行时会话状态，丢失后用户重新发消息即可重建。

- **IntentParseResult（意图解析结果）**: LLM 返回的结构化对象。关键属性：`intent`（枚举值）、`entities`（JSON 键值对）、`confidence`（0-1）、`raw_message`（用户原始消息引用）、`parsed_at`。不单独建表——作为 `agent_messages`（REQ-052）的扩展字段存储，或作为对话日志的 transient metadata。

- **InterviewSession（复用）**: 现有 `interview_sessions` 表。微信模拟面试创建的 session 通过 `mode` 字段区分（现有 `full`/`quick_drill`/`doubao`，微信面试使用 `full` 或 `quick_drill`）。Session 的 `status` 生命周期与 Web 端面试一致（pending → in_progress → completed/expired）。

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 用户在微信中通过自然语言完成一次新增岗位操作（从发送消息到 Agent 确认创建成功）的时间 ≤ 60 秒（含用户确认等待时间中位数 15 秒）。
- **SC-002**: 意图解析准确率 ≥ 90%（连续 100 条求职相关消息中，Agent 正确识别意图并提取关键实体的比例 ≥ 90%）。测试集覆盖 20 种以上中文口语表达变体。
- **SC-003**: 微信模拟面试的 5 轮完成率 ≥ 60%（启动微信面试的用户中，至少完成 5 轮并收到报告的比例）。对比 Web 端模拟面试的完成率作为 baseline。
- **SC-004**: Agent 在用户消息到达后 15 秒内发送回复（P95，含 LLM 意图解析 + 工具调用 + 回复生成），不含用户在"确认/取消"环节的等待时间。
- **SC-005**: 100% 的写操作（创建岗位、推进状态、修改地点/JD/备注）在 Agent 执行前经过用户明确确认——0 次"Agent 未经确认就修改用户数据"的事故。
- **SC-006**: 岗位模糊匹配的首选命中率 ≥ 85%（用户提及公司名/岗位名的部分信息时，Agent 列出的第 1 个候选项即为用户意图的岗位）。测试集覆盖单岗位/多岗位/零岗位三种场景。
- **SC-007**: 模拟面试中断后恢复成功率 ≥ 95%（用户发送"暂停面试"+ 后续"继续面试"后，从正确的中断点继续，不丢失已完成轮次的数据）。
- **SC-008**: 用户满意度评分 ≥ 4.0/5.0——在微信对话结束后（用户主动结束或会话超时），Agent 发送满意度调查链接"本次对话有帮助吗？1-5 星"。目标回收率 ≥ 20%。
- **SC-009**: Playwright E2E 测试覆盖：US1（微信新增岗位全流程，模拟微信消息 → 验证后端数据落库）、US2（状态推进 + 面试时间设置）、US4（模拟面试 5 轮完整流程）。

## Assumptions

- **REQ-052 和 REQ-053 已就绪**: 微信消息收发、Agent 数据访问、新状态模型（含 interview_time）均可用。若前置 REQ 未完成，本规范的部分工具调用（尤其是 update_job_status 中的 interview_time 设置）需要降级处理。
- **LLM 意图解析**: 使用 DeepSeek V4 Pro 进行意图解析（与现有面试 Agent 共用 LLM client）。每条对话消息消耗约 500-1500 token（含 system prompt + user message + tool definitions）。按日均 100 次对话交互计算，月度增量约 100 * 30 * 1500 = 4.5M token——在现有 500K/月配额之外需扩容。
- **LangGraph 面试 Agent 复用**: 现有面试 Agent 的 graph nodes（question_gen、score_llm、report）可被微信面试流程调用，无需重写。但调用方式需要从 LangGraph streaming API 改为 per-node 调用——plan 阶段需要确认 LangGraph 是否支持节点级别的无状态调用，或需要实现一个适配层。
- **面试评分延迟**: 微信模拟面试的评分需要调用 LLM（score_llm node），耗时约 5-15 秒。用户在此期间等待。若 LLM 响应超过 30 秒，Agent 先回复"评分中，请稍候…"，评分完成后主动推送结果。此行为与 Web 端的实时流式体验有差异，但微信的异步消息模型天然适合。
- **确认机制为文字形式**: 微信 iLink 不支持交互式按钮（如 Telegram 的 inline keyboard），因此确认/取消通过用户回复文字（"确认"/"取消"）实现。若未来 iLink 支持交互式消息（如模板消息卡片），可升级确认 UI。本规范 v1 使用文字确认。
- **多轮对话的上下文窗口限制**: 超过 10 轮的对话（如面试 5 轮 + 前后交互）可能超出 LLM 上下文限制。plan 阶段需要设计对话摘要策略（summarize 早期对话），确保 LLM 始终拥有足够的上下文理解当前消息。
- **模拟面试的安全与公平**: 微信模拟面试的评分和反馈与 Web 端完全一致（使用相同的 score_llm prompt 和评分标准）。不因微信渠道而降低评分质量或使用更轻量的模型。
- **国际化**: 所有 Agent 消息使用简体中文。帮助文档和错误提示使用中文。
