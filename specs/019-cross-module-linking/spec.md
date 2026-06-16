# Feature Specification: Cross-Module Linking (Job ↔ Resume ↔ Interview, Interview → Error Book)

**Feature Branch**: `019-cross-module-linking`

**Created**: 2026-06-17

**Status**: Draft

**Input**: User description — 把简历中心、求职追踪、模拟面试三个模块之间的联动串起来,并打通"模拟面试 → 个人画像 → 错题本"的内容沉淀链路。

## Background

当前四个模块各自已经落地:

- **求职追踪 (`jobs`, specs/014)**: 已支持 CRUD、状态机、`branch_id` 外键、`jd_url`、`notes_md`。详情面板 / 时间线 / 状态推进 / 编辑 / 绑定简历分支走 outbox。
- **简历中心 (`resume_branches`, Phase 1)**: 已支持分支 CRUD、COW 继承、`is_main / is_pinned / status`。`CreateBranchInput` 只接受 `name / company / position / parent_id / is_main`,没有"招聘需求"或"base 地"字段。
- **模拟面试 (`interview_sessions`, Phase 4)**: 已跑通 5 轮 WS 流式 + LangGraph。`InterviewSession` 表只有 `branch_id / position / company / mode / status / overall_score`,**没有 `job_id` 字段**,也没有把岗位的"招聘需求 / base 地"预填进 GraphState。
- **个人画像 (specs/006) + 模拟面试 (Phase 4 ability_diagnose)**: 已经实现"面试评分 → 能力维度聚合(时间衰减加权)",不需要重写。
- **错题本 (specs/016, `error_questions`)**: 表已经有 `source_session_id` 外键,但当前是用户手动录入;**没有任何"从面试自动沉淀"的逻辑**。

存在的"模块间空隙":
1. **从岗位起一份简历**: 现在必须先在 `/resume/new` 选 parent、再到 `/jobs` 详情手动绑定 `branch_id`;中间没有"以岗位为基础创建分支"的快捷入口,岗位的 `requirements_md / base_location` 也没法传到分支元数据。
2. **从岗位开一场面试**: 现在 InterviewList 只接受手填 `position / company`,**不能选 Job**;也无法把岗位的 `requirements_md` 喂给 `question_gen` 节点做针对性提问。
3. **面试题 → 错题本**: 当前每题答完没有钩子把低分题自动沉淀到 `error_questions`;用户只能事后手抄。
4. **岗位字段不够用**: 用户登记岗位时只能填 `company / position / jd_url / notes_md`,base 地、招聘需求、岗位类型、薪资范围、headcount 都塞在 `notes_md` 里无法结构化查询,后续画像分析、面试针对性提问都拿不到。

本规范把这四条空隙一次性补齐,作为 P1 切片落地,**只覆盖联动层**(不重写现有模块内部)。

### 范围

**In-scope(本次增量联动层)**:
- `jobs` 表新增 5 个字段:`base_location / requirements_md / employment_type / salary_range_text / headcount`。
- `interview_sessions` 表新增 1 个字段:`job_id`(指向 `jobs.id`,ON DELETE SET NULL)。
- 新建简历分支时,可选择"基于岗位创建",把岗位元数据自动预填。
- Job 详情面板新增 CTA「为该岗位创建简历分支」「为该岗位开始模拟面试」。
- 模拟面试每题评分落库时,若 `score < 6`,自动在 `error_questions` 创建一行(frequency=3, status=fresh, source_session_id = 当前 session.id)。
- Error Book 列表新增筛选"来自面试自动生成"与单条"移除自动来源"操作(软删除原 session 来源,只清溯源标记,保留错题记录)。

**Out-of-scope(留给后续 feature)**:
- 个人画像聚合逻辑(006 + Phase 4 已就位,本规范不复述)。
- 邮件解析 / 自动入库岗位、Offer 谈判追踪、面试日程与日历集成(014 已记为范围外)。
- 简历分支元数据新增 `requirements_md / base_location` 字段(本规范只把这两个值通过"基于岗位创建"流程预填到分支的 `name / company / position`,不增加 ResumeBranch 列)。

### 与现有规范的关系

- **014-job-tracking**: 新增的 5 个 Job 字段在 014 上扩列,迁移随本 feature 一起出;`CreateJobInput / PatchJobInput / JobOut` 同步扩字段;**不修改** 014 的状态机、详情抽屉时间线、活动流等任何逻辑。
- **016-error-book-completion**: 复用现有 `error_questions` 表与 Recall/Reset 流程;新增"按来源筛选"与"移除自动来源"两个前端 affordance + 一个 `PATCH /error-questions/{id}/clear-source` 端点;**不改** 016 的频率 / 状态机。
- **006-personal-ability-profile**: 不动;链路确认(见 §"端到端联动示意")。

## Clarifications

### Session 2026-06-17

