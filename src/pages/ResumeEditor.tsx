import { useState } from 'react'
import { useParams, Link, useNavigate } from 'react-router-dom'
import {
  ArrowLeft,
  Sparkles,
  Download,
  Share2,
  History,
  GitCompare,
  Wand2,
  Type,
  Heading2,
  List,
  Plus,
  GripVertical,
  Trash2,
  Copy,
  ChevronDown,
  ChevronRight,
  Eye,
  Code,
  Layout,
  MoreHorizontal,
  Check,
  X,
  Loader2,
  FileText,
  TrendingUp,
  AlertCircle,
  Zap,
  Star,
  Command,
} from 'lucide-react'
import { Card, CardHeader } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { Badge } from '@/components/ui/Badge'
import { Tabs } from '@/components/ui/Tabs'
import { Progress } from '@/components/ui/Progress'
import { Textarea } from '@/components/ui/Input'
import { coreResumeBlocks, resumeBranches, sampleJD, type ResumeBlock } from '@/data/mockData'
import { cn, timeAgo } from '@/lib/utils'

const blockTypeMeta = {
  heading: { label: '标题', icon: Heading2, color: 'text-brand-600 dark:text-brand-300' },
  summary: { label: '简介', icon: Type, color: 'text-emerald-600 dark:text-emerald-400' },
  experience: { label: '经历', icon: List, color: 'text-violet-600 dark:text-violet-400' },
  project: { label: '项目', icon: FileText, color: 'text-amber-600 dark:text-amber-400' },
  skill: { label: '技能', icon: Zap, color: 'text-cyan-600 dark:text-cyan-400' },
  education: { label: '教育', icon: Star, color: 'text-pink-600 dark:text-pink-400' },
}

const templates = [
  { key: 'classic', name: '经典', desc: '稳重专业，适合传统大厂' },
  { key: 'modern', name: '现代', desc: '信息密度高，适合互联网' },
  { key: 'minimal', name: '极简', desc: 'Notion 风格，内容优先' },
  { key: 'tech', name: '技术', desc: '突出技术栈与项目' },
]

