import { useState, useEffect } from 'react'
import { BookOpen, Sparkles, ArrowRight, Clock, ExternalLink, Filter, Search } from 'lucide-react'
import { Card, CardHeader } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { Badge } from '@/components/ui/Badge'
import { contentApi, type ResourceItem } from '@/api/content'

const CATEGORIES = [
  { value: '', label: '全部' },
  { value: 'interview_tips', label: '面试技巧' },
  { value: 'resume_guide', label: '简历指南' },
  { value: 'tech_prep', label: '技术准备' },
]

export default function Resources() {
  const [resources, setResources] = useState<ResourceItem[]>([])
  const [loading, setLoading] = useState(true)
  const [category, setCategory] = useState('')
  const [selectedResource, setSelectedResource] = useState<ResourceItem | null>(null)
  const [detail, setDetail] = useState<{ content: string; related_resources: { id: string; title: string }[] } | null>(null)

  useEffect(() => {
    setLoading(true)
    contentApi.listResources({ category: category || undefined }).then((res) => {
      setResources(res.items)
      setLoading(false)
    })
  }, [category])

  const handleViewDetail = async (r: ResourceItem) => {
    setSelectedResource(r)
    const detailData = await contentApi.getResource(r.id)
    setDetail(detailData)
  }

  if (selectedResource && detail) {
    return (
      <div className="px-8 py-6 max-w-4xl mx-auto">
        <Button variant="ghost"  className="mb-4" onClick={() => { setSelectedResource(null); setDetail(null) }}>
          ← 返回列表
        </Button>
        <h1 className="text-2xl font-semibold text-ink-1 tracking-tight mb-2">{selectedResource.title}</h1>
        <div className="flex items-center gap-2 mb-4">
          <Badge variant="brand" >{CATEGORIES.find(c => c.value === selectedResource.category)?.label || selectedResource.category}</Badge>
          {selectedResource.read_time_minutes && (
            <span className="text-2xs text-ink-3 flex items-center gap-1">
              <Clock className="h-3 w-3" /> {selectedResource.read_time_minutes} 分钟
            </span>
          )}
        </div>
        <Card className="p-6">
          <div className="prose prose-sm max-w-none dark:prose-invert">
            {detail.content.split('\n').map((line, i) => {
              if (line.startsWith('# ')) return <h1 key={i} className="text-xl font-semibold mt-4 mb-2">{line.slice(2)}</h1>
              if (line.startsWith('## ')) return <h2 key={i} className="text-lg font-semibold mt-3 mb-1">{line.slice(3)}</h2>
              if (line.startsWith('### ')) return <h3 key={i} className="text-base font-medium mt-2 mb-1">{line.slice(4)}</h3>
              if (line.startsWith('- ')) return <li key={i} className="text-sm text-ink-2 ml-4">{line.slice(2)}</li>
              if (line.trim() === '') return <br key={i} />
              return <p key={i} className="text-sm text-ink-2 leading-relaxed">{line}</p>
            })}
          </div>
        </Card>
        {detail.related_resources.length > 0 && (
          <div className="mt-4">
            <h3 className="text-sm font-semibold text-ink-1 mb-2">相关资源</h3>
            <div className="space-y-1">
              {detail.related_resources.map((r) => (
                <div key={r.id} className="text-sm text-brand-500 cursor-pointer hover:underline">{r.title}</div>
              ))}
            </div>
          </div>
        )}
      </div>
    )
  }

  return (
    <div className="px-8 py-6 max-w-7xl mx-auto">
      <div className="mb-6">
        <h1 className="text-2xl font-semibold text-ink-1 tracking-tight">学习资源</h1>
        <p className="text-sm text-ink-3 mt-1">提升面试技能的学习资料</p>
      </div>

      <div className="flex items-center gap-2 mb-4">
        {CATEGORIES.map((c) => (
          <button
            key={c.value}
            onClick={() => setCategory(c.value)}
            className={`px-3 py-1.5 text-xs rounded-md transition-colors ${
              category === c.value
                ? 'bg-brand-500 text-white'
                : 'bg-surface-muted dark:bg-dark-surface-muted text-ink-2 hover:text-ink-1'
            }`}
          >
            {c.label}
          </button>
        ))}
      </div>

      {loading ? (
        <div className="text-center py-12 text-sm text-ink-3">加载中...</div>
      ) : resources.length === 0 ? (
        <div className="text-center py-12 text-sm text-ink-3">暂无资源</div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
          {resources.map((r) => (
            <Card key={r.id} hover className="p-4 cursor-pointer" onClick={() => handleViewDetail(r)}>
              <div className="flex items-start gap-2 mb-2">
                <Badge variant="brand" >{CATEGORIES.find(c => c.value === r.category)?.label || r.category}</Badge>
                {r.read_time_minutes && (
                  <span className="text-2xs text-ink-3 flex items-center gap-1 ml-auto">
                    <Clock className="h-3 w-3" /> {r.read_time_minutes} 分钟
                  </span>
                )}
              </div>
              <h3 className="text-sm font-semibold text-ink-1 mb-1">{r.title}</h3>
              <p className="text-2xs text-ink-3 leading-relaxed">{r.summary}</p>
              <div className="flex items-center gap-1 mt-3 text-xs text-brand-500">
                查看详情 <ArrowRight className="h-3 w-3" />
              </div>
            </Card>
          ))}
        </div>
      )}
    </div>
  )
}
