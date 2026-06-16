# Feature Specification: Job Application Tracking

**Feature Branch**: `014-job-tracking`

**Created**: 2026-06-16

**Status**: Draft

**Input**: User description: "当前求职追踪模块功能空缺,帮我规划一下需求"。

## Background

`Job` 实体、状态机、后端 7 端点(`/jobs` 列表 / 创建 / 详情 / 修改 / 改状态 / 删除 / 时间线 / 统计)以及前端 Jobs 列表页骨架(在 Phase 2 已交付,见 `specs/001-intercraft-product-spec/data-model-phase-2.md` §7 与 `backend/app/modules/jobs/`)都已就位。但用户进入 `/jobs` 后只能看到一张表格,**点不进行、看不到时间线、改不了字段、关联不了简历、状态机按钮和后端不一致**。从用户视角,这个模块"空缺"的不是 CRUD 本身,而是把已有的能力呈现为一个可操作、能驱动下一步行动的产品闭环。

本规范把"求职追踪"作为一个完整用户旅程来规划 P1 切片,聚焦:
1. **能用** — 详情面板、时间线、状态推进、备注编辑
2. **对得上** — 前端状态机 / 状态徽章 / 状态选项与后端 `JOB_TRANSITIONS` 严格一致
3. **联得动** — 关联简历分支、JD 链接、Offer 附加信息
4. **不掉链** — 离线 / 慢网下的写操作通过 outbox 兜底,网络恢复后自动重放
5. **看得见进展** — 当前求职活动(创建 / 改状态)在用户视角的时间线与活动流里浮现

范围外(留待后续 feature):公司情报聚合、邮箱解析自动入库、招聘官联系人 CRM、Offer 谈判追踪、面试日程与日历集成。

## Clarifications

### Session 2026-06-16

- Q: 前端 `StatusBadge` 与 Jobs.tsx 的 NEXT_STATUS 用 `wishlist / applied / screening / interview / offer / rejected`,但后端状态机是 `applied / test / oa / hr / offer / rejected / withdrawn`。两套该以哪边为准? → A: 以**后端**为准(`JOB_TRANSITIONS` 与 `JOB_STATUS_CN`)。前端 `StatusBadge` / `NEXT_STATUS` / 状态 Tab / 推进菜单全部按后端 7 状态重写,删除不存在的 `wishlist` 与 `screening / interview`。
- Q: 后端 `JobOut.notes_md` 与前端仓库 `Job.note` 字段不一致(命名 + 含义轻微差),改哪边? → A: 以**后端 `notes_md` 为准**——它是 Markdown 富文本,前端 `note` 改为 `notes_md`,Jobs.tsx 详情面板用 textarea 编辑;`UpdateJobStatusInput.note`(状态变更备注,后端上限 500 字符)保留 `note` 字段名,二者区分清楚。
- Q: 状态变更时是否要强制要求填备注? → A: 不强制。备注是可选的"为什么推进 / 哪轮反馈",但若新状态为 `rejected / withdrawn`,UI 提示建议填写。
- Q: 离线 / 慢网下写操作如何兜底? → A: 复用 Phase 3 的 outbox 模式(`src/lib/outbox/` 与 `backend/app/modules/outbox/`)——创建 / 改状态 / 编辑 / 删除全部入 outbox,断网时本地立即生效(乐观更新),恢复后由后端 worker 重放。Job 模块此前未走 outbox,本规范纳入。
- Q: 关联简历分支的入口放哪里? → A: 详情面板基本信息区放一个"绑定简历分支"下拉,数据来自 `useResumeBranches()`。可绑定 / 换绑 / 解绑(置 null)。
- Q: Offer 阶段的薪资、HR 联系人、签约截止日是新增字段吗? → A: 是。`jobs` 表新增可选列 `offer_salary_text` (TEXT)、`offer_contact_name` (TEXT)、`offer_contact_info` (TEXT)、`offer_deadline_at` (TIMESTAMPTZ),迁移随本 feature 一起出。Offer 阶段详情面板额外展示,其他阶段不显示。
- Q: `JobTimeline` 组件已经存在但 Jobs.tsx 没用,本规范要复用吗? → A: 是。组件已经按 `from_status / to_status / changed_at / note` 渲染,但后端实际返回 `from / to / at / note`(见 `service.py:84`)。本规范让前端统一改用后端的字段名,组件也同步。