export default function ResumeEditor() {
  const { branchId = 'core' } = useParams<{ branchId: string }>()
  const navigate = useNavigate()
  const branch = resumeBranches.find((b) => b.id === branchId) || resumeBranches[0]

  const [blocks, setBlocks] = useState<ResumeBlock[]>(coreResumeBlocks)
  const [activeBlock, setActiveBlock] = useState<string | null>(null)
  const [view, setView] = useState<'edit' | 'preview' | 'split' | 'diff'>('split')
  const [template, setTemplate] = useState('minimal')
  const [aiPanelOpen, setAiPanelOpen] = useState(true)
  const [jdInput, setJdInput] = useState(sampleJD)
  const [aiGenerating, setAiGenerating] = useState(false)
  const [aiStage, setAiStage] = useState(0)
  const [templatePickerOpen, setTemplatePickerOpen] = useState(false)

  const startAiGenerate = () => {
    setAiGenerating(true)
    setAiStage(0)
    const stages = [
      { time: 600, stage: 1 }, // 分析 JD
      { time: 1200, stage: 2 }, // 匹配核心
      { time: 1800, stage: 3 }, // 生成优化
      { time: 2400, stage: 4 }, // 完成
    ]
    stages.forEach(({ time, stage }) => {
      setTimeout(() => setAiStage(stage), time)
    })
    setTimeout(() => setAiGenerating(false), 3000)
  }

  return (
    <div className="h-full flex flex-col">
      {/* 编辑器工具栏 */}
      <div className="border-b border-surface-border dark:border-dark-surface-border bg-surface dark:bg-dark-surface flex-shrink-0">
        <div className="px-6 py-2.5 flex items-center gap-3">
          <Link
            to="/resume"
            className="p-1.5 -ml-1.5 rounded text-ink-3 hover:bg-surface-muted hover:text-ink-1 transition-colors"
            aria-label="返回"
          >
            <ArrowLeft className="h-4 w-4" />
          </Link>

          <div className="flex items-center gap-2 min-w-0 flex-1">
            <div className="text-sm font-medium text-ink-1 truncate">{branch.name}</div>
            {!branch.isMain && branch.matchScore && (
              <div className="flex items-center gap-1.5 flex-shrink-0">
                <span className="text-2xs text-ink-3">匹配度</span>
                <span
                  className={cn(
                    'text-xs font-semibold tabular-nums',
                    branch.matchScore >= 90
                      ? 'text-emerald-600 dark:text-emerald-400'
                      : 'text-brand-600 dark:text-brand-300',
                  )}
                >
                  {branch.matchScore}
                </span>
              </div>
            )}
            <Badge
              variant={
                branch.status === 'ready'
                  ? 'success'
                  : branch.status === 'optimizing'
                    ? 'warning'
                    : 'default'
              }
            >
              {branch.status === 'ready' ? '已就绪' : branch.status === 'optimizing' ? '优化中' : '草稿'}
            </Badge>
            <span className="text-2xs text-ink-3 hidden md:inline">·</span>
            <span className="text-2xs text-ink-3 hidden md:inline">
              {timeAgo(branch.lastEdited)} · {branch.versionCount} 个版本
            </span>
          </div>

          <div className="flex items-center gap-1.5">
            <Tabs
              value={view}
              onChange={(v) => setView(v as typeof view)}
              size="sm"
              items={[
                { key: 'edit', label: '编辑' },
                { key: 'split', label: '分屏' },
                { key: 'preview', label: '预览' },
                { key: 'diff', label: '对比' },
              ]}
            />

            <div className="w-px h-5 bg-surface-border dark:bg-dark-surface-border mx-1" />

            <div className="relative">
              <Button
                size="sm"
                variant="ghost"
                leftIcon={<Layout className="h-3.5 w-3.5" />}
                rightIcon={<ChevronDown className="h-3 w-3" />}
                onClick={() => setTemplatePickerOpen((v) => !v)}
              >
                {templates.find((t) => t.key === template)?.name}
              </Button>
              {templatePickerOpen && (
                <>
                  <div className="fixed inset-0 z-40" onClick={() => setTemplatePickerOpen(false)} />
                  <div className="absolute right-0 top-full mt-1 w-64 z-50 surface-1 rounded-md border border-surface-border dark:border-dark-surface-border shadow-notion-md p-1.5 animate-fade-in">
                    {templates.map((t) => (
                      <button
                        key={t.key}
                        onClick={() => {
                          setTemplate(t.key)
                          setTemplatePickerOpen(false)
                        }}
                        className={cn(
                          'w-full flex items-start gap-2.5 p-2 rounded text-left transition-colors',
                          template === t.key
                            ? 'bg-brand-50 dark:bg-brand-500/15'
                            : 'hover:bg-surface-muted dark:hover:bg-dark-surface-muted',
                        )}
                      >
                        <div
                          className={cn(
                            'h-7 w-5 rounded border flex-shrink-0 flex items-center justify-center text-2xs font-bold',
                            template === t.key
                              ? 'border-brand-500 bg-brand-500 text-white'
                              : 'border-surface-border dark:border-dark-surface-border text-ink-3',
                          )}
                        >
                          Aa
                        </div>
                        <div className="min-w-0 flex-1">
                          <div className="text-sm font-medium text-ink-1">{t.name}</div>
                          <div className="text-2xs text-ink-3 mt-0.5">{t.desc}</div>
                        </div>
                        {template === t.key && <Check className="h-3.5 w-3.5 text-brand-500 mt-1" />}
                      </button>
                    ))}
                  </div>
                </>
              )}
            </div>

            <Button size="sm" variant="ghost" leftIcon={<History className="h-3.5 w-3.5" />}>
              历史
            </Button>
            <Button size="sm" variant="ghost" leftIcon={<Share2 className="h-3.5 w-3.5" />}>
              分享
            </Button>
            <Button size="sm" variant="primary" leftIcon={<Download className="h-3.5 w-3.5" />}>
              导出 PDF
            </Button>
          </div>
        </div>
      </div>

      {/* 主工作区 - 三栏 */}
      <div className="flex-1 flex min-h-0">
        {/* 左侧：块编辑器 */}
        {(view === 'edit' || view === 'split' || view === 'diff') && (
          <div
            className={cn(
              'flex-1 overflow-y-auto',
              view === 'split' && 'lg:flex-none lg:w-[44%] border-r border-surface-border dark:border-dark-surface-border',
            )}
          >
            <div className="max-w-3xl mx-auto px-8 py-8">
              {/* 块列表 */}
              <div className="space-y-1">
                {blocks.map((block, idx) => (
                  <BlockEditor
                    key={block.id}
                    block={block}
                    index={idx}
                    isActive={activeBlock === block.id}
                    isDiff={view === 'diff'}
                    onSelect={() => setActiveBlock(block.id)}
                    onUpdate={(updates) => {
                      setBlocks((prev) => prev.map((b) => (b.id === block.id ? { ...b, ...updates } : b)))
                    }}
                    onDelete={() => setBlocks((prev) => prev.filter((b) => b.id !== block.id))}
                    onDuplicate={() => {
                      const newBlock = { ...block, id: `b-${Date.now()}` }
                      setBlocks((prev) => [...prev.slice(0, idx + 1), newBlock, ...prev.slice(idx + 1)])
                    }}
                  />
                ))}

                <button
                  className="w-full mt-2 flex items-center justify-center gap-1.5 h-9 rounded border border-dashed border-surface-border dark:border-dark-surface-border text-2xs text-ink-3 hover:border-ink-muted hover:text-ink-1 hover:bg-surface-muted/50 dark:hover:bg-dark-surface-muted/30 transition-colors"
                  onClick={() => {
                    const id = `b-${Date.now()}`
                    setBlocks((prev) => [
                      ...prev,
                      { id, type: 'experience', title: '', content: '', meta: '' },
                    ])
                    setActiveBlock(id)
                  }}
                >
                  <Plus className="h-3 w-3" />
                  添加块
                </button>
              </div>
            </div>
          </div>
        )}

        {/* 右侧：实时预览 */}
        {(view === 'preview' || view === 'split') && (
          <div
            className={cn(
              'flex-1 overflow-y-auto bg-surface-muted/40 dark:bg-dark-surface-subtle/40',
              view === 'split' && 'lg:flex-none lg:w-[56%]',
            )}
          >
            <div className="px-8 py-8 max-w-3xl mx-auto">
              <div className="mb-3 flex items-center justify-between">
                <div className="text-2xs text-ink-3">实时预览 · {templates.find((t) => t.key === template)?.name} 模板</div>
                <Button size="sm" variant="ghost" leftIcon={<Eye className="h-3.5 w-3.5" />}>
                  全屏预览
                </Button>
              </div>
              <ResumePreview blocks={blocks} template={template} />
            </div>
          </div>
        )}

        {/* 对比模式 */}
        {view === 'diff' && (
          <div className="flex-1 overflow-y-auto bg-surface-muted/40 dark:bg-dark-surface-subtle/40">
            <div className="px-8 py-8 max-w-4xl mx-auto">
              <div className="mb-4 flex items-center gap-3">
                <GitCompare className="h-4 w-4 text-ink-3" />
                <div className="text-sm font-medium text-ink-1">
                  对比：V{branch.versionCount - 1} <span className="text-ink-3 mx-1">→</span> V
                  {branch.versionCount}
                </div>
                <Badge variant="brand" leftIcon={<Sparkles className="h-2.5 w-2.5" />}>
                  AI 修改
                </Badge>
                <div className="flex-1" />
                <div className="flex items-center gap-2 text-2xs text-ink-3">
                  <span className="flex items-center gap-1">
                    <span className="h-2.5 w-2.5 rounded-sm bg-emerald-500/30 border border-emerald-500/40" />
                    新增
                  </span>
                  <span className="flex items-center gap-1">
                    <span className="h-2.5 w-2.5 rounded-sm bg-amber-500/30 border border-amber-500/40" />
                    修改
                  </span>
                  <span className="flex items-center gap-1">
                    <span className="h-2.5 w-2.5 rounded-sm bg-red-500/30 border border-red-500/40" />
                    删除
                  </span>
                </div>
              </div>
              <DiffView blocks={blocks} />
            </div>
          </div>
        )}
      </div>

      {/* AI 助手浮动按钮 / 侧边面板 */}
      {!aiPanelOpen && (
        <button
          onClick={() => setAiPanelOpen(true)}
          className="fixed bottom-6 right-6 z-30 h-12 w-12 rounded-full bg-gradient-to-br from-brand-500 to-brand-700 text-white shadow-notion-md hover:shadow-notion-lg hover:scale-105 transition-all flex items-center justify-center"
          aria-label="打开 AI 助手"
        >
          <Sparkles className="h-5 w-5" />
        </button>
      )}

      {aiPanelOpen && (
        <aside className="w-80 border-l border-surface-border dark:border-dark-surface-border bg-surface dark:bg-dark-surface flex flex-col flex-shrink-0 animate-slide-in-right">
          <div className="px-4 py-3 border-b border-surface-border dark:border-dark-surface-border flex items-center justify-between flex-shrink-0">
            <div className="flex items-center gap-2">
              <div className="h-6 w-6 rounded-md bg-gradient-to-br from-brand-500 to-brand-700 flex items-center justify-center">
                <Sparkles className="h-3 w-3 text-white" strokeWidth={2.5} />
              </div>
              <span className="text-sm font-semibold text-ink-1">AI 简历助手</span>
            </div>
            <button
              onClick={() => setAiPanelOpen(false)}
              className="p-1 rounded text-ink-3 hover:bg-surface-muted hover:text-ink-1 transition-colors"
              aria-label="关闭"
            >
              <X className="h-3.5 w-3.5" />
            </button>
          </div>

          <div className="flex-1 overflow-y-auto p-4 space-y-4">
            {/* JD 输入 */}
            <div>
              <div className="flex items-center justify-between mb-1.5">
                <label className="text-xs font-medium text-ink-1">招聘 JD</label>
                <button className="text-2xs text-ink-3 hover:text-ink-1 transition-colors">
                  粘贴 URL
                </button>
              </div>
              <Textarea
                value={jdInput}
                onChange={(e) => setJdInput(e.target.value)}
                rows={6}
                placeholder="将招聘 JD 粘贴到这里…"
                className="text-xs leading-relaxed"
              />
            </div>

            {/* AI 生成按钮 */}
            <Button
              variant="primary"
              className="w-full"
              leftIcon={
                aiGenerating ? (
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                ) : (
                  <Wand2 className="h-3.5 w-3.5" />
                )
              }
              onClick={startAiGenerate}
              loading={aiGenerating}
            >
              {aiGenerating ? 'AI 正在优化…' : '开始 AI 优化'}
            </Button>

            {/* 进度指示器 */}
            {aiGenerating && (
              <div className="space-y-2 animate-fade-in">
                <div className="space-y-1.5">
                  <Stage done={aiStage >= 1} active={aiStage === 1} label="解析 JD 关键能力词" />
                  <Stage done={aiStage >= 2} active={aiStage === 2} label="匹配核心简历内容" />
                  <Stage done={aiStage >= 3} active={aiStage === 3} label="生成针对性优化建议" />
                  <Stage done={aiStage >= 4} active={aiStage === 4} label="应用修改并预览" />
                </div>
              </div>
            )}

            {/* 生成结果 */}
            {!aiGenerating && aiStage === 0 && (
              <>
                <div>
                  <div className="text-xs font-medium text-ink-1 mb-2">AI 建议</div>
                  <div className="space-y-2">
                    <Suggestion
                      title="突出「微前端架构」经验"
                      impact="匹配度 +3"
                      detail="JD 第 2 条提到「微前端、组件库」，建议将 EdgeKit 项目的描述前置。"
                    />
                    <Suggestion
                      title="补充电商业务理解"
                      impact="匹配度 +4"
                      detail="JD 强调电商交易链路，可在项目经历中加入「订单」「履约」相关关键词。"
                    />
                    <Suggestion
                      title="强化 TypeScript 进阶能力"
                      impact="匹配度 +2"
                      detail="JD 提到「TypeScript 原理」，建议在技能清单中标注 TS 高级类型应用经验。"
                    />
                  </div>
                </div>

                <div>
                  <div className="text-xs font-medium text-ink-1 mb-2">智能操作</div>
                  <div className="grid grid-cols-2 gap-1.5">
                    <ActionBtn icon={<Zap className="h-3 w-3" />} label="智能重写" />
                    <ActionBtn icon={<Type className="h-3 w-3" />} label="润色措辞" />
                    <ActionBtn icon={<TrendingUp className="h-3 w-3" />} label="量化成果" />
                    <ActionBtn icon={<Layout className="h-3 w-3" />} label="优化排版" />
                  </div>
                </div>
              </>
            )}

            {aiStage === 4 && !aiGenerating && (
              <div className="animate-fade-in space-y-3">
                <div className="p-3 rounded-md bg-emerald-50 dark:bg-emerald-500/10 border border-emerald-200/60 dark:border-emerald-500/20">
                  <div className="flex items-center gap-1.5 mb-1">
                    <Check className="h-3.5 w-3.5 text-emerald-600 dark:text-emerald-400" />
                    <span className="text-sm font-medium text-emerald-700 dark:text-emerald-300">
                      优化完成
                    </span>
                  </div>
                  <div className="text-xs text-emerald-700/80 dark:text-emerald-300/80 leading-relaxed">
                    匹配度从 82 提升至
                    <span className="font-semibold mx-0.5">87</span>
                    · 共修改 6 处 · 新增 2 个亮点
                  </div>
                </div>
                <div className="space-y-1.5">
                  <Button variant="primary" className="w-full" size="sm">
                    应用所有修改
                  </Button>
                  <Button variant="secondary" className="w-full" size="sm">
                    逐条审阅
                  </Button>
                </div>
              </div>
            )}
          </div>

          <div className="px-4 py-2.5 border-t border-surface-border dark:border-dark-surface-border text-2xs text-ink-3 flex items-center gap-1.5 flex-shrink-0">
            <Command className="h-2.5 w-2.5" />
            <span>选中文本按</span>
            <kbd className="px-1 rounded bg-surface-muted dark:bg-dark-surface-muted">⌘ K</kbd>
            <span>召唤 AI</span>
          </div>
        </aside>
      )}
    </div>
  )
}

