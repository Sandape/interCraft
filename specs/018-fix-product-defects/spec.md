# Feature Specification: Fix Product Defects (v1 Quality Batch)

**Feature Branch**: `018-fix-product-defects`
**Created**: 2026-06-17
**Status**: Draft
**Input**: User description: "当前系统有以下问题清单：14 项从 Blocker 到 Low 级别的产品缺陷批次，覆盖注册深链、Dashboard 假数据、新建简历不可编辑、空简历假 AI 摘要、PDF 导出 404、面试未关联简历、面试恢复暴露技术文案、面试总分 0-100 vs 0-10 量纲错位、面试后能力画像未更新、错题 Coach 启动无反馈、新增错题未自动选中、求职记录备注未保存、退出登录菜单不可达、React Router v7 future flag console 警告。"

## Clarifications

### Session 2026-06-17

- Q: 面试总分与题分量纲最终对外展示用哪一套？(影响 FR-013、SC-005、能力画像换算、报告 PDF 等所有展示位) → A: 保留 **0-10 题分 + 0-10 总分**，UI 文案统一"满分 10"；能力画像直接复用 0-10 区间，**不做 0-100 换算**；LLM 出题保持 0-10 粒度不调整。
- Q: Dashboard 智能建议区在不同数据状态下分别展示什么？(影响 FR-003 / FR-004 / 新增档位 FR、SC 与 US3 验收) → A: **渐进式披露** — ① 零数据（无面试 / 简历 / 错题 / 投递）显示"完成首场面试以获取建议"CTA；② ≥1 场面试 但 错题/简历/投递 三项中 <2 项时显示"单场面试要点 + 该场关联简历"；③ ≥3 场面试 且 简历+错题+投递 三项齐全时显示"全局综合建议"。
- Q: 求职记录「备注」字段在数据库层（Feature 014 job-tracking schema）是否已落库？(影响 A-003 / FR-019 / FR-020 / SC-010) → A: **字段已存在**，本特性**只修前端** — 修复读取 / 字段映射（form 字段 ↔ API payload key）/ 序列化 / 编辑回填，schema 与后端 API 路径不动。

## User Scenarios & Testing *(mandatory)*

### User Story 1 - 新建简历可以直接编辑并导出 (Priority: P1)

访客 / 已登录用户通过「新建简历」入口创建一份空简历后，能立即进入编辑器、添加 / 修改 / 删除简历块、写入代码模式内容，并将结果成功导出为 PDF。

**Why this priority**: 缺陷等级为 Blocker 且直接阻断简历编辑核心闭环；同时 PDF 导出与编辑器状态耦合；不修这个故事，新用户 / 老用户都无法完成"创建 → 编辑 → 导出"主流程。

**Independent Test**: 创建一份空简历后，编辑器进入可写状态，"添加块"入口可见且可点击；代码模式下 textarea 可输入；导出 PDF 通过弹窗的「导出 → PDF 文件」触发，后端返回 200 与 PDF 文件，前端下载成功。

**Acceptance Scenarios**:

1. **Given** 用户已登录且在「新建简历」表单提交成功, **When** 跳转进入编辑器, **Then** 编辑器状态为「可编辑」，「+ 添加块」入口可见且可点击。
2. **Given** 编辑器为可编辑状态, **When** 用户在代码模式 textarea 中输入文字, **Then** 文字可被输入且变更被记录。
3. **Given** 用户在编辑器中保存了至少一个简历块, **When** 用户点击「导出 → PDF 文件」, **Then** 浏览器下载一份非空 PDF 文件，UI 提示「导出成功」或同等可读反馈。
4. **Given** 后端 PDF 渲染服务出现错误, **When** 用户触发导出, **Then** UI 提示包含具体错误原因（如简历无内容 / 后端错误码 / 模板未找到），而非裸字符串 `Rendering failed:`。

---

### User Story 2 - 注册深链直达注册态 (Priority: P1)

未登录用户访问 `/register` 链接或带 `?mode=register` 的链接时，看到的是「创建账号」表单而非「欢迎回来 / 登录」表单。

**Why this priority**: 影响所有外部引流（营销、邮件、邀请链接）到注册入口的转化路径，列为 High。

