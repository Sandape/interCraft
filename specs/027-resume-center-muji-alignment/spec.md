# Feature Specification: Resume Center Muji Alignment

**Feature Branch**: `027-resume-center-muji-alignment`

**Created**: 2026-06-24

**Status**: Draft

**Input**: User description: "参照木及简历（D:\\Project\\react-resume-site）的实现，全面优化 InterCraft 当前项目的简历中心。用户授权可以全面向木及简历靠拢，即便改变现有技术选型或技术栈；但改动局限在简历中心。验收标准：通过 Playwright E2E 测试。"

## Clarifications

### Session 2026-06-24

- Q: 渲染引擎是否可以全面替换（废弃现有 react-markdown 方案）？ → A: 是 — 用户明确授权"全面向木及简历靠拢，即便是改变现有技术选型或技术栈"，但改动局限在简历中心（不动 auth/jobs/interviews/errors/ability_profile 等其他模块的全局基础设施）。
- Q: 是否保留 eGGG 已有的结构化优势（block 模型 + version 快照 + COW 分支 + AI 优化）？ → A: 保留 — 这些是木及简历（localStorage 单机应用）没有的，废弃等于重写。采用"block 模型 + 木及渲染引擎"组合：Code 模式下 blocks→markdown 聚合→markdown-it→分页→主题 CSS 渲染。
- Q: preview 与 PDF 渲染漂移问题如何解决？ → A: 统一渲染引擎 — 前端生成完整 HTML（含主题 CSS + 分页标记），后端 PDF 渲染器废弃自研 markdown 解析器，只负责渲染壳。这样 preview 和 PDF 用同一个 HTML 生成器，彻底消除漂移。
- Q: 是否搬运木及简历的硬编码 HMAC 密钥（htmlToPdf.ts:4-5）？ → A: 不搬运 — PDF 签名必须后端处理，密钥严禁入仓（宪法"安全与隐私"原则）。
- Q: 木及的 OnePage 组件（只是 CSS clip 不是真智能分页）是否搬运？ → A: 不搬运 — 用 rs-md-html-parser 的真正 DOM 分页算法替代。
- Q: 木及的 MobX / AntD 4 / CodeMirror / Webpack 是否搬运？ → A: 不搬运 — 保留 eGGG 的 Zustand / Tailwind / Monaco / Vite，避免越界影响其他模块。

## User Scenarios & Testing *(mandatory)*

### User Story 1 - 统一渲染引擎：预览与导出一致 (Priority: P1)

用户在简历编辑器中编辑简历时，右侧预览区显示的简历外观与最终导出的 PDF/图片完全一致——同样的排版、同样的分页、同样的主题样式。当前系统因预览与导出使用两套独立的 Markdown 渲染器（前端一套、后端一套），导致同一份 Markdown 在预览和导出中呈现不同效果（表格/图片/内联 HTML/链接等在后端导出时丢失或变形），违反"所见即所得"承诺。本故事统一渲染管线，让预览和导出共用同一 HTML 生成器。

**Why this priority**: 这是整个优化的技术基石——所有其他视觉优化（智能分页、主题系统、自定义语法）都依赖统一渲染引擎。不解决漂移问题，后续优化在预览中生效但导出时失效，用户体验仍是割裂的。P1 因为它是其他故事的前置条件，且直接影响"所见即所得"核心承诺。

**Independent Test**: 在编辑器中输入包含表格、图片、内联 HTML、链接、加粗、列表的复杂 Markdown，确认右侧预览渲染结果与导出的 PDF 在排版、分页、样式上完全一致；同一份 Markdown 多次导出结果稳定可复现。

**Acceptance Scenarios**:

1. **Given** 用户在所见即所得模式下编辑包含表格的 Markdown，**When** 查看右侧预览，**Then** 表格以正确的列宽和边框渲染显示
2. **Given** 用户预览中看到表格已正确渲染，**When** 点击导出 PDF，**Then** 导出的 PDF 中表格与预览完全一致（列数、边框、内容对齐）
3. **Given** 用户在 Markdown 中使用图片语法 `![alt](url)`，**When** 预览，**Then** 图片在预览中正确显示且不超出 A4 页面宽度
4. **Given** 用户预览中看到图片已正确显示，**When** 导出 PDF，**Then** PDF 中的图片与预览一致（尺寸、位置、清晰度）
5. **Given** 用户使用内联 HTML（如 `<span style="color: red">`）或链接语法 `[text](url)`，**When** 预览并导出，**Then** 预览和导出中 HTML 与链接渲染一致
6. **Given** 同一份 Markdown 内容，**When** 多次导出 PDF，**Then** 每次导出的 PDF 字节级一致或视觉级一致（无随机差异）
7. **Given** 用户切换主题样式，**When** 预览并导出，**Then** 导出的 PDF 应用当前主题样式（与预览一致）

