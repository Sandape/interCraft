/**
 * 全局模拟数据 - InterCraft 面试工坊
 * 在真实环境中应替换为后端 API
 */

// ============== 用户信息 ==============
export const currentUser = {
  id: 'u-001',
  name: '林浩然',
  email: 'haoran.lin@intercraft.io',
  avatar: '',
  title: '高级前端工程师 · 求职中',
  yearsOfExperience: 3,
  targetRole: '高级前端工程师',
  subscription: 'Pro',
}

// ============== 简历中心 ==============
export interface ResumeBranch {
  id: string
  name: string
  company: string
  position: string
  status: 'draft' | 'optimizing' | 'ready' | 'submitted'
  matchScore: number
  lastEdited: string
  versionCount: number
  isMain?: boolean
  isPinned?: boolean
  parentId?: string
}

export const resumeBranches: ResumeBranch[] = [
  {
    id: 'core',
    name: '核心简历',
    company: '—',
    position: '基础版本',
    status: 'ready',
    matchScore: 100,
    lastEdited: '2026-06-08T10:00:00Z',
    versionCount: 12,
    isMain: true,
    isPinned: true,
  },
  {
    id: 'b-001',
    name: '字节跳动 · 高级前端',
    company: '字节跳动',
    position: '高级前端工程师',
    status: 'optimizing',
    matchScore: 87,
    lastEdited: '2026-06-11T15:23:00Z',
    versionCount: 5,
    parentId: 'core',
    isPinned: true,
  },
  {
    id: 'b-002',
    name: '美团 · 高级前端',
    company: '美团',
    position: '高级前端工程师',
    status: 'ready',
    matchScore: 92,
    lastEdited: '2026-06-10T09:14:00Z',
    versionCount: 3,
    parentId: 'core',
  },
  {
    id: 'b-003',
    name: '腾讯 · Web 前端',
    company: '腾讯',
    position: 'Web 前端开发',
    status: 'ready',
    matchScore: 85,
    lastEdited: '2026-06-07T14:42:00Z',
    versionCount: 4,
    parentId: 'core',
  },
  {
    id: 'b-004',
    name: '小红书 · 资深前端',
    company: '小红书',
    position: '资深前端工程师',
    status: 'draft',
    matchScore: 78,
    lastEdited: '2026-06-05T20:11:00Z',
    versionCount: 2,
    parentId: 'core',
  },
  {
    id: 'b-005',
    name: '蚂蚁集团 · 前端架构',
    company: '蚂蚁集团',
    position: '前端架构师',
    status: 'submitted',
    matchScore: 89,
    lastEdited: '2026-06-02T11:30:00Z',
    versionCount: 7,
    parentId: 'core',
  },
]

// 简历块（Notion 式）
export interface ResumeBlock {
  id: string
  type: 'heading' | 'summary' | 'experience' | 'project' | 'skill' | 'education'
  title: string
  content: string
  meta?: string
  collapsed?: boolean
}

export const coreResumeBlocks: ResumeBlock[] = [
  {
    id: 'b-h-1',
    type: 'heading',
    title: '林浩然',
    content: '高级前端工程师 · 3 年经验 · 北京',
    meta: 'haoran.lin@example.com · 138****0001',
  },
  {
    id: 'b-s-1',
    type: 'summary',
    title: '个人简介',
    content:
      '3 年大厂前端开发经验，专注于大型 SPA 性能优化与组件库架构设计。主导过从 0 到 1 的中后台系统搭建，熟悉 React 18 / TypeScript 工程化体系，对前端工程化、可观测性、微前端有深入理解。',
  },
  {
    id: 'b-e-1',
    type: 'experience',
    title: '工作经历',
    meta: '2023.03 - 至今 · 某互联网大厂 · 高级前端工程师',
    content:
      '• 主导中后台统一门户重构，将 12 个分散系统整合为单页面架构，首屏加载从 4.2s 降至 1.1s\n• 设计并落地 30+ 通用业务组件，被 4 个 BU 复用，节省 35% 开发工时\n• 推进团队 TypeScript 覆盖率从 42% 提升至 96%，建立 ESLint + Prettier 统一规范',
  },
  {
    id: 'b-e-2',
    type: 'experience',
    title: '',
    meta: '2021.07 - 2023.02 · 某 SaaS 创业公司 · 前端工程师',
    content:
      '• 独立负责 BI 看板产品前端实现，支持 200+ 客户使用\n• 封装可视化图表库 18 种，渲染性能优化 60%\n• 推动 Cypress 自动化测试覆盖核心链路，回归测试时间从 2 天缩短至 30 分钟',
  },
  {
    id: 'b-p-1',
    type: 'project',
    title: '代表项目',
    meta: 'EdgeKit · 内部微前端框架',
    content:
      '自研基于 Web Components + Module Federation 的微前端框架。支持独立部署、依赖共享、沙箱隔离，已在公司 6 个核心产品落地，体积较 qiankun 减少 40%。',
  },
  {
    id: 'b-sk-1',
    type: 'skill',
    title: '技能清单',
    content: 'React 18 · TypeScript · Vite · 微前端 · 可视化 · 性能优化 · Node.js · 设计系统',
  },
  {
    id: 'b-ed-1',
    type: 'education',
    title: '教育背景',
    meta: '2017.09 - 2021.06 · 北京邮电大学 · 计算机科学与技术 · 本科',
    content: 'GPA 3.7/4.0 · 校级优秀毕业生 · 全国大学生互联网大赛二等奖',
  },
]

