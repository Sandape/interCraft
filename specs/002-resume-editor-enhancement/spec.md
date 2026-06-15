# Feature Specification: Resume Editor Enhancement

**Feature Branch**: `002-resume-editor-enhancement`

**Created**: 2026-06-13

**Status**: Draft

**Input**: User description: "我期望针对简历中心的简历编辑做更多提升，有以下几个核心方向：1、简历所见即所得模式，参考木及简历的方式，我期望页面应该是分为两块，左侧是markdown编辑器，右侧是markdown渲染为简历的预览器，当前这种分栏的编辑模式，可以作为快捷模式和所见即所得模式分开，在页面上提供切换模式的入口；2、简历应该支持导出为markdown或PDF或图片，同时支持导入markdown简历；3、主简历不应该和下面的特性简历卡片混在一起，而应该在特性卡片的区域上面给一个大的横向卡片用于标识主简历。4、应该支持用户切换不同的简历样式。"

## Clarifications

### Session 2026-06-13

- Q: 样式选择持久化范围（per branch 还是 per user）？ → A: 分支级 — 每份简历分支独立记忆自己的样式选择，互不影响
- Q: 紧凑一页样式是否需要「智能一页」自动缩放？ → A: 不做自动缩放 — 固定字号和排版，用户自行精简内容控制在一页内
- Q: 是否支持证件照/头像？ → A: v1 不包含照片支持 — 样式模板中照片区域显示姓名首字母头像或留空作为占位
- Q: 图片导出分辨率？ → A: 2x 高清分辨率（A4 ≈ 1654×2339px，192 DPI），适配 Retina 屏幕
- Q: 所见即所得模式下的操作栏布局？ → A: 统一顶部工具栏 — 模式切换、导出、样式选择、版本保存/历史、锁定状态全部在页面顶部的统一工具栏中，左右分栏面板下方无额外操作

## User Scenarios & Testing *(mandatory)*

### User Story 1 - WYSIWYG Resume Editing (Priority: P1)

用户在编辑简历时，可以在两种模式之间切换：**快捷模式**（当前的分栏折叠卡片编辑模式）和**所见即所得模式**（左侧 Markdown 编辑器 + 右侧实时简历预览）。在所见即所得模式下，左侧编辑 Markdown 内容，右侧即时渲染为简历外观，用户所见即所得地调整简历内容和版式。

**Why this priority**: 这是本次提升的核心交互改进，直接改变用户编辑简历的方式，提升编辑效率和体验。所见即所得模式让用户无需在脑中想象最终效果，可以实时看到修改结果。

**Independent Test**: 打开任意简历分支进入编辑页，点击模式切换按钮切换到所见即所得模式，在左侧编辑器中输入或修改 Markdown 内容，右侧预览区域实时更新显示简历渲染结果，再切换回快捷模式确认原有编辑功能正常。

**Acceptance Scenarios**:

1. **Given** 用户在快捷模式下编辑简历，**When** 点击"所见即所得"模式切换按钮，**Then** 页面变为左右分栏布局：左侧为 Markdown 编辑器，右侧为简历预览器，已有的模块内容自动合并为 Markdown 并显示在左侧编辑器中
2. **Given** 用户在所见即所得模式下，**When** 在左侧编辑器中输入或修改 Markdown 文本，**Then** 右侧预览器在 1 秒内实时更新显示渲染后的简历效果
3. **Given** 用户在所见即所得模式下，**When** 点击切换回"快捷模式"，**Then** 页面恢复为当前的分栏折叠卡片布局，Markdown 内容被解析并拆分为对应的模块（block），模块内容保持完整
4. **Given** 用户在所见即所得模式下编辑了内容，**When** 未保存版本就切换模式，**Then** 系统保留已编辑的内容，不丢失数据
5. **Given** 用户在所见即所得模式下，**When** 对简历进行了修改，**Then** 系统按现有自动保存机制（1.5s 防抖）保存内容

---

### User Story 2 - Resume Export (Priority: P1)

用户可以将当前编辑的简历导出为 Markdown 文件、PDF 文件或图片（PNG/JPEG）。导出内容基于右侧预览器的渲染结果，保证导出效果与预览一致。

**Why this priority**: 导出是简历编辑的核心下游需求——用户编辑简历的最终目的是投递，而投递需要不同格式的文件。Markdown 便于版本管理和跨平台编辑，PDF 是投递标准格式，图片便于分享和预览。

**Independent Test**: 在简历编辑页（任意模式），点击导出按钮，选择 Markdown / PDF / 图片格式，确认浏览器下载了对应格式的文件，内容与编辑器中的简历内容一致。

**Acceptance Scenarios**:

1. **Given** 用户在简历编辑页，**When** 点击"导出"按钮并选择"Markdown"，**Then** 浏览器下载一个 `.md` 文件，内容为当前简历的完整 Markdown 源码
2. **Given** 用户在简历编辑页，**When** 点击"导出"按钮并选择"PDF"，**Then** 系统生成一份 A4 尺寸的 PDF 文件并触发下载，PDF 中的简历排版与预览器显示的样式一致
3. **Given** 用户在简历编辑页，**When** 点击"导出"按钮并选择"图片（PNG）"或"图片（JPEG）"，**Then** 系统生成一张高清图片并触发下载，图片中的简历外观与预览器一致
4. **Given** 用户在所见即所得模式下，**When** 导出 PDF 或图片，**Then** 导出的内容基于右侧预览器的当前渲染结果，所见即所得
5. **Given** 简历内容为空（无任何模块），**When** 用户尝试导出，**Then** 系统提示"简历内容为空，无法导出"

---

### User Story 3 - Markdown Resume Import (Priority: P2)

用户可以导入一份 Markdown 格式的简历文件，系统解析 Markdown 结构并自动创建对应的简历分支和模块。

**Why this priority**: 导入功能让用户能够将已有的 Markdown 简历快速迁移到平台，降低迁移成本。也支持用户从其他 Markdown 简历工具或导出备份中恢复简历。

**Independent Test**: 在简历列表页点击"导入"按钮，选择一个 Markdown 文件，确认系统创建了新分支并正确解析了 Markdown 结构为对应的模块。

**Acceptance Scenarios**:

1. **Given** 用户在简历列表页，**When** 点击"导入 Markdown"按钮并选择一个 `.md` 文件，**Then** 系统弹窗让用户输入新分支名称（预填文件名），确认后创建分支并跳转到编辑页
2. **Given** 用户导入的 Markdown 文件包含标题（`#`）、段落、列表等标准 Markdown 语法，**When** 导入完成，**Then** 系统将 `#` 标题映射为 heading 模块、段落映射为 summary/custom 模块、列表映射为 experience/skill 模块
3. **Given** Markdown 文件包含不支持的语法（如表格、内嵌 HTML），**When** 导入时，**Then** 系统保留原始 Markdown 内容到 custom 模块中，并给出提示说明部分格式可能无法精确映射
4. **Given** 用户选择的文件不是 `.md` 格式或内容无法解析，**When** 导入时，**Then** 系统提示"文件格式不支持，请选择 Markdown (.md) 文件"

---

### User Story 4 - Primary Resume Prominent Card (Priority: P2)

在简历列表页，主简历（数据源）以一个大尺寸横向卡片的形式展示在特性简历卡片网格的上方，与下方的派生简历卡片形成视觉层级区分。

**Why this priority**: 主简历是简历管理的核心数据源，将其与特性简历卡片分开突出显示，帮助用户建立清晰的"数据源 vs 定制版本"认知，降低误操作风险。

**Independent Test**: 在简历列表页，确认主简历以大尺寸横向卡片展示在顶部，下方是派生简历的网格卡片，两者视觉层级清晰可辨。

**Acceptance Scenarios**:

1. **Given** 用户在简历列表页，**When** 页面加载完成，**Then** 主简历以横向大卡片形式展示在页面顶部，占据整行宽度，包含简历名称、状态、公司/职位信息、最后编辑时间和主要操作按钮
2. **Given** 页面中有主简历和多份派生简历，**When** 用户浏览页面，**Then** 主简历卡片与下方的派生简历卡片网格之间有明显的视觉分隔，主简历卡片上有"主简历（数据源）"的明确标识
3. **Given** 用户还没有创建任何简历，**When** 页面加载，**Then** 不显示主简历卡片区域，显示原有的空状态提示
4. **Given** 用户 hover 主简历卡片，**When** 显示操作按钮，**Then** 与派生简历卡片一致的操作（编辑属性、置顶等）可用，但删除按钮对主简历不可用

---

### User Story 5 - Resume Style Switching (Priority: P2)

用户可以在多种预设的简历样式模板之间切换，改变简历的视觉外观（包括配色方案、字体和布局风格）。切换样式后，预览器和导出效果同步更新。

**Why this priority**: 不同投递场景可能需要不同的简历风格。样式切换让用户在不修改内容的前提下快速调整简历的视觉效果，提升个性化和适配能力。

**Independent Test**: 在简历编辑页（所见即所得模式或预览中），从样式选择器中选择一个不同样式，确认右侧预览立即以新样式渲染，且切换回原样式后渲染恢复。

**Acceptance Scenarios**:

1. **Given** 用户在简历编辑页，**When** 点击样式切换入口（如顶部工具栏的样式选择下拉菜单），**Then** 显示可用的样式模板列表，每个样式有缩略图预览或名称描述
2. **Given** 用户选择了一个新的样式模板，**When** 样式应用后，**Then** 右侧预览器立即以新样式渲染简历，内容包括配色、字体、布局均发生变化，但文本内容不变
3. **Given** 用户使用了某个样式，**When** 导出 PDF 或图片，**Then** 导出文件使用当前选中的样式进行渲染
4. **Given** 用户切换样式后未保存版本，**When** 刷新页面或下次打开，**Then** 系统记住最后选择的样式设置
5. **Given** 样式模板列表，**When** 用户查看，**Then** 提供 2 种预设样式——「紧凑一页」（单栏全宽 A4 单页布局）和「现代双栏」（左窄右宽双栏布局），两种均为极简风格，用户可预览当前简历在各样式下的外观

---

### Edge Cases

- 在所见即所得模式下，模块元数据（如 experience 的 company/role）如何编辑？——通过 Markdown 中的 frontmatter 或特殊语法块编辑，或在右侧预览中直接点击对应字段进行编辑
- Markdown 编辑器内容与现有 block 结构如何双向转换？——需要定义明确的映射规则：block type ↔ Markdown heading + content
- 导出 PDF 时如果简历内容超过一页如何处理？——自动分页，保持 A4 尺寸。紧凑一页样式不做自动缩放，用户可通过预览判断是否需要精简内容
- 导入 Markdown 时如果文件很大（如超过 100KB）如何处理？——设置文件大小上限，超出时提示用户
- 样式切换后，块级编辑（快捷模式下的元数据字段）的数据是否受影响？——不受影响，样式仅改变视觉渲染，不改变数据模型
- 如果用户在快捷模式下修改了 block 元数据（如 company、role），切换到所见即所得模式后这些元数据如何呈现？——以 Markdown frontmatter 形式体现在编辑器中
- 主简历被删除或不存在时，主简历卡片区域如何处理？——不显示主简历卡片区域，仅显示派生简历网格
- 多种样式下，Markdown 中的某些内容（如自定义 HTML）可能渲染不一致，如何处理？——样式模板明确声明支持的 Markdown 子集，不支持的语法降级为纯文本
- 服务端 PDF 渲染服务不可用时如何处理？——显示友好提示"PDF 导出服务暂不可用，请稍后重试"，同时 Markdown 导出仍可正常使用作为降级方案
- 证件照/头像功能？——v1 不包含，样式模板中照片区域以姓名首字母头像或灰色占位圆替代

## Requirements *(mandatory)*

### Functional Requirements

**WYSIWYG Mode**

- **FR-001**: System MUST provide a unified top toolbar on the resume editor page, containing: mode toggle (Quick Mode / WYSIWYG Mode), export button, style selector, version save/rollback controls, and lock status indicator. This toolbar is present in both editing modes.
- **FR-002**: In WYSIWYG mode, the page MUST display a two-column layout: left column contains a Markdown editor, right column contains a real-time resume preview rendered from the Markdown
- **FR-003**: When switching from Quick Mode to WYSIWYG mode, the system MUST aggregate all block contents into a single Markdown document (preserving block order and metadata) and display it in the left editor
- **FR-004**: When switching from WYSIWYG mode back to Quick Mode, the system MUST parse the Markdown document back into individual blocks (heading/summary/experience/skill/education/custom) and persist them
- **FR-005**: The right-side preview in WYSIWYG mode MUST update in real-time (within 1 second) as the user types in the left editor
- **FR-006**: The right-side preview MUST render the resume in a realistic A4 page appearance, using the currently selected resume style

**Export**

- **FR-007**: System MUST support exporting the current resume as a Markdown (.md) file
- **FR-008**: System MUST support exporting the current resume as a PDF (.pdf) file via server-side rendering (headless Chrome/Puppeteer on the backend), ensuring consistent, pixel-perfect output across all clients. The backend rendering service receives the Markdown content + selected style identifier, renders the resume, and returns the PDF binary for download.
- **FR-009**: System MUST support exporting the current resume as an image (PNG and JPEG formats) at 2x resolution (A4 ≈ 1654×2339px, 192 DPI), rendered with the currently selected resume style
- **FR-010**: Exported PDF and image files MUST match the visual appearance shown in the WYSIWYG preview
- **FR-011**: When the resume has no content, the export action MUST show an appropriate message and prevent the export

**Import**