---

### User Story 2 - 智能分页预览：A4 分页线与页数指示 (Priority: P1)

用户编辑简历时，右侧预览区按 A4 页面尺寸真实分页显示——内容超出 A4 一页时自动出现分页线，并在预览区顶部或角落显示"1/2 页"页数指示器。用户可以切换"单页模式"（只显示第一页，超出部分隐藏）和"多页模式"（显示所有页）。当前系统预览区只有一个 `min-height: 297mm` 的容器，内容超出时静默滚动，用户无法直观看到分页效果，也无法预知导出后的页数。

**Why this priority**: 简历的核心约束是"控制在 N 页内"（通常 1 页）。没有分页预览，用户只能在导出后才知道实际页数，反复试错成本高。智能分页让用户在编辑时实时看到分页效果，直接调整内容。P1 因为这是简历编辑区别于普通 Markdown 编辑器的核心差异化能力。

**Independent Test**: 在编辑器中输入超过 A4 一页的内容，确认预览区出现分页线、显示"2 页"指示器；删减内容至一页内，确认分页线消失、指示器变为"1 页"；切换单页模式，确认只显示第一页。

**Acceptance Scenarios**:

1. **Given** 用户编辑的内容少于 A4 一页，**When** 查看预览，**Then** 预览区显示"1 页"指示器且无分页线
2. **Given** 用户编辑的内容超过 A4 一页，**When** 查看预览，**Then** 预览区在 A4 页面边界处显示分页线，并显示"2 页"（或更多）指示器
3. **Given** 用户在多页模式下，**When** 点击"单页模式"切换按钮，**Then** 预览区只显示第一页内容，超出部分被裁剪隐藏
4. **Given** 用户在单页模式下，**When** 点击切换回"多页模式"，**Then** 预览区恢复显示所有页，分页线重新出现
5. **Given** 用户调整内容（增减段落），**When** 内容跨越一页边界，**Then** 分页线和页数指示器在 1 秒内实时更新
6. **Given** 用户在单页模式下导出 PDF，**Then** 导出的 PDF 只包含第一页内容（与单页模式预览一致）
7. **Given** 用户在多页模式下导出 PDF，**Then** 导出的 PDF 包含所有页且分页位置与预览一致

---

### User Story 3 - 主题系统与主题色定制 (Priority: P1)

用户可以从多套预设主题（至少 4 套：默认、蓝色、橙色、紫色等木及简历风格）中选择简历视觉主题，并通过颜色拾取器实时调整主题色（单一强调色，影响标题底色、分隔线、链接等所有主题色元素）。主题切换和颜色调整即时生效，无需刷新页面。当前系统虽有 4 套样式（classic/compact/modern/editorial），但样式间差异主要在布局，缺乏木及简历那种"主题色驱动整体视觉"的能力，也没有颜色拾取器。

**Why this priority**: 主题与颜色是简历个性化的核心——不同岗位、不同行业偏好不同视觉风格（创意岗用橙色、金融岗用蓝色）。木及简历的 `--bg` 单 CSS 变量驱动整个主题色的设计简洁且强大，是用户感知最强的视觉差异化。P1 因为它是用户最直接的"美观度"诉求。

**Independent Test**: 在编辑器中切换 4 套主题，确认每套主题视觉差异明显且切换即时生效；打开颜色拾取器选择新颜色，确认标题底色、分隔线、链接等所有主题色元素即时变为新颜色；导出 PDF 确认主题和颜色已应用。

**Acceptance Scenarios**:

1. **Given** 用户在编辑器中，**When** 打开主题选择器，**Then** 显示至少 4 套主题缩略图（默认、蓝色、橙色、紫色），每套主题有名称和预览
2. **Given** 用户在主题选择器中，**When** 点击某套主题，**Then** 预览区在 1 秒内切换为该主题的视觉样式（标题底色、分隔线、字体等）
3. **Given** 用户已选择一套主题，**When** 打开颜色拾取器并选择新颜色，**Then** 预览区中所有主题色元素（标题底色、h1 下划线、链接等）即时变为新颜色
4. **Given** 用户调整颜色，**When** 颜色拾取器交互中（拖动过程中），**Then** 预览实时跟随更新（无需松开鼠标才更新）
5. **Given** 用户切换主题，**When** 主题切换后，**Then** 当前选择的主题色保留（主题与颜色是两个独立维度）
6. **Given** 用户已选择主题和颜色，**When** 导出 PDF，**Then** PDF 应用当前主题和颜色样式
7. **Given** 用户离开编辑器后返回，**When** 重新打开同一简历分支，**Then** 之前选择的主题和颜色已持久化（主题存分支级，颜色可存本地或分支级）
8. **Given** 用户切换主题，**When** 切换后，**Then** 简历内容（Markdown 文本）不受影响——主题只改视觉不改内容