**Independent Test**: 在未登录态下打开 `http://<host>/register`，页面表单标题、提交按钮文案、字段集合（确认密码 / 协议勾选）均对应注册流程。

**Acceptance Scenarios**:

1. **Given** 用户未登录, **When** 访问 `/register`, **Then** 页面标题/主按钮显示「创建账号」语义，提交时调用注册接口。
2. **Given** 用户已登录, **When** 访问 `/register`, **Then** 行为同「已登录访问 /login」一致：跳转到主页或显示「已登录」提示，不再次注册。

---

### User Story 3 - Dashboard 智能建议基于真实数据 (Priority: P1)

登录用户打开 Dashboard 时看到的能力建议、提示卡片、岗位 / 公司、简历分支等，全部来源于该用户真实的面试、错题、简历与投递记录；建议区按数据档位（0/1/2）渐进式披露，新账号看到「完成首场面试以获取建议」引导态而非假数据。

**Why this priority**: 直接影响用户对能力提升闭环的信任度，是「数据 → 反馈 → 成长」核心叙事的可信基础。High 级别缺陷。

**Independent Test**: 一个新注册、未做面试、未创建简历、未添加错题 / 投递的账号打开 Dashboard，看到空态；同一账号完成一次面试并刷新 Dashboard，建议内容引用该面试 / 该简历 / 该岗位信息而非"系统设计失分 3 次""字节跳动简历分支"等占位文案。

**Acceptance Scenarios**:

1. **Given** 新账号无面试 / 简历 / 错题 / 投递数据（档位 0）, **When** 打开 Dashboard, **Then** 智能建议区显示「完成首场面试以获取建议」CTA，不出现任何公司名 / 简历名 / 失分统计 / "全局"措辞。
2. **Given** 用户完成 1 场面试（档位 1）, **When** 再次打开 Dashboard, **Then** 建议中出现的公司名、岗位、简历名、失分维度与该用户本次真实记录一致，且不出现"全局"措辞。
3. **Given** 用户有 ≥3 场面试 + 简历 + 错题 + 投递齐全（档位 2）, **When** 打开 Dashboard, **Then** 建议内容覆盖能力维度趋势 / 简历优化 / 错题强化三类中至少两类。
4. **Given** 真实数据更新（新增面试 / 简历 / 错题）, **When** 用户在 Dashboard 停留或刷新, **Then** 建议内容随之更新（手动刷新或自动刷新策略见 Assumption）。

---

### User Story 4 - 面试评分与能力画像口径一致 (Priority: P1)

用户在面试报告页与能力画像页看到的分数，使用统一量纲；完成一场面试后，能力画像 Dashboard / `/ability-profile` 同步反映该面试的维度得分。

**Why this priority**: High 级别，破坏量纲一致性（3.6/100 vs 3.6/10）会让用户对系统打分能力失去信任；能力画像不同步会让"能力提升闭环"叙事的下游体验断裂。

**Independent Test**: 一次 5 题面试每题 0-10 分，完成后报告卡显示「3.6 / 10」且文案与"满分 100"统一为「满分 10」；同一场面试结束后跳转 `/ability-profile`，对应维度分数非零并与报告中各维度的 0-10 折算结果一致。

**Acceptance Scenarios**:

1. **Given** 5 题评分依次为 2/10、7/10、3/10、5/10、1/10, **When** 报告页展示完成卡, **Then** 总分显示为「3.6 / 10」（或等价的「36 / 100」），不再出现「满分 100」与 0-10 题分并存。
2. **Given** 一场面试刚刚完成, **When** 用户跳转 `/ability-profile` 或 Dashboard 综合能力卡, **Then** 至少一个能力维度分数 > 0 并与本次面试报告中各维度均分一致（允许有四舍五入与归一化处理）。
3. **Given** 能力画像正在被异步刷新, **When** 用户在刷新窗口内查看, **Then** UI 显示「更新中」等可读状态，不出现「全部维度 0」与「报告有分」并存的情况。

---

### User Story 5 - 面试启动关联简历、恢复状态友好 (Priority: P2)

新启动一场面试时，用户能选择或确认将要使用的简历；中途退出后再次恢复，看到的是"已恢复到第 N 题"等中文友好文案，而非英文 / 调试技术文案。

**Why this priority**: Medium 级别，影响面试环节"基于简历生成"的承诺与跨设备恢复体验，但不会阻断主流程。