## User Scenarios & Testing *(mandatory)*

### User Story 1 - 打开职位详情并查看时间线 (Priority: P1)

求职者在 `/jobs` 列表里看到一行的公司名 / 岗位,点击该行任意位置,在右侧或弹出抽屉里看到:
- 完整字段(公司、岗位、JD 链接、绑定的简历分支、状态、备注、Offer 阶段附加信息)
- 状态变更时间线(从创建到当前,每一步的"从 → 到 / 时间 / 备注")
- 操作按钮:编辑、推进状态、删除

**Why this priority**: 详情面板是其余所有 P1 操作(编辑、推进、绑定简历、查看时间线)的承载面。没有详情,求职追踪模块就只是一张表,没有"追踪"二字可言。

**Independent Test**: 在列表上点击任意一行,验证详情面板在 1 秒内打开,显示该公司 / 岗位的所有字段和完整时间线,操作按钮可见。

**Acceptance Scenarios**:

1. **Given** 用户在 `/jobs` 列表, **When** 点击任意一行的公司 / 岗位单元格, **Then** 右侧抽屉打开,显示该 job 的所有字段和状态时间线。
2. **Given** 详情抽屉已打开, **When** 用户查看时间线, **Then** 看到从创建起的每条状态变更(来源状态 → 目标状态 + 发生时间 + 备注),按时间倒序排列,最新一条在最上。
3. **Given** 详情抽屉已打开, **When** 用户查看时间线, **Then** 时间线条目数为 `status_history.length`,与后端 `GET /jobs/{id}/timeline` 返回数量一致。
4. **Given** 详情抽屉已打开, **When** 用户按 `Esc` 或点击抽屉外区域, **Then** 抽屉关闭,列表状态保持原样(搜索词、Tab 不重置)。
5. **Given** 用户从详情抽屉里点击「删除」, **When** 弹出确认, **Then** 用户取消则不删、确认则抽屉关闭、列表刷新、Toast 提示「已删除」。

---

### User Story 2 - 状态推进与备注 (Priority: P1)

求职者在详情抽屉里点击「推进状态」,弹出状态选择器(只列出后端 `JOB_TRANSITIONS` 允许的下一步),选中目标状态、可选填备注(<= 500 字符)、确认。状态徽章立即更新到新状态,时间线新增一条,列表的对应行也立即更新。

**Why this priority**: 状态推进是模块的核心动作。求职者每天做的事就是"简历已读 → 笔试 → OA → HR 面 → Offer",如果推不动,模块失去价值。

**Independent Test**: 在 `applied` 状态的 job 上打开详情,点击推进 → 选 `test` → 提交,验证状态徽章更新、时间线多一条 `applied → test`、列表行的徽章同步。

**Acceptance Scenarios**:

1. **Given** 详情抽屉中一个 `applied` 状态的 job, **When** 用户打开「推进状态」, **Then** 下拉选项里只出现后端允许的目标(`test / oa / hr / offer / rejected / withdrawn`),不会出现 `screening / interview / wishlist` 等非法值。
2. **Given** 用户选中一个目标状态并提交, **When** 请求成功, **Then** 抽屉内状态徽章更新到新值,时间线顶部新增一条「`from → to` + 时间 + 备注」,列表中该行的徽章同步。
3. **Given** 用户选 `rejected` 或 `withdrawn` 但备注为空, **When** 提交, **Then** UI 给出"建议填一段备注(如反馈 / 撤回原因)"的软提示但仍允许提交,不阻塞。
4. **Given** 用户选了一个非法转换(如 `offer → applied`), **When** 提交, **Then** 抽屉内显示后端 409 返回的 `invalid_status_transition` 错误,不修改本地状态,提示明确告知"当前状态 X 不能转到 Y"。
5. **Given** 网络断开, **When** 用户提交状态推进, **Then** 抽屉内状态立即更新为新值(乐观),时间线新增一条标注「待同步」,网络恢复后由 outbox 自动重放到后端,成功后「待同步」标记消失。
6. **Given** 用户填的备注超过 500 字符, **When** 提交, **Then** UI 阻止提交并显示字符计数提示,不让请求出网。