// ============== 子组件 ==============

function BlockEditor({
  block,
  index,
  isActive,
  isDiff,
  onSelect,
  onUpdate,
  onDelete,
  onDuplicate,
}: {
  block: ResumeBlock
  index: number
  isActive: boolean
  isDiff: boolean
  onSelect: () => void
  onUpdate: (updates: Partial<ResumeBlock>) => void
  onDelete: () => void
  onDuplicate: () => void
}) {
  const meta = blockTypeMeta[block.type]
  const [hovered, setHovered] = useState(false)

  return (
    <div
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      onClick={onSelect}
      className={cn(
        'group relative rounded transition-colors cursor-text',
        isActive ? 'bg-surface-muted/50 dark:bg-dark-surface-muted/30' : 'hover:bg-surface-muted/30 dark:hover:bg-dark-surface-muted/20',
      )}
    >
      <div className="flex items-start pl-9 pr-2 py-2">
        {/* 拖拽手柄 + 类型指示 */}
        <div className="absolute left-0 top-0 h-full flex flex-col items-center pt-2.5 gap-1.5">
          <button
            className={cn(
              'h-5 w-5 rounded flex items-center justify-center text-ink-muted',
              'hover:bg-surface-muted hover:text-ink-2 transition-all',
              hovered || isActive ? 'opacity-100' : 'opacity-0',
            )}
            aria-label="拖拽排序"
            onClick={(e) => e.stopPropagation()}
          >
            <GripVertical className="h-3.5 w-3.5" />
          </button>
          <div
            className={cn(
              'h-5 w-5 rounded flex items-center justify-center transition-opacity',
              hovered || isActive ? 'opacity-100' : 'opacity-0',
              meta.color,
            )}
            title={meta.label}
          >
            <meta.icon className="h-3.5 w-3.5" />
          </div>
        </div>

        {/* 块内容 */}
        <div className="flex-1 min-w-0">
          {block.type === 'heading' ? (
            <input
              type="text"
              value={block.title}
              onChange={(e) => onUpdate({ title: e.target.value })}
              placeholder="姓名"
              className="w-full text-2xl font-semibold text-ink-1 bg-transparent border-0 focus:outline-none placeholder:text-ink-muted tracking-tight"
            />
          ) : (
            <>
              {block.title && (
                <input
                  type="text"
                  value={block.title}
                  onChange={(e) => onUpdate({ title: e.target.value })}
                  placeholder="块标题"
                  className="w-full text-sm font-semibold text-ink-1 bg-transparent border-0 focus:outline-none placeholder:text-ink-muted mb-1"
                />
              )}
              {!block.title && block.type !== 'experience' && (
                <input
                  type="text"
                  value={block.meta || ''}
                  onChange={(e) => onUpdate({ meta: e.target.value })}
                  placeholder="添加副标题…"
                  className="w-full text-xs text-ink-3 bg-transparent border-0 focus:outline-none placeholder:text-ink-muted mb-1.5 italic"
                />
              )}
              {block.type === 'experience' && (
                <input
                  type="text"
                  value={block.meta || ''}
                  onChange={(e) => onUpdate({ meta: e.target.value })}
                  placeholder="时间 · 公司 · 职位"
                  className="w-full text-xs text-ink-3 bg-transparent border-0 focus:outline-none placeholder:text-ink-muted mb-1.5"
                />
              )}
              <textarea
                value={block.content}
                onChange={(e) => onUpdate({ content: e.target.value })}
                placeholder="开始输入，或按 / 召唤 AI 助手…"
                rows={block.content.split('\n').length || 1}
                className="w-full text-sm leading-relaxed text-ink-2 bg-transparent border-0 focus:outline-none placeholder:text-ink-muted resize-none"
              />
            </>
          )}
        </div>

        {/* 块操作按钮 */}
        <div
          className={cn(
            'flex items-center gap-0.5 flex-shrink-0 transition-opacity',
            hovered || isActive ? 'opacity-100' : 'opacity-0',
          )}
        >
          <button
            onClick={(e) => {
              e.stopPropagation()
              onUpdate({ collapsed: !block.collapsed })
            }}
            className="p-1 rounded text-ink-3 hover:bg-surface-muted hover:text-ink-1 transition-colors"
            aria-label="折叠"
            title="折叠"
          >
            {block.collapsed ? (
              <ChevronRight className="h-3.5 w-3.5" />
            ) : (
              <ChevronDown className="h-3.5 w-3.5" />
            )}
          </button>
          <button
            onClick={(e) => {
              e.stopPropagation()
              onDuplicate()
            }}
            className="p-1 rounded text-ink-3 hover:bg-surface-muted hover:text-ink-1 transition-colors"
            aria-label="复制"
            title="复制"
          >
            <Copy className="h-3.5 w-3.5" />
          </button>
          <button
            onClick={(e) => {
              e.stopPropagation()
              onDelete()
            }}
            className="p-1 rounded text-ink-3 hover:bg-red-50 hover:text-red-600 dark:hover:bg-red-500/10 dark:hover:text-red-400 transition-colors"
            aria-label="删除"
            title="删除"
          >
            <Trash2 className="h-3.5 w-3.5" />
          </button>
        </div>
      </div>
    </div>
  )
}

