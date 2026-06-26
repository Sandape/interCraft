# Feature Specification: Resume Renderer v2 (JSON Schema + Multi-Template)

**Feature Branch**: `032-resume-renderer-v2`
**Created**: 2026-06-25
**Status**: Draft
**Input**: User description: "针对当前简历中心的简历编辑器进行一次大版本更新，以追求更好的简历渲染效果和更多的可选择模板，其中重点是简历的渲染效果，当前渲染效果实在太糟糕，我需要一份稳定、优雅、效果优秀的改造方案。"

## Clarifications

### Session 2026-06-25

- Q: 数据模型路线？ → A: **JSON Schema 路线** — 彻底放弃 Markdown，改强类型 sections（12+ section + custom），与 reactive-resume v5 对齐。
- Q: PDF 渲染引擎？ → A: **后端 Playwright 保持** — 与 027 一致，零漂移；前端只生成完整 HTML（含主题 CSS + 分页标记 + style 内联），后端只包壳渲染。
- Q: 模板数量？ → A: **8-10 个精选** — 覆盖经典/双栏/紧凑/创意/杂志/编辑式/纯文本/双带 header 等档位。
- Q: 范围是否局限在简历中心？ → A: 是 — 不动 auth / jobs / interviews / errors / ability_profile / agents 等其他模块的基础设施。
- Q: 已有数据如何处理？ → A: **新建数据表，新简历走 v2 模型；旧 block 简历保留只读访问**，写入路径仅 v2。
- Q: 027 实现的 preview↔PDF 零漂移、双向定位、auto-save 500ms、COW 分支、版本快照是否保留？ → A: 全部保留，作为 v2 的基础设施。
- Q: v2 简历的「锁定」语义是什么？ → A: **乐观并发** — `resumes_v2` 新增 `version: int` 字段（默认 0），每次 PUT 带 `If-Match: version`；服务端用 `WHERE id = ? AND version = ?` 原子更新，匹配则 `version+1`，不匹配返回 409 + 响应体含最新 `data` + 最新 `version`。客户端收到 409 MUST toast 提示「其他设备刚保存了更新，正在刷新数据」并自动重新 GET 拉取最新数据。锁仅在保存瞬间检查，不阻塞编辑过程；`is_locked: boolean` 字段仅用于 owner 主动设置的「永久只读锁」，与并发编辑锁解耦。
- Q: DOCX 导出（FR-070 / SC-006）是否必需？ → A: **完全去除**。v2 只导出 PDF + JSON；不再提供 DOCX 导出，理由是：DOCX 渲染对 8-10 套模板的视觉保真度天花板低（70%-99%），工程量与收益不匹配；用户求职场景下 PDF 已是主流交付格式。同步更新：US10 dock 按钮（9 → 8）、FR-052 Export 面板（JSON/DOCX/PDF → JSON/PDF）、删除 FR-070。
- Q: AI 简历分析的调用策略？ → A: **不设限 / 裸调用** — 不做用户级日限额，不做结果缓存；调用频率完全由用户控制；DeepSeek V4 Pro 限流时自动 retry 3 次（指数退避 1s/2s/4s），3 次后仍失败则 toast 错误并写入 `resume_analysis_v2.status='failed'`。理由：v2 用户量不大、DeepSeek 配额 500K/月够用，限额 + 缓存带来的产品复杂度与当前阶段不匹配。
- Q: 用户能否在 v2 中复制已有简历为新变体？ → A: **支持 Duplicate 按钮** — 在简历列表卡片 + 编辑器顶部 Header（breadcrumb 旁）提供「Duplicate」按钮；不放底部 dock（避免破坏 FR-067 的 8 按钮约束）；点击后创建新 v2 简历（复制 data / metadata / template；生成新 UUIDv7 + 新 slug；name 加「(Copy)」后缀；statistics / analysis 字段不复制，默认值）。理由：求职场景下用户经常根据不同 JD 调简历，没有 Duplicate 体验差。同步新增 US16 + FR-098~100。
- Q: v2 编辑器是否需要 Undo/Redo？ → A: **20 步历史栈 + Ctrl+Z** — Zustand store 维护最近 20 步 ResumeDataV2 全量快照栈；Ctrl/Cmd+Z 撤销，Ctrl/Cmd+Shift+Z 重做；连续 30 分钟无编辑活动后历史栈清空（避免内存膨胀）；可与 500ms auto-save + 027 COW 版本快照共存。同步新增 US17 + FR-101~103。

---

## Background & Motivation

当前 eGGG 简历中心经 027 spec 改造后，已经实现了：
- preview↔PDF 零漂移（后端 Playwright + 前端 HTML 生成器统一）
- 真实 A4 分页（rs-md-html-parser 算法）
- 4 套主题（default/blue/orange/pupple）+ 颜色拾取器
- 4 套样式（classic-one-page/compact-one-page/modern-two-column/editorial）
- Block 模型 + Markdown 写作
- AI 优化（真轮询 + per-patch + diff）
- 版本快照 + COW 分支
- 双向定位（Quick/Code ↔ 预览）
- 头像/证件照调整
- 模板市场（Square 模板市场）

但用户反馈**"当前渲染效果实在太糟糕"**。核心原因：
1. **模板视觉风格单一** — 4 套主题仅是颜色差异，4 套样式仅是布局差异，视觉缺乏多样性
2. **样式与主题的乘法关系** — 4×4=16 组合，但实际效果同质化
3. **结构表达力受限** — block + Markdown 模型难以表达 reactive-resume 那样的"双栏 sidebar+main" / "彩色 header 卡片" / "featured summary" / "时间轴" / "侧边卡片" / "顶部色带" 等高级版式
4. **没有可视化模板切换** — 用户必须先选主题再选样式，无法像 reactive-resume 那样打开 Gallery 直接选一套完整的视觉风格
5. **设计系统颗粒度粗** — 字体只有 1 个、颜色只有 3 个（primary/text/background），无法精细控制 heading/font/lineHeight/icon
6. **没有 level 设计** — Skills/Languages 的 0-5 等级只能用 5 颗星，无法切换 circle/square/progress-bar/icon 等样式

本次 v2 的目标：参考 reactive-resume v5 的设计系统（已对开源代码 `D:\Project\reactive-resume` 做完整调研），用 JSON Schema 数据模型 + 8-10 套精选模板 + 15+ style slots 自定义 + 客户端 Tiptap 富文本，把简历渲染效果和模板多样性提升到 reactive-resume 同等水平。

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 - JSON Schema 数据模型与结构化 sections (Priority: P1)

用户在新建简历时，进入的是一个全新的结构化编辑器：左侧 12+ 个 sections（Picture / Basics / Summary / Profiles / Experience / Education / Projects / Skills / Languages / Interests / Awards / Certifications / Publications / Volunteer / References / Custom），每个 section 都有自己强类型的字段（不再是 Markdown 文本块）。例如 Experience section 的每个 item 有 company / position / period / location / website / description / roles[] 等独立字段；Skills 的每个 item 有 name / level (0-5) / keywords[] 等。数据以 JSON Schema 形式持久化，与 reactive-resume v5 的 schema 对齐。

**Why this priority**: 这是整个 v2 的数据基础。所有其他能力（多模板、style slots、自定义 section、双带 header 等）都依赖强类型 sections。放弃 Markdown 才能解锁 reactive-resume 级别的视觉表达力。P1 因为它是其他故事的前置条件。

**Independent Test**: 创建一个新 v2 简历，确认 12+ sections 全部列出；展开 Experience section 添加一个 item，确认 7 个字段（company/position/period/location/website/description/roles）都出现且为表单控件（非 textarea）；保存后刷新页面，所有数据原样恢复。

**Acceptance Scenarios**:
1. **Given** 用户创建新简历，**When** 进入编辑器，**Then** 左侧 sidebar 列出 16 个 sections：Picture、Basics、Summary、Profiles、Experience、Education、Projects、Skills、Languages、Interests、Awards、Certifications、Publications、Volunteer、References、Custom
2. **Given** 用户展开 Experience section，**When** 点击 "Add a new experience"，**Then** 弹出包含 company、position、period、location、website、description（富文本）、roles[] 的强类型表单
3. **Given** 用户填写 Experience 表单后点击 Save，**When** 重新打开简历，**Then** 所有字段值原样恢复
4. **Given** 用户展开 Skills section，**When** 添加一个 skill，**Then** 出现 name、level (0-5)、keywords[] 三个字段（level 用星级或圆点等可视化控件）
5. **Given** 用户展开 Profiles section，**When** 添加一个 profile，**Then** 出现 network（带网络图标联想）、username、website、show-link-in-title 四个字段
6. **Given** 用户在 Basics section，**When** 输入，**Then** 字段包括 name、headline、email、phone、location、website、customFields[]（用户自定义键值对）
7. **Given** 已有 block 简历（v1），**When** 用户打开，**Then** 仍可只读查看但提示"该简历使用旧版格式，请创建新版 v2 简历"；不允许编辑