// ============== 模拟面试 ==============
export interface InterviewHistory {
  id: string
  position: string
  company: string
  date: string
  duration: number
  mode: 'text' | 'voice'
  score: number
  status: 'completed' | 'in_progress' | 'aborted'
  dimensions: { name: string; score: number }[]
  questions: number
}

export const interviewHistory: InterviewHistory[] = [
  {
    id: 'i-001',
    position: '高级前端工程师',
    company: '字节跳动',
    date: '2026-06-11T15:30:00Z',
    duration: 42 * 60,
    mode: 'text',
    score: 87,
    status: 'completed',
    questions: 8,
    dimensions: [
      { name: '技术深度', score: 88 },
      { name: '系统设计', score: 82 },
      { name: '工程实践', score: 90 },
      { name: '沟通表达', score: 85 },
      { name: '算法能力', score: 89 },
    ],
  },
  {
    id: 'i-002',
    position: '资深前端工程师',
    company: '小红书',
    date: '2026-06-09T20:00:00Z',
    duration: 38 * 60,
    mode: 'voice',
    score: 78,
    status: 'completed',
    questions: 7,
    dimensions: [
      { name: '技术深度', score: 75 },
      { name: '系统设计', score: 72 },
      { name: '工程实践', score: 85 },
      { name: '沟通表达', score: 80 },
      { name: '算法能力', score: 76 },
    ],
  },
  {
    id: 'i-003',
    position: '高级前端工程师',
    company: '美团',
    date: '2026-06-07T10:15:00Z',
    duration: 45 * 60,
    mode: 'text',
    score: 92,
    status: 'completed',
    questions: 9,
    dimensions: [
      { name: '技术深度', score: 94 },
      { name: '系统设计', score: 90 },
      { name: '工程实践', score: 95 },
      { name: '沟通表达', score: 88 },
      { name: '算法能力', score: 92 },
    ],
  },
  {
    id: 'i-004',
    position: '前端架构师',
    company: '蚂蚁集团',
    date: '2026-06-02T14:00:00Z',
    duration: 50 * 60,
    mode: 'voice',
    score: 89,
    status: 'completed',
    questions: 10,
    dimensions: [
      { name: '技术深度', score: 92 },
      { name: '系统设计', score: 88 },
      { name: '工程实践', score: 90 },
      { name: '沟通表达', score: 86 },
      { name: '算法能力', score: 85 },
    ],
  },
  {
    id: 'i-005',
    position: 'Web 前端开发',
    company: '腾讯',
    date: '2026-05-28T11:30:00Z',
    duration: 35 * 60,
    mode: 'text',
    score: 81,
    status: 'completed',
    questions: 7,
    dimensions: [
      { name: '技术深度', score: 80 },
      { name: '系统设计', score: 78 },
      { name: '工程实践', score: 85 },
      { name: '沟通表达', score: 82 },
      { name: '算法能力', score: 79 },
    ],
  },
]

// 错题本
export interface ErrorQuestion {
  id: string
  question: string
  category: string
  frequency: number
  lastMissed: string
  difficulty: 'easy' | 'medium' | 'hard'
  hint: string
}