---

### User Story 4 - 木及自定义语法：容器、图标、颜色 token (Priority: P2)

用户在 Markdown 中可以使用木及简历扩展的自定义语法：（1）`::: left / ::: right / ::: header / ::: title` 容器块实现两栏布局（如头像+联系方式左右排列）；（2）`icon:<name>` 内联语法插入品牌图标（github、email、blog、weixin、juejin、zhihu、weibo、qq 等 14 个）；（3）`#{color}` token 在内联样式中引用当前主题色（如 `<span style="color: #{color}">` 自动跟随颜色拾取器）；（4）连续空行保留为可见垂直间距；（5）标题（#/##/###）被结构化包装为区块，允许主题 CSS 针对整个 section 应用样式。当前系统的 Markdown 解析不支持这些扩展语法。

**Why this priority**: 这些语法是木及简历"简历专用 Markdown 方言"的核心，让用户用纯 Markdown 表达复杂的简历版式（两栏头部、品牌图标行、跟随主题色的强调），而不需要 HTML。P2 因为这是高级用户的能力提升，基础用户可用标准 Markdown，但搬运这些语法让木及简历用户迁移无成本。

**Independent Test**: 在编辑器中输入包含 `::: left / ::: right` 两栏、`icon:github` 图标、`#{color}` token、连续空行的 Markdown，确认预览正确渲染两栏布局、图标 SVG、跟随主题色的文字、保留的垂直间距。

**Acceptance Scenarios**:

1. **Given** 用户在 Markdown 中输入 `::: left\n左侧内容\n:::\n::: right\n右侧内容\n:::`，**When** 预览，**Then** 左右两栏并排显示，左侧内容在左、右侧内容在右
2. **Given** 用户在 Markdown 中输入 `icon:github username`，**When** 预览，**Then** 显示 GitHub 图标 SVG 后跟 username 文本
3. **Given** 用户在 Markdown 中输入 `[icon:blog 博客](https://example.com)`，**When** 预览，**Then** 显示博客图标 + "博客" 文本 + 链接，点击跳转
4. **Given** 用户在 Markdown 中使用 `<span style="color: #{color}">强调</span>`，**When** 预览，**Then** "强调" 文字颜色为当前主题色
5. **Given** 用户已使用 `#{color}` token，**When** 通过颜色拾取器调整主题色，**Then** 使用 `#{color}` 的文字颜色即时跟随更新
6. **Given** 用户在 Markdown 中输入多个连续空行（如段落间留 3 行空行），**When** 预览，**Then** 空行保留为可见的垂直间距（不被合并为单一段落间距）
7. **Given** 用户在 Markdown 中输入 `# 标题` 后跟内容，**When** 预览，**Then** 标题与内容被结构化包装为一个区块，主题 CSS 可对整个区块应用样式（如背景色、内边距）
8. **Given** 用户使用上述自定义语法，**When** 导出 PDF，**Then** PDF 中自定义语法渲染与预览一致（两栏、图标、颜色 token、空行、区块结构）

---

### User Story 5 - AI 优化增强：真轮询、逐项接受、diff 视图 (Priority: P1)

用户使用 AI 优化简历时：（1）优化过程中系统真正轮询后端状态（而非当前的单次查询后挂起），在 5-30 秒的 AI 处理时间内显示进度；（2）AI 返回的多个优化建议（patch）可以逐项接受或拒绝，而非全有或全无；（3）每个 patch 显示前后对比 diff（增加 vs 删除），让用户判断是否采纳；（4）应用前有确认对话框，明确告知将创建新版本。当前系统的 AI 优化面板只调用一次状态查询就挂起（无轮询循环），patch 只能全量应用或全量放弃，且无 diff 视图。