---

### User Story 3 - 编辑职位信息 (Priority: P1)

求职者在详情抽屉里点击「编辑」,字段变成可编辑状态(公司、岗位、JD 链接、绑定的简历分支、`notes_md`)。保存后字段立即更新,列表行的公司 / 岗位 / 备注同步刷新。

**Why this priority**: 写错公司名 / JD 链接忘了贴 / 想换绑简历分支,是最常见的小修小补。没有编辑就只能删了重建,代价高且丢失时间线。

**Independent Test**: 在任意 job 的详情抽屉点编辑,改公司名为新值,保存,验证抽屉与列表中该字段都更新。

**Acceptance Scenarios**:

1. **Given** 详情抽屉中一个 job, **When** 用户点击「编辑」, **Then** 公司、岗位、JD 链接、绑定的简历分支、备注变为可编辑,状态 / 时间线 / 操作按钮暂时禁用。
2. **Given** 编辑态中, **When** 用户在"绑定简历分支"下拉中选了一个分支 / 选"(无)"解绑, **Then** 字段值正确反映。
3. **Given** 编辑态中, **When** 用户点击「保存」且通过校验, **Then** 字段回到只读,抽屉内显示更新后的值,列表行同步,Toast 提示「已更新」。
4. **Given** 编辑态中, **When** 用户把公司名清空(违反 `length BETWEEN 1 AND 100`), **Then** 保存按钮被禁用,字段下方显示内联校验错误。
5. **Given** 编辑态中, **When** 用户点击「取消」, **Then** 所有未保存的修改被丢弃,字段回到只读并保留原值。
6. **Given** 网络断开, **When** 用户点击保存, **Then** 抽屉字段保持新值(乐观),右上 Toast 提示「离线时已保存,网络恢复后同步」,网络恢复后由 outbox 重放。

---

### User Story 4 - 关联简历分支与 JD 链接 (Priority: P1)

求职者在新建 job 或编辑 job 时,可以填一个 JD 链接(`https?://` 校验)、可以下拉绑定一个简历分支(选 `(无)` 表示不绑)。详情面板里 JD 链接是可点击新窗口打开,绑定的简历分支显示名称并可点击跳转到该分支编辑器。

**Why this priority**: 这是 InterCraft 把"求职追踪"和"简历分支"两个模块咬合起来的关键连接点。Phase 2 后端 schema 已支持 `jd_url` 和 `branch_id`,本规范让前端真正消费它。

**Independent Test**: 新建一个 job 时填一个 JD URL、绑定一个简历分支,保存后详情面板里 JD 链接可点、简历分支名可点跳转到 `/resume/{branchId}`。

**Acceptance Scenarios**:

1. **Given** 用户在「添加职位」弹窗中, **When** 输入 JD 链接, **Then** 非 `https?://` 开头的输入给出内联校验错误,无法保存。
2. **Given** 用户在「添加职位」弹窗中, **When** 选了一个简历分支, **Then** 提交后该 job 记录上 `branch_id` 正确。
3. **Given** 详情抽屉中一个绑定了简历分支的 job, **When** 用户点击简历分支名, **Then** 跳转到 `/resume/{branchId}` 编辑器。
4. **Given** 详情抽屉中一个带 JD 链接的 job, **When** 用户点击链接, **Then** 在新标签页打开,目标 URL 与存储的 `jd_url` 一致。
5. **Given** 用户解除简历分支绑定, **When** 保存, **Then** 详情面板显示"(无)",列表行不显示简历分支名(列表本身只展示公司 / 岗位 / 状态 / 投递时间 / 备注)。