- Q: `jobs` 表需要新增哪些字段?→ A: 完整字段集。5 个新字段:`base_location` (TEXT, 1–50 字符, 必填)、`requirements_md` (TEXT, ≤5000 字符, 可选, Markdown 富文本)、`employment_type` (TEXT, 枚举 `internship / campus / experienced / contract / unspecified`, 默认 `unspecified`)、`salary_range_text` (TEXT, ≤100 字符, 可选, 自由文本)、`headcount` (INTEGER, ≥1, 可选)。
- Q: "从岗位创建简历分支"的入口位置?→ A: 双向。Job 详情面板基本信息区放「为该岗位创建简历分支」CTA(仅当 `branch_id IS NULL` 时显示);Topbar「新建简历」下拉里新增「基于岗位创建」,下拉选 job 后跳到 `/resume/{newBranchId}?source_job_id={jobId}` 并把 job 的 company/position 预填到分支 `name`,`requirements_md` 预填到分支 `notes_md`(分支无该字段则不入库,只是初始空白草稿)。
- Q: "从岗位开始模拟面试"的入口与简历分支约束?→ A: Job 详情面板放「为该岗位开始模拟面试」CTA,**仅当 `branch_id IS NOT NULL` 时可点击**;点击后调用 `POST /interview-sessions`,body 同时携带 `job_id = job.id` 与 `branch_id = job.branch_id`,服务端校验二者同属该 user;前端跳到 InterviewLive,Intake 阶段 `position / company / base_location / requirements_md` 全量预填,`question_gen` 节点 prompt 注入 `requirements_md` 关键段(裁 1500 token 内)。
- Q: 错题自动沉淀策略?→ A: 按分数阈值自动 + 用户复审。每次 `score` 节点写入 `interview_questions.score` 后,后端同步触发 `ErrorQuestionService.maybe_create_from_question(session_id, question_id, score)`,若 `score < 6` 则创建 `error_questions` 记录:`frequency=3 / status=fresh / source_session_id = session.id / source_question_id` 新增列指向 `interview_questions.id`;错题本列表新增 `source` 筛选(`auto / manual / all`);单条详情面板新增**两个**操作——「移除自动来源」(调用 `PATCH /error-questions/{id}/clear-source`,仅清空 `source_session_id / source_question_id`,错题保留转为手动)与「删除」(调用 `DELETE /error-questions/{id}`,复用 016 现有删除流程,带确认弹窗),让用户既能"清溯源保留题目"也能"直接丢弃"。UI 显示一行小字"来自 {company} · {position} · {interview_started_at}"提示溯源。
- Q: `interview_sessions` 与 job 关联字段命名?→ A: 使用 `job_id`,与同表 `branch_id` 命名风格一致(简洁 FK 风格);不采用 `source_job_id` 后缀。
- Q: 个人画像联动是否在本 SPEC 重新实现?→ A: 不实现。Phase 4 ability_diagnose → 006 时间衰减加权链路已就位,本规范在文字上确认,不写实现细节。
- Q: 范围边界?→ A: 仅增量联动层。不重写 014 / 016 / 006 / Phase 4 任何模块内部逻辑,只在不破坏现有契约的前提下加字段、加端点、加 UI 入口。
- Q: SPEC 命名 / 位置?→ A: `specs/019-cross-module-linking/spec.md`,与现有 feature spec 同构。
- Q: SPEC 语言?→ A: 全中文,与现有 spec 一致;FR/SC 编号保留英文 key。

## User Scenarios & Testing *(mandatory)*

### User Story 1 — 登记完整岗位信息 (Priority: P1)

求职者在「添加职位」弹窗里填完整岗位信息(公司、岗位、base 地、招聘需求、岗位类型、薪资范围、headcount),保存后在 Job 详情面板看到这些字段;后续的简历分支、模拟面试、错题本都能读取到。

**Why this priority**: base 地 / 招聘需求 / 岗位类型是后续所有联动的前置数据源。没有结构化字段,后面所有"基于岗位的简历 / 基于岗位的面试 / 画像归因"都是空中楼阁。

**Independent Test**: 在 `/jobs` 新建一个 job,填 `base_location=北京`、`requirements_md` 200 字 Markdown、`employment_type=experienced`,保存后刷新,详情面板显示这三项;再次打开编辑,字段值保留。

**Acceptance Scenarios**:

1. **Given** 用户在「添加职位」弹窗, **When** 填必填项 `company / position` 并填 `base_location`, **Then** 保存后 `jobs.base_location` 入库,JobOut 返回该字段,详情面板显示「base 地:北京」。
2. **Given** 用户填了 `requirements_md`(200–5000 字符 Markdown), **When** 保存, **Then** 后端接受,详情面板渲染为 Markdown(标题加粗、列表项缩进);非 Markdown 文本原样显示。
3. **Given** 用户从下拉里选 `employment_type=experienced`, **When** 保存, **Then** 详情面板「岗位类型」徽标显示"社招",与后端枚举值一致。
4. **Given** 用户填了 `salary_range_text` 超过 100 字符, **When** 提交, **Then** UI 阻止并提示字符计数;`headcount` 填 0 或负数也阻止。
5. **Given** 用户填了 `base_location` 超过 50 字符, **When** 提交, **Then** UI 阻止并提示。
6. **Given** 用户没填 `requirements_md`, **When** 保存, **Then** 字段为 NULL,详情面板显示「未填写招聘需求」占位;**不阻塞**保存。
7. **Given** 用户编辑既有 job 改了 `base_location`, **When** 保存, **Then** 详情面板与列表行(如列表展示)同步更新,无需刷新页面。

---

### User Story 2 — 从岗位创建简历分支 (Priority: P1)