**Why this priority**: AI 优化是简历中心的高价值功能（M16 已交付基础版），但当前实现有明显缺陷导致实际可用性低——AI 处理稍慢就永远转圈、不能逐项采纳导致用户要么全接受要么放弃、看不到 diff 无法判断。这些缺陷让一个本应高频使用的功能沦为摆设。P1 因为它修复已交付功能的关键可用性 bug，投入产出比高。

**Independent Test**: 触发 AI 优化，输入 JD，确认优化过程中显示进度（轮询而非挂起）；AI 返回多个 patch 后，确认可以逐项勾选接受/拒绝；每个 patch 显示前后 diff；点击应用前弹出确认对话框。

**Acceptance Scenarios**:

1. **Given** 用户在 AI 优化面板输入 JD 并点击"开始优化"，**When** AI 正在处理（5-30 秒），**Then** 面板显示"优化中…"进度状态并持续轮询后端（而非单次查询后挂起）
2. **Given** AI 处理完成返回多个 patch，**When** 面板显示 patch 列表，**Then** 每个 patch 单独显示，包含路径、操作类型、前后对比 diff（增加行绿色、删除行红色）
3. **Given** 用户查看 patch 列表，**When** 勾选部分 patch 接受、部分拒绝，**Then** 只有勾选接受的 patch 会被应用
4. **Given** 用户已勾选要接受的 patch，**When** 点击"应用选中修改"，**Then** 弹出确认对话框，明确告知将创建新版本并应用 N 项修改
5. **Given** 用户在确认对话框点击"确认应用"，**When** 应用完成，**Then** 简历内容更新为新版本，版本历史中新增一条 AI 触发的版本记录
6. **Given** AI 处理超过 60 秒仍未返回，**When** 轮询超时，**Then** 面板显示"优化超时，请重试"而非永远转圈
7. **Given** AI 处理失败返回错误，**When** 面板显示，**Then** 显示错误信息并提供"重试"按钮
8. **Given** 用户在 AI 优化过程中切换到其他页面，**When** 返回编辑器，**Then** AI 优化状态恢复显示（基于后端 thread 状态，而非丢失）

---

### User Story 6 - 编辑器交互增强：拖拽、搜索、工具栏、快捷键 (Priority: P2)

用户在简历中心和编辑器中获得多项交互增强：（1）Quick 模式下支持拖拽手柄排序 block（替代当前的↑/↓按钮）；（2）简历列表页支持按名称/公司/职位搜索、按状态筛选、按编辑时间/创建时间/匹配分数排序；（3）派生分支点击"同步父级"时弹出确认对话框，明确警告会覆盖当前分支的本地修改；（4）Code 模式 Markdown 编辑器顶部有格式工具栏（加粗、斜体、标题、列表、链接、图标插入）；（5）常用键盘快捷键（Ctrl+S 保存版本、Ctrl+B 加粗等）。

**Why this priority**: 这些是审计发现的 15 个 gap 中影响日常编辑效率的部分。拖拽排序比按钮更直观，搜索筛选让多分支用户快速定位，确认对话框防止误操作丢失修改，工具栏降低 Markdown 语法记忆负担。P2 因为每个单独看是"nice to have"，但合起来显著提升编辑体验。

**Independent Test**: 在 Quick 模式拖拽 block 重排顺序；在列表页搜索某公司名称筛选简历；在派生分支点击"同步父级"确认弹出警告对话框；在 Code 模式点击工具栏加粗按钮插入 `**`；按 Ctrl+S 触发保存版本。

**Acceptance Scenarios**:

1. **Given** 用户在 Quick 模式查看 block 列表，**When** 拖拽某 block 的手柄到新位置，**Then** block 顺序更新且后端持久化（fractional indexing）
2. **Given** 用户在简历列表页，**When** 在搜索框输入公司名称，**Then** 列表筛选出匹配的简历分支（实时筛选）
3. **Given** 用户在简历列表页，**When** 选择状态筛选（如"草稿"），**Then** 列表只显示该状态的分支
4. **Given** 用户在简历列表页，**When** 选择排序方式（编辑时间/创建时间/匹配分数），**Then** 列表按所选方式排序
5. **Given** 用户在派生分支编辑器，**When** 点击"同步父级"按钮，**Then** 弹出确认对话框，警告"此操作将覆盖当前分支的所有本地修改，是否继续？"
6. **Given** 用户在确认对话框点击"取消"，**When** 取消同步，**Then** 当前分支内容不变
7. **Given** 用户在 Code 模式 Markdown 编辑器，**When** 选中文本并点击工具栏"加粗"按钮，**Then** 选中文本被 `**` 包裹
8. **Given** 用户在 Code 模式编辑器，**When** 点击工具栏"图标"按钮，**Then** 弹出图标选择器，选择后插入 `icon:<name>` 语法
9. **Given** 用户在编辑器中按 Ctrl+S，**When** 触发保存版本，**Then** 弹出保存版本对话框（与点击工具栏"保存版本"一致）
10. **Given** 用户在编辑器中按 Ctrl+B，**When** 触发加粗，**Then** 当前选中文本被 `**` 包裹（与工具栏按钮一致）