---

### User Story 5 - 列表筛选 / 搜索 / 排序 (Priority: P2)

求职者在列表页有 7 个状态 Tab(对应后端 7 个状态 + "全部"),在搜索框输入公司 / 岗位关键字,列表立即过滤。可以按"创建时间"或"最近状态变更时间"排序(默认后者倒序)。

**Why this priority**: 求职进行到中后期,一个用户可能同时追踪 20+ 个 job,没有筛选 / 搜索 / 排序就找不回。重要但排在 P1 闭环之后。

**Independent Test**: 创建一个 `applied`、一个 `test`、一个 `offer` 的 job,切到 `test` Tab,只看到那一个;在搜索框输入部分公司名,只看到匹配行。

**Acceptance Scenarios**:

1. **Given** 用户在 `/jobs`, **When** 看到状态 Tab, **Then** 选项是"全部 / 已投递 / 笔试 / OA / HR 面 / Offer / 已拒 / 已撤回",与后端 7 状态的中文名一一对应。
2. **Given** 用户点击 "Offer" Tab, **When** 列表刷新, **Then** 只展示 `status == "offer"` 的行,数量与 `/jobs?status=offer` 返回一致。
3. **Given** 用户在搜索框输入 `字节`, **When** 任意 Tab 下, **Then** 列表过滤为公司或岗位包含"字节"的行,大小写不敏感。
4. **Given** 用户清空搜索框, **When** 列表重新渲染, **Then** 全部当前 Tab 的行回归。
5. **Given** 用户切换"按创建时间 / 按最近状态变更"排序, **When** 列表重排, **Then** 行的顺序与后端返回顺序一致(默认按 `last_status_changed_at DESC`)。

---

### User Story 6 - 删除与回收 (Priority: P2)

求职者在详情抽屉点击「删除」,弹出确认(明确写出公司名 / 岗位,默认中文"删除后无法恢复,关联任务将被归档")。确认后 job 软删除(`deleted_at` 置位),关联的 `interview_prep` 任务被归档,列表移除该行,Toast 提示「已删除」。

**Why this priority**: 删除是必备但低频功能,排在 P1 之后。

**Independent Test**: 创建一个 job 后在详情抽屉点删除,确认,验证列表中该行消失、任务列表中对应 `interview_prep` 任务被归档(状态 `archived`)。

**Acceptance Scenarios**:

1. **Given** 详情抽屉中一个 job, **When** 用户点击「删除」, **Then** 弹出确认框,文案明确"删除『{company} · {position}』",按钮「取消」/「删除」。
2. **Given** 用户在确认框中点「删除」, **When** 请求成功, **Then** 抽屉关闭,列表移除该行,Toast 出现「已删除」并在 3 秒后消失。
3. **Given** 用户在确认框中点「取消」, **When** 弹窗关闭, **Then** 抽屉与列表状态保持原样。
4. **Given** 后端对该 job 还有未完成 `interview_prep` 任务, **When** 删除成功, **Then** 该任务状态变为 `archived`,在任务列表里不再出现于"待办"视图。

---

### User Story 7 - Offer 阶段附加信息 (Priority: P3)

当 job 状态进入 `offer` 时,详情面板的「Offer 信息」区出现:薪资范围(自由文本,200 字符内)、HR 联系人姓名、HR 联系方式(邮箱 / 微信 / 电话,自由文本)、签约截止日(日期选择器)。这些字段非 offer 状态下隐藏,但仍可在后端持久化(允许回填)。

**Why this priority**: Offer 是求职旅程的"金终点",但完整信息录入在 P1 闭环之后,不会阻塞求职追踪主流程。