求职者在 Job 详情面板看到「为该岗位创建简历分支」CTA(仅当 `branch_id IS NULL`),点击后跳到分支编辑器,分支名自动预填为「{company} · {position}」,并把 `requirements_md` 复制到分支草稿(若分支无该字段则不入库,只作为 UI 引导文案);保存分支后,`jobs.branch_id` 自动回填为新分支 id。Topbar「新建简历」下拉里也能选「基于岗位创建」,行为一致。

**Why this priority**: 这是用户描述的"Job → Resume"主链路入口。缺失这个 CTA,用户必须手工复制岗位信息到简历分支,既慢又容易出错。

**Independent Test**: 在一个 `branch_id IS NULL` 的 job 上点「为该岗位创建简历分支」,验证:跳转 `/resume/{newId}?source_job_id={jobId}`、分支编辑器显示预填的 `name / company / position`、保存分支后 `/jobs` 详情面板的「绑定的简历分支」字段由"(无)"变为新分支名。

**Acceptance Scenarios**:

1. **Given** Job 详情面板中一个 `branch_id IS NULL` 的 job, **When** 用户看到基本信息区, **Then** 「为该岗位创建简历分支」CTA 可见,文案清晰;若已绑定分支,该 CTA 隐藏,改为「换绑简历分支」下拉(复用 014 现有逻辑)。
2. **Given** 用户点击「为该岗位创建简历分支」, **When** 跳转, **Then** URL 为 `/resume/{newBranchId}?source_job_id={jobId}`,分支编辑器中 `name` 输入框预填为「{company} · {position}」,`company` 预填为 `{company}`,`position` 预填为 `{position}`,用户可在原字段上直接修改。
3. **Given** 用户在分支编辑器看到预填, **When** 保存分支, **Then** `POST /resumes/branches` 返回 `branch.id`,前端用 `PATCH /jobs/{jobId}` 把 `branch_id` 设为该值(走 014 outbox);若 PATCH 失败,前端显示 Toast「简历已保存,但岗位绑定失败,请到求职追踪里手动绑定」。
4. **Given** Topbar「新建简历」下拉, **When** 用户选「基于岗位创建」并从二级下拉选一个 job, **Then** 行为与从 Job 详情进入完全一致(同一 URL 模板)。
5. **Given** `requirements_md` 超过 200 字, **When** 进入分支编辑器, **Then** 编辑器顶部显示一行折叠提示「本岗位的招聘需求(点击展开复制)」,展开后是只读 Markdown,用户可手动复制到分支 blocks 中(不强制注入到 `notes_md`——分支无该字段,避免误存)。
6. **Given** 用户从分支编辑器返回 Job 详情, **When** 查看基本信息区, **Then** 「绑定的简历分支」字段显示新分支名(可点击跳转 `/resume/{branchId}`)。
7. **Given** 用户中途关闭分支编辑器没保存, **When** 再次进入 Job 详情, **Then** Job 的 `branch_id` 仍为 NULL,CTA 仍显示,无副作用。

---

### User Story 3 — 从岗位开始模拟面试 (Priority: P1)

求职者在 Job 详情面板看到「为该岗位开始模拟面试」CTA,**仅当 `branch_id IS NOT NULL` 时可点击**。点击后,后端创建 `interview_sessions` 记录(`job_id / branch_id` 同步落库),前端跳到 InterviewLive,Intake 阶段 `position / company / base_location / requirements_md` 全量预填,`question_gen` 节点 prompt 注入 `requirements_md` 关键段。

**Why this priority**: 这是用户描述的"Job → Interview"主链路。岗位的招聘需求是 AI 出题的依据,base 地影响公司画像推荐,没有这个联动 AI 就是"无的放矢"。

**Independent Test**: 在一个 `branch_id IS NOT NULL` 的 job 上点「为该岗位开始模拟面试」,验证:`POST /interview-sessions` 请求 body 含 `job_id / branch_id`,返回的 session 入库后 `job_id` 字段正确;InterviewLive Intake 页 4 个字段都预填;完成 5 轮后查看 GraphState,`requirements_md` 出现在 `question_gen` 节点的 prompt 上下文。

**Acceptance Scenarios**:

1. **Given** Job 详情面板中一个 `branch_id IS NOT NULL` 的 job, **When** 用户看到基本信息区, **Then** 「为该岗位开始模拟面试」CTA 可见且可点击。
2. **Given** Job 详情面板中一个 `branch_id IS NULL` 的 job, **When** 用户看到基本信息区, **Then** 「为该岗位开始模拟面试」CTA 可见但置灰,鼠标悬停提示"请先绑定简历分支";不可点击。
3. **Given** 用户点击可点击的 CTA, **When** 调用 `POST /interview-sessions`, **Then** body 含 `job_id = job.id` 与 `branch_id = job.branch_id`,两个字段都被服务端校验属于当前 user;成功 200 后跳转 InterviewLive。
4. **Given** InterviewLive 进入 Intake 阶段, **When** 用户看到表单, **Then** `position` 预填 job.position、`company` 预填 job.company、`base_location` 预填 job.base_location(只读,带"(来自岗位信息)"灰色说明)、`requirements_md` 以折叠卡片形式展示供用户参考(只读)。
5. **Given** 用户修改了 Intake 阶段任意预填字段(如改成另一家公司的面试), **When** 提交, **Then** 入库以用户修改后值为准,不影响 job 表原值。
6. **Given** `question_gen` 节点执行, **When** LLM prompt 构造, **Then** 注入 `requirements_md` 前 1500 token(超出截断)作为"context",并在 GraphState 标记 `requirements_provided=true`;后续 report 节点汇总"该面试基于以下招聘需求"列出原始 `requirements_md` 摘要。
7. **Given** 同一用户多次从同一 job 启动面试, **When** 提交, **Then** 每次都创建新的 `interview_sessions` 行(不与上一次共享),`job_id` 指向同一 job。
8. **Given** `branch_id` 已被软删, **When** 用户点击 CTA, **Then** 后端 422 拒绝(分支不存在);前端 Toast「简历分支已删除,请先在求职追踪里重新绑定」。

