import { BookOpen, Sparkles, ArrowRight, Clock, Star, ExternalLink } from 'lucide-react'
import { Card, CardHeader } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { Badge } from '@/components/ui/Badge'

const resources = [
  { cat: '面试题库', items: ['React 18 原理 50 问', '系统设计 L4 题库', '前端工程化 100 题', '算法高频题 Top 100'] },
  { cat: '学习路径', items: ['高级前端进阶路径', '架构师成长地图', '面试突击 30 天'] },
  { cat: '经典书籍', items: ['《JavaScript 高级程序设计》', '《深入浅出 React 与 Redux》', '《数据密集型应用系统设计》', '《Designing Data-Intensive Applications》'] },
]

export default function Resources() {
  return (
    <div className="px-8 py-6 max-w-7xl mx-auto">
      <div className="mb-6">
        <h1 className="text-2xl font-semibold text-ink-1 tracking-tight">学习资源</h1>
        <p className="text-sm text-ink-3 mt-1">基于你的能力画像推荐</p>
      </div>

      <Card className="mb-6 p-5 bg-gradient-to-br from-violet-50/50 to-surface dark:from-violet-500/5 dark:to-dark-surface">
        <div className="flex items-start gap-3">
          <div className="h-9 w-9 rounded-md bg-gradient-to-br from-violet-500 to-violet-700 flex items-center justify-center flex-shrink-0">
            <Sparkles className="h-4 w-4 text-white" strokeWidth={2.5} />
          </div>
          <div>
            <h2 className="text-base font-semibold text-ink-1">AI 学习路径</h2>
            <p className="text-sm text-ink-2 mt-1 leading-relaxed">
              基于你的「系统设计 75 分」短板，AI 推荐了 4 周系统化提升路径
            </p>
            <Button size="sm" variant="primary" className="mt-3" rightIcon={<ArrowRight className="h-3 w-3" />}>
              查看完整路径
            </Button>
          </div>
        </div>
      </Card>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
        {resources.map((r) => (
          <Card key={r.cat}>
            <CardHeader title={r.cat} />
            <ul className="space-y-1.5">
              {r.items.map((it) => (
                <li
                  key={it}
                  className="flex items-center justify-between gap-2 p-2 -mx-2 rounded hover:bg-surface-muted/60 dark:hover:bg-dark-surface-muted/40 transition-colors cursor-pointer group"
                >
                  <div className="flex items-center gap-2 min-w-0">
                    <BookOpen className="h-3.5 w-3.5 text-ink-3 flex-shrink-0" />
                    <span className="text-sm text-ink-1 truncate">{it}</span>
                  </div>
                  <ExternalLink className="h-3 w-3 text-ink-muted opacity-0 group-hover:opacity-100 transition-opacity" />
                </li>
              ))}
            </ul>
          </Card>
        ))}
      </div>
    </div>
  )
}