function Stage({ done, active, label }: { done: boolean; active?: boolean; label: string }) {
  return (
    <div className="flex items-center gap-2">
      <div
        className={cn(
          'h-4 w-4 rounded-full flex items-center justify-center flex-shrink-0 transition-all',
          done
            ? 'bg-emerald-500 text-white'
            : active
              ? 'bg-brand-500/20 text-brand-600 dark:text-brand-300 ring-2 ring-brand-500/30'
              : 'bg-surface-muted dark:bg-dark-surface-muted text-ink-muted',
        )}
      >
        {done ? (
          <Check className="h-2.5 w-2.5" strokeWidth={3} />
        ) : active ? (
          <Loader2 className="h-2.5 w-2.5 animate-spin" />
        ) : (
          <div className="h-1 w-1 rounded-full bg-current" />
        )}
      </div>
      <span
        className={cn(
          'text-xs',
          done
            ? 'text-ink-2 dark:text-dark-ink-secondary'
            : active
              ? 'text-ink-1 font-medium'
              : 'text-ink-3',
        )}
      >
        {label}
      </span>
    </div>
  )
}

function Suggestion({
  title,
  impact,
  detail,
}: {
  title: string
  impact: string
  detail: string
}) {
  return (
    <div className="p-2.5 rounded-md border border-surface-border dark:border-dark-surface-border hover:border-ink-muted/40 transition-colors cursor-pointer group">
      <div className="flex items-start justify-between gap-2 mb-1">
        <div className="text-xs font-medium text-ink-1 leading-snug">{title}</div>
        <Badge variant="success">{impact}</Badge>
      </div>
      <div className="text-2xs text-ink-3 leading-relaxed">{detail}</div>
    </div>
  )
}

