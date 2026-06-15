# InterCraft UI/UX 评估报告

> 评估时间: 2026-06-14 | 评估方式: 全页面 Playwright 遍历 + 组件代码审查

## 一、总体评估

项目定位：中国技术求职者 AI 辅助准备平台，包含简历分支管理、模拟面试、能力画像、求职追踪、错题本等模块。

**技术栈**：React + TypeScript + Tailwind CSS + @tanstack/react-query，自研 Notion 风格组件库（非 shadcn/ui）。

**设计语言评分：8/10** — 自研了一套完整的设计令牌系统，深色/浅色双模式覆盖，Notion 灵感的美学执行到位。

**交互状态覆盖：5/10** — 基础 CRUD 操作流程完整，但缺少大量关键 UX 状态（骨架屏、错误边界、空状态引导）。

---

## 二、组件库审计（src/components/ui/）

| 组件 | 质量 | 缺失能力 |
|------|------|----------|
| **Button** | 良好。4 变体（primary/secondary/ghost/danger），3 尺寸，loading 态内联 spinner | 无 `asChild`/组合模式（无法套 `<Link>`）；loading 时覆盖 leftIcon 可读性差 |
| **Card** | 良好。hover 变体，4 级内边距，CardHeader 子组件 | 缺少 `CardFooter`；无 `variant`（如 danger border 卡） |
| **Badge** | 良好。6 变体，leftIcon | 无 |
| **Input** | 基础可用。leftIcon/rightIcon 支持 | 无 `error`/`hint` 属性；密码可见性需手动实现；无 `Textarea` 的正规封装 |
| **Modal** | 良好。ESC 关闭，backdrop blur，role=dialog，aria-modal | 缺少 `footer` 的对齐控制（始终 flex-end）；无 `closeOnOverlay` 选项；无 body 滚动锁定 |
| **Tabs** | 良好。role=tablist，count badge | 无下划线指示器（Notion 风格应是底部滑动条） |
| **Progress** | 良好。aria-progressbar，5 色变体 | 无 indeterminate 模式 |
| **Avatar** | 良好。颜色来自姓名哈希（一致性），fallback 为首字母 | 无 online/offline 指示器 |
| **Tooltip** | 基础。纯 CSS hover | 无延迟显示；无自动定位（屏幕边缘溢出）；不可用于移动端 |
| **ThemeToggle** | 良好 | 无 |
| **缺失组件** | `Skeleton`、`Toast/Notification`、`Dropdown/Popover`、`EmptyState`、`ConfirmDialog`、`Pagination`、`ScrollArea` | — |

---

## 三、全局缺失（影响所有页面）

### 3.1 无 Error Boundary（严重）
没有任何 `React.ErrorBoundary` 或 `Suspense`。运行时异常会导致整个应用白屏。应至少在 `AppShell` 层级添加 `ErrorBoundary`。

### 3.2 无骨架屏加载（严重）
尽管 `tailwind.config.js` 和 `index.css` 中定义了 `shimmer` 动画，但项目中**没有任何 Skeleton 组件**。所有加载状态都是纯文本或 spinner，导致布局跳动（CLS）。

### 3.3 空状态不统一（中等）
各页面自行实现空状态，设计语言不一致。建议统一为 `EmptyState` 组件。

### 3.4 无 Toast 通知系统（中等）
所有 mutation 操作成功后无任何用户可见的反馈。

### 3.5 无全局 ConfirmDialog（低）
删除操作全部使用 `Modal` + 手动组装危险按钮。

---

## 四、逐页评估

### 4.1 Dashboard — 评分：7/10
**亮点**：数据可视化丰富（SVG sparkline、StatCard、能力进度条），信息密度高但不杂乱
**缺失**：硬编码 "早上好，浩然"；无骨架屏；Sparkline 不可访问；简历分支硬截断 `.slice(0, 5)`
**理想功能**：动态用户问候、StatCard 骨架屏、首次用户 Onboarding 引导

### 4.2 Login / Register — 评分：8/10
**亮点**：双栏布局、Login/Register 无缝切换、密码显隐切换、错误分类中文提示
**缺失**：无 "忘记密码" 链接、无第三方登录、无密码强度指示器
**理想功能**：忘记密码流程、密码强度指示条、微信扫码登录

### 4.3 ResumeList — 评分：7/10
**亮点**：PrimaryResumeCard 视觉区分、Hover 操作按钮、匹配度分数颜色编码
**缺失**：加载态仅 "加载中…"、无搜索/筛选/排序、无拖拽排序
**理想功能**：卡片网格骨架屏、按状态筛选、批量操作、导出 ZIP