- **FR-012**: System MUST provide a "Import Markdown" entry point on the resume list page
- **FR-013**: System MUST parse imported Markdown files and map the content structure to resume blocks based on heading levels and content patterns
- **FR-014**: System MUST create a new resume branch from the imported Markdown and navigate to the editor after creation
- **FR-015**: System MUST validate that the imported file is a valid Markdown file (.md extension)
- **FR-016**: System MUST handle unsupported Markdown syntax gracefully by preserving the raw content in a custom block

**Primary Resume Card**

- **FR-017**: On the resume list page, the main resume (is_main = true) MUST be displayed as a full-width horizontal card above the grid of feature branch cards. The card displays: resume name, status badge, company/position info, last edited time, block/module count, and a text preview excerpt of the first few lines of resume content.
- **FR-018**: The primary resume card MUST be visually distinct from the feature branch cards in the grid below, with clear "Primary Resume / Data Source" labeling
- **FR-019**: If no main resume exists (e.g., all deleted), the primary resume card area MUST be hidden and only the feature branch grid is shown
- **FR-020**: Feature branch cards (non-main resumes) MUST continue to be displayed in the existing grid layout below the primary card

**Style Switching**

- **FR-021**: System MUST provide 2 preset resume style templates, both minimalist in aesthetic. Each style controls the full visual presentation: color scheme, typography (font family, size, weight), and overall page layout (section ordering, column structure, spacing).
    - **Style 1 — "紧凑一页" (Compact One-Page)**: Single full-width column layout, designed to fit on one A4 page. Content sections stacked vertically with clear section headers. Minimal color (black/white + one subtle accent color). Clean typographic hierarchy: large name at top, contact info inline below, section titles in bold with a thin underline separator. Focus on content density without feeling cramped. Reference: 木及简历 single-page style.
    - **Style 2 — "现代双栏" (Modern Two-Column)**: Left narrow sidebar (~30%) + right wide main area (~70%). Left sidebar: subtle background tint, contains personal info, education, skills, languages — displayed compactly. Right main area: professional summary, work experience, project experience — each with clear heading, time range, and bullet-point details. Subtle color accent on section headers. Clean sans-serif typography. Better suited for experienced professionals with more content.
- **FR-022**: Users MUST be able to preview the current resume in each available style before selecting
- **FR-023**: Changing the resume style MUST NOT modify the underlying resume data (blocks, content, metadata)
- **FR-024**: The selected style MUST persist across sessions, stored per resume branch. Each branch independently remembers its own style choice; changing the style on one branch does not affect other branches.
- **FR-025**: Exported PDF and images MUST use the currently selected style for rendering

### Key Entities

- **ResumeStyle**: Represents a visual style template for resume rendering. Key attributes: name, display label, color scheme, font configuration, layout parameters. Not directly tied to content data.
- **ExportFormat**: Represents the supported export target formats (Markdown, PDF, PNG, JPEG). Each format has specific rendering requirements and file MIME types.
- **ImportSource**: Represents a Markdown file imported from external sources. Contains raw Markdown content that needs to be parsed and mapped to the internal block structure.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Users can switch between Quick Mode and WYSIWYG mode in under 2 seconds, with content correctly preserved in both directions
- **SC-002**: In WYSIWYG mode, preview updates appear within 1 second of the user stopping typing
- **SC-003**: Users can complete a full export (any format) in under 5 seconds from click to file download
- **SC-004**: Imported Markdown resumes with standard formatting map at least 90% of content to the correct block types without manual correction
- **SC-005**: Users can identify the main resume (data source) on the list page within 3 seconds of page load
- **SC-006**: Switching between resume styles updates the preview in under 1 second
- **SC-007**: Exported PDF matches the on-screen preview with at least 95% visual fidelity

## Assumptions

- Markdown editing and rendering will use a standard Markdown parser (e.g., unified/remark/rehype ecosystem); the spec does not prescribe a specific library
- The WYSIWYG preview targets desktop screen sizes (≥1024px width); mobile responsiveness is a secondary concern for the editor view
- PDF export uses server-side rendering (headless Chrome/Puppeteer) to ensure consistent output across all clients. Image export (PNG/JPEG) may share the same server-side rendering pipeline or use client-side canvas-based rendering as a lighter alternative.
- Style templates are defined as HTML/CSS page templates on the backend rendering service, each controlling the full layout, typography, and color scheme of the resume. The frontend preview uses the same CSS for faithful WYSIWYG rendering.
- The existing auto-save mechanism (1.5s debounce) and version control system remain unchanged
- The current block types (heading, summary, experience, project, skill, education, custom) remain the data model for resume content
- Markdown import parsing follows the mapping: `# heading` → heading block, `## heading` → section title, paragraphs → custom/summary blocks, list items → skill/experience blocks
- The primary resume card reuses existing branch data from the API without schema changes
