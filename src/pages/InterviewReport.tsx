import { Link, useParams } from 'react-router-dom'
import {
  ArrowLeft,
  Download,
  Share2,
  Sparkles,
  CheckCircle2,
  AlertCircle,
  TrendingUp,
  TrendingDown,
  Lightbulb,
  ThumbsUp,
  Clock,
  Calendar,
  Briefcase,
  MessageSquare,
  Mic,
  BarChart3,
  ArrowRight,
  Star,
} from 'lucide-react'
import { Card, CardHeader } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { Badge } from '@/components/ui/Badge'
import { Progress } from '@/components/ui/Progress'
import { Avatar } from '@/components/ui/Avatar'
import { interviewHistory } from '@/data/mockData'
import { cn, formatDuration, timeAgo } from '@/lib/utils'

const questionDetails = [
  {
    id: 'q-1',
    question: '请简单介绍一下你自己，并重点说说最有代表性的一个项目。',
    dimension: '沟通表达',
    score: 85,
    answer:
      '我有 3 年大厂前端经验，目前在某互联网公司担任高级前端工程师。我最自豪的项目是从 0 到 1 设计并落地了 EdgeKit 内部微前端框架，已在公司 6 个核心产品中使用，体积比 qiankun 减少 40%。',
    feedback: {
      strengths: ['回答结构清晰，有 STAR 法则的影子', '主动量化了项目成果'],
      improvements: ['可以更深入地讲技术选型的权衡', 'EdgeKit 性能数据需要更具体'],
    },
  },
  {
    id: 'q-2',
    question: '能详细讲讲这个微前端框架的沙箱隔离机制吗？',
    dimension: '技术深度',
    score: 78,
    answer:
      '我们采用了基于 Proxy 的 JS 沙箱和基于 Shadow DOM 的 CSS 沙箱。',
    feedback: {
      strengths: ['准确指出了核心技术点'],
      improvements: ['未说明快照机制在多实例下的内存影响', '可以补充异常逃逸的处理方案'],
    },
  },
  {
    id: 'q-3',
    question: '如何设计一个支持百万级 QPS 的短链生成系统？',
    dimension: '系统设计',
    score: 72,
    answer: '使用哈希算法生成短链，配合 Redis 缓存。',
    feedback: {
      strengths: ['基础思路正确'],
      improvements: [
        '未考虑哈希冲突的解决方案',
        '缺少对读写分离、布隆过滤器、分库分表的讨论',
        '没有量化容量预估数据',
      ],
    },
  },
  {
    id: 'q-4',
    question: 'React 18 中 concurrent mode 的工作原理是什么？',
    dimension: '框架原理',
    score: 88,
    answer: '从 Scheduler 调度、Lane 优先级模型、batchedUpdates 三个角度详细回答。',
    feedback: {
      strengths: ['知识面广、概念清晰', '能够从源码层面解释机制'],
      improvements: ['可以补充 time slicing 的具体实现'],
    },
  },
]