---

### User Story 7 - 版本对比与本地历史 (Priority: P2)

用户可以：（1）在版本历史中选择任意两个版本进行 diff 对比，查看两个版本之间的内容差异（增加/删除/修改的 block）；（2）系统在 localStorage 中维护轻量编辑历史（最多 8 条 FIFO），作为后端版本快照之外的快速撤销兜底；（3）编辑器的模式（Quick/Code）、分屏比例、滚动位置等 UI 偏好持久化到 localStorage，刷新或返回时恢复。

**Why this priority**: 版本对比让用户判断是否回滚到某历史版本，避免盲目回滚后才发现丢失重要内容。本地历史是快速撤销的安全网（后端版本需要主动保存，本地历史自动记录）。UI 偏好持久化避免每次返回都要重设模式。P2 因为后端版本快照已存在，这些是增强而非基础能力。

**Independent Test**: 在版本历史中选择两个版本进行 diff，确认显示内容差异；编辑内容后等待本地历史记录（防抖后），确认 localStorage 中新增一条；切换到 Code 模式并调整分屏比例，刷新页面后确认模式和比例恢复。

**Acceptance Scenarios**:

1. **Given** 用户打开版本历史抽屉，**When** 选择两个版本并点击"对比"，**Then** 显示 diff 视图，标注增加（绿色）、删除（红色）、修改（黄色）的 block
2. **Given** 用户查看 diff 视图，**When** 查看某个修改的 block，**Then** 显示修改前后的内容对比（行级或字段级 diff）
3. **Given** 用户在编辑器中编辑内容，**When** 编辑停顿 2 秒后，**Then** localStorage 中自动记录一条历史（包含 Markdown、主题、颜色、时间戳）
4. **Given** localStorage 历史已满 8 条，**When** 新增一条，**Then** 最旧的一条被移除（FIFO）
5. **Given** 用户打开本地历史列表，**When** 选择某条历史恢复，**Then** 编辑器内容、主题、颜色恢复为该历史状态
6. **Given** 用户切换到 Code 模式并调整分屏比例为 70/30，**When** 刷新页面或返回后重新进入，**Then** 模式恢复为 Code、分屏比例恢复为 70/30
7. **Given** 用户在预览区滚动到某位置，**When** 切换 block 后返回，**Then** 滚动位置恢复（会话内）

---

### Edge Cases

- Markdown 内容为空时，预览区显示空状态提示，导出按钮禁用并提示"简历内容为空"
- Markdown 包含恶意 HTML（如 `<script>`）时，系统过滤危险标签（保留样式相关标签）防止 XSS
- 主题 CSS 文件加载失败时，回退到默认主题并提示用户
- AI 优化返回 0 个 patch 时，面板显示"未发现可优化项"
- AI 优化返回的 patch 路径无效（指向不存在的 block）时，该 patch 标记为"无法应用"并跳过
- 拖拽排序时网络断开，本地顺序更新但后端持久化失败，显示"同步失败，已重试"并重试
- 版本 diff 中两个版本结构差异巨大（如一个有 10 block 一个有 2 block）时，diff 视图仍可读（不全屏堆砌）
- localStorage 配额满时，本地历史写入失败静默处理（不影响编辑主流程）
- 颜色拾取器输入无效颜色（如 `#ZZZ`）时，保留上一个有效颜色
- 分页计算在内容频繁变化时防抖（避免每次按键都重算分页导致卡顿）
- 用户在派生分支编辑后未保存版本就点击"同步父级"，确认对话框明确提示"未保存的修改将丢失"

## Requirements *(mandatory)*

### Functional Requirements

**统一渲染引擎（US1）**