---

### User Story 4 — 模拟面试自动沉淀错题 (Priority: P1)

求职者完成 5 轮模拟面试后,所有 `score < 6` 的题目自动在 `error_questions` 创建错题记录,`frequency=3 / status=fresh / source_session_id = session.id / source_question_id = question.id`;错题本列表筛选"来自面试自动生成"可看到这些题目;详情面板提供两个操作——「移除自动来源」(清空溯源标记,错题保留转为手动)与「删除」(复用 016 现有删除流程,带确认弹窗,直接从错题本消失),让用户既能"清溯源保留题目"也能"直接丢弃"。

**Why this priority**: 错题本是用户描述的"面试 → 个人画像 → 错题本"闭环的最后一环。不自动沉淀,用户就只能事后手抄,体验断裂。

**Independent Test**: 完成一场 5 轮面试(其中第 2、4 题故意答错或低分),结束后查 `error_questions` 表,该场 session 的 `score < 6` 题目都已创建错题记录,且 `source_session_id` 指向该 session;在 `/error-book` 选筛选「来自面试」,看到这些错题,详情面板显示「来自 XX 公司 · YY 岗位 · HH:mm」;点「移除自动来源」,刷新页面后该错题的 source 标签消失,但题目仍在列表中。

**Acceptance Scenarios**:

1. **Given** `interview_questions.score` 由 score 节点写入且 `score < 6`, **When** 持久化完成, **Then** 后端同步调用 `ErrorQuestionService.maybe_create_from_question`,在 `error_questions` 插入一行:`frequency=3 / status=fresh / source_session_id=session.id / source_question_id=question.id / dimension=question.dimension / question_text=question.text / answer_text=answer.body / reference_answer_md=feedback.reference_answer`。
2. **Given** 同一题因 retry / 重评分导致 `score` 多次写入, **When** 已存在同 `source_question_id` 的错题, **Then** **不重复创建**(UPSERT 或幂等检查,后端用 `SELECT ... FOR UPDATE` 或唯一约束 `UNIQUE(source_question_id) WHERE source_question_id IS NOT NULL`);只更新 `score / answer_text / reference_answer_md`。
3. **Given** 用户在 `/error-book` 列表, **When** 选筛选「来自面试自动生成」, **Then** 只显示 `source_session_id IS NOT NULL` 的错题;选「手动录入」显示 `source_session_id IS NULL`;默认「全部」。
4. **Given** 一条 `source_session_id IS NOT NULL` 的错题详情, **When** 用户点击「移除自动来源」, **Then** 调用 `PATCH /error-questions/{id}/clear-source`,后端将 `source_session_id / source_question_id` 置 NULL,`updated_at` 更新;前端 Toast「已移除自动来源」,该错题不再显示"来自 XX 公司"溯源文案,默认列表仍可见(已转为手动来源)。
4a. **Given** 一条 `source_session_id IS NOT NULL` 的错题详情, **When** 用户点击「删除」, **Then** 复用 016 的确认弹窗(文案「删除『来自 {company} · {position} · {interview_started_at} 的错题』· 删除后无法恢复」),确认后调用 `DELETE /error-questions/{id}`,错题从默认列表移除;取消则无副作用。
4b. **Given** 一条 `source_session_id IS NULL` 的错题详情, **When** 用户查看操作区, **Then** 不显示「移除自动来源」按钮;「删除」按钮文案保持 016 既有写法("删除『{question_text 前 30 字}』")。
4c. **Given** 用户想"快速丢弃"自动错题不想确认, **When** 看到详情面板, **Then** 「移除自动来源」与「删除」均需一次操作(前者直接执行,后者弹确认);不提供"无确认直接删除"的快捷入口(避免误删)。
5. **Given** 用户从错题详情跳转源面试(本规范**不**做跳转 UI,只在详情面板显示一行静态文案"来自 {company} · {position} · {interview_started_at 格式化}"),**When** 想看面试详情, **Then** 文案清晰,但不提供跳转链接(避免引入跨模块路由依赖)。
6. **Given** 阈值可配置, **When** 在 `backend/app/modules/errors/service.py` 中常量 `AUTO_ERROR_THRESHOLD = 6`, **Then** 修改该常量即可全局生效;不为单用户暴露配置 UI(避免在产品上引入细粒度开关)。
7. **Given** 面试 session 被软删, **When** 用户查错题本, **Then** 错题仍可见(因为 `error_questions.deleted_at` 是独立的);「移除自动来源」操作仍可用,避免 session 删除导致错题失去溯源上下文。
8. **Given** 错题通过 Recall 推进到 mastered(`frequency=0`), **When** 用户想重新练习, **Then** 「重置为未掌握」(016 已实现)行为不变,与「移除自动来源」互不干扰。

---

### User Story 5 — 端到端联动冒烟 (Priority: P2)

