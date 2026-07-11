import { useState, useEffect } from 'react'
import { Search, BookOpen, MessageCircle, Mail, ChevronDown, Sparkles, ExternalLink } from 'lucide-react'
import { Card } from '@/components/ui/Card'
import { contentApi, type FaqCategory, type FaqItem, type SearchResult } from '@/api/content'

export default function Help() {
  const [categories, setCategories] = useState<FaqCategory[]>([])
  const [loading, setLoading] = useState(true)
  const [searchQuery, setSearchQuery] = useState('')
  const [searchResults, setSearchResults] = useState<{ faq: SearchResult[]; resources: SearchResult[] } | null>(null)
  const [searching, setSearching] = useState(false)
  const [expandedFaq, setExpandedFaq] = useState<string | null>(null)
  const [faqAnswers, setFaqAnswers] = useState<Record<string, string>>({})

  useEffect(() => {
    contentApi.listFaq().then((res) => {
      setCategories(res.categories)
      setLoading(false)
    })
  }, [])

  const handleSearch = async (q: string) => {
    setSearchQuery(q)
    if (!q.trim()) {
      setSearchResults(null)
      return
    }
    setSearching(true)
    const res = await contentApi.search(q)
    setSearchResults(res)
    setSearching(false)
  }

  const handleToggleFaq = async (item: FaqItem) => {
    if (expandedFaq === item.id) {
      setExpandedFaq(null)
      return
    }
    setExpandedFaq(item.id)
    if (!faqAnswers[item.id]) {
      const detail = await contentApi.getFaq(item.id)
      setFaqAnswers((prev) => ({ ...prev, [item.id]: detail.answer }))
    }
  }

  return (
    <div className="px-4 py-5 sm:px-6 lg:px-8 lg:py-6 max-w-3xl mx-auto">
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
            value={searchQuery}
            onChange={(e) => handleSearch(e.target.value)}
            className="w-full h-10 pl-10 pr-4 text-sm rounded-md bg-surface-muted dark:bg-dark-surface-muted text-ink-1 placeholder:text-ink-muted border-0 focus:outline-none focus:ring-2 focus:ring-brand-500/30"
          />
        </div>
      </div>

      {searchQuery.trim() && searchResults && (
        <div className="mb-8">
          <h2 className="text-sm font-semibold text-ink-1 mb-3">搜索结果</h2>
          {searchResults.faq.length === 0 && searchResults.resources.length === 0 && (
            <p className="text-sm text-ink-3 text-center py-4">未找到相关结果</p>
          )}
          {searchResults.faq.length > 0 && (
            <div className="mb-4">
              <p className="text-2xs text-ink-3 mb-2 font-medium">常见问题</p>
              {searchResults.faq.map((r) => (
                <Card key={r.id} hover padding="sm" className="flex items-center justify-between mb-1">
                  <span className="text-sm text-ink-1">{r.question}</span>
                  <ExternalLink className="h-3.5 w-3.5 text-ink-muted" />
                </Card>
              ))}
            </div>
          )}
          {searchResults.resources.length > 0 && (
            <div>
              <p className="text-2xs text-ink-3 mb-2 font-medium">学习资源</p>
              {searchResults.resources.map((r) => (
                <Card key={r.id} hover padding="sm" className="flex items-center justify-between mb-1">
                  <span className="text-sm text-ink-1">{r.title}</span>
                  <ExternalLink className="h-3.5 w-3.5 text-ink-muted" />
                </Card>
              ))}
            </div>
          )}
        </div>
      )}

      <div className="grid grid-cols-1 gap-2 mb-6 sm:grid-cols-3">
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
          <div className="mt-0.5 break-all text-2xs text-ink-3">support@intercraft.io</div>
        </Card>
      </div>

      <h2 className="text-sm font-semibold text-ink-1 mb-3">常见问题</h2>

      {loading ? (
        <p className="text-sm text-ink-3 text-center py-4">加载中...</p>
      ) : categories.length === 0 ? (
        <p className="text-sm text-ink-3 text-center py-4">暂无常见问题</p>
      ) : (
        categories.map((cat) => (
          <div key={cat.category} className="mb-6">
            <h3 className="text-xs font-semibold text-ink-3 uppercase tracking-wider mb-2">{cat.label}</h3>
            <div className="space-y-1">
              {cat.items.map((item) => (
                <div key={item.id}>
                  <Card
                    hover
                    padding="sm"
                    className="flex items-center justify-between cursor-pointer"
                    onClick={() => handleToggleFaq(item)}
                  >
                    <span className="text-sm text-ink-1">{item.question}</span>
                    <ChevronDown
                      className={`h-3.5 w-3.5 text-ink-muted transition-transform ${
                        expandedFaq === item.id ? 'rotate-180' : ''
                      }`}
                    />
                  </Card>
                  {expandedFaq === item.id && faqAnswers[item.id] && (
                    <div className="px-4 py-3 bg-surface-muted dark:bg-dark-surface-muted rounded-b-md text-sm text-ink-2 leading-relaxed">
                      {faqAnswers[item.id].split('\n').map((line, i) => (
                        <p key={i}>{line}</p>
                      ))}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        ))
      )}
    </div>
  )
}