export const errorBook: ErrorQuestion[] = [
  {
    id: 'eq-001',
    question: 'React 18 中 concurrent mode 的工作原理是什么？',
    category: '框架原理',
    frequency: 3,
    lastMissed: '2026-06-11',
    difficulty: 'hard',
    hint: '从 Scheduler、Lane 模型、batchedUpdates 三个角度拆解',
  },
  {
    id: 'eq-002',
    question: '如何设计一个支持百万级 QPS 的短链生成系统？',
    category: '系统设计',
    frequency: 2,
    lastMissed: '2026-06-09',
    difficulty: 'hard',
    hint: '考虑发号器策略、布隆过滤器、缓存分层、读写分离',
  },
  {
    id: 'eq-003',
    question: 'BFF 层在微前端架构中的职责边界？',
    category: '架构设计',
    frequency: 2,
    lastMissed: '2026-06-07',
    difficulty: 'medium',
    hint: '聚合、鉴权、协议转换、流量染色',
  },
  {
    id: 'eq-004',
    question: 'LCP / FCP / TTFB 三个核心指标的优化路径？',
    category: '性能优化',
    frequency: 4,
    lastMissed: '2026-06-05',
    difficulty: 'medium',
    hint: '资源加载优先级、关键 CSS 提取、SSR vs SSG 选型',
  },
]

// ============== 个人画像 ==============
export interface AbilityDimension {
  key: string
  name: string
  ideal: number
  actual: number
  description: string
  subItems: { name: string; score: number }[]
}

export const abilityDimensions: AbilityDimension[] = [
  {
    key: 'tech',
    name: '技术深度',
    ideal: 90,
    actual: 82,
    description: '对前端核心技术的掌握深度，包括框架原理、浏览器机制、网络协议等',
    subItems: [
      { name: 'React 原理', score: 88 },
      { name: '浏览器渲染', score: 85 },
      { name: '网络与安全', score: 78 },
      { name: 'TypeScript 进阶', score: 84 },
    ],
  },
  {
    key: 'arch',
    name: '系统设计',
    ideal: 88,
    actual: 75,
    description: '将复杂业务抽象为可扩展、可维护架构的能力',
    subItems: [
      { name: '微前端架构', score: 80 },
      { name: '组件库设计', score: 82 },
      { name: '状态管理', score: 76 },
      { name: '设计模式', score: 68 },
    ],
  },
  {
    key: 'eng',
    name: '工程实践',
    ideal: 85,
    actual: 90,
    description: '将工程化方法论应用到日常开发中的能力',
    subItems: [
      { name: 'CI/CD', score: 92 },
      { name: '测试体系', score: 88 },
      { name: '监控告警', score: 90 },
      { name: '代码质量', score: 92 },
    ],
  },
  {
    key: 'comm',
    name: '沟通表达',
    ideal: 80,
    actual: 72,
    description: '技术方案阐述、跨团队协作、向上汇报',
    subItems: [
      { name: '技术分享', score: 78 },
      { name: '需求拆解', score: 75 },
      { name: '冲突处理', score: 65 },
    ],
  },
  {
    key: 'algo',
    name: '算法能力',
    ideal: 82,
    actual: 86,
    description: '基础算法和数据结构的应用能力',
    subItems: [
      { name: '数据结构', score: 90 },
      { name: '动态规划', score: 82 },
      { name: '图论基础', score: 85 },
    ],
  },
  {
    key: 'biz',
    name: '业务理解',
    ideal: 85,
    actual: 70,
    description: '对所处行业业务模型、用户场景、价值链的理解',
    subItems: [
      { name: '行业洞察', score: 68 },
      { name: '用户视角', score: 75 },
      { name: '数据分析', score: 70 },
    ],
  },
]

// 成长轨迹
export const growthTrajectory = [
  { date: '2026-01', tech: 65, arch: 55, eng: 78, comm: 60, algo: 70, biz: 58 },
  { date: '2026-02', tech: 70, arch: 60, eng: 82, comm: 62, algo: 74, biz: 60 },
  { date: '2026-03', tech: 73, arch: 64, eng: 84, comm: 65, algo: 78, biz: 63 },
  { date: '2026-04', tech: 76, arch: 68, eng: 86, comm: 67, algo: 81, biz: 66 },
  { date: '2026-05', tech: 79, arch: 72, eng: 88, comm: 70, algo: 84, biz: 68 },
  { date: '2026-06', tech: 82, arch: 75, eng: 90, comm: 72, algo: 86, biz: 70 },
]