**Independent Test**: 把一个 job 推进到 `offer`,验证详情面板出现"Offer 信息"区,字段为空可填;保存后再次打开依然保留。

**Acceptance Scenarios**:

1. **Given** 一个状态为 `offer` 的 job, **When** 用户打开详情面板, **Then** 出现「Offer 信息」区,包含薪资、HR 联系人姓名、HR 联系方式、签约截止日 4 个字段。
2. **Given** 一个非 `offer` 状态的 job(例如 `hr` / `rejected`), **When** 用户打开详情面板, **Then** "Offer 信息"区不显示。
3. **Given** 用户在 `offer` 状态下填了 4 个字段并保存, **When** 重新打开详情, **Then** 字段值保留。
4. **Given** 用户填的薪资范围超过 200 字符, **When** 尝试保存, **Then** UI 阻止并提示。

---

### Edge Cases

- **状态机冲突**: 两个浏览器标签页同时把同一 job 从 `applied` 推进到 `test` 和 `oa`,后到的请求 409,UI 用后端 error.envelope 中的 `details.from / to` 给出明确提示,不覆盖本地状态。
- **详情抽屉打开中,job 被另一端删除**: 抽屉内显示"该职位已不存在"占位,提供"返回列表"按钮。
- **离线期间多次状态推进**: 每条都进 outbox 按顺序重放,后端状态机依次校验(可能中间某条被业务规则拒绝,UI 在恢复后用红色 toast 告知哪一条失败,但已成功的保留)。
- **JD 链接包含特殊字符(空格、中文、井号)**: 提交前用 `URL.canParse` 二次校验,失败时给内联错误。
- **简历分支列表为空(用户没有创建分支)**: 「绑定简历分支」下拉只有"(无)"选项,引导文案指向简历中心。
- **时间线空(刚创建未改过状态)**: 抽屉里时间线区显示「暂无状态变更」,不报错。
- **后端 `status_history` schema 漂移**: 若某条 `from / to` 字段缺失,UI 用 "(未知)" 占位,绝不整行崩溃。
- **offer 状态从 `offer` 被改成 `rejected / withdrawn`**: 「Offer 信息」区不再显示,但已保存的数据仍在,后续再回到 `offer` 时回填出来。
- **列表为空时**: 显示占位卡"暂无求职记录 · 点击「添加职位」开始追踪",与现有 `Jobs.tsx:115-120` 行为一致。
- **删除最后一个 job 后回到列表**: 抽屉关闭,列表显示空状态,统计卡归零。
- **公司名 / 岗位超 100 字符**: 提交时按后端 `length BETWEEN 1 AND 100` 校验,UI 阻止并提示。
- **Job 关联的简历分支被软删**: 详情面板的简历分支名变成"已删除的分支(请解绑)",「解绑」按钮置灰时仍允许点击,点击后置 null 走 PATCH。

## Requirements *(mandatory)*

### Functional Requirements

#### 详情面板与时间线
- **FR-001**: System MUST 在 `/jobs` 列表的每一行可点击区域(公司 / 岗位单元格、整行 hover 状态)提供点击入口,点击后 1 秒内打开右侧抽屉显示该 job 的完整字段与时间线。
- **FR-002**: System MUST 渲染从 `GET /jobs/{id}/timeline` 返回的 `status_history` 数组(后端字段 `from / to / at / note`),按 `at` 倒序,最新一条在最上;空数组显示「暂无状态变更」占位。
- **FR-003**: System MUST 在抽屉内提供"关闭"(Esc / 抽屉外点击 / 右上角 ×),"编辑","推进状态","删除"四个操作;关闭时不重置列表的搜索 / Tab。
- **FR-004**: System MUST 抽屉打开期间,若后端该 job 已被另一端删除(GET 返回 404),抽屉显示「该职位已不存在」占位 + "返回列表" 按钮,不再渲染字段。