- **FR-001**: 系统 MUST 使用单一 Markdown 渲染引擎同时驱动预览区和导出功能，确保同一份 Markdown 在预览和导出中渲染结果一致
- **FR-002**: 渲染引擎 MUST 支持标准 Markdown 语法（标题、段落、列表、加粗、斜体、链接、图片、代码块、引用、分隔线）
- **FR-003**: 渲染引擎 MUST 支持 GFM 扩展语法（表格、任务列表、删除线、自动链接）
- **FR-004**: 渲染引擎 MUST 支持内联 HTML（`style`、`span`、`div`、`img` 等样式相关标签），同时过滤危险标签（`script`、`iframe`、`on*` 事件属性）
- **FR-005**: 后端导出功能 MUST 接收前端生成的完整 HTML（含主题 CSS 与分页标记），仅负责渲染为 PDF/图片，不再独立解析 Markdown
- **FR-006**: 同一份 Markdown 多次导出 MUST 产生视觉一致的输出（无随机差异）
- **FR-007**: 系统 MUST 在导出前校验 Markdown 内容非空，空内容时拒绝导出并提示用户

**智能分页（US2）**

- **FR-008**: 预览区 MUST 按 A4 尺寸（210mm × 297mm）真实分页渲染，内容超出时在页面边界显示分页线
- **FR-009**: 预览区 MUST 显示当前页数指示器（如"1/2 页"），内容变化时 1 秒内更新
- **FR-010**: 系统 MUST 提供"单页模式"与"多页模式"切换，单页模式只显示第一页（超出部分裁剪），多页模式显示所有页
- **FR-011**: 分页计算 MUST 在内容变化时防抖（避免每次按键重算），防抖时间不超过 500ms
- **FR-012**: 单页模式导出的 PDF MUST 只包含第一页内容；多页模式导出的 PDF 包含所有页且分页位置与预览一致
- **FR-013**: 分页 MUST 处理表格、图片、列表等块级元素不被分页线切断（或若切断则按视觉可接受方式处理）

**主题系统（US3）**

- **FR-014**: 系统 MUST 提供至少 4 套预设主题（默认、蓝色、橙色、紫色或其他木及简历风格），每套主题有独立的视觉样式（标题底色、分隔线、字体、间距等）
- **FR-015**: 主题切换 MUST 在 1 秒内即时生效，无需刷新页面
- **FR-016**: 系统 MUST 提供颜色拾取器，允许用户选择任意 HEX 颜色作为主题强调色
- **FR-017**: 主题强调色 MUST 通过单一 CSS 变量驱动所有主题色元素（标题底色、分隔线、链接、强调文字等），颜色调整即时生效
- **FR-018**: 主题选择 MUST 持久化到分支级（每份简历分支独立记忆主题选择）
- **FR-019**: 主题强调色可持久化到本地或分支级（实现时决定，但同一分支返回时颜色恢复）
- **FR-020**: 主题切换 MUST NOT 修改简历内容（Markdown 文本），只改变视觉呈现
- **FR-021**: 主题 CSS MUST 作为独立资源加载，新增主题无需重新构建应用

**木及自定义语法（US4）**

- **FR-022**: 渲染引擎 MUST 支持 `::: left / ::: right / ::: header / ::: title` 容器语法，渲染为两栏或带语义的区块结构
- **FR-023**: 渲染引擎 MUST 支持 `icon:<name>` 内联语法，提供至少 14 个品牌图标（github、email、blog、weixin、juejin、zhihu、weibo、qq、twitter、facebook、csdn、yuque、sifou、phone）
- **FR-024**: 渲染引擎 MUST 支持 `#{color}` token，在内联样式中引用当前主题强调色，颜色调整时即时更新
- **FR-025**: 渲染引擎 MUST 保留 Markdown 中的连续空行为可见垂直间距（不被合并为单一段落间距）
- **FR-026**: 渲染引擎 MUST 将标题（#/##/###/####/#####）结构化包装为区块，允许主题 CSS 针对整个 section 应用样式
- **FR-027**: 系统 MUST 提供图标语法快捷参考（如点击复制的 cheatsheet），降低用户记忆负担
- **FR-028**: 自定义语法渲染结果 MUST 在预览和导出中一致（依赖统一渲染引擎）

**AI 优化增强（US5）**

- **FR-029**: AI 优化面板 MUST 在触发优化后持续轮询后端状态，轮询间隔指数退避（如 1s、2s、4s、8s），最长轮询 60 秒后超时
- **FR-030**: AI 优化超时后 MUST 显示"优化超时，请重试"并提供重试按钮，而非永远转圈
- **FR-031**: AI 返回多个 patch 时，面板 MUST 逐项显示，每个 patch 含路径、操作类型、前后对比 diff
- **FR-032**: diff 视图 MUST 标注增加（绿色）、删除（红色）、修改（黄色）行，让用户直观判断
- **FR-033**: 用户 MUST 能逐项勾选接受或拒绝每个 patch，只有勾选接受的 patch 被应用
- **FR-034**: 应用 patch 前 MUST 弹出确认对话框，明确告知将创建新版本并应用 N 项修改
- **FR-035**: AI 优化失败时 MUST 显示错误信息并提供重试按钮
- **FR-036**: AI 优化状态 MUST 基于后端 thread 持久化，用户切换页面后返回能恢复状态
- **FR-037**: AI 返回 0 个 patch 时 MUST 显示"未发现可优化项"提示