function ActionBtn({ icon, label }: { icon: React.ReactNode; label: string }) {
  return (
    <button className="flex items-center gap-1.5 px-2.5 h-7 rounded border border-surface-border dark:border-dark-surface-border text-xs text-ink-2 dark:text-dark-ink-secondary hover:bg-surface-muted dark:hover:bg-dark-surface-muted hover:border-ink-muted/40 transition-all">
      {icon}
      {label}
    </button>
  )
}

// 简历预览（极简风，模拟 A4 纸张）
function ResumePreview({ blocks, template }: { blocks: ResumeBlock[]; template: string }) {
  return (
    <div className="rounded-md border border-surface-border dark:border-dark-surface-border shadow-notion-md overflow-hidden bg-white text-ink-primary">
      {/* 模拟 A4 纸张比例 */}
      <div className="aspect-[1/1.414] p-10 text-[11px] leading-relaxed">
        {blocks.map((b) => {
          if (b.collapsed) return null
          if (b.type === 'heading') {
            return (
              <div key={b.id} className="pb-3 mb-4 border-b-2 border-ink-primary">
                <h1 className="text-2xl font-bold tracking-tight text-ink-primary">{b.title}</h1>
                <div className="text-xs text-ink-secondary mt-1">{b.content}</div>
                {b.meta && <div className="text-2xs text-ink-tertiary mt-0.5">{b.meta}</div>}
              </div>
            )
          }
          if (b.type === 'summary') {
            return (
              <div key={b.id} className="mb-4">
                <div className="text-2xs font-semibold text-ink-tertiary uppercase tracking-wider mb-1">
                  {b.title}
                </div>
                <p className="text-xs text-ink-secondary leading-relaxed">{b.content}</p>
              </div>
            )
          }
          if (b.type === 'experience') {
            return (
              <div key={b.id} className="mb-4">
                {b.title && (
                  <div className="text-2xs font-semibold text-ink-tertiary uppercase tracking-wider mb-1.5">
                    {b.title}
                  </div>
                )}
                <div className="text-2xs text-ink-tertiary mb-1">{b.meta}</div>
                <div className="text-xs text-ink-secondary whitespace-pre-line leading-relaxed">
                  {b.content}
                </div>
              </div>
            )
          }
          if (b.type === 'project') {
            return (
              <div key={b.id} className="mb-4">
                <div className="text-2xs font-semibold text-ink-tertiary uppercase tracking-wider mb-1.5">
                  {b.title}
                </div>
                <div className="text-2xs font-medium text-ink-primary mb-1">{b.meta}</div>
                <div className="text-xs text-ink-secondary leading-relaxed">{b.content}</div>
              </div>
            )
          }
          if (b.type === 'skill') {
            return (
              <div key={b.id} className="mb-4">
                <div className="text-2xs font-semibold text-ink-tertiary uppercase tracking-wider mb-1.5">
                  {b.title}
                </div>
                <div className="flex flex-wrap gap-1">
                  {b.content.split('·').map((s, i) => (
                    <span
                      key={i}
                      className="text-2xs px-1.5 py-0.5 rounded bg-slate-100 text-slate-700"
                    >
                      {s.trim()}
                    </span>
                  ))}
                </div>
              </div>
            )
          }
          if (b.type === 'education') {
            return (
              <div key={b.id} className="mb-4">
                <div className="text-2xs font-semibold text-ink-tertiary uppercase tracking-wider mb-1.5">
                  {b.title}
                </div>
                <div className="text-2xs text-ink-tertiary mb-0.5">{b.meta}</div>
                <div className="text-xs text-ink-secondary">{b.content}</div>
              </div>
            )
          }
          return null
        })}
      </div>
    </div>
  )
}