---

### User Story 2 - 8-10 套精选模板与可视化 Gallery (Priority: P1)

用户点击右侧 Settings 面板的 "Template" 区域，弹出 Template Gallery 对话框，展示 8-10 套精选模板的缩略图（4 列网格），每套模板有名称、缩略图、标签（如 "Two-column / Creative / Tech / Visual flair"）和简短描述。点击任意模板缩略图，中间预览区实时切换到该模板的渲染效果（无需刷新页面），右侧 Settings 顶部 Template 区域更新为新模板名 + 描述。

**Why this priority**: 这是用户感知最强的差异化能力——一秒钟从"通用模板"切换到"杂志风"，比 027 的 4×4 组合提升 10 倍。P1 因为模板多样性是用户的核心痛点。

**Independent Test**: 打开 Template Gallery，确认 8-10 个模板缩略图清晰可见；点击 Pikachu（彩色 header 卡片风格），预览立即变彩色卡片；切回 Onyx（极简纯文本），预览立即变极简；刷新页面后上次选择的模板保留。

**Acceptance Scenarios**:
1. **Given** 用户在编辑器中，**When** 点击右侧 Settings 顶部 Template 区域的缩略图，**Then** 弹出 Template Gallery 对话框
2. **Given** Gallery 打开，**When** 查看，**Then** 显示 8-10 个模板缩略图（4 列网格），每个有名称、描述和 3-5 个标签（如 "Two-column"、"Creative"、"Tech"、"Visual flair"、"Minimal"、"ATS friendly"）
3. **Given** Gallery 中的模板缩略图，**When** 点击，**Then** Gallery 关闭，中间预览区在 1 秒内切换到该模板的渲染效果，右侧 Template 区域更新为新模板名 + 描述
4. **Given** 用户切换模板，**When** 重新打开简历，**Then** 上次选择的模板被恢复
5. **Given** 用户已选 Pikachu（彩色 header 卡片），**When** 切换到 Onyx（极简纯文本），**Then** 预览中所有装饰元素消失（无 sidebar、无彩色 header、无下划线），仅保留纯文本
6. **Given** 8-10 套模板，**When** 列表，**Then** 至少包含：经典商务（azurill/onyx 风格）、双栏 sidebar（chikorita/pikachu 风格）、极简纯文本（kakuna 风格）、编辑设计（scizor 风格）、紧凑单页（bronzor 风格）这 5 个档位

**8-10 套模板清单**（v2 精选，参考 reactive-resume 15 套）：

| 模板 | 风格档位 | 主要特征 | 适用场景 |
|---|---|---|---|
| 1. Onyx（极简纯文本） | 极简 | 顶部单栏 header + 主体纯文本，无装饰 | 通用 / 工程师 |
| 2. Azurill（双栏时间轴） | 商务 | 左 sidebar + 右 main，main 区单列 section 渲染为时间轴 | 通用现代 |
| 3. Kakuna（居中对称） | 极简 | 顶部居中 header + 主体居中对称 | 学术 / 教育 |
| 4. Chikorita（实色 sidebar） | 创意 | 左 main + 右 solid primary sidebar，sidebar 文字反相 | 创意 / 设计 |
| 5. Ditgar（tint sidebar + item 边框） | 商务 | 左 tint sidebar + 右 main，main item 加左侧 2px 竖线 | 工程师 / 技术 |
| 6. Bronzor（行式 section） | 商务 | 单栏行式（section title 在左，items 在右），顶横线分割 | 传统商务 |
| 7. Pikachu（彩色 header 卡片） | 创意 | 左 sidebar + 右 main，main 顶部是 primary 实色圆角 header 卡片 | 创意 / 设计 / 前端 |
| 8. Lapras（卡片化 + 浮动标题） | 创意 | 顶部圆角 header 卡片 + 主体全卡片化 + 标题悬浮在边框上 | 产品 / 运营 |
| 9. Scizor（杂志风） | 编辑 | 顶部 primary 色 letterhead + 大写 section heading + 重字重 | 品牌 / 创意总监 |
| 10. Rhyhorn（管道分隔） | 商务 | 顶部 header + 联系方式间用竖线分隔 | 金融 / 法律 / 咨询 |

---

### User Story 3 - 三栏编辑器与 12+12 settings 面板 (Priority: P1)

用户进入编辑器，看到三栏布局：左侧 section 列表（可拖拽宽度），中间 A4 真实分页预览，右侧 settings 面板（可拖拽宽度）。左侧包含 16 个 sections（Picture / Basics / Summary / 12 内置 / Custom / Custom fields），每个 section 展开后是该 section 的 items 列表，每个 item 卡片可点击打开编辑 dialog。右侧 12 个 settings 子面板：Template、Layout（多页 dnd-kit）、Typography（body/heading 字体/字号/行高）、Design（colors primary/text/background + level type）、Styles（style rules）、Page（format/marginX/marginY/gapX/gapY）、Notes、Sharing（公开开关 + 密码）、Statistics、Analysis（AI）、Export、Information。每个 settings 子面板可折叠（accordion）。

**Why this priority**: 这是 v2 编辑器的"骨架"，与 reactive-resume v5 完全对齐。P1 因为 UI 框架是其他能力（多模板切换、style rules、富文本编辑）的承载层。

**Independent Test**: 打开编辑器，确认三栏布局清晰；拖拽左/右 sidebar 边框，宽度实时变化；折叠左侧 section、展开右侧 settings 子面板，确认所有 12 个 settings 都可访问。

**Acceptance Scenarios**:
1. **Given** 用户进入编辑器，**When** 查看，**Then** 看到三栏布局：左 section 列表（约 22%）+ 中预览（约 56%）+ 右 settings（约 22%）
2. **Given** 三栏布局，**When** 拖拽左/右 sidebar 边框，**Then** 宽度实时变化，比例持久化到 localStorage
3. **Given** 移动端访问，**When** 查看，**Then** 左右 sidebar 折叠为 48px 图标轨道，仅显示 section/settings 图标
4. **Given** 左侧 section 列表，**When** 展开，**Then** Picture/Basics/Summary 在顶部独立；12 个内置 sections 排列其后；Custom 容器在最后
5. **Given** 右侧 settings 面板，**When** 查看，**Then** 12 个子面板：Template、Layout、Typography、Design、Styles、Page、Notes、Sharing、Statistics、Analysis、Export、Information
6. **Given** 任意 settings 子面板，**When** 点击标题，**Then** 折叠/展开该面板（accordion）
7. **Given** 左侧 section 的 item 卡片，**When** 点击，**Then** 弹出编辑 dialog（与 027 的"先选模板"风格一致：Create / Update dialog 分开）
8. **Given** 编辑器顶部，**When** 查看，**Then** 居中显示 home 图标 + breadcrumb (`/` + 简历名 + caret 下拉)，左右各一个 sidebar toggle 按钮

---

### User Story 4 - Layout 多页布局与 dnd-kit 拖拽 (Priority: P1)

用户在右侧 Settings → Layout 面板中，管理多页布局：每页有 Full Width 开关、main 列、sidebar 列；section 在 main/sidebar 之间可拖拽；可添加/删除页。默认 1 页。Full Width 开启时该页 sidebar 合并入 main。每个 section 的 main/sidebar 归属由模板的 sidebarPosition 约束（left sidebar / right sidebar / no sidebar）。用户可拖拽改变 section 在 main 内的顺序。

**Why this priority**: 多页布局是 reactive-resume 的核心差异化——单页简历、内容溢出、混合 sidebar 等场景都靠它。P1 因为它直接影响渲染效果。

**Independent Test**: 创建一个 2 页布局，确认 Page 1 / Page 2 两个卡片显示；把 Profiles 从 main 拖到 sidebar，section 位置实时变化；Full Width 开启，sidebar 内容合并入 main。

**Acceptance Scenarios**:
1. **Given** 新建简历，**When** 打开 Layout 面板，**Then** 默认显示 1 页 (Page 1)，含 Full Width 开关 + main 列（按模板默认顺序列出 sections）+ sidebar 列
2. **Given** Layout 面板，**When** 点击 "Add Page"，**Then** 增加 Page 2 卡片
3. **Given** 2 页布局，**When** 拖拽 section 从 main 到 sidebar，**Then** 该 section 渲染位置实时变化（dnd-kit sortable 库）
4. **Given** 单页，**When** 开启 Full Width，**Then** sidebar 内容合并入 main（单列布局）
5. **Given** 删除某页，**When** 点击 Delete Page 按钮（最后一页禁用），**Then** 该页移除
6. **Given** Layout 面板底部，**When** 查看，**Then** 有 "Sidebar Width" 滑块（10%-50%），数值实时同步到预览
7. **Given** 拖拽 sidebar 内 sections 顺序，**When** 完成，**Then** 预览中的 sidebar section 顺序相应变化

---

### User Story 5 - 主题色三色系统与 level 设计 (Priority: P1)