**Independent Test**: 在面试设置页能选择一份已有简历（或明确无简历时跳过）；强制刷新或退出后重新进入对应 session，页面状态显示「已恢复到第 N 题」或「从第 N 题继续」等中文友好文本。

**Acceptance Scenarios**:

1. **Given** 用户有 ≥1 份简历, **When** 打开「新建面试」表单, **Then** 存在「选择简历」控件，可选择具体简历并在提交时携带。
2. **Given** 用户无简历, **When** 打开「新建面试」表单, **Then** 提示「暂无可用简历，是否先创建？」并提供跳转入口（允许跳过，行为有明确文案）。
3. **Given** 一次进行中的面试因断网 / 刷新 / 退出而被恢复, **When** 重新加载面试页, **Then** 顶部状态显示「已恢复到第 N 题」等中文友好文案，不出现 `Restored N answers, N questions, N scores` 之类的英文技术日志。

---

### User Story 6 - 错题 Coach 启动有反馈、错题自动选中 (Priority: P2)

用户在错题详情点「开始强化」进入 Coach 面板后，Coach 给出明确的加载态、错误态或第一道题；新增一道错题后，错题详情区自动定位到该新错题。

**Why this priority**: Medium / Low 级别，Coach 启动无反馈会让用户怀疑功能是否生效；不自动选中则增加一步操作。

**Independent Test**: 在错题详情点「开始强化」后 5 秒内出现加载提示或第一道题；输入框为空时给出可读错误（如「请先输入答案」），不为静默失败。保存新错题后，右侧详情区自动展示该错题内容。

**Acceptance Scenarios**:

1. **Given** 用户在错题详情点击「开始强化」, **When** 进入 Coach 面板, **Then** 5 秒内出现 loading 指示、错误提示或第一道强化题，UI 不会停留在「按了之后什么都没发生」。
2. **Given** Coach 启动失败（网络 / 后端错误）, **When** 失败发生, **Then** 面板显示可读错误信息并保留「重试」入口，按钮不会消失而不告知结果。
3. **Given** 用户在错题列表新增一条错题, **When** 保存成功, **Then** 右侧详情区自动切换到该新错题的内容，不再停留在「请选择左侧错题查看详情」。

---

### User Story 7 - 求职记录备注可保存可展示 (Priority: P2)

用户在「添加职位 / 投递记录」表单中填写的备注被持久化，并在列表 / 详情页正确显示。

**Why this priority**: Medium 级别，影响求职记录作为「用户个人上下文」的可信度；表单收集字段不落库会让用户怀疑系统是否真在记录。

**Independent Test**: 添加一条投递记录时输入备注，提交后列表「备注」列与详情页都展示该备注内容；后续编辑能保留并更新该备注。

**Acceptance Scenarios**:

1. **Given** 用户在「添加职位」表单输入备注（如「Codex E2E ... 测试投递记录」）, **When** 提交成功, **Then** 列表中该条记录的「备注」列展示该文本（不再显示「—」）。
2. **Given** 一条已有备注的投递记录, **When** 用户进入详情 / 编辑, **Then** 备注字段被回填，可编辑并保存。
3. **Given** 后端暂时不支持备注字段, **When** 前端收集到备注, **Then** 表现行为为「在保存前明确告知用户该字段暂未启用」或「不显示该字段」二选一（见 Assumptions），不可在用户填了之后静默丢弃。

---

### User Story 8 - 生产级 Console 与无障碍 (Priority: P3)

生产质量页面不再有 React Router v7 future flag 警告；用户菜单中的「退出登录」具备可访问 / 可定位语义（button role / name 稳定）。

**Why this priority**: Low 级别，Console 警告影响开发与定位效率，无障碍语义影响读屏 / 键盘 / E2E 稳定性；不直接阻断主流程。

**Independent Test**: 在登录后浏览主要页面（Dashboard / 简历 / 面试 / 错题 / 能力画像），DevTools Console 不出现 `React Router Future Flag Warning`；用户菜单中「退出登录」项在 a11y tree 中具备 `button` role 与可见 name。

**Acceptance Scenarios**:

1. **Given** 任意已登录页面, **When** 用户浏览 / 切换路由, **Then** Console 不出现 `v7_startTransition`、`v7_relativeSplatPath` 等 React Router future flag 警告。
2. **Given** 用户打开个人菜单, **When** 焦点落在「退出登录」项, **Then** 该项以 `button` 或 `menuitem` 形式可被辅助技术 / E2E 工具稳定选中并触发。

## Requirements *(mandatory)*

### Functional Requirements

**Auth & Routing**

- **FR-001**: 路由层 MUST 区分 `/login` 与 `/register` 两种入口态，使 `/register` 在未登录时默认呈现注册表单。
- **FR-002**: 路由层 MUST 在用户已登录态访问 `/login` 或 `/register` 时，跳转到主页或给出「已登录」语义提示，不重复登录 / 注册。

**Dashboard Data Integrity**

- **FR-003**: Dashboard 的智能建议区 MUST **仅基于当前用户真实的面试、简历、错题与投递记录**渲染；任何档位下 MUST 不出现占位公司、占位简历名、占位失分统计（"字节跳动简历分支"、"系统设计失分 3 次" 等硬编码文案）。
- **FR-004**: Dashboard 的智能建议区 MUST 按数据档位渐进式披露：
  - **档位 0（零数据）**：无面试 / 简历 / 错题 / 投递 任一项时，显示「完成首场面试以获取建议」CTA（带跳转入口）。
  - **档位 1（单场）**：≥1 场面试 且 简历 / 错题 / 投递 三项中 <2 项时，显示「单场面试要点 + 该场关联简历」提示（如本次失分维度、相关简历块建议），不出现"全局"措辞。
  - **档位 2（全局）**：≥3 场面试 且 简历 + 错题 + 投递 三项齐全时，显示「全局综合建议」（能力维度趋势、简历优化方向、错题强化建议）。
- **FR-005**: Dashboard 的数据源 MUST 可被替换 / 注入（便于单测与 Storybook）。

**Resume Editor & Export**

- **FR-006**: 新建简历后默认状态 MUST 为「可编辑」，并暴露「+ 添加块」入口与代码模式可写 textarea。
- **FR-007**: 简历编辑器 MUST 在用户拥有写权限且后端 session 正常时维持可写状态；不可写时 MUST 给具体原因（鉴权 / 网络 / 锁），而不是统一回落到「只读」。
- **FR-008**: 简历 PDF 导出 MUST 走产品后端契约中的渲染接口（与 Feature 012 导出网关一致），并返回可下载 PDF 与成功状态码 2xx。
- **FR-009**: 简历 PDF 导出失败时，前端 MUST 给出可读错误（如「简历为空，请先添加内容」「渲染服务暂不可用」），后端 MUST 返回结构化错误（错误码 + 人类可读消息），日志中保留可复现上下文。

**Empty Resume State**

- **FR-010**: 当简历无内容或低于最低可分析阈值时，AI 优化 / 匹配度面板 MUST 显示空态 / 引导态，不得渲染硬编码数字（"LCP 1.4s""76% 复用""+14" 等）。

**Interview Setup & Recovery**

- **FR-011**: 新建面试表单 MUST 允许选择（且默认选择）一份简历作为上下文；当用户没有简历时 MUST 明确提示并提供跳转到新建简历的入口。
- **FR-012**: 面试恢复 UI MUST 将技术文案（`Restored N answers...`）翻译为用户友好中文状态（"已恢复到第 N 题" / "从第 N 题继续"），且 MUST 不在前端控制台或页面正文泄露内部日志。

**Interview Scoring Consistency**

- **FR-013**: 面试评分 MUST 使用 **0-10 量纲**（0-10 题分、0-10 总分）；**禁止在 UI 上把总分换算成 0-100 展示**（即不再出现"3.6 / 100"或"36 / 100"这类表达），避免与 0-10 题分并存产生歧义。LLM 出题协议保持 0-10 粒度不动。
- **FR-014**: 完成卡与详情卡的「满分」文案 MUST 与实际量纲一致（0-10 总分时显示「满分 10」）。
- **FR-015**: 完成面试后能力画像 MUST 同步反映该面试的维度均分（或显式说明「正在同步」）；不允许「报告有分 + 画像全 0」并存超过一次会话边界。

**Error Book Coach**