**编辑器交互增强（US6）**

- **FR-038**: Quick 模式 block 列表 MUST 支持拖拽手柄排序，拖拽完成即时持久化（fractional indexing）
- **FR-039**: 简历列表页 MUST 提供搜索框，按名称/公司/职位实时筛选（输入即筛选）
- **FR-040**: 简历列表页 MUST 提供状态筛选（草稿/优化中/就绪/已投递/归档），可多选
- **FR-041**: 简历列表页 MUST 提供排序选项（编辑时间/创建时间/匹配分数），默认按编辑时间倒序
- **FR-042**: 派生分支"同步父级"操作 MUST 弹出确认对话框，明确警告"将覆盖当前分支的所有本地修改"
- **FR-043**: 确认对话框 MUST 提供"取消"与"确认同步"两个选项，取消时不执行同步
- **FR-044**: Code 模式 Markdown 编辑器顶部 MUST 提供格式工具栏，至少包含加粗、斜体、标题（H1/H2/H3）、无序列表、链接、图标插入按钮
- **FR-045**: 工具栏按钮 MUST 对选中文本执行包裹操作（如加粗包裹 `**`），无选中文本时插入占位符
- **FR-046**: 图标按钮点击 MUST 弹出图标选择器，选择后插入 `icon:<name>` 语法到光标位置
- **FR-047**: 编辑器 MUST 支持 Ctrl+S 快捷键触发保存版本对话框，并阻止浏览器默认保存行为
- **FR-048**: 编辑器 MUST 支持 Ctrl+B 快捷键触发加粗（与工具栏按钮一致）

**版本对比与本地历史（US7）**

- **FR-049**: 版本历史抽屉 MUST 支持选择两个版本进行 diff 对比
- **FR-050**: diff 视图 MUST 标注增加（绿色）、删除（红色）、修改（黄色）的 block，并提供行级或字段级内容对比
- **FR-051**: 系统 MUST 在 localStorage 中维护编辑历史，每次编辑停顿 2 秒后自动记录一条（含 Markdown、主题、颜色、时间戳）
- **FR-052**: localStorage 历史 MUST 采用 FIFO 策略，最多保留 8 条，超出时移除最旧的
- **FR-053**: 本地历史列表 MUST 支持选择某条恢复，恢复时编辑器内容、主题、颜色一并恢复
- **FR-054**: 编辑器模式（Quick/Code）MUST 持久化到 localStorage，返回时恢复
- **FR-055**: 分屏比例 MUST 持久化到 localStorage，返回时恢复
- **FR-056**: 预览区滚动位置 MUST 在会话内持久化（切换 block 后返回恢复）

**回归与不破坏（跨故事）**

- **FR-057**: 现有 002/017/019/M16 的 E2E 测试 MUST 全部通过（不回归）
- **FR-058**: 现有 round-1 + round-2 E2E 测试套件 MUST 全部通过（不回归）
- **FR-059**: 简历分支 CRUD、block 增删改、版本保存/回滚、AI 优化基础流程 MUST 保持可用
- **FR-060**: Markdown 导入流程（.md 文件解析为 block）MUST 保持可用且与新的渲染引擎兼容
- **FR-061**: 导出 Markdown / PDF / PNG / JPEG 四种格式 MUST 保持可用
- **FR-062**: 简历分支的 COW（copy-on-write）派生机制 MUST 保持可用
- **FR-063**: 简历中心的改动 MUST NOT 影响其他模块（auth/jobs/interviews/errors/ability_profile 等）

### Key Entities *(include if feature involves data)*