export default function InterviewReport() {
  const { id = 'i-001' } = useParams<{ id: string }>()
  const record = interviewHistory.find((i) => i.id === id) || interviewHistory[0]

  return (
    <div className="px-8 py-6 max-w-6xl mx-auto">
      {/* 页头 */}
      <div className="flex items-start justify-between gap-4 mb-6">
        <div>
          <Link
            to="/interview"
            className="inline-flex items-center gap-1 text-xs text-ink-3 hover:text-ink-1 transition-colors mb-2"
          >
            <ArrowLeft className="h-3 w-3" />
            返回面试历史
          </Link>
          <div className="flex items-center gap-2.5 mb-1">
            <h1 className="text-2xl font-semibold text-ink-1 tracking-tight">
              {record.company} · {record.position}
            </h1>
            <Badge variant={record.score >= 85 ? 'success' : record.score >= 75 ? 'brand' : 'warning'}>
              {record.score >= 85 ? '优秀' : record.score >= 75 ? '良好' : '待提升'}
            </Badge>
          </div>
          <div className="flex items-center gap-3 text-sm text-ink-3">
            <span className="flex items-center gap-1">
              <Calendar className="h-3.5 w-3.5" />
              {timeAgo(record.date)}
            </span>
            <span>·</span>
            <span className="flex items-center gap-1">
              <Clock className="h-3.5 w-3.5" />
              {formatDuration(record.duration)}
            </span>
            <span>·</span>
            <span className="flex items-center gap-1">
              {record.mode === 'voice' ? <Mic className="h-3.5 w-3.5" /> : <MessageSquare className="h-3.5 w-3.5" />}
              {record.mode === 'voice' ? '语音面试' : '文字面试'}
            </span>
            <span>·</span>
            <span>{record.questions} 道题</span>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="secondary" leftIcon={<Share2 className="h-3.5 w-3.5" />}>
            分享报告
          </Button>
          <Button variant="primary" leftIcon={<Download className="h-3.5 w-3.5" />}>
            导出 PDF
          </Button>
        </div>
      </div>

      {/* 总览卡 */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-3 mb-6">
        <Card className="md:col-span-2 p-6 bg-gradient-to-br from-brand-50/40 to-surface dark:from-brand-500/5 dark:to-dark-surface">
          <div className="flex items-center gap-5">
            <div className="relative">
              <svg className="h-24 w-24 -rotate-90" viewBox="0 0 100 100">
                <circle
                  cx="50"
                  cy="50"
                  r="42"
                  fill="none"
                  stroke="currentColor"
                  strokeOpacity="0.08"
                  strokeWidth="8"
                />
                <circle
                  cx="50"
                  cy="50"
                  r="42"
                  fill="none"
                  stroke="rgb(59, 130, 246)"
                  strokeWidth="8"
                  strokeDasharray={`${(record.score / 100) * 264} 264`}
                  strokeLinecap="round"
                />
              </svg>
              <div className="absolute inset-0 flex items-center justify-center flex-col">
                <div className="text-2xl font-semibold text-ink-1 tabular-nums">{record.score}</div>
                <div className="text-2xs text-ink-3">综合评分</div>
              </div>
            </div>
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-1.5 mb-1">
                <Sparkles className="h-3.5 w-3.5 text-brand-500" />
                <span className="text-xs font-medium text-brand-600 dark:text-brand-300">AI 总结</span>
              </div>
              <p className="text-sm text-ink-2 leading-relaxed">
                本次面试表现
                <span className="text-emerald-600 dark:text-emerald-400 font-medium mx-1">良好</span>
                ，技术深度扎实，沟通表达清晰。建议在「系统设计」维度加强：
                答题时缺乏对容量预估、限流降级等生产级关注点的讨论。
              </p>
              <div className="mt-3 text-2xs text-ink-3">
                对比上次面试：
                <span className="text-emerald-600 dark:text-emerald-400 font-medium ml-1">+5 分</span>
              </div>
            </div>
          </div>
        </Card>

        <Card className="p-4">
          <div className="text-2xs text-ink-3 mb-1.5">最强维度</div>
          <div className="text-xl font-semibold text-ink-1">工程实践</div>
          <div className="text-2xs text-ink-3 mt-0.5">95 分 · 保持优势</div>
          <div className="mt-3 p-2 rounded-md bg-emerald-50 dark:bg-emerald-500/10 text-2xs text-emerald-700 dark:text-emerald-400 flex items-center gap-1.5">
            <TrendingUp className="h-3 w-3" />
            对比上次 +3 分
          </div>
        </Card>

        <Card className="p-4">
          <div className="text-2xs text-ink-3 mb-1.5">最弱维度</div>
          <div className="text-xl font-semibold text-ink-1">系统设计</div>
          <div className="text-2xs text-ink-3 mt-0.5">72 分 · 急需提升</div>
          <div className="mt-3 p-2 rounded-md bg-amber-50 dark:bg-amber-500/10 text-2xs text-amber-700 dark:text-amber-400 flex items-center gap-1.5">
            <AlertCircle className="h-3 w-3" />
            影响整体评分
          </div>
        </Card>
      </div>

      {/* 五维表现 */}
      <Card className="mb-6 p-5">
        <CardHeader
          title="五维能力表现"
          description="对比上次面试与目标岗位的期望"
        />
        <div className="grid grid-cols-1 md:grid-cols-5 gap-4">
          {record.dimensions.map((d) => {
            const target = d.name === '系统设计' ? 88 : d.name === '技术深度' ? 90 : 80
            return (
              <div key={d.name} className="text-center">
                <div className="relative inline-block mb-2">
                  <svg className="h-20 w-20 -rotate-90" viewBox="0 0 100 100">
                    <circle
                      cx="50"
                      cy="50"
                      r="40"
                      fill="none"
                      stroke="currentColor"
                      strokeOpacity="0.08"
                      strokeWidth="6"
                    />
                    <circle
                      cx="50"
                      cy="50"
                      r="40"
                      fill="none"
                      stroke="rgb(59, 130, 246)"
                      strokeWidth="6"
                      strokeDasharray={`${(d.score / 100) * 251} 251`}
                      strokeLinecap="round"
                    />
                  </svg>
                  <div className="absolute inset-0 flex items-center justify-center">
                    <span className="text-lg font-semibold text-ink-1 tabular-nums">{d.score}</span>
                  </div>
                </div>
                <div className="text-xs font-medium text-ink-1">{d.name}</div>
                <div className="text-2xs text-ink-3 mt-0.5">
                  目标 {target} ·{' '}
                  <span
                    className={cn(
                      'font-medium',
                      d.score >= target
                        ? 'text-emerald-600 dark:text-emerald-400'
                        : 'text-amber-600 dark:text-amber-400',
                    )}
                  >
                    {d.score >= target ? `+${d.score - target}` : d.score - target}
                  </span>
                </div>
              </div>
            )
          })}
        </div>
      </Card>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 mb-6">
        {/* 优势与短板 */}
        <Card>
          <CardHeader title="整体优势" description="值得在面试中重点展示" />
          <ul className="space-y-2">
            {[
              '工程项目经验扎实，能用数据说话',
              '前端基础概念清晰，能从原理层面回答',
              '沟通表达有条理，善于结构化输出',
            ].map((s, i) => (
              <li key={i} className="flex gap-2 text-sm text-ink-2 leading-relaxed">
                <CheckCircle2 className="h-4 w-4 text-emerald-500 flex-shrink-0 mt-0.5" />
                <span>{s}</span>
              </li>
            ))}
          </ul>
        </Card>

        <Card>
          <CardHeader title="关键短板" description="影响整体评分，需重点突破" />
          <ul className="space-y-2">
            {[
              '系统设计缺乏容量预估、限流降级等生产级考虑',
              '回答深度不均，简单问题讲太多，难题点到为止',
              '缺少对失败案例的反思与总结',
            ].map((s, i) => (
              <li key={i} className="flex gap-2 text-sm text-ink-2 leading-relaxed">
                <AlertCircle className="h-4 w-4 text-amber-500 flex-shrink-0 mt-0.5" />
                <span>{s}</span>
              </li>
            ))}
          </ul>
        </Card>

        <Card className="bg-gradient-to-br from-violet-50/40 to-surface dark:from-violet-500/5 dark:to-dark-surface border-violet-200/40 dark:border-violet-500/20">
          <CardHeader
            title={
              <div className="flex items-center gap-1.5">
                <Lightbulb className="h-3.5 w-3.5 text-violet-500" />
                提升建议
              </div>
            }
            description="基于本次表现生成"
          />
          <ul className="space-y-2">
            <li className="text-sm text-ink-2 leading-relaxed flex gap-2">
              <span className="text-violet-500 font-medium">1.</span>
              完成 3 道 L4 系统设计题（短链、Feed、IM）
            </li>
            <li className="text-sm text-ink-2 leading-relaxed flex gap-2">
              <span className="text-violet-500 font-medium">2.</span>
              准备 1 个失败案例的反思，体现成长性
            </li>
            <li className="text-sm text-ink-2 leading-relaxed flex gap-2">
              <span className="text-violet-500 font-medium">3.</span>
              模拟真实面试限时（每题 5 分钟内）
            </li>
          </ul>
          <Link to="/profile" className="mt-3 pt-3 border-t border-surface-border dark:border-dark-surface-border block text-xs text-center text-violet-600 dark:text-violet-300 hover:underline">
            查看能力画像 →
          </Link>
        </Card>
      </div>

      {/* 逐题复盘 */}
      <Card>
        <CardHeader
          title="逐题复盘"
          description="回顾每道题的回答与反馈"
          action={<BarChart3 className="h-3.5 w-3.5 text-ink-3" />}
        />
        <div className="divide-y divide-surface-border dark:divide-dark-surface-border">
          {questionDetails.map((q, i) => (
            <div key={q.id} className="py-4 first:pt-0 last:pb-0">
              <div className="flex items-start gap-3 mb-3">
                <div
                  className={cn(
                    'h-7 w-7 rounded-md flex items-center justify-center text-xs font-semibold flex-shrink-0',
                    q.score >= 85
                      ? 'bg-emerald-50 dark:bg-emerald-500/15 text-emerald-700 dark:text-emerald-400'
                      : q.score >= 75
                        ? 'bg-brand-50 dark:bg-brand-500/15 text-brand-700 dark:text-brand-300'
                        : 'bg-amber-50 dark:bg-amber-500/15 text-amber-700 dark:text-amber-400',
                  )}
                >
                  {i + 1}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1">
                    <span className="text-sm font-medium text-ink-1">{q.question}</span>
                  </div>
                  <div className="flex items-center gap-2 text-2xs text-ink-3">
                    <Badge variant="default" className="!h-4">
                      {q.dimension}
                    </Badge>
                    <span>得分</span>
                    <span
                      className={cn(
                        'font-semibold tabular-nums',
                        q.score >= 85
                          ? 'text-emerald-600 dark:text-emerald-400'
                          : q.score >= 75
                            ? 'text-brand-600 dark:text-brand-300'
                            : 'text-amber-600 dark:text-amber-400',
                      )}
                    >
                      {q.score}
                    </span>
                  </div>
                </div>
              </div>
              <div className="ml-10 space-y-2">
                <div className="p-3 rounded-md bg-surface-muted dark:bg-dark-surface-muted">
                  <div className="text-2xs text-ink-3 mb-1">你的回答</div>
                  <div className="text-sm text-ink-1 leading-relaxed">{q.answer}</div>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                  <div className="p-3 rounded-md bg-emerald-50/40 dark:bg-emerald-500/5 border border-emerald-200/30 dark:border-emerald-500/10">
                    <div className="flex items-center gap-1 text-2xs font-medium text-emerald-700 dark:text-emerald-400 mb-1.5">
                      <ThumbsUp className="h-3 w-3" />
                      亮点
                    </div>
                    <ul className="space-y-1">
                      {q.feedback.strengths.map((s, i) => (
                        <li key={i} className="text-xs text-ink-2 flex gap-1.5">
                          <span className="text-emerald-500">•</span>
                          <span>{s}</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                  <div className="p-3 rounded-md bg-amber-50/40 dark:bg-amber-500/5 border border-amber-200/30 dark:border-amber-500/10">
                    <div className="flex items-center gap-1 text-2xs font-medium text-amber-700 dark:text-amber-400 mb-1.5">
                      <AlertCircle className="h-3 w-3" />
                      可改进
                    </div>
                    <ul className="space-y-1">
                      {q.feedback.improvements.map((s, i) => (
                        <li key={i} className="text-xs text-ink-2 flex gap-1.5">
                          <span className="text-amber-500">•</span>
                          <span>{s}</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>
      </Card>
    </div>
  )
}