求职者在一天内完成"新建岗位 → 基于岗位创建简历分支 → 编辑分支 → 基于岗位开一场模拟面试 → 答完 5 轮 → 错题本自动沉淀 → 个人画像刷新"完整链路,中间不出现断点、错配或回退到手动填字段。

**Why this priority**: 这是验证前 4 个 User Story 联动正确的端到端冒烟,作为本规范整体完成度的最终判定。

**Independent Test**: 自动化 E2E 脚本一次跑完上述链路,验证每个节点状态字段(`job.base_location / branch_id / interview.job_id / error_questions.source_session_id / ability_dimensions.updated_at`)正确写入,且前端 6 个页面(`/jobs / /resume/{id} / /interview/{id}/live / /interview/{id}/report / /error-book / /profile`)均能看到正确数据。

**Acceptance Scenarios**:

1. **Given** 全新注册用户, **When** 完整走完 5 步联动, **Then** 每个步骤页面无 console error,后端日志无 4xx/5xx。
2. **Given** 用户在 Job 详情看到 `base_location / requirements_md / employment_type` 都填了, **When** 进入基于该 job 的面试, **Then** Intake 页 4 个字段(预填 3 + 参考卡片 1)与岗位一致。
3. **Given** 面试完成后 1 分钟内, **When** 用户查 `/profile`, **Then** 至少有一个能力维度被更新(`updated_at` 在面试完成时间之后)。
4. **Given** 面试中至少有 1 题 `score < 6`, **When** 用户查 `/error-book`, **Then** 该题出现在列表,详情显示溯源文案。

### Edge Cases

| # | 场景 | 预期行为 |
|---|---|---|
| E1 | 用户在「添加职位」里填了 `requirements_md` 含 50KB 的粘贴文本 | UI 阻止,后端 Pydantic `max_length=5000` 兜底,提示"招聘需求过长" |
| E2 | 用户从 Job 详情 CTA 创建简历分支,中途断网 | 简历分支保存走 Phase 3 outbox;`PATCH /jobs/{id}` 同步入 outbox;网络恢复后两条都重放成功 |
| E3 | 用户在 Branch 编辑器改了 `name`(与预填不一致),保存 | 分支以用户值为准;`PATCH /jobs/{id}` 仍把 `branch_id` 设为新分支 |
| E4 | 用户从 Job A 的详情开面试,Intake 页改了 `company = B` | 入库 interview 的 `company = B`,但 `job_id` 仍指向 A;report 页展示"该面试基于岗位 A,但用户改写了公司字段"提示 |
| E5 | `question_gen` 节点接收到 `requirements_md` 为 NULL | 行为与没传一样,prompt 不注入"context",GraphState 标记 `requirements_provided=false` |
| E6 | `requirements_md` 超 1500 token | 后端用 `tiktoken` 截断前 1500 token,记录截断日志;前端展示"招聘需求已截断" |
| E7 | 同一题在面试中重答(用户改答案)并重新评分 | `score` 节点多次写 `interview_questions.score`;错题 UPSERT,以最新 `score / answer_text` 为准 |
| E8 | 用户手动在「错题本」页面手动录入一条错题,然后面试里有相同题被自动沉淀 | 两条独立存在(手动 `source_session_id = NULL`,自动有 `source_session_id`),列表都展示 |
| E9 | 用户的 Job 被软删,但绑定的简历分支还在 | `interview_sessions.job_id` ON DELETE SET NULL,但 `branch_id` 仍指向分支;InterviewLive 仍可继续 |
| E10 | 用户从错题本「移除自动来源」后,该场面试又有同题被自动沉淀 | 不重复创建(因为已移除的 source_question_id 已被清空);若评分再次触发,会创建**新一条**错题(`source_question_id` 重新被占用,等价于历史已移除) |
| E11 | LLM 返回 `score=5`,但格式异常被 score 节点 fallback 默认 `score=0` | `score=0 < 6`,错题自动沉淀,以 fallback 后的值落库 |
| E12 | 用户删除某场面试后,该场所有自动沉淀的错题仍带 `source_session_id` | 错题独立软删(`error_questions.deleted_at`),不依赖 session;UI 仍展示溯源文案(直到用户主动「移除自动来源」) |
| E13 | `interview_sessions.job_id` 字段已存在(误报) | migration 检查 IF NOT EXISTS,避免破坏性变更 |
| E14 | 求职者在不同设备打开同一 job 详情,同时点 CTA 创建分支 | 服务端不锁,允许两条;前端根据 409/200 区分,以最后一个 PATCH 成功值为准 |
| E15 | Topbar「基于岗位创建」下拉里岗位数 > 100 | 走搜索下拉(参考 `useResumeBranches` 的下拉实现),不全量渲染 |

## Requirements *(mandatory)*

### Functional Requirements