- **ResumeBranch**: 简历分支（主简历或派生版本），新增字段 `theme_id`（主题标识，如 default/blue/orange/pupple）、`accent_color`（主题强调色 HEX）。保留现有字段（name、company、position、status、match_score、is_main、is_pinned、style_preference、parent_id 等）。
- **ResumeBlock**: 简历模块（heading/summary/experience/project/skill/education/custom），结构与现有保持一致。`meta` JSONB 字段扩展支持 project（tech_stack/timeframe）、education（school/degree/year）、skill（proficiency）等结构化元数据。
- **ResumeVersion**: 简历版本快照，新增 `diff_patch` 支持（已有字段但未实现），实现 diff 快照以支持版本对比。
- **ResumeTheme**: 主题资源（CSS 文件 + 元数据），作为独立资源加载，不内嵌到应用 bundle。
- **AIOptimizePatch**: AI 优化建议项，含 `path`（目标 block）、`op`（操作类型）、`value`（新值）、`accepted`（用户是否接受，默认 false）。
- **LocalHistoryEntry**: 本地历史条目（localStorage），含 `markdown`、`theme_id`、`accent_color`、`timestamp`，FIFO 最多 8 条。

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: preview 与导出 PDF 的视觉一致性 ≥ 95%（同 HTML 生成器，抽样 10 份不同复杂度简历对比）
- **SC-002**: 智能分页在内容变化后 1 秒内更新页数指示器与分页线
- **SC-003**: 主题切换在 1 秒内即时生效，颜色调整实时跟随（拖动过程中即更新）
- **SC-004**: AI 优化轮询在 60 秒内返回结果或超时，不出现"永远转圈"状态
- **SC-005**: AI 优化 patch 逐项接受/拒绝功能可用，用户可只应用部分 patch
- **SC-006**: 简历列表搜索筛选响应时间 < 200ms（输入即筛选）
- **SC-007**: 拖拽排序完成到后端持久化延迟 < 500ms
- **SC-008**: 版本 diff 视图能正确标注增加/删除/修改的 block
- **SC-009**: 现有 E2E 测试套件（round-1 + round-2 + 002/017/019/M16 feature specs）100% 通过，无回归
- **SC-010**: 新增 E2E 测试套件覆盖 027 所有用户故事，100% 通过
- **SC-011**: 简历中心改动不影响其他模块的 E2E 测试（auth/jobs/interviews/errors/ability_profile 全部通过）
- **SC-012**: 木及自定义语法（容器、图标、颜色 token、空行、heading-block）在预览和导出中一致渲染
- **SC-013**: 单页模式导出的 PDF 只包含第一页内容；多页模式导出的 PDF 分页与预览一致
- **SC-014**: 编辑器 UI 偏好（模式、分屏比例）持久化，刷新后恢复
- **SC-015**: localStorage 历史正确维护 8 条 FIFO，恢复功能可用

## Assumptions

- 用户已有稳定网络连接，主题 CSS 资源可正常加载
- 简历中心改动局限在 `/resume` 列表 + `/resume/:branchId` 编辑器 + `src/components/resume/` + `src/styles/resume-*.css` + `src/lib/markdown-*` + `src/lib/resume-styles/` + `backend/app/modules/resumes/` + `backend/app/modules/versions/` + `backend/src/services/pdf_renderer/`，不动其他模块
- 保留全局基础设施：Zustand（状态）/ TanStack Query（缓存）/ Tailwind（样式）/ Vite（构建）/ React Router（路由）/ 后端 FastAPI + SQLAlchemy + ARQ（服务）
- 保留 eGGG 结构化优势：block 模型 + version 快照 + COW 分支 + AI 优化（这些是木及简历没有的，因木及是 localStorage 单机应用）
- 在简历中心内部引入木及渲染引擎（markdown-it + 自定义插件 + 智能分页库），废弃前端 react-markdown 方案与后端自研 markdown 解析器
- 不搬运木及简历的硬编码 HMAC 密钥（PDF 签名必须后端处理，密钥严禁入仓，符合宪法"安全与隐私"原则）
- 不搬运木及的 OnePage 组件（只是 CSS clip 不是真智能分页），改用真正的 DOM 分页算法
- 不搬运木及的 MobX / AntD 4 / CodeMirror / Webpack（保留 eGGG 的 Zustand / Tailwind / Monaco / Vite，避免越界影响其他模块）
- 浏览器支持 CSS 变量（`var(--bg)`）、`transform: scale()`、localStorage 等现代特性（Chrome/Edge/Firefox 最新版）
- 后端 PDF 渲染使用 Playwright/Puppeteer（headless Chromium），已存在于项目中
- 现有简历数据（已创建的 branch/block/version）在迁移后保持可用，`theme_id` 与 `accent_color` 字段对旧数据有默认值（default 主题、默认强调色）
- E2E 测试使用项目现有 Playwright 框架，测试账号与夹具沿用现有 `tests/e2e/resume-center/fixture.ts`