### 4.4 ResumeEditor — 评分：8.5/10（最高分）
**亮点**：创新双模式（Quick/Code）、可拖拽分割面板、实时预览、版本控制、锁定机制、样式选择器
**缺失**：加载态简陋、无撤销/重做、Code 模式无语法高亮、移动端 split-pane 不可用
**理想功能**：Markdown 语法高亮、移动端 tab 视图、快捷键面板、图像拖拽上传

### 4.5 Profile — 评分：8/10
**亮点**：手写 SVG 雷达图（双层对比）、历史折线图、维度详情面板、里程碑时间线
**缺失**：雷达图数据 < 3 维度时多边形退化、空数据 SVG 错误、无动画
**理想功能**：雷达图入场动画、对比功能、导出能力报告、空数据引导流

### 4.6 InterviewList — 评分：7.5/10
**亮点**：Hero 卡片视觉突出、模式选项卡片、历史记录设计清晰、错题本联动
**缺失**：无分页、面试卡片无 onClick、语音面试仅展示 UI
**理想功能**：分页/无限滚动、继续未完成面试、搜索自动补全

### 4.7 InterviewLive — 评分：8.5/10
**亮点**：三阶段界面、WebSocket 实时通信、流式文本渲染、气泡对话、实时反馈侧边栏、Loading 态完整
**缺失**：无离开确认、语音/暂停按钮无功能、移动端面板遮挡
**理想功能**：退出确认对话框、语音输入集成、暂停/恢复、准备倒计时

### 4.8 InterviewReport — 评分：7.5/10
**亮点**：圆形进度 SVG、总览卡、最强/最弱维度高亮、逐题复盘列表
**缺失**：导出 PDF 无功能、圆环无动画、AI 总结未渲染 Markdown
**理想功能**：评分圆环动画、Markdown 渲染、PDF 导出、对比历史报告

### 4.9 Jobs — 评分：7/10
**亮点**：数据表设计清晰、Kanban 式统计卡、Tabs 筛选、行 hover 操作按钮
**缺失**：备注列不可编辑、无看板视图、无时间线集成、无批量操作
**理想功能**：拖拽看板视图、时间线集成、行内编辑、简历关联展示

### 4.10 ErrorBook — 评分：7/10
**亮点**：列表+详情面板布局、状态+维度双重筛选、搜索功能、专用 Badge 组件
**缺失**：无间隔重复/复习提醒、无批量操作、维度名未汉化
**理想功能**：间隔重复学习系统、复习提醒、维度中文映射、批量操作

### 4.11 Settings — 评分：7.5/10
**亮点**：macOS 风格设置布局、Pro 会员卡视觉突出、自定义 Toggle 开关、危险操作红色边框
**缺失**：表单无 loading 反馈、无未保存警告、账单硬编码
**理想功能**：头像上传、第三方账号绑定、两步验证、数据导出进度

### 4.12 Resources — 评分：4/10
**缺失**：全部数据硬编码、无搜索、无进度跟踪、无与能力画像联动、列表项无点击行为

### 4.13 Help — 评分：4/10
**缺失**：搜索框无功能、FAQ 无展开/折叠、全部硬编码、无工单提交

---

## 五、无障碍审计

**已做好的**：Modal role/dialog、Tabs role/tablist、Progress aria、Avatar aria-label、focus-visible ring、Toggle role/switch

**需要改进的**：无 Skip-to-content 链接、侧边栏搜索无 label、SVG 图表无 title/desc、部分颜色对比度不足、部分元素缺少键盘支持

---

## 六、响应式设计审计

**已做好的**：全局 Tailwind 响应式类、Topbar 搜索移动端隐藏、统计卡网格适配

**需要改进的**：ResumeEditor split-pane 移动端不可用、InterviewLive 右侧面板遮挡、ErrorBook 双栏移动端适配

---

## 七、改进优先级

### 高优先级（UX 基础缺失）
1. 添加 Skeleton 组件（利用已有的 shimmer CSS）
2. 添加 ErrorBoundary（包裹 AppShell + 每个页面）
3. 统一 EmptyState 组件
4. 添加 Toast 通知

### 中优先级（功能完整性）
5. InterviewLive：退出确认、暂停、语音集成
6. Help/Resources：从硬编码迁移到动态数据
7. Jobs：拖拽看板视图、时间线集成
8. 移动端适配：ResumeEditor、InterviewLive
9. Dropdown 组件

### 低优先级（体验打磨）
10. Tabs 底部滑动指示器
11. 深色模式 Resume 预览准确性
12. 页面过渡动画
13. Command+K 全局搜索面板
14. Onboarding 引导流程

---

*报告生成时间: 2026-06-14*