#### Job 字段扩展
- **FR-001**: System MUST 在 `jobs` 表新增 5 个可选列:`base_location` (TEXT, NOT NULL 默认 `''`,长度 1–50)、`requirements_md` (TEXT, 可选,长度 ≤5000)、`employment_type` (TEXT, NOT NULL 默认 `unspecified`,枚举 `internship / campus / experienced / contract / unspecified`)、`salary_range_text` (TEXT, 可选,长度 ≤100)、`headcount` (INTEGER, 可选, ≥1),以新 alembic 迁移落地。
- **FR-002**: System MUST 在 `CreateJobInput / PatchJobInput / JobOut / JobListOut` 同步增加上述 5 字段,Pydantic 校验:`base_location` 长度 1–50(空字符串视为未填);`requirements_md` ≤5000;`salary_range_text` ≤100;`headcount` ≥1;`employment_type` ∈ 5 枚举值。
- **FR-003**: System MUST 在 `GET /jobs / GET /jobs/{id}` 响应中返回全部 5 字段,前端 Jobs 详情面板基本信息区按"base 地 / 招聘需求(折叠) / 岗位类型 / 薪资范围 / headcount"顺序展示。
- **FR-004**: System MUST 在「添加职位」弹窗与编辑模式下提供这 5 个字段的输入控件(文本 / Markdown textarea / 下拉枚举 / 数字),并复用 014 的字符计数提示与 PATCH outbox 流程。

#### Job → Resume 双向入口
- **FR-005**: System MUST 在 Job 详情面板基本信息区新增两个 CTA:「为该岗位创建简历分支」「为该岗位开始模拟面试」;前者仅在 `branch_id IS NULL` 时可见可点击,后者在该字段非空时可见可点击(详见 FR-013)。
- **FR-006**: System MUST 在 Topbar「新建简历」下拉里新增「基于岗位创建」二级入口,弹出的下拉列出当前 user 的所有 job(默认按 `last_status_changed_at DESC`,可搜索),用户选择一个 job 后跳转 `/resume/{newBranchId}?source_job_id={jobId}`。
- **FR-007**: System MUST 在前端分支编辑器(`/resume/{id}`)中,若 URL 含 `source_job_id`,自动调用 `GET /jobs/{jobId}` 取岗位元数据,并把 `name` 输入框预填为「{company} · {position}」(用户可改),`company / position` 输入框预填为岗位值;若 `requirements_md` 存在且 ≥50 字符,编辑器顶部展示折叠提示卡「本岗位的招聘需求(点击展开复制)」。
- **FR-008**: System MUST 在用户保存从 Job 创建的分支后,前端用 `PATCH /jobs/{jobId}` 把 `branch_id` 设为新分支 id;若该 PATCH 失败(outbox),前端显示 Toast「简历已保存,但岗位绑定失败,请到求职追踪里手动绑定」;不阻塞简历保存成功状态。

#### Resume → Interview 单向入口(Job 详情启动)
- **FR-009**: System MUST 在 `interview_sessions` 表新增 1 列 `job_id`(UUID,可空,FK `jobs.id` ON DELETE SET NULL),并加索引 `interview_sessions_job_id_idx`;以新 alembic 迁移落地。
- **FR-010**: System MUST 在 `InterviewSessionCreate / InterviewSessionStartOut / InterviewSessionOut / InterviewSessionListOut` 同步增加 `job_id` 字段;`POST /interview-sessions` 接受 `job_id` 可空,与 `branch_id` 独立校验。
- **FR-011**: System MUST 在 Job 详情面板的「为该岗位开始模拟面试」CTA 上,点击后调用 `POST /interview-sessions`,body 同时携带 `job_id = job.id` 与 `branch_id = job.branch_id`;服务端校验二者同属当前 user,否则 422。
- **FR-012**: System MUST 在 InterviewLive Intake 阶段,从后端取 `interview_sessions.job_id` 对应的 `jobs.{position, company, base_location, requirements_md}`,把前 3 个字段预填表单(只读,带说明),把 `requirements_md` 以折叠卡片形式展示(只读);用户可改写,改写后入库以用户值为准。
- **FR-013**: System MUST 在 LangGraph `question_gen` 节点 prompt 构造时,从 GraphState 取 `requirements_md`(若有),用 `tiktoken` 截断前 1500 token,作为"context"段注入;GraphState 标记 `requirements_provided=true/false`。report 节点在最终汇总里展示"该面试基于以下招聘需求(摘要)"列出原始 `requirements_md` 前 500 字符。
- **FR-014**: System MUST 在前端 Job 详情面板 `branch_id IS NULL` 时,把「为该岗位开始模拟面试」CTA 置灰并加 tooltip"请先绑定简历分支"。