用户在右侧 Settings → Design 面板中，调整简历的视觉设计：Colors 部分有 primary / text / background 三个 rgba 拾色器（含 22 个快速色板和手动 hex/rgba 输入）；Level 部分有 type combobox（hidden / circle / square / rectangle / rectangle-full / progress-bar / icon）和 icon combobox（1500+ Phosphor 图标可选）。所有调整实时反映到中间预览。

**Why this priority**: 三色系统 + level 设计是 reactive-resume 设计系统的核心，决定整体视觉的"色感"和"质感"。P1 因为它直接决定渲染效果。

**Independent Test**: 调整 primary 颜色从蓝色 (#0084d1) 到橙色 (#ff8c00)，预览区所有 primary 色元素（sidebar 背景、icon、heading 下划线）立即变橙色；切换 level type 从 star 到 progress bar，Skills/Languages 的等级条变进度条样式。

**Acceptance Scenarios**:
1. **Given** Design 面板，**When** 查看 Colors 部分，**Then** 显示 primary / text / background 三个拾色器，每个含 22 个快速色板 + 手动 rgba 输入
2. **Given** 用户调整 primary 颜色，**When** 输入新 rgba 值或点击快速色板，**Then** 预览区所有使用 primary 的元素（sidebar 背景、heading 下划线、icon、level 等级条）实时变化
3. **Given** 用户调整 text 或 background 颜色，**When** 完成，**Then** 预览区所有使用 text/background 的元素（正文文字、卡片背景、sidebar 文字）实时变化
4. **Given** Design 面板 Level 部分，**When** 切换 type combobox 到 progress-bar，**Then** Skills/Languages 的 0-5 等级渲染为进度条
5. **Given** Level type 是 icon，**When** 选择不同的 icon（如 "star" / "heart" / "trophy"），**Then** Skills/Languages 的等级图标实时变化
6. **Given** 调整 design 后，**When** 重新打开简历，**Then** 上次的设计选择被恢复

---

### User Story 6 - Typography 字体与排版 (Priority: P1)

用户在右侧 Settings → Typography 面板中，分 Body 和 Heading 两组独立调整：每组有 Font Family combobox（内置 20+ 字体如 IBM Plex Sans/Serif、Fira Sans Condensed、Roboto、Inter 等）、Font Weight（多选 100-900）、Font Size（6-24 pt）、Line Height（0.5-4 倍数）。所有调整实时反映到预览。

**Why this priority**: Typography 决定简历的"字感"和"气质"，与 color、template 并列三大设计维度。P1 因为它直接决定渲染效果。

**Independent Test**: 把 Body 字体从 IBM Plex Serif 改为 Fira Sans，预览正文字体立即变化；把 Heading 字号从 14 改为 18 pt，section heading 立即变大；Line Height 从 1.5 改为 1.2，行间距立即变窄。

**Acceptance Scenarios**:
1. **Given** Typography 面板，**When** 查看，**Then** 显示 Body 和 Heading 两组控件
2. **Given** Body Font Family combobox，**When** 点击，**Then** 列出至少 20 种字体（IBM Plex Sans/Serif、Fira Sans/Serif/Condensed、Roboto、Inter、Lato、Source Sans Pro、Open Sans、Montserrat、Raleway、PT Sans、Noto Sans、JetBrains Mono 等）
3. **Given** 用户选择新字体，**When** 完成，**Then** 预览区所有正文文字立即应用新字体
4. **Given** Body Font Weight，**When** 切换，**Then** 预览正文字重变化（100-900）
5. **Given** Body Font Size 6-24 pt，**When** 调整，**Then** 预览正文字号变化
6. **Given** Body Line Height 0.5-4 倍数，**When** 调整，**Then** 预览行间距变化
7. **Given** Heading 组，**When** 调整，**Then** section heading 字号/字体/字重/行高独立于 body 调整
8. **Given** 调整 typography 后，**When** 重新打开简历，**Then** 上次选择被恢复

---

### User Story 7 - Page 页面格式与边距 (Priority: P1)

用户在右侧 Settings → Page 面板中，调整：Language combobox（i18n locale）、Format combobox（A4 / Letter / Free-form）、marginX / marginY / gapX / gapY（数字输入，pt 单位）、hideLinkUnderline / hideIcons / hideSectionIcons 三个 switch。所有调整实时反映到预览。

**Why this priority**: 页面格式与边距是简历的"物理约束"，决定能否装入一页、能否通过 ATS 解析。P1 因为它直接影响渲染效果和 ATS 友好度。

**Independent Test**: 把 Format 从 A4 切到 Letter，预览区比例从 1:1.414 变到 1:1.294；marginX 从 14 调到 30 pt，预览内容宽度立即缩小；hideSectionIcons 开启，所有 section heading 前的图标立即隐藏。

**Acceptance Scenarios**:
1. **Given** Page 面板，**When** 查看，**Then** 显示 Language、Format、marginX/Y、gapX/Y、hide* 三个 switch
2. **Given** Format combobox，**When** 切换 A4 / Letter / Free-form，**Then** 预览比例相应变化
3. **Given** marginX / marginY 输入框，**When** 调整数值，**Then** 预览页边距变化
4. **Given** gapX / gapY 输入框，**When** 调整，**Then** 预览 section 间距变化
5. **Given** hideLinkUnderline switch，**When** 开启，**Then** 预览中所有链接下划线消失
6. **Given** hideIcons switch，**When** 开启，**Then** Skills/Profiles/Interests 的 item-level 图标消失
7. **Given** hideSectionIcons switch（默认 true），**When** 关闭，**Then** section heading 前的图标显示出来
8. **Given** 调整 page 后，**When** 重新打开简历，**Then** 上次选择被恢复

---

### User Story 8 - Style Rules 自定义样式 (Priority: P2)

用户在右侧 Settings → Styles 面板中，添加自定义样式规则：每条规则有 Target（global / sectionType / sectionId 三个 scope）、Slots（15 种语义槽：section / heading / item / text / secondaryText / link / icon / level / richParagraph / richList / richListItemRow / richListItemContent / richLink / richBold / richMark）、Intent（Color / Text / Spacing / Border 4 组 CSS-like 属性）。specificity 规则：sectionId > sectionType > global。

**Why this priority**: Style Rules 是 v2 的"高级"能力，让 power user 精细控制每个 section/item 的样式。不是 P1 因为大多数用户用模板默认就够。

**Independent Test**: 创建一个 style rule：target sectionId=experience, slot heading, intent color=orange, 预览中 Experience section heading 立即变橙色；改成 target global, slot link, intent textDecoration=underline, 预览中所有链接都加下划线。

**Acceptance Scenarios**:
1. **Given** Styles 面板，**When** 点击 "Add a new style rule"，**Then** 弹出 rule 编辑器
2. **Given** Target scope，**When** 选择 global / sectionType / sectionId，**Then** 弹出对应 selector（global 无；sectionType 下拉 14 种；sectionId 自动联想）
3. **Given** Slots 列表，**When** 选择，**Then** 15 种语义槽中多选
4. **Given** Intent 编辑器，**When** 查看，**Then** 4 组 CSS-like 属性：Color（text/bg/decoration/opacity）、Text（size/weight/style/lineHeight/letterSpacing/decoration/align/transform）、Spacing（padding/margin 4 边 + row/column gap）、Border（style/width/radius/color）
5. **Given** 用户编辑 style rule，**When** 保存，**Then** 预览中匹配 rule 的元素立即应用
6. **Given** 同 slot 有多个 rule，**When** specificity 冲突，**Then** sectionId > sectionType > global 优先级生效
7. **Given** 删除某 style rule，**When** 完成，**Then** 预览中相应元素的样式恢复默认

---

### User Story 9 - Tiptap 富文本编辑器 (Priority: P1)

用户编辑 Summary、Experience description、Project description 等富文本字段时，使用 Tiptap 富文本编辑器：工具栏含 Bold / Italic / Underline / Strike / Highlight Color / Text Color / Heading 1-6 / 对齐 / Bullet List / Ordered List / Outdent / Indent / Link / Inline Code / Code Block / Table / Hard Break / Horizontal Rule。富文本存为 HTML 字符串。提供 Fullscreen 模式（95svh × 95svw 全屏 Dialog）。

**Why this priority**: 富文本是简历 description 字段的核心交互——加粗关键词、列表化经验、表格化技能对比等都靠它。P1 因为它是 daily-use 能力。

**Independent Test**: 在 Experience description 字段输入文本，加粗 "Engineer" 一词，预览中该词立即变粗；切换到 Bullet List 把 3 段经验转为列表项，预览中显示为列表；点击 Fullscreen 按钮，编辑器全屏。

**Acceptance Scenarios**:
1. **Given** 用户编辑 description 字段（Summary/Experience/Project 等），**When** 聚焦，**Then** 显示 Tiptap 工具栏
2. **Given** 工具栏，**When** 使用，**Then** 15+ 功能：B / I / U / S / Highlight / Text Color / Heading 1-6 / 对齐（左中右两端）/ Bullet / Ordered / Outdent / Indent / Link / Inline Code / Code Block / Table / Hard Break / Horizontal Rule
3. **Given** 用户在富文本中输入，**When** 完成，**Then** 数据存为 HTML 字符串
4. **Given** 用户点击 Fullscreen 按钮，**When** 触发，**Then** 编辑器切换为 95svh × 95svw 全屏 Dialog
5. **Given** 用户按 ESC 或点击关闭，**When** Fullscreen 退出，**Then** 内容保留，回到常规编辑
6. **Given** 富文本支持 Table，**When** 用户插入 2x2 表格，**Then** 预览中显示 2x2 表格（无边框或淡边框，模板决定）
7. **Given** 富文本支持 Link，**When** 用户高亮文本点击 Link 输入 URL，**Then** 文本变为可点击链接，URL 仅接受 http/https

---

### User Story 10 - 8 个 dock 按钮与导出 (Priority: P1)

编辑器底部居中浮动一个 dock（rounded-full），含 8 个图标按钮：Zoom in / Zoom out / Center view / Toggle page stacking（水平堆叠 ↔ 垂直堆叠）/ Open AI agent / Copy URL / Download JSON / Download PDF。两个 Download 按钮触发对应导出格式；前 5 个是查看/导航控制。

**Why this priority**: 导出是简历编辑器的最终目的——用户做完简历要能拿到 PDF。P1 因为它是 daily-use 能力。

**Independent Test**: 点击 Download PDF，浏览器下载文件名为 `{slug}-{YYYY-MM-DD}.pdf` 的 PDF；点击 Download JSON，下载完整 JSON 数据。

**Acceptance Scenarios**:
1. **Given** 编辑器底部，**When** 查看，**Then** 居中浮动一个 rounded-full dock，含 8 个图标按钮
2. **Given** Zoom in / Zoom out，**When** 点击，**Then** 预览缩放 0.5x-5x，smooth 动画
3. **Given** Center view，**When** 点击，**Then** 预览回到默认居中位置
4. **Given** Toggle page stacking，**When** 点击，**Then** 多页从水平排列切换到垂直排列
5. **Given** Open AI agent，**When** 点击，**Then** 导航到 `/agent/new?resumeId=...`
6. **Given** Copy URL，**When** 点击，**Then** 复制 `{origin}/r/{username}/{slug}` 到剪贴板，toast 提示
7. **Given** Download JSON，**When** 点击，**Then** 下载完整 JSON Resume Data
8. **Given** Download PDF，**When** 点击，**Then** 下载 `.pdf` 文件（按当前模板 + layout 渲染），文件名 `{slug}-{YYYY-MM-DD}.pdf`

---

### User Story 11 - 公开分享链接 + 密码保护 + 统计 (Priority: P2)

用户在右侧 Settings → Sharing 面板中，开启 "Allow Public Access" 开关后，简历生成公开 URL（`{origin}/r/{username}/{slug}`），任何人都可查看（但不能编辑）。可选 Set Password 设置 6-64 字符密码，访问者需输入密码才能查看。开启公开后，Statistics 面板激活：实时显示 views 和 downloads 计数 + 最后访问/下载时间。

**Why this priority**: 分享链接是简历的"出口"——求职时把链接发给 HR。P2 因为不是 daily-use，但缺它就少一个重要能力。

**Independent Test**: 开启公开访问，用 incognito 窗口打开 URL，确认能正常查看；回到原窗口确认 Statistics 显示 +1 view；开启密码保护，incognito 访问需输入密码才能查看。

**Acceptance Scenarios**:
1. **Given** Sharing 面板，**When** 开启 "Allow Public Access" 开关，**Then** 显示公开 URL（只读 + 复制按钮）
2. **Given** 公开 URL，**When** 在新窗口/incognito 打开，**Then** 简历以只读模式渲染（无编辑入口）
3. **Given** Set Password，**When** 设置 6-64 字符密码，**Then** 公开访问者需输入密码才能查看
4. **Given** 密码保护，**When** 公开访问者输入错误密码，**Then** 拒绝访问
5. **Given** 公开访问者输入正确密码，**When** 验证，**Then** 简历渲染，10 分钟内同一浏览器免再次输入
6. **Given** 简历已公开，**When** Statistics 面板查看，**Then** 显示 views / downloads 计数 + lastViewedAt / lastDownloadedAt
7. **Given** 简历已公开，**When** 公开访问者访问，**Then** Statistics 实时 +1 view（owner 自身访问不计）
8. **Given** 简历从公开切回私有，**When** 完成，**Then** 公开 URL 立即失效，访问者看到 404

---

### User Story 12 - 500ms auto-save 与实时同步 (Priority: P1)

用户编辑简历时，所有修改通过 Zustand store + immer 立即应用到内存，并通过 500ms debounce 触发后台保存（PUT `/api/v1/v2/resumes/{id}`）。保存期间再次编辑则取消旧请求、合并到新请求。`beforeunload` 事件强制 flush 一次保存。服务端用 PostgreSQL LISTEN/NOTIFY 实现 SSE 实时推送：其他标签页/设备的修改实时反映到当前编辑器（无本地未保存改动时直接替换，有则合并 metadata）。锁定状态的简历拒绝所有修改（toast 提示）。

**Why this priority**: auto-save 是数据安全的最后一道防线——用户不会因为刷新页面丢失工作。P1 因为它是 daily-use 能力。

**Independent Test**: 在编辑器中修改字段，500ms 后网络面板出现 PUT 请求；刷新页面，所有数据原样恢复；在两个标签页同时打开同一简历，在一个标签页编辑，另一个标签页 1 秒内看到修改。

**Acceptance Scenarios**:
1. **Given** 用户编辑字段，**When** 完成 500ms 内无新编辑，**Then** 触发 PUT 保存请求
2. **Given** 500ms 内连续多次编辑，**When** 完成最后一次编辑，**Then** 只触发 1 次 PUT 请求
3. **Given** 保存期间用户继续编辑，**When** 完成，**Then** 取消旧请求、合并到新请求（AbortController）
4. **Given** 用户关闭页面，**When** 触发 beforeunload，**Then** 强制 flush 一次保存
5. **Given** 简历已锁定，**When** 用户尝试编辑，**Then** toast 提示"This resume is locked and cannot be updated."，不触发 PUT
6. **Given** 同一简历在两个标签页打开，**When** 一个标签页编辑并保存，**Then** 另一个标签页 1 秒内通过 SSE 收到更新
7. **Given** 另一标签页有未保存本地编辑，**When** SSE 推送更新，**Then** 合并 metadata（slug/name/isPublic），保留本地 data
8. **Given** 用户按 Cmd+S，**When** 触发，**Then** 不保存（已自动），仅 toast 提示"Your changes are saved automatically."

---

### User Story 13 - 模板市场 (Square 模板市场兼容) (Priority: P3)

用户访问 `/resume/marketplace` 页面，浏览 Square 模板市场（已在 027 完成）：可按行业、风格筛选模板；点击模板查看详情（缩略图 + 描述 + tags）；点击 "Use this template" 跳转到新简历编辑器，自动应用该模板的配置（template + theme + colors + typography + sample data）。

**Why this priority**: 模板市场是 027 已完成的能力，v2 主要做模板格式升级（兼容新数据模型）。

**Independent Test**: 打开模板市场，确认至少 4 个模板卡片可见；点击 Pikachu 模板的 "Use this template"，新建 v2 简历并应用 Pikachu 配置。

**Acceptance Scenarios**:
1. **Given** 用户访问 `/resume/marketplace`，**When** 查看，**Then** 看到 Square 模板市场页面
2. **Given** 模板卡片，**When** 点击，**Then** 弹出详情：缩略图 + 名称 + 描述 + tags
3. **Given** "Use this template" 按钮，**When** 点击，**Then** 创建新 v2 简历，自动应用模板配置（含 sample data）
4. **Given** 模板市场筛选，**When** 按 industry / style 筛选，**Then** 模板卡片实时过滤
5. **Given** 027 模板市场数据格式（JSON），**When** v2 加载，**Then** 兼容：旧模板数据映射到 v2 字段（缺失字段用默认值）

---

### User Story 14 - AI 简历分析 (Priority: P2)

用户访问右侧 Settings → Analysis 面板（或 Open AI agent dock 按钮），启动 AI 简历分析：AI 评估简历整体得分（0-100）、按 10 个维度评分（内容完整性 / 量化程度 / 关键词密度 / 行业匹配 / 表达清晰 / 格式规范 / 长度合适 / 技能相关性 / 经验连续性 / 整体影响），列出 Top 3-5 优点和 3-5 改进建议（每个建议按 high/medium/low impact 排序，包含 why + example rewrite 示例）。分析结果存到 resume_analysis 表，1 简历 1 分析。

**Why this priority**: AI 分析是 reactive-resume v5 的亮点能力，也是 InterCraft 027 已实现的能力扩展。P2 因为它属于锦上添花。

**Independent Test**: 打开 Analysis 面板，点击 "Analyze"，等待 30 秒，确认出现 overall score、10 维度评分、strengths、suggestions。

**Acceptance Scenarios**:
1. **Given** Analysis 面板，**When** 点击 "Analyze Resume"，**Then** 触发 AI 分析请求，显示 loading
2. **Given** AI 分析完成，**When** 查看，**Then** 显示 Overall Score（圆环 0-100）+ 10 维度评分（进度条）
3. **Given** 分析结果，**When** 查看 Strengths 部分，**Then** 列出 3-5 个优点（简短陈述）
4. **Given** 分析结果，**When** 查看 Suggestions 部分，**Then** 列出 3-5 个建议，按 high/medium/low impact 排序，每个含 why 解释 + example rewrite 示例
5. **Given** AI provider 不可用，**When** 打开 Analysis 面板，**Then** 显示 DisabledState + 配置 AI provider 提示
6. **Given** 简历修改后，**When** 再次分析，**Then** 更新 resume_analysis 表（同 resumeId 单条记录覆盖）

---

### User Story 16 - Duplicate 简历变体 (Priority: P2)

用户在简历列表卡片右上角（或编辑器顶部 dock）点击「Duplicate」按钮，系统在 1 秒内创建一份新 v2 简历：复制源简历的 `data`（ResumeDataV2 完整内容）+ `metadata.template` + `metadata.layout` + `metadata.page` + `metadata.design` + `metadata.typography` + `metadata.styleRules` + `metadata.notes`；生成新的 `id` (UUIDv7) + 新的 `slug`（源 slug + `-copy-N`，N 为该 slug 下副本计数）+ `name` 加「(Copy)」后缀（中文环境显示「(副本)」）；`is_public` 重置为 false；`is_locked` 重置为 false；`password_hash` 置空；`resume_statistics_v2` 不复制（新建空记录）；`resume_analysis_v2` 不复制；创建后自动跳转到新简历编辑器。

**Why this priority**: 求职场景下用户经常根据不同 JD 调整简历内容（项目经验侧重 / 技能关键词 / 个人陈述）。没有 Duplicate 意味着每次都要从模板市场或空模板手动重建，效率极差。P2 因为不是 daily-use，但是高频使用的能力。

**Independent Test**: 创建简历 A，编辑后 Duplicate，确认新简历 B 生成；B 的 name 是 A 加「(Copy)」；B 的 slug 是 A 加 `-copy-1`；B 的 data 与 A 完全相同；B 的 is_public 是 false；编辑 B 的内容不影响 A；删除 B 不影响 A。

**Acceptance Scenarios**:
1. **Given** 简历列表中有简历 A，**When** 点击 A 卡片上的「Duplicate」按钮，**Then** 1 秒内创建简历 B 并跳转到 B 的编辑器
2. **Given** 简历 A 的 name 是「Senior Engineer」，**When** Duplicate，**Then** B 的 name 是「Senior Engineer (Copy)」（中文环境「Senior Engineer (副本)」）
3. **Given** 简历 A 的 slug 是 `senior-eng`，**When** Duplicate，**Then** B 的 slug 是 `senior-eng-copy-1`
4. **Given** 简历 A 的 data 完整内容，**When** Duplicate，**Then** B 的 data 与 A 字段级完全相同（包括所有 section items + metadata）
5. **Given** 简历 A 是公开的，**When** Duplicate，**Then** B 是私有的（is_public = false）
6. **Given** 简历 A 已分析过（resume_analysis_v2 有记录），**When** Duplicate，**Then** B 无分析记录，Analysis 面板显示「未分析」状态
7. **Given** 简历 A 存在 -copy-1 已占用，**When** 再次 Duplicate A，**Then** 新简历 slug 是 `senior-eng-copy-2`，N 自动递增
8. **Given** 用户在编辑器中，**When** 查看 dock，**Then** 顶部 dock 也有「Duplicate」按钮，点击行为与列表卡片一致

### User Story 17 - Undo/Redo 20 步历史栈 (Priority: P2)

用户在编辑器中按 Ctrl/Cmd+Z 撤销最近一次编辑，按 Ctrl/Cmd+Shift+Z 重做。系统维护最近 20 步 ResumeDataV2 全量快照栈；用户每次编辑后入栈（栈满则丢弃最旧）；连续 30 分钟无编辑活动后整个历史栈清空（避免内存膨胀）；重做栈在用户新编辑时清空（标准编辑器行为）。所有 section 字段（text / select / rich text / DnD 排序）均纳入撤销范围；模板切换 / 设计调整 / 字体调整也纳入；模板市场 Duplicate 不纳入（独立操作流）。

**Why this priority**: 编辑器核心交互的肌肉记忆——用户在 027 编辑器中已习惯 Ctrl+Z。v2 数据模型更复杂，误改一个字段的影响更大，没有 Undo 体验割裂。P2 因为可与 auto-save + COW 互补，不阻塞 MVP。

**Independent Test**: 在 Summary 字段输入 5 段文本；按 Ctrl+Z 4 次，文本回到第 1 段；按 Ctrl+Shift+Z 2 次，文本回到第 3 段；输入新文本后，redo 栈清空；空闲 30 分钟后按 Ctrl+Z，提示「历史已过期」toast，撤销栈空。

**Acceptance Scenarios**:
1. **Given** 用户编辑了 5 个字段，**When** 按 Ctrl/Cmd+Z 4 次，**Then** 字段值依次回退到第 4/3/2/1 次编辑前的状态
2. **Given** 用户撤销了 N 步，**When** 按 Ctrl/Cmd+Shift+Z，**Then** 字段值依次前进（M ≤ N 步）
3. **Given** 用户撤销 5 步后输入新内容，**When** 完成，**Then** redo 栈清空（按 Ctrl+Shift+Z 不再前进到被撤销的内容）
4. **Given** 连续 30 分钟无编辑活动，**When** 之后按 Ctrl+Z，**Then** toast 提示「历史已过期」+ 撤销栈为空（无操作）
5. **Given** 历史栈已满 20 步，**When** 继续编辑，**Then** 最旧一步被丢弃，栈深度仍 ≤ 20
6. **Given** 用户在 Templates Gallery 切换模板，**When** 完成，**Then** 此操作也纳入撤销栈（按 Ctrl+Z 可回退到切换前的模板）
7. **Given** 用户点击 Duplicate 按钮，**When** 完成，**Then** Duplicate 操作 NOT 纳入撤销栈（独立操作流，避免误撤销破坏新简历）
8. **Given** 用户在撤销过程中触发 auto-save，**When** 完成，**Then** 撤销栈状态不变（仅快照 data 同步到服务器）

### User Story 15 - 模板切换实时预览 + 数据兼容 (Priority: P1)

用户切换模板时，预览实时更新（无需刷新页面），所有 section 数据原样保留（模板不修改数据，只改变渲染样式）。从 block 模式导入的旧简历在 v2 中标记为"legacy"，不可编辑但可只读查看（不破坏用户体验）。新简历走 v2 数据模型。`metadata.template` 字段存储当前模板 ID（8-10 套之一）。

**Why this priority**: 数据兼容是 v2 切换的关键——不能丢失用户已有数据。P1 因为它是 daily-use 能力。

**Independent Test**: 切换模板，确认预览实时变化；确认 section 数据不变；打开旧 block 简历，确认提示信息正确显示。

**Acceptance Scenarios**:
1. **Given** 用户切换模板，**When** 完成，**Then** 预览实时更新，数据无任何修改
2. **Given** 用户切换模板，**When** 重新打开简历，**Then** 上次模板被恢复
3. **Given** 旧 block 简历，**When** 打开 v2 编辑器，**Then** 显示"该简历使用旧版格式，请创建新版 v2 简历"提示，无编辑入口
4. **Given** 旧 block 简历，**When** 查看只读模式，**Then** 按原 v1 Markdown 渲染（保留原木及模板），仅供只读
5. **Given** 新 v2 简历，**When** 模板字段为某模板 ID，**Then** 数据存储用 `metadata.template` 字段（与 reactive-resume v5 一致）
6. **Given** 模板切换性能，**When** 切换，**Then** 预览更新延迟 < 1 秒（500ms debounce + 渲染）

---

### Edge Cases

- **模板切换时 section 数据不匹配**：某些 section 在 A 模板有 sidebar、B 模板无 sidebar；切换后 section 数据保留，layout 自动调整归属（无 sidebar 模板：所有 section 移入 main）
- (已删除 — v2 仅使用预置 Google Fonts 子集，不支持用户字体上传；详见 research.md §2 依赖决策)
- **预览 PDF 渲染失败（Playwright 异常）**：前端 5 秒后显示 fallback 提示"PDF 渲染失败，请稍后重试或导出 PDF"
- **多端并发编辑同一简历**：服务端按 lastModified 拒绝旧版本（409 冲突），提示用户刷新
- **模板 Gallery 中的模板预览图加载失败**：fallback 到默认占位图，不阻塞 dialog
- **大字段（Summary > 50000 字符）**：前端限制输入长度 50000；超出时阻止输入
- **section item 数量超过 100 个**：限制 100 个/branch；超出时阻止添加并提示
- **DND 拖拽到无效位置（sidebar 模板无 sidebar）**：拖拽时目标区高亮提示"该模板无 sidebar，请切换模板或选择 full width"
- **公开 URL 被搜索引擎收录**：默认 `<meta name="robots" content="noindex, follow">`，不主动推 SEO
- **密码保护失效（10 分钟 cookie 过期）**：用户需重新输入密码

---

## Requirements *(mandatory)*

### Functional Requirements

#### 数据模型

- **FR-001**: System MUST 新建数据表 `resumes_v2` 存储 v2 简历，包含 `id` (UUIDv7), `user_id` (FK users), `name` (1-64 chars), `slug` (URL-friendly, unique per user), `tags` (text[]), `is_public` (boolean), `is_locked` (boolean), `password_hash` (bcrypt, nullable), `data` (jsonb, ResumeDataV2), `created_at`, `updated_at`
- **FR-002**: System MUST 新建数据表 `resume_statistics_v2` 存储 v2 简历统计，包含 `resume_id` (FK, 1:1), `views` (int default 0), `downloads` (int default 0), `last_viewed_at`, `last_downloaded_at`
- **FR-003**: System MUST 新建数据表 `resume_analysis_v2` 存储 v2 简历 AI 分析，1:1 with `resumes_v2`
- **FR-004**: `data` (jsonb) MUST 遵循 `ResumeDataV2` Zod schema：`{ picture, basics, summary, sections: { profiles, experience, education, projects, skills, languages, interests, awards, certifications, publications, volunteer, references }, customSections: CustomSection[], metadata: { template, layout, page, design, typography, notes, styleRules } }`
- **FR-005**: `metadata.template` MUST 是 8-10 套模板的 enum 之一（`onyx` / `azurill` / `kakuna` / `chikorita` / `ditgar` / `bronzor` / `pikachu` / `lapras` / `scizor` / `rhyhorn`）
- **FR-006**: `metadata.layout` MUST 是 `{ sidebarWidth: 10..50, pages: [{ fullWidth: boolean, main: string[], sidebar: string[] }] }`
- **FR-007**: `metadata.page` MUST 是 `{ gapX, gapY, marginX, marginY, format: "a4"|"letter"|"free-form", locale, hideLinkUnderline, hideIcons, hideSectionIcons }`
- **FR-008**: `metadata.design` MUST 是 `{ level: { icon: IconName, type: "hidden"|"circle"|"square"|"rectangle"|"rectangle-full"|"progress-bar"|"icon" }, colors: { primary: rgba, text: rgba, background: rgba } }`
- **FR-009**: `metadata.typography` MUST 是 `{ body: { fontFamily, fontWeights[], fontSize: 6..24, lineHeight: 0.5..4 }, heading: {...} }`
- **FR-010**: `metadata.styleRules` MUST 是 `StyleRule[]`，每条 rule 含 `id`, `label`, `enabled`, `target: { scope: "global"|"sectionType"|"sectionId", sectionType?, sectionId? }`, `slots: Partial<Record<StyleSlot, StyleIntent>>`
- **FR-011**: System MUST 保留 v1 旧 block 简历表 `resume_branches` 不删除；`data_format_version` 字段标记 v1/v2
- **FR-012**: System MUST 拒绝 v1 简历的 v2 写入操作（API 返回 400 错误 + `LEGACY_FORMAT` 错误码）

#### 12+ sections 数据模型

- **FR-013**: System MUST 支持 12 个内置 section 类型：`profiles` / `experience` / `education` / `projects` / `skills` / `languages` / `interests` / `awards` / `certifications` / `publications` / `volunteer` / `references`
- **FR-014**: 每个内置 section MUST 是 `{ title, icon: IconName, columns: 1..6, hidden: boolean, items: Item[] }`
- **FR-015**: `summary` section MUST 是 singleton（不在 sections 内，在根级）：`{ title, icon, columns, hidden, content: html }`
- **FR-016**: `experience` item MUST 含 `company` / `position` / `period` / `location` / `website: { url, label, inlineLink }` / `description: html` / `roles: { position, period, description }[]`
- **FR-017**: `education` item MUST 含 `school` / `degree` / `area` / `grade` / `location` / `period` / `website` / `description`
- **FR-018**: `projects` item MUST 含 `name` / `period` / `website` / `description`
- **FR-019**: `skills` item MUST 含 `name` / `level: 0..5` / `keywords: string[]` / `icon` / `iconColor`
- **FR-020**: `languages` item MUST 含 `language` / `fluency` / `level: 0..5`
- **FR-021**: `profiles` item MUST 含 `network` / `username` / `website: { url, label, inlineLink }` / `icon` / `iconColor`
- **FR-022**: `interests` item MUST 含 `name` / `keywords: string[]` / `icon` / `iconColor`
- **FR-023**: `awards` / `certifications` / `publications` items MUST 含 `title` / `awarder|issuer|publisher` / `date` / `website` / `description`
- **FR-024**: `volunteer` item MUST 含 `organization` / `location` / `period` / `website` / `description`
- **FR-025**: `references` item MUST 含 `name` / `position` / `website` / `phone` / `description`
- **FR-026**: System MUST 支持 `customSections: CustomSection[]`，每条 custom section 含 `id` (UUID), `type` (14 种 sectionType 之一), `title`, `icon`, `columns`, `hidden`, `items: CustomSectionItem[]`
- **FR-027**: System MUST 支持 `basics: { name, headline, email, phone, location, website, customFields: { id, icon, name, value }[] }`

#### 8-10 套模板

- **FR-028**: System MUST 提供 10 套精选模板（onyx / azurill / kakuna / chikorita / ditgar / bronzor / pikachu / lapras / scizor / rhyhorn），每套含 HTML/CSS 渲染器（由 027 Playwright 管线渲染为 PDF；无 DOCX 渲染器）
- **FR-029**: 每套模板 MUST 是 `TemplatePage` 组件，接收 `data: ResumeDataV2` props，输出 PDF `<Page>` 段落
- **FR-030**: System MUST 提供 `templateSchema = z.enum([...])` 强类型校验
- **FR-031**: Template Gallery MUST 展示模板缩略图（来自 `public/templates/jpg/{name}.jpg`，4 列网格布局）
- **FR-032**: 切换模板 MUST 实时（<1 秒）更新预览，不修改 `data` 字段
- **FR-033**: 模板 MUST 支持模板特定的 sidebar 位置（left / right / none）；无 sidebar 模板自动把所有 section 移入 main

#### 三栏编辑器

- **FR-034**: 编辑器 MUST 是三栏 ResizableGroup 布局：左 section 列表（默认 22%）/ 中预览（默认 56%）/ 右 settings（默认 22%）
- **FR-035**: 拖拽左/右 sidebar 边框 MUST 实时调整宽度；比例持久化到 localStorage / cookie
- **FR-036**: 移动端 MUST 折叠 sidebar 为 48px 图标轨道（< sm 断点）
- **FR-037**: 左侧 MUST 列出 16 个 sections：Picture / Basics / Summary / 12 内置 / Custom / Custom fields
- **FR-038**: 右侧 MUST 提供 12 个 settings 子面板：Template / Layout / Typography / Design / Styles / Page / Notes / Sharing / Statistics / Analysis / Export / Information
- **FR-039**: 任意 settings 子面板 MUST 可折叠（accordion）

#### 12 个 settings 子面板

- **FR-040**: Template 面板 MUST 显示当前模板缩略图 + 名称 + 描述 + 3-5 个标签 + "Swap" 按钮
- **FR-041**: Layout 面板 MUST 支持多页布局：每页 Full Width 开关 + main 列 + sidebar 列 + Delete Page 按钮 + Add Page 按钮 + 整体 Sidebar Width 滑块
- **FR-042**: Section 在 main/sidebar 间 MUST 可拖拽（@dnd-kit/core + @dnd-kit/sortable）
- **FR-043**: Typography 面板 MUST 独立调整 body / heading 字体、字重、字号、行高
- **FR-044**: Design 面板 MUST 含 Colors（primary/text/background rgba 拾色器 + 22 快速色板）+ Level（type + icon）
- **FR-045**: Styles 面板 MUST 支持自定义 style rules：Target (global/sectionType/sectionId) + Slots (15 种) + Intent (Color/Text/Spacing/Border)
- **FR-046**: Style rules resolution MUST 遵循 specificity：`sectionId > sectionType > global`，合并方式为 Object.assign per slot
- **FR-047**: Page 面板 MUST 支持 Format (A4/Letter/Free-form) + Language + marginX/Y + gapX/Y + hide* 三个 switch
- **FR-048**: Notes 面板 MUST 提供私有 Tiptap 富文本笔记，不对外暴露
- **FR-049**: Sharing 面板 MUST 含 "Allow Public Access" switch + 公开 URL（只读 + 复制按钮）+ Set Password / Remove Password
- **FR-050**: Statistics 面板 MUST 在公开时显示 views/downloads 计数 + lastViewedAt/lastDownloadedAt
- **FR-051**: Analysis 面板 MUST 含 "Analyze Resume" 按钮 + Overall Score 圆环 + 10 维度评分 + Strengths + Suggestions
- **FR-052**: Export 面板 MUST 含 JSON / PDF 两个下载按钮

#### Layout 拖拽

- **FR-053**: System MUST 使用 `@dnd-kit/core` + `@dnd-kit/sortable` 实现 main/sidebar 拖拽
- **FR-054**: 拖拽 Section 时 MUST 显示 placeholder/drop indicator
- **FR-055**: 拖拽完成后 MUST 立即保存到 `metadata.layout.pages[].main/sidebar`
- **FR-056**: Full Width 开启时 MUST 把 sidebar items 合并入 main，单列渲染

#### 模板画廊

- **FR-057**: Template Gallery 必须是 modal/dialog，4 列网格布局
- **FR-058**: 每个模板卡片 MUST 含缩略图、名称、描述、3-5 个标签
- **FR-059**: 点击模板卡片 MUST 关闭 dialog 并应用模板

#### Tiptap 富文本

- **FR-060**: 富文本编辑器 MUST 用 Tiptap 库
- **FR-061**: 工具栏 MUST 含：B / I / U / S / Highlight Color / Text Color / Heading 1-6 / 对齐 / Bullet / Ordered / Outdent / Indent / Link / Inline Code / Code Block / Table / Hard Break / Horizontal Rule
- **FR-062**: 富文本 MUST 存为 HTML 字符串
- **FR-063**: Tiptap MUST 支持 Fullscreen 模式（95svh × 95svw Dialog）
- **FR-064**: Tiptap MUST 支持 RTL（i18n.locale 为 rtl 时）
- **FR-065**: Link MUST 仅接受 http/https URL

#### 8 个 dock 按钮

- **FR-066**: Dock MUST 是 fixed bottom-4 center, rounded-full 容器
- **FR-067**: Dock MUST 含 8 个图标按钮：Zoom in / Zoom out / Center view / Toggle page stacking / Open AI agent / Copy URL / Download JSON / Download PDF
- **FR-068**: 每个 dock 按钮 MUST 有 tooltip（top）+ hover y:-1 scale:1.04 动画

#### 导出

- **FR-069**: System MUST 支持 JSON 导出（直接 JSON.stringify ResumeDataV2）
- **FR-070**: [已删除 — 详见 Clarifications：v2 不提供 DOCX 导出]
- **FR-071**: System MUST 支持 PDF 导出（按当前模板 + layout 渲染为 .pdf，文件名 `{slug}-{YYYY-MM-DD}.pdf`）
- **FR-072**: PDF 渲染 MUST 走后端 Playwright（与 027 一致）；前端生成完整 HTML（含主题 CSS + 分页标记 + style 内联），后端只包壳渲染
- **FR-073**: preview↔PDF MUST 零漂移（同一 HTML 生成器）
- **FR-074**: PDF 渲染 MUST 异步队列（避免单次大请求阻塞 worker）；超时 60s

#### 公开分享 + 统计

- **FR-075**: System MUST 提供公开 URL `{origin}/r/{username}/{slug}`，公开访问者只读模式
- **FR-076**: Set Password MUST 接受 6-64 字符密码，bcrypt 哈希存储
- **FR-077**: 密码验证后 MUST 设置 HttpOnly cookie（10 分钟 TTL），同一浏览器免再次输入
- **FR-078**: 公开访问者非 owner 访问 MUST `views++` 计数（owner 自身不计）
- **FR-079**: Download PDF MUST `downloads++` 计数
- **FR-080**: 公开页面 MUST `<meta name="robots" content="noindex, follow">` 防 SEO 收录

#### auto-save + 实时同步

- **FR-081**: 编辑 MUST 走 Zustand store + immer；500ms debounce 后 PUT `/api/v1/v2/resumes/{id}`
- **FR-082**: 保存期间再次编辑 MUST 取消旧请求（AbortController）+ 合并到新请求
- **FR-083**: `beforeunload` MUST 强制 flush 一次保存
- **FR-084a**: `resumes_v2` MUST 新增 `version: int` 字段（默认 0），每次成功 PUT 后 `version+1`；PUT 请求 MUST 带 `If-Match: version` header
- **FR-084b**: 当 PUT 检测到 version 不匹配（被其他设备/标签页抢先保存），服务端 MUST 返回 HTTP 409 + 响应体含最新 `data` + 最新 `version`
- **FR-084c**: 客户端收到 409 MUST 自动重新 GET 拉取最新数据并 toast 提示「其他设备刚保存了更新，正在刷新数据」；不阻塞本地编辑过程，乐观并发
- **FR-084d**: `is_locked: boolean` 字段 MUST 仅用于 owner 主动设置的「永久只读锁」（如分享前冻结定稿版本），与并发编辑锁解耦
- **FR-085**: System MUST 通过 PostgreSQL LISTEN/NOTIFY + SSE 推送实时更新
- **FR-086**: SSE 推送时如有本地未保存改动 MUST 合并 metadata 保留本地 data

#### AI 简历分析

- **FR-087**: System MUST 通过 InterCraft 的 LLM 配置（DeepSeek V4 Pro）做 AI 简历分析
- **FR-088**: 分析结果 MUST 含 Overall Score (0-100) + 10 维度评分（内容完整性/量化程度/关键词密度/行业匹配/表达清晰/格式规范/长度合适/技能相关性/经验连续性/整体影响）
- **FR-089**: 分析结果 MUST 含 3-5 个 Strengths + 3-5 个 Suggestions（按 high/medium/low impact 排序）
- **FR-090**: 每条 Suggestion MUST 含 why 解释 + example rewrite 示例
- **FR-091a**: AI 调用 MUST 不设用户级限额、不做结果缓存；调用频率完全由用户控制
- **FR-091b**: DeepSeek V4 Pro 返回 429 / 5xx 时 MUST 自动 retry 3 次（指数退避 1s / 2s / 4s），3 次后仍失败则 `resume_analysis_v2.status='failed'`，前端 toast「服务繁忙，请稍后重试」并展示失败状态
- **FR-091c**: AI provider 不可用时 MUST 显示 DisabledState 提示

#### 模板市场兼容

- **FR-092**: Square 模板市场 MUST 兼容 v2 数据模型
- **FR-093**: 旧模板数据（v1 JSON 格式） MUST 映射到 v2 字段（缺失字段用默认值）
- **FR-094**: 模板市场 MUST 支持按 industry / style 筛选

#### 兼容与降级

- **FR-095**: 旧 v1 block 简历 MUST 可只读访问（不破坏现有用户体验）
- **FR-096**: 旧 v1 block 简历 MUST 提示"该简历使用旧版格式，请创建新版 v2 简历"
- **FR-097**: System MUST 不动 auth / jobs / interviews / errors / ability_profile / agents 等其他模块
- **FR-098**: System MUST 提供 `POST /api/v1/v2/resumes/{id}/duplicate` endpoint，body 空，response 含新简历完整数据
- **FR-099**: Duplicate 流程 MUST 复制 `data` (jsonb) + `metadata` 全部子字段；生成新的 `id` (UUIDv7) + 新的 `slug`（源 slug + `-copy-N`，N 为该用户下该源 slug 已存在的副本计数 + 1）；`name` 追加「(Copy)」后缀（中文环境 i18n 翻译为「(副本)」）
- **FR-100**: Duplicate 流程 MUST 重置 `is_public=false` / `is_locked=false` / `password_hash=null` / `resume_statistics_v2` 不复制（创建空记录：views=0, downloads=0） / `resume_analysis_v2` 不复制（不创建记录，Analysis 面板显示「未分析」）
- **FR-101**: Zustand store MUST 维护 ResumeDataV2 历史快照栈，深度上限 20 步；栈满时丢弃最旧
- **FR-102**: 编辑器 MUST 绑定 Ctrl/Cmd+Z 触发撤销、Ctrl/Cmd+Shift+Z 触发重做；新编辑 MUST 清空 redo 栈
- **FR-103**: 连续 30 分钟无编辑活动后 MUST 清空整个历史栈（避免内存膨胀）；之后按 Ctrl+Z 显示 toast「历史已过期」

### Key Entities *(include if feature involves data)*

- **ResumeV2 (DB row)**: 主表 — id / user_id / name / slug / tags / is_public / is_locked / password_hash / data (jsonb) / created_at / updated_at
- **ResumeDataV2 (jsonb)**: 简历数据 — picture / basics / summary / sections (12) / customSections / metadata
- **Metadata**: template (10 enum) / layout (sidebarWidth + pages[]) / page (gapX/Y + marginX/Y + format + locale + hide*) / design (level + colors) / typography (body + heading) / notes (html) / styleRules[]
- **StyleRule**: id / label / enabled / target (global/sectionType/sectionId) / slots (15 种)
- **StyleSlot**: 15 种语义槽 — section / heading / item / text / secondaryText / link / icon / level / richParagraph / richList / richListItemRow / richListItemContent / richLink / richBold / richMark
- **ResumeStatisticsV2**: views / downloads / lastViewedAt / lastDownloadedAt (1:1 with ResumeV2)
- **ResumeAnalysisV2**: analysis (jsonb, 10 维度评分 + strengths + suggestions) + status (`'success' | 'failed'`, default `'success'`) + failure_reason (nullable) (1:1 with ResumeV2)
- **Template (8-10 套)**: onyx / azurill / kakuna / chikorita / ditgar / bronzor / pikachu / lapras / scizor / rhyhorn — 每套含 PDF 渲染器（无 DOCX）
- **IconName**: 1500+ Phosphor 图标 enum（如 "github-logo" / "linkedin-logo" / "star" / "trophy" / "circle" / "square" 等）

---

## Success Criteria *(mandatory)*

### 可衡量的成果

- **SC-001**: 用户可在 5 分钟内创建一份 v2 简历（选择模板 + 填写 6 个核心 section + 预览）
- **SC-002**: 模板切换延迟 < 1 秒（500ms debounce + 渲染）
- **SC-003**: preview↔PDF 零漂移：同一份数据生成的 HTML 和 PDF 在排版、分页、样式上字节级一致
- **SC-004**: 8-10 套模板视觉差异显著（10 个模板中任意两个至少有 3 个视觉特征差异：sidebar 位置 / header 风格 / section heading 样式 / 背景色 / icon 系统）
- **SC-005**: PDF 导出成功率 ≥ 99%（错误情况 5 秒内 fallback）
- **SC-006**: [已删除 — 详见 Clarifications：v2 不提供 DOCX 导出]
- **SC-007**: auto-save 500ms debounce 触发，2 次连续编辑合并为 1 次 PUT 请求
- **SC-008**: SSE 实时同步延迟 < 2 秒（一个标签页编辑后，另一个标签页 2 秒内看到）
- **SC-009**: 公开分享 URL 命中率 100%（开启公开后任何浏览器可访问）
- **SC-010**: 密码保护 cookie 10 分钟 TTL 准确（过期后必须重新输入）
- **SC-011**: AI 简历分析响应 < 60 秒（typical 30 秒）
- **SC-012**: Tiptap 富文本支持 18+ 功能，Fullscreen 模式可用
- **SC-013**: 三栏布局响应式：桌面 22/56/22，移动端 sidebar 折叠为 48px
- **SC-014**: 样式与模板解耦：每套模板独立于其他模板，切换不影响 data 字段
- **SC-015**: 旧 v1 简历只读访问可用，提示清晰，无破坏性变更
- **SC-016**: 端到端 E2E 测试（Playwright）覆盖：创建 → 编辑 → 切换模板 → 调整设计 → 导出 PDF → 公开分享 → AI 分析 全链路
- **SC-017**: 用户对 v2 渲染效果的满意度 ≥ 4/5（相比 v1 提升）
- **SC-018**: 模板多样性提升：用户首屏看到的视觉变化数从 4 套（v1）提升到 8-10 套（v2）

### 验收检查

- [ ] 通过 Playwright E2E 完整跑通 6+ 关键场景
- [ ] 8-10 套模板在编辑器中均可应用，预览正确
- [ ] 后端 Playwright PDF 渲染输出与前端 preview 视觉一致
- [ ] 公开分享 URL 可在 incognito 窗口打开
- [ ] AI 简历分析返回 10 维度评分
- [ ] 500ms auto-save 正常触发，SSE 实时同步工作
- [ ] 旧 v1 简历只读访问可用

---

## Assumptions

- v2 的前端/后端数据流与 027 一致（前端生成 HTML → 后端 Playwright 渲染 PDF）
- 10 套模板的 HTML/CSS 渲染器可参考 reactive-resume v5 的 `packages/pdf/src/templates/` 视觉风格移植并简化为 HTML+CSS（v2 不做 DOCX 渲染器；eGGG 使用 027 Playwright 管线渲染 PDF，非 React-PDF）
- 三栏 ResizableGroup 使用 react-resizable-panels（与 reactive-resume v5 一致）
- 富文本 Tiptap 已在项目 `package.json` 中（来自 027/008 评估），无新增依赖
- @dnd-kit/core + @dnd-kit/sortable 已在项目 `package.json` 中（来自 027 Phase B），无新增依赖
- 后端 DeepSeek V4 Pro LLM 已配置（来自 027/008 AI 优化能力），AI 分析复用同一 provider
- 需要新增 8 个前端依赖（详见 research.md §2）：`@tiptap/react`、`@tiptap/starter-kit`、`@tiptap/extension-link`、`@tiptap/extension-highlight`、`@tiptap/extension-text-align`、`react-resizable-panels`、`immer`、`zod`；`@dnd-kit/core` + `@dnd-kit/sortable` 已在 027 Phase B 引入
- 用户已登录态有会话，公开分享 URL 走相同鉴权（owner 看到编辑入口，非 owner 看到只读）
- 旧 v1 简历的 `resume_branches` 表数据保留 6 个月（之后提示用户迁移或归档）
- PostgreSQL LISTEN/NOTIFY 性能足够支撑 SSE 推送（已用 027 验证）

---

## Out of Scope

- 用户头像上传优化（v1 已有，本 v2 不动）
- AI 优化（生成简历内容）—— 027 已实现，本 v2 不动
- 多语言 i18n 翻译（仅保留 locale 字段，翻译资源由后续 feature 处理）
- LinkedIn 自动导入（v1 没有，reactive-resume v5 也没有，保留为 backlog）
- DOCX 导出（v2 不提供，详见 Clarifications）
- 实时协作（多人同时编辑，reactive-resume v5 也不支持）
- 模板作者市场（用户上传模板到公开市场，v2 不做）
- v1 → v2 数据迁移工具（v2 优先新简历，v1 保留只读；迁移工具留 v3）

---

## Technical Risks & Mitigations

| 风险 | 影响 | 缓解 |
|---|---|---|
| 8-10 套模板移植工作量大 | US2 延期 | 优先核心 5 套（onyx/azurill/chikorita/pikachu/scizor）覆盖主要档位，剩余 5 套作为后续迭代 |
| JSON Schema 路线破坏性变更 | 旧 block 简历数据不可写 | 仅新简历走 v2；旧 v1 保留只读 + 清晰提示 |
| Tiptap 富文本→HTML 渲染在 PDF 中可能与 editor 视觉不一致 | 渲染漂移 | 复用 027 的统一 HTML 生成器；Tiptap 输出 HTML 后用 markdown-it 解析生成最终渲染 HTML |
| 后端 Playwright 资源消耗大 | 性能瓶颈 | 异步队列 + worker pool；超时 fallback |
| dnd-kit 在三栏布局中性能 | 拖拽卡顿 | 使用 motion 的 Reorder.Group 作为备选；按 section 类型分批渲染 |
| 模板切换时 layout 自动调整规则复杂 | 用户困惑 | 明确规则文档化：no-sidebar 模板 → 所有 section 移入 main；UI 提示 |
| 公开分享 URL 路由与鉴权集成 | 越权风险 | owner session 才能编辑；非 owner session 强制只读；密码 cookie HttpOnly + 10 分钟 TTL |

---

## Notes

- 本 spec 由用户与 Claude 通过"调研 reactive-resume 源码 + Playwright 实操 builder + eGGG 现状调研"三轮迭代后写定
- reactive-resume v5 完整调研报告见 `D:\Project\reactive-resume`（共 4 份：数据模型、15 模板、编辑器 UX、导出导入）
- eGGG 现状调研：027 已实现渲染引擎/分页/主题/导出/AI 优化/双向定位/头像/Square 模板市场；v2 站在这些之上做"JSON Schema 化数据 + 多模板 + 12+12 settings 面板"
- 032 之前曾有 Reactive Resume 路线 spec（已回滚，2026-06-25），用户原话"我后续打算针对 reactive resume 进行一次全新的需求设计"——本 spec 是新需求设计
- 实施顺序：US1（数据模型）→ US2/3（模板+三栏）→ US5/6/7（design/typography/page）→ US4（layout 拖拽）→ US9（Tiptap）→ US10（dock+导出）→ US12（auto-save）→ US15（兼容）→ US8（style rules）→ US11（分享）→ US14（AI 分析）→ US16（Duplicate）→ US17（Undo/Redo）→ US13（模板市场）