#### 状态机对齐与推进
- **FR-005**: System MUST 让前端"状态 Tab"、"状态徽章"、"推进状态下拉"三处使用的状态集,与后端 `JOB_TRANSITIONS` 与 `JOB_STATUS_CN` 完全一致(7 状态:`applied / test / oa / hr / offer / rejected / withdrawn`);删除前端 `wishlist / screening / interview`。
- **FR-006**: System MUST 在「推进状态」弹窗中,只列出从当前状态出发 `JOB_TRANSITIONS[old_status]` 允许的目标;非法目标不出现在 UI 中,后端 409 时给出 `invalid_status_transition` 的明确提示,不修改本地状态。
- **FR-007**: System MUST 在状态推进时,允许用户填 0–500 字符的备注(对应后端 `UpdateJobStatusInput.note`);超过 500 字符阻止提交并显示字符计数。
- **FR-008**: System MUST 在目标状态为 `rejected / withdrawn` 且备注为空时,给出软提示"建议填一段备注(如反馈 / 撤回原因)",但允许提交。

#### 编辑与字段
- **FR-009**: System MUST 在编辑模式下允许修改 `company` (1–100 字符)、`position` (1–100 字符)、`jd_url` (可选,`https?://` 校验)、`branch_id` (可选,`UUID | null`)、`notes_md` (可选,Markdown 纯文本 textarea),并以 PATCH `/jobs/{id}` 提交;前端 Job 类型字段名 `notes_md` 取代现有 `note`。
- **FR-010**: System MUST 在编辑模式下禁用状态 / 时间线 / 操作按钮;点击「保存」成功后字段回到只读、列表行同步;点击「取消」时丢弃未保存修改。
- **FR-011**: System MUST 在新建 job 时允许填 `company` (必填 1–100)、`position` (必填 1–100)、`jd_url` (可选)、`branch_id` (可选)、`notes_md` (可选);非 `https?://` 的 JD 链接阻止提交并内联报错。
- **FR-012**: System MUST 在详情面板的简历分支名渲染为可点击链接(指向 `/resume/{branchId}`);JD 链接渲染为可点击 `<a target="_blank" rel="noopener noreferrer">`。

#### 列表与排序
- **FR-013**: System MUST 提供 7 个状态 Tab("全部 / 已投递 / 笔试 / OA / HR 面 / Offer / 已拒 / 已撤回")+ 搜索框(对 `company / position` 大小写不敏感子串匹配);搜索词、Tab 状态保留在 URL query(`?tab=&q=`)以便分享与刷新。
- **FR-014**: System MUST 支持按"创建时间"或"最近状态变更时间"排序,默认后者倒序(`last_status_changed_at DESC`),与后端索引 `jobs_user_status_changed_idx` 保持一致。
- **FR-015**: System MUST 列表为空时显示「暂无求职记录 · 点击「添加职位」开始追踪」占位卡。

#### 删除
- **FR-016**: System MUST 删除前弹出确认框,文案明确"删除『{company} · {position}』· 删除后无法恢复,关联任务将被归档",按钮「取消」/「删除」;确认后调用 `DELETE /jobs/{id}`,成功后抽屉关闭、列表移除该行、Toast「已删除」,关联的 `interview_prep` 任务被后端归档。
- **FR-017**: System MUST 列表行 hover 时的删除按钮,与详情抽屉中的删除按钮,共用同一确认弹窗组件,行为一致。

#### Offer 阶段附加信息
- **FR-018**: System MUST `jobs` 表新增 4 个可选列:`offer_salary_text` (TEXT, 上限 200)、`offer_contact_name` (TEXT, 上限 100)、`offer_contact_info` (TEXT, 上限 200)、`offer_deadline_at` (TIMESTAMPTZ);以新 alembic 迁移落地。
- **FR-019**: System MUST 详情面板在 `status == "offer"` 时展示「Offer 信息」区,包含 4 个字段(薪资、HR 联系人姓名、HR 联系方式、签约截止日);其他状态隐藏该区。
- **FR-020**: System MUST 「Offer 信息」字段可独立保存(PATCH `/jobs/{id}` 提交 4 个字段),非 offer 状态下也可单独 PATCH 这 4 个字段(后端不限制);前端非 offer 状态下不展示但允许后端写入。
- **FR-021**: System MUST 薪资超 200 字符阻止保存并显示字符计数;HR 联系人姓名超 100 字符、联系方式超 200 字符同样阻止。