#### Interview → Error Book 自动沉淀
- **FR-015**: System MUST 在 `error_questions` 表新增 1 列 `source_question_id`(UUID,可空,FK `interview_questions.id` ON DELETE SET NULL),加索引;并加 `UNIQUE(source_question_id) WHERE source_question_id IS NOT NULL` 部分唯一约束;以新 alembic 迁移落地。
- **FR-016**: System MUST 在 `score` 节点持久化 `interview_questions.score` 后,同步调用 `ErrorQuestionService.maybe_create_from_question(session_id, question_id, score)`,若 `score < AUTO_ERROR_THRESHOLD`(默认 6),在 `error_questions` UPSERT 一行:`frequency=3 / status=fresh / source_session_id=session.id / source_question_id=question.id / dimension=question.dimension / question_text=question.text / answer_text=answer.body / reference_answer_md=feedback.reference_answer`(若有);重复触发以 UPSERT 为准(由部分唯一约束保证)。
- **FR-017**: System MUST 新增 `PATCH /error-questions/{id}/clear-source` 端点,把 `source_session_id / source_question_id` 置 NULL,`updated_at` 更新;前端 ErrorBook 详情面板的「移除自动来源」按钮调用该端点。「删除」操作复用 016 已有的 `DELETE /error-questions/{id}` 端点(软删除,`deleted_at` 置位),**不新增** delete 端点。
- **FR-018**: System MUST 在 `ErrorQuestionOut` 增加 `source_session_id / source_question_id` 字段输出;在 `ErrorQuestionListOut` 接受 `source` 查询参数(`auto / manual / all`,默认 `all`),后端按 `source_session_id IS NOT NULL / IS NULL` 过滤。
- **FR-019**: System MUST 在前端 ErrorBook 列表筛选区增加 3 选项(全部 / 来自面试 / 手动录入);在错题详情面板若 `source_session_id IS NOT NULL`,显示一行静态文案「来自 {company} · {position} · {interview_started_at 格式化为 YYYY-MM-DD HH:mm}」+「移除自动来源」按钮 +「删除」按钮(复用 016 删除确认弹窗,文案改为「删除『来自 {company} · {position} · {interview_started_at} 的错题』」);若 `source_session_id IS NULL`,不显示「移除自动来源」,「删除」按钮文案沿用 016 既有格式(「删除『{question_text 前 30 字}』」)。
- **FR-020**: System MUST 把阈值 `AUTO_ERROR_THRESHOLD = 6` 写在 `backend/app/modules/errors/service.py` 顶部,可被修改;不为单用户暴露 UI 配置。

#### Personal Ability Profile 链路确认
- **FR-021**: System MUST 维持 Phase 4 ability_diagnose → Spec 006 时间衰减加权聚合链路,**不在本规范修改实现**;端到端冒烟验证:`interview_sessions.ended_at` 后,`ability_dimensions` 至少有 1 个维度的 `updated_at` 在该时间之后。

#### 兼容性 / 不破坏现有契约
- **FR-022**: System MUST 不修改 014 的状态机、`status_history` 字段、outbox 流程、详情抽屉时间线;Job 新字段对 014 现有逻辑全部默认兼容(`base_location = '' / employment_type = 'unspecified' / 其余 NULL`)。
- **FR-023**: System MUST 不修改 016 的状态机、frequency/recall/reset 流程;错题自动沉淀**只在 score < 6 时触发**,mastered / practicing / archived 状态不变。
- **FR-024**: System MUST 不修改 006 与 Phase 4 ability_diagnose 子图;只在数据链路冒烟上确认。
- **FR-025**: System MUST 不修改 ResumeBranch 模型;岗位元数据通过"基于岗位创建"流程预填到分支 `name / company / position`,不增加 ResumeBranch 新列。

#### 可访问性 / 国际化
- **FR-026**: System MUST 所有新增 / 修改文案使用简体中文(「为该岗位创建简历分支」「为该岗位开始模拟面试」「来自 XX 公司 · YY 岗位 · YYYY-MM-DD HH:mm」「移除自动来源」「删除『来自 XX 公司 · YY 岗位 的错题』」「本岗位的招聘需求(点击展开复制)」等);按钮 / 卡片 / 输入控件暴露稳定 `data-testid`。
- **FR-027**: System MUST 新增的**三个** alembic 迁移(Job 5 字段 / InterviewSession.job_id / ErrorQuestion.source_question_id + 部分唯一约束)分别在迁移文件名中标注 `019_job_fields / 019_interview_job_id / 019_error_source_question_id`,并提供 down-migration;不允许破坏现有 schema。

### Key Entities *(include if feature involves data)*

- **Job (扩展)**: 新增 5 个字段(`base_location / requirements_md / employment_type / salary_range_text / headcount`)。原有 `company / position / jd_url / branch_id / status / status_history / notes_md` 不变。
- **InterviewSession (扩展)**: 新增 `job_id`(UUID, FK `jobs.id`, ON DELETE SET NULL,可空)。原有 `branch_id / position / company / mode / status / overall_score` 不变。
- **ErrorQuestion (扩展)**: 新增 `source_question_id`(UUID, FK `interview_questions.id`, ON DELETE SET NULL,可空,部分唯一约束)。原有 `source_session_id` 不变;两者都为空代表纯手动录入。
- **ResumeBranch (不变)**: 复用现有 `name / company / position` 字段;岗位元数据通过创建流程预填。
- **InterviewQuestion (不扩展)**: Phase 4 已落,本规范只读取 `score / dimension / text` 与对应 `ai_message.body`(answer_text)。

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 5 字段新增后,`POST /jobs` 接受空 body(只填 company/position),后端用默认值入库,前端展示「base 地: 未填写 / 岗位类型: 未指定」占位;Pydantic 校验在 100 次随机生成输入下 0 次漏报。
- **SC-002**: 从 Job 详情创建简历分支后,`jobs.branch_id` 100% 被自动回填(E2E 100 次跑测 0 次失败);断网时 PATCH 入 outbox,网络恢复后 30 秒内重放成功。
- **SC-003**: 从 Job 详情开面试后,`interview_sessions.job_id` 与 `branch_id` 同时入库,5 轮结束后 GraphState 含 `requirements_md` 截断片段(若岗位填了);5 轮面试的平均出题时间 < 1.5s 不受影响。
- **SC-004**: 模拟面试中每题 `score < 6` 100% 触发错题自动沉淀(E2E 5 场面试 × 5 题,共 25 题,其中至少 1 题低分,自动沉淀 100% 命中);同一题重评不重复创建(由部分唯一约束保证,100 次重复触发 0 次重复行)。
- **SC-005**: 「移除自动来源」操作后,该错题 `source_session_id / source_question_id` 100% 置 NULL,但 `error_questions.id` 与题目内容不变;列表筛选「来自面试」100% 排除该错题。「删除」操作后该错题从默认列表消失(`deleted_at` 置位),调用 016 现有 `DELETE /error-questions/{id}` 软删除流程,默认列表与筛选视图都不再展示。
- **SC-006**: 端到端冒烟:全新用户一次跑通「添加 Job → 创建分支 → 开面试 → 答完 5 轮 → 错题本沉淀 → 个人画像更新」完整链路,Playwright E2E 1 次通过,中间无 console error 与 4xx/5xx。
- **SC-007**: 100% 新增 / 修改文案为简体中文,无英文 UI 字符串;Playwright E2E 可零额外等待定位新增 CTA(`data-testid` 暴露稳定)。
- **SC-008**: 既有 014 / 016 / 006 / Phase 4 单测在 5 字段 + 1 外键 + 1 部分唯一约束 + 1 端点新增后**全部继续通过**(无回归);后端 `pytest` 与前端 `vitest` 0 失败。