- **FR-016**: 错题 Coach 启动 MUST 给出明确的 loading / error / first-question 状态，超时阈值内 MUST 不出现"按了按钮毫无反应"。
- **FR-017**: Coach 启动失败 MUST 保留「重试」入口并附可读错误。
- **FR-018**: 新增一条错题后，错题详情区 MUST 自动定位到该新错题；不允许停留在「请选择左侧错题查看详情」。

**Job Tracking Notes**

- **FR-019**: 求职记录 / 投递记录的「备注」字段（后端 schema 已存在）MUST 在前端正确读 / 写并在列表与详情中展示；本特性 MUST 修复的是前端层 — 包含 form 字段 ↔ API payload key 的字段映射、序列化（如 trim / null vs 空串）、列表列与详情面板的回填。**schema 与后端 API 路径不动**。
- **FR-020**: 编辑投递记录时，备注字段 MUST 被回填（读取时正确映射）、可保存（提交时正确序列化），提交成功后列表与详情同步更新。

**Production Quality**

- **FR-021**: 应用 MUST 显式接受 React Router v7 future flag（`v7_startTransition` / `v7_relativeSplatPath` / `v7_fetcherPersist` / `v7_normalizeFormMethod` / `v7_partialHydration` / `v7_skipActionErrorRevalidation`），保证生产构建下 console 不出现相应警告。
- **FR-022**: 用户菜单中的「退出登录」项 MUST 在 a11y tree 中具有 `button` 或 `menuitem` role + 可见 name，并可通过键盘 / 屏幕阅读器 / 自动化测试稳定触发。

### Key Entities

- **Resume（简历）**: 用户简历；含基本属性（标题、最近一次编辑时间、是否含内容）、版本与块集合；与 User 多对一。
- **ResumeBlock（简历块）**: 简历内的具体内容单元（标题 / 段落 / 列表 / 技能 / 项目等），可被新增 / 编辑 / 删除 / 排序。
- **InterviewSession（面试会话）**: 用户的某次面试；含岗位、目标公司、关联简历 ID（可空）、题目列表、答案、评分、状态（草稿 / 进行中 / 已完成）、恢复点。
- **Question / Score（题目 / 评分）**: 面试中的题与 0-10 题分、维度标签。
- **AbilityProfile（能力画像）**: 用户粒度的能力维度（如系统设计 / 编码 / 沟通 / 学习 / 表达 / 项目）当前分数与最近一次更新时间。
- **ErrorQuestion（错题）**: 错题本中的一条记录；含题干、答案、来源（面试 / 手动）、维度、强化状态。
- **JobApplication（投递记录）**: 用户对某岗位的投递记录；含公司、岗位、状态、备注、投递时间。
- **User（用户）**: 登录态下的注册用户；其所有数据通过会话与 RLS 范围隔离。

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% 的新注册用户创建第一份简历后，编辑器在 1 次点击内可进入「可编辑」状态，「+ 添加块」入口可见可点击。
- **SC-002**: 100% 的简历 PDF 导出请求按 Feature 012 契约返回 2xx 且下载得到非空 PDF，或返回带可读错误信息的 4xx/5xx。
- **SC-003**: 未登录访问 `/register` 的 100% 页面渲染显示「创建账号」表单（字段、按钮文案、提交目标一致）。
- **SC-004**: 对 100% 完成 ≥1 场面试的用户，`/ability-profile` 与 Dashboard 综合能力卡显示的维度分数至少 1 项 > 0（与该面试维度均分一致，允许四舍五入）。
- **SC-011**（新增）：Dashboard 智能建议区在三个数据档位下分别命中预期：零数据 → 100% 显示「完成首场面试」CTA 而非任何公司 / 简历 / 失分文案；≥1 场面试（档位 1）→ 100% 建议内容引用该场面试与关联简历，不出现"全局"措辞；≥3 场面试 + 简历 + 错题 + 投递齐全（档位 2）→ 100% 建议内容覆盖能力维度趋势 / 简历优化 / 错题强化三类中至少两类。
- **SC-005**: 100% 的面试报告总分显示与"满分"文案保持 **0-10 量纲**（总分显示 `X.X / 10`，"满分"文案显示"满分 10"），**全应用不再出现 `X.X / 100` 或 `XX / 100` 形式的总分展示**。
- **SC-006**: 100% 启动错题 Coach 的用户在 5 秒内观察到 loading / error / first-question 之一；无任何"按了无反应"路径。
- **SC-007**: 在主流程页面（Dashboard / 简历 / 面试 / 错题 / 能力画像）任意一处，DevTools Console 不出现 `React Router Future Flag Warning`。
- **SC-008**: 用户菜单「退出登录」项可被 Playwright `getByRole('button' | 'menuitem', { name: /退出登录|Logout/ })` 稳定定位并触发。
- **SC-009**: 新增错题 / 新增投递记录后，相关列表 + 详情页 100% 自动定位到新建项（无需手动点击）。
- **SC-010**: 投递记录的「备注」字段在 100% 的创建 / 编辑路径下被正确写入并在列表「备注」列与详情面板展示；列表「备注」列仅在用户**确实未填**时显示「—」，填了就不再为「—」；编辑进入表单时备注 MUST 被回填。