#### 离线 / 慢网兜底
- **FR-022**: System MUST 创建 / 改状态 / 编辑 / 删除 4 个写操作全部走 outbox 模式(参考 `src/lib/outbox/` 与 `backend/app/modules/outbox/`);离线时本地立即反映(乐观更新),网络恢复后由后端 worker 重放。
- **FR-023**: System MUST 时间线条目在尚未同步的状态下显示「待同步」徽标;重放成功后徽标消失,失败则给出红色 toast 告知哪一条失败。
- **FR-024**: System MUST 离线时禁用"删除"按钮(避免乐观删除后无法恢复);其他 3 个写操作允许。

#### 活动流(基础)
- **FR-025**: System MUST 详情面板的"近期活动"区(在时间线之上或并列)显示 `activities` 表中 `type IN ('job_created', 'job_status_changed')` 且 `payload_json->>'job_id' = {this.id}` 的最近 20 条,按 `occurred_at DESC` 排序;点击某条活动高亮对应时间线条目。
- **FR-026**: System MUST 不为"活动"功能新建数据——只读后端 `activities` 表,使用现有 `GET /activities?entity_type=job&entity_id={id}` 端点(若已有;否则在 plan 阶段决定扩展)。

#### 国际化与可访问性
- **FR-027**: System MUST 所有新增 / 修改文案使用简体中文,与现有 `Jobs.tsx` 与 `Sidebar.tsx` 一致(标题「求职追踪」、按钮「添加职位」「保存」「取消」「删除」「推进状态」「编辑」等)。
- **FR-028**: System MUST 所有新交互控件(抽屉内编辑 / 推进 / 删除按钮、状态 Tab、搜索框、列表行)暴露稳定 `data-testid` 供 E2E 选择。

### Key Entities *(include if feature involves data)*

- **Job**: 求职追踪记录(已在 `backend/app/modules/jobs/models.py` 落位,Phase 2)。本规范新增 4 个可选列 `offer_salary_text / offer_contact_name / offer_contact_info / offer_deadline_at`,并把前端 `note` 字段名统一为 `notes_md`(与后端 JobOut 一致)。状态机、status_history、last_status_changed_at、jd_url、branch_id、关联的 interview_prep 任务,行为均沿用。
- **StatusChange 条目**: 由后端 `Job.status_history` 数组承载,字段 `{from, to, at, note}`(后端实际命名,见 `service.py:84`)。前端 `JobTimeline` 组件与 `JobTimelineEntry` 类型同步改用此命名。
- **Outbox Entry**: 写操作的离线兜底,与 Phase 3 outbox 同构(`src/lib/outbox/`)。

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 用户在 `/jobs` 列表点击任意一行,1 秒内详情抽屉打开并显示完整字段与时间线;关闭抽屉后列表搜索词、Tab、滚动位置保持原样。
- **SC-002**: 状态推进请求的成功响应中位延迟 < 300 ms(本地网络,本地 Postgres);成功后抽屉 / 列表 / 时间线三处 UI 同步更新,无可见闪烁。
- **SC-003**: 100% 的状态推进操作,UI 上不会出现后端状态机拒绝的非法转换(连续 100 次操作中 0 次出现"前端让用户提交了后端 409 的请求")。
- **SC-004**: 离线(断网)状态下,创建 / 改状态 / 编辑 3 类写操作均能完成,UI 立即反映新值并标记「待同步」;网络恢复后 30 秒内 outbox 重放完成,「待同步」徽标消失,数据与后端一致。
- **SC-005**: 详情抽屉打开后 5 秒内再次发起同一 job 的 GET,缓存命中(从 React Query 缓存)且无网络请求;切换到其他 job 再切回,抽屉不出现空白闪烁。
- **SC-006**: 100% 的新增 / 修改文案为简体中文,与现有 `Jobs.tsx` / `Sidebar.tsx` 用语一致;不出现英文 UI 字符串。
- **SC-007**: 详情面板 / 列表行 / 状态 Tab / 推进下拉 / 删除按钮 / 编辑保存按钮 / 搜索框,100% 暴露稳定 `data-testid`,Playwright E2E 可零额外等待定位。
- **SC-008**: 详情面板中"Offer 信息"区在 `status == "offer"` 时必显示,在其他 6 个状态时绝不显示(连续 20 次切换 0 次错显)。
- **SC-009**: 删除一个有未完成 `interview_prep` 任务的 job 后,该任务在任务列表"待办"视图中消失(`status == "archived"`),与后端 `JobService.delete` 行为一致。
- **SC-010**: Playwright E2E 套件 1 次完整跑通以下故事:US1 抽屉打开与关闭、US2 状态推进(applied → test 含备注)、US3 编辑公司名、US4 绑定简历分支并跳转、US5 切 Tab 与搜索、US6 删除带确认、US7 Offer 信息展示。