## Assumptions

- 014 / 016 / 006 / Phase 4 的现有契约(`JobOut / InterviewSessionCreate / ErrorQuestionOut / AbilityDiagnose 输出`)在本次扩展中保持向后兼容;前端 014 / 016 / 006 现有代码在不修改上述契约的前提下无须改动。
- `interview_questions` 表 Phase 4 已落地,本规范不重新设计;只需新增 `error_questions.source_question_id` 外键并加部分唯一约束。
- LLM 不会因为 prompt 注入 `requirements_md` 切片而出题质量下降;若发现质量下降,Plan 阶段需 prompt engineering 进一步调优,本规范不在范围。
- 错题自动沉淀的阈值是产品级默认(6 分),不为单用户暴露 UI 配置;后续如需 per-user 配置,留待后续 feature(本规范已记为 Out-of-scope)。
- 不引入新的前端路由;`/resume/{id}?source_job_id={jobId}` 走现有路由 + query param,与 014 URL 风格一致。
- `interview_sessions.job_id` 字段迁移前先查表确认不存在(避免破坏性变更),若有同名字段需在 plan 阶段协商重命名或合并。
- 简历分支元数据扩展(`requirements_md / base_location` 进 ResumeBranch)留待后续 feature;本规范只通过"预填 name/company/position"满足"以岗位为基础"的体验需求。
- 错题自动沉淀**仅**对**面试**触发;对用户手动录入或未来其他来源(Error Coach、Email Import)暂不沉淀。
- 个人画像归因(`interview_sessions.job_id` 影响画像变化)是后续 feature 的范围,本规范只保证能力数据正确更新,不展示归因。

## 端到端联动示意

```
[1] 用户在 /jobs 添加职位
    POST /jobs { company, position, base_location, requirements_md, employment_type, ... }
    → jobs.branch_id = NULL

[2] 用户在 Job 详情点「为该岗位创建简历分支」
    → 前端 POST /resumes/branches { name: "{company} · {position}", company, position, ... }
    → 前端 PATCH /jobs/{jobId} { branch_id: newBranchId }

[3] 用户在 Job 详情点「为该岗位开始模拟面试」(branch_id 已绑)
    → POST /interview-sessions { job_id, branch_id, ... }
    → interview_sessions.job_id / branch_id 入库

[4] 5 轮对话中,score 节点每题写入 interview_questions.score
    → score < 6 时,ErrorQuestionService.maybe_create_from_question 触发 UPSERT
    → error_questions.source_session_id / source_question_id 写入

[5] 报告节点结束后,ability_diagnose 子图异步执行(006 已实现)
    → ability_dimensions 至少 1 个维度 updated_at 刷新

[6] 用户在 /error-book 选筛选「来自面试」
    → 看到该场 session 自动沉淀的错题
    → 可点「移除自动来源」清溯源
```

## Boundaries

### Always do
- 跑 `pytest` 后端单测与 `vitest` 前端单测再提交,保证 014 / 016 / 006 / Phase 4 无回归
- 任何对现有 014 / 016 / 006 / Phase 4 契约的扩展都保持向后兼容(默认字段、新增可空列、新增可选 query param)
- 新增 UI 文案用简体中文,暴露稳定 `data-testid`
- 新增 alembic 迁移提供 down-migration

### Ask first
- 修改 `interview_sessions` 已有列(如 `position / company`)、修改 `JobOut` 既有字段类型 / 长度
- 修改 Phase 4 ability_diagnose 子图、修改 006 的聚合算法
- 修改 016 的状态机、frequency / recall / reset 流程
- 修改错误码 / 错误信息格式、修改 outbox 流程

### Never do
- 删除 / 重命名现有字段(`jobs.company / position / jd_url` 等)
- 删除 014 / 016 / 006 / Phase 4 现有端点
- 跳过 alembic 迁移直接改库
- 把 `requirements_md` 全量注入 LLM prompt(必须 tiktoken 截断 1500 token)
- 把错题自动沉淀做成"事后批量回填"(必须 score 节点同步触发,保证实时性)
- 把 `source_session_id` / `source_question_id` 当唯一标识删除错题(它们只是溯源标记)
