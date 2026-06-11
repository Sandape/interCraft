import { Search, BookOpen, MessageCircle, Mail, ChevronRight, Sparkles } from 'lucide-react'
import { Card } from '@/components/ui/Card'

const faqs = [
  { q: '如何开始第一次模拟面试？', a: '进入「模拟面试」页面，点击「开始新面试」即可。' },
  { q: 'AI 简历优化是如何工作的？', a: '粘贴招聘 JD 后，AI 会分析关键能力词，与你的核心简历匹配，生成针对性优化建议。' },
  { q: '如何切换深色 / 浅色模式？', a: '点击右上角的太阳/月亮图标即可切换。' },
  { q: '数据是否安全？', a: '所有数据传输使用 TLS 加密，存储使用 AES-256，已通过 ISO 27001 认证。' },
]

export default function Help() {
  return (
    <div className="px-8 py-6 max-w-3xl mx-auto">
      <div className="text-center mb-8">
        <div className="inline-flex h-12 w-12 items-center justify-center rounded-lg bg-gradient-to-br from-brand-500 to-brand-700 mb-3 shadow-notion">
          <Sparkles className="h-5 w-5 text-white" strokeWidth={2.5} />
        </div>
        <h1 className="text-2xl font-semibold text-ink-1 tracking-tight">需要帮助？</h1>
        <p className="text-sm text-ink-3 mt-1">搜索常见问题或联系我们的支持团队</p>
        <div className="relative max-w-md mx-auto mt-4">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-ink-muted" />
          <input
            placeholder="搜索问题…"
            className="w-full h-10 pl-10 pr-4 text-sm rounded-md bg-surface-muted dark:bg-dark-surface-muted text-ink-1 placeholder:text-ink-muted border-0 focus:outline-none focus:ring-2 focus:ring-brand-500/30"
          />
        </div>
      </div>

      <div className="grid grid-cols-3 gap-2 mb-6">
        <Card hover className="text-center p-4">
          <BookOpen className="h-5 w-5 text-brand-500 mx-auto mb-2" />
          <div className="text-sm font-medium text-ink-1">使用文档</div>
          <div className="text-2xs text-ink-3 mt-0.5">详尽的功能说明</div>
        </Card>
        <Card hover className="text-center p-4">
          <MessageCircle className="h-5 w-5 text-emerald-500 mx-auto mb-2" />
          <div className="text-sm font-medium text-ink-1">在线客服</div>
          <div className="text-2xs text-ink-3 mt-0.5">工作日 9:00-21:00</div>
        </Card>
        <Card hover className="text-center p-4">
          <Mail className="h-5 w-5 text-violet-500 mx-auto mb-2" />
          <div className="text-sm font-medium text-ink-1">邮件支持</div>
          <div className="text-2xs text-ink-3 mt-0.5">support@intercraft.io</div>
        </Card>
      </div>

      <h2 className="text-sm font-semibold text-ink-1 mb-2">常见问题</h2>
      <div className="space-y-1.5">
        {faqs.map((f) => (
          <Card key={f.q} hover padding="sm" className="flex items-center justify-between">
            <div>
              <div className="text-sm font-medium text-ink-1">{f.q}</div>
              <div className="text-2xs text-ink-3 mt-0.5">{f.a}</div>
            </div>
            <ChevronRight className="h-3.5 w-3.5 text-ink-muted" />
          </Card>
        ))}
      </div>
    </div>
  )
}