## Assumptions

- 后端 `Job` 实体、状态机、7 端点(`list / create / get / patch / updateStatus / delete / stats / timeline`)在 Phase 2 已落地,本规范不重写后端业务逻辑,只新增 4 个可选列、修正 Pydantic 字段命名一致性、保证 `PATCH /jobs/{id}` 接受 `notes_md` 与 4 个 Offer 字段。
- 后端 `activities` 表与 `GET /activities` 端点已就位(Phase 2),Job 模块的活动流视图通过 `?entity_type=job&entity_id={id}`(若后端已支持 entity 过滤)或客户端按 `payload_json->>'job_id'` 过滤实现;若后端未支持 entity 过滤,Plan 阶段需扩展 `/activities` 端点(小改动,本规范默认它会扩展)。
- 前端现有 `JobTimeline` 组件按 `{from_status, to_status, changed_at, note}` 渲染,本规范让它改用后端真实字段名 `{from, to, at, note}`;同时 `JobRepository.JobTimelineEntry` 类型与 `JobTimeline` 组件同步。
- 前端现有 `JobRepository.Job.note` 改为 `notes_md`,Jobs.tsx 旧引用(`job.note`)同步替换;`UpdateJobStatusInput.note`(状态变更备注)字段名不变,语义区别需要代码注释 + 测试明确区分。
- 简历分支下拉数据源为 `useResumeBranches()`(已存在,Phase 1);简历中心删除某分支后,Job 详情面板的处理(占位文案 + 解绑)由本规范 FR-012 末条款保障。
- 离线 outbox 复用 Phase 3 模式,本规范不重新设计;`create / updateStatus / patch / delete` 4 个 mutation 加入 outbox 队列(参考 `src/lib/outbox/db.ts` 的 `enqueue`)。
- 不引入新的前端路由;`/jobs` 单页 + 抽屉(右侧滑出),URL 同步 Tab / 搜索词,详情不进入单独路由(避免和"详情直链"等扩展冲突)。
- 列表分页:Phase 2 `list_jobs` 默认 `limit=20`,本规范不引入 cursor 分页 UI,默认 20 条上限已经够 P1 范围;后续可扩展(留待 Phase 6 或独立 feature)。
- 国际化:全简体中文(产品当前语言),不引入 i18n 框架。
- Job 与 Interview Session 的双向链接(`interview_sessions.job_id`)已存在(Phase 4 数据模型),但 Phase 4 端点未对外暴露"按 job 查 interview_sessions";本规范不强制实现"按 job 列出面试报告"入口,留待后续 feature。