// 个性化建议
export const improvementSuggestions = [
  {
    id: 's-1',
    title: '系统设计强化训练',
    type: '能力短板',
    priority: 'high' as const,
    description: '当前系统设计 75 分，距理想 88 分差 13 分，是面试中最高频短板',
    actions: [
      { label: '完成 3 道 L4 级别系统设计题', estimatedTime: '2 周' },
      { label: '阅读《数据密集型应用系统设计》第 5-7 章', estimatedTime: '1 周' },
      { label: '在 EdgeKit 项目中产出架构文档', estimatedTime: '3 天' },
    ],
  },
  {
    id: 's-2',
    title: '业务领域知识补充',
    type: '能力短板',
    priority: 'high' as const,
    description: '业务理解 70 分，需要建立对目标公司核心业务的深度认知',
    actions: [
      { label: '研究字节电商业务架构 3 篇深度文章', estimatedTime: '3 天' },
      { label: '整理 To C 产品增长方法论笔记', estimatedTime: '1 周' },
    ],
  },
  {
    id: 's-3',
    title: '错题本：性能优化专题',
    type: '错题巩固',
    priority: 'medium' as const,
    description: 'LCP/FCP/TTFB 优化已错 4 次，建议系统化学习',
    actions: [
      { label: '复习 Web Vitals 官方文档', estimatedTime: '2 天' },
      { label: '动手实现 SSR 性能优化 demo', estimatedTime: '4 天' },
    ],
  },
  {
    id: 's-4',
    title: '保持工程实践优势',
    type: '能力保持',
    priority: 'low' as const,
    description: '工程实践是你的强项，继续在面试中重点展示案例',
    actions: [
      { label: '准备 3 个最具说服力的工程化案例', estimatedTime: '2 天' },
    ],
  },
]

// ============== Dashboard ==============
export const dashboardStats = {
  resumeBranches: 5,
  activeBranches: 4,
  interviewsCompleted: 12,
  averageScore: 85.4,
  abilityGrowth: 13, // %
  totalQuestions: 156,
}

export const upcomingTasks = [
  {
    id: 't-1',
    title: '完成字节跳动简历分支 V3 优化',
    type: 'resume',
    due: '今天 18:00',
    priority: 'high',
  },
  {
    id: 't-2',
    title: '美团一面模拟面试',
    type: 'interview',
    due: '明天 10:00',
    priority: 'medium',
  },
  {
    id: 't-3',
    title: '复习错题本：系统设计 5 题',
    type: 'review',
    due: '本周内',
    priority: 'medium',
  },
]

export const recentActivities = [
  {
    id: 'a-1',
    type: 'resume',
    title: 'AI 优化了「字节跳动 · 高级前端」简历',
    detail: '匹配度从 82 提升到 87',
    time: '2 小时前',
  },
  {
    id: 'a-2',
    type: 'interview',
    title: '完成了字节跳动模拟面试',
    detail: '综合评分 87 分 · 8 道题',
    time: '昨天',
  },
  {
    id: 'a-3',
    type: 'profile',
    title: '能力画像已更新',
    detail: '系统设计 +3 分',
    time: '2 天前',
  },
  {
    id: 'a-4',
    type: 'resume',
    title: '创建了「小红书 · 资深前端」简历分支',
    detail: '已继承核心简历内容',
    time: '5 天前',
  },
]

// 招聘 JD 示例
export const sampleJD = `【字节跳动 · 电商前端 · 高级工程师】

岗位职责：
1. 负责抖音电商中后台 Web 应用的设计与开发，支撑商家、运营日常工作
2. 深入业务，理解电商交易链路，参与前端架构演进与核心模块建设
3. 推进前端工程化体系建设，提升团队开发效率与代码质量
4. 与产品、设计、后端紧密协作，输出可落地的技术方案

任职要求：
• 本科及以上学历，3 年以上前端开发经验
• 精通 React/TypeScript，熟悉其原理（Fiber、Concurrent、Scheduler 等）
• 具备复杂中后台系统设计经验，熟悉微前端、组件库、监控体系
• 理解性能优化（Web Vitals、加载、运行时），有 SSR/SSG 实战经验
• 良好的工程化意识，熟悉 Vite/Webpack 测试体系
• 加分：电商业务经验、可视化、低代码、Node.js 全栈`