// Diff 视图
function DiffView({ blocks }: { blocks: ResumeBlock[] }) {
  return (
    <div className="rounded-md border border-surface-border dark:border-dark-surface-border bg-white text-ink-primary overflow-hidden">
      <div className="aspect-[1/1.414] p-10 text-[11px] leading-relaxed overflow-hidden">
        {blocks.slice(0, 4).map((b) => (
          <div key={b.id} className="mb-4">
            {b.title && (
              <div className="text-2xs font-semibold uppercase tracking-wider mb-1 bg-amber-100/60 -mx-1 px-1 rounded">
                {b.title}
              </div>
            )}
            {b.meta && (
              <div className="text-2xs mb-1 bg-emerald-100/60 -mx-1 px-1 rounded">{b.meta}</div>
            )}
            <div className="text-xs whitespace-pre-line">
              {b.content.split('\n').map((line, i) => {
                if (line.includes('12 个分散系统'))
                  return (
                    <div key={i} className="bg-emerald-100/60 -mx-1 px-1 rounded">
                      {line}
                    </div>
                  )
                if (line.includes('4.2s 降至 1.1s'))
                  return (
                    <div key={i} className="bg-amber-100/60 -mx-1 px-1 rounded">
                      {line}
                    </div>
                  )
                return <div key={i}>{line}</div>
              })}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