## Assumptions

- **A-001**: 简历 PDF 渲染服务由 Feature 012（resume-export-gateway）提供；本特性不重写渲染逻辑，仅修复契约对齐与错误信息。
- **A-002**: 能力画像同步允许「异步刷新」语义；UI 在刷新窗口期可显示「更新中」状态，但必须在同一会话边界内收敛到正确数据。
- **A-003**: 投递记录「备注」字段在数据库层 **已落库**（Feature 014 / job-tracking 的 schema 包含该字段），本特性只修前端（字段映射 / 序列化 / 回填），**不**触发 schema migration 或后端 API 变更。如果实施时通过后端日志或 4xx 错误发现字段实际未落库，需作为独立 issue 拆出，不在本批次范围。
- **A-004**: Dashboard 智能建议的数据源与生成策略属于既有 Phase 5 / Phase 6 能力范围；本特性不引入新 AI 能力，只保证现有生成结果对当前用户真实。
- **A-005**: React Router 当前为 v6，未来 flag 一旦在 v7 成为默认，FR-021 视为自动满足。
- **A-006**: 「未登录访问 `/register`」不会触发后端注册接口；仅前端路由与表单渲染变化。
- **A-007**: 「退出登录」的可访问语义以 `button` + 可见 name 为优先实现方案；若既有组件受第三方菜单库限制且短期内不可改，可接受 `role="menuitem"` 方案，但 MUST 保留键盘可达与 name。
- **A-008**: 错题 Coach 后端能力已存在（Feature 016 错题本能力收尾），本特性只修复前端启动反馈与状态缺失，不补后端能力。
- **A-009**: 数据隔离遵循 Constitution 中的「会话与 RLS 层」约束；本特性所有"当前用户"判断 MUST 走后端会话，不在前端硬编码。
- **A-010**: 本特性不引入新的库或服务；修复范围限定在已有前端页面、组件、状态机与已有后端契约内。

## Out of Scope

- 新建 AI 能力（例如"Dashboard 智能建议生成器"），仅保证其结果对当前用户真实。
- 重写简历编辑器，仅修复"新建后只读"与"代码模式只读"两个具体症状。
- 简历 PDF 渲染引擎本体实现，仅做契约对齐与错误信息修复。
- 错题 Coach 后端能力扩展，仅修复前端启动反馈。
- 错题本核心数据模型变更。
- 投递记录核心数据模型变更；本特性**不**触发 schema migration。
- 重新设计能力画像的维度体系或算法；本特性只保证"面试 → 画像"的同步链路通。

## Dependencies

- Feature 001（InterCraft 主产品规格）— 主产品基础。
- Feature 002（Resume Editor Enhancement）— 简历编辑器主能力。
- Feature 003 / 004（Phase 4 / Phase 5）— 面试与 Agent 能力。
- Feature 006（Personal Ability Profile）— 能力画像。
- Feature 012（Resume Export Gateway）— PDF 渲染服务契约。
- Feature 013（User Avatar）— 用户菜单中可能影响可访问语义的部分。
- Feature 014（Job Tracking）— 求职记录。
- Feature 016（Error Book Completion）— 错题本与 Coach。
- Constitution 原则 III（Test-First）：所有修复 MUST 配套对应层级的测试（单元 / 组件 / E2E）。
- Constitution 原则 V（Observability）：新增错误分支 MUST 在前端有可读错误信息，在后端有结构化日志。
