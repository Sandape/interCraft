/**
 * Square — Resume template marketplace.
 *
 * Phase B B5: 1:1 搬运木及简历 Square 模板市场。
 * Adapted to eGGG's Tailwind + own UI components (Button/Card/Modal),
 * not MobX/AntD. Template JSON loaded from /data/template.json.
 *
 * "Use template" creates a new branch + writes parsed template blocks,
 * then navigates into the editor (mirrors ImportModal flow).
 */
import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Download, Eye, ArrowLeft, User, Loader2 } from 'lucide-react'
import { Card } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { Modal } from '@/components/ui/Modal'
import { useCreateBranch } from '@/hooks/mutations/useBranchMutations'
import { getResumeBlockRepository } from '@/repositories/types'
import { parseMarkdownImport } from '@/modules/resume/converter/markdown-parser'

interface TemplateItem {
  id: number
  title: string
  thumbnail: string
  template: string
  author: string
  avatar: string
  themeColor?: string
  theme: string
  collect: number
  updateTime: number
}

export default function Square() {
  const navigate = useNavigate()
  const createBranch = useCreateBranch()
  const [list, setList] = useState<TemplateItem[]>([])
  const [selected, setSelected] = useState<TemplateItem | null>(null)
  const [confirmOpen, setConfirmOpen] = useState(false)
  const [applying, setApplying] = useState(false)

  useEffect(() => {
    fetch('/data/template.json')
      .then((r) => r.json())
      .then((items: TemplateItem[]) => setList(items))
      .catch(() => setList([]))
  }, [])

  function downloadMd(t: TemplateItem) {
    const blob = new Blob([t.template], { type: 'text/markdown' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `${t.title}.md`
    a.click()
    URL.revokeObjectURL(url)
  }

  async function useTemplate(t: TemplateItem) {
    setApplying(true)
    try {
      const result = parseMarkdownImport(t.template, `${t.title}.md`)
      const branch = await createBranch.mutateAsync({
        name: t.title,
        company: null,
        position: null,
        parent_id: null,
      })
      // Write parsed blocks in sequence (backend assigns order_index)
      const blockRepo = getResumeBlockRepository()
      for (const b of result.blocks) {
        await blockRepo.create(branch.id, b)
      }
      navigate(`/resume/${branch.id}`)
    } catch (err) {
      console.error('useTemplate failed:', err)
      setApplying(false)
      setConfirmOpen(false)
    }
  }

  return (
    <div className="px-8 py-6 max-w-7xl mx-auto">
      <div className="flex items-center gap-3 mb-6">
        <Button
          variant="ghost"
          size="sm"
          leftIcon={<ArrowLeft className="h-3.5 w-3.5" />}
          onClick={() => navigate('/resume')}
        >
          返回简历中心
        </Button>
        <div>
          <h1 className="text-2xl font-semibold text-ink-1 tracking-tight">模板市场</h1>
          <p className="text-sm text-ink-3 mt-1">
            参考模板快速起手 — 选择「使用模板」会创建新分支并预填模板内容
          </p>
        </div>
      </div>

      {list.length === 0 ? (
        <Card padding="lg" className="text-center text-sm text-ink-3">
          正在加载模板…
        </Card>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {list.map((t) => (
            <Card
              key={t.id}
              hover
              padding="none"
              className="overflow-hidden group relative"
            >
              <div className="aspect-[3/4] bg-surface-muted dark:bg-dark-surface-muted overflow-hidden">
                <img
                  src={t.thumbnail}
                  alt={t.title}
                  loading="lazy"
                  className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300"
                />
                <div className="absolute inset-0 bg-gradient-to-t from-black/60 via-transparent to-transparent opacity-0 group-hover:opacity-100 transition-opacity flex items-end justify-center pb-4 gap-2">
                  <Button
                    size="sm"
                    variant="ghost"
                    leftIcon={<Eye className="h-3.5 w-3.5" />}
                    onClick={() => setSelected(t)}
                    className="bg-white/90 dark:bg-dark-surface/90"
                  >
                    预览
                  </Button>
                  <Button
                    size="sm"
                    variant="primary"
                    leftIcon={<Download className="h-3.5 w-3.5" />}
                    onClick={() => downloadMd(t)}
                  >
                    下载
                  </Button>
                </div>
              </div>
              <div className="p-3">
                <h3 className="text-sm font-semibold text-ink-1 truncate">{t.title}</h3>
                <div className="flex items-center gap-1.5 mt-1 text-2xs text-ink-3">
                  <User className="h-3 w-3" />
                  <span>{t.author}</span>
                  <span>·</span>
                  <span>主题 {t.theme}</span>
                  <span>·</span>
                  <span>收藏 {t.collect}+</span>
                </div>
                <Button
                  variant="secondary"
                  size="sm"
                  className="w-full mt-3"
                  onClick={() => {
                    setSelected(t)
                    setConfirmOpen(true)
                  }}
                >
                  使用此模板
                </Button>
              </div>
            </Card>
          ))}
        </div>
      )}

      {/* Preview modal */}
      {selected && !confirmOpen && (
        <Modal
          open={!!selected}
          onClose={() => setSelected(null)}
          title={selected.title}
          size="md"
          footer={
            <>
              <Button variant="ghost" onClick={() => setSelected(null)}>
                关闭
              </Button>
              <Button
                variant="ghost"
                leftIcon={<Download className="h-3.5 w-3.5" />}
                onClick={() => downloadMd(selected)}
              >
                下载 md
              </Button>
              <Button
                variant="primary"
                onClick={() => {
                  setConfirmOpen(true)
                }}
              >
                使用模板
              </Button>
            </>
          }
        >
          <div className="space-y-3">
            <img
              src={selected.thumbnail}
              alt={selected.title}
              className="w-full max-h-96 object-contain rounded-md border border-surface-border dark:border-dark-surface-border"
            />
            <div className="text-xs text-ink-3 space-y-1">
              <p>作者：{selected.author}</p>
              <p>主题：{selected.theme}</p>
              <p>收藏：{selected.collect}+</p>
            </div>
            <details className="text-xs">
              <summary className="cursor-pointer text-ink-2">查看 Markdown 内容</summary>
              <pre className="mt-2 p-3 bg-surface-muted dark:bg-dark-surface-muted rounded-md text-2xs text-ink-2 overflow-x-auto max-h-48 whitespace-pre-wrap">
                {selected.template}
              </pre>
            </details>
          </div>
        </Modal>
      )}

      {/* Use-confirm modal */}
      <Modal
        open={confirmOpen}
        onClose={() => !applying && setConfirmOpen(false)}
        title="使用此模板？"
        description="将基于此模板创建一个新简历分支，预填模板内容。"
        size="sm"
        footer={
          <>
            <Button variant="ghost" onClick={() => setConfirmOpen(false)} disabled={applying}>
              再想想
            </Button>
            <Button
              variant="primary"
              onClick={() => selected && useTemplate(selected)}
              disabled={applying || createBranch.isPending}
              leftIcon={applying ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : undefined}
            >
              {applying ? '创建中…' : '决定了'}
            </Button>
          </>
        }
      >
        <p className="text-sm text-ink-2">
          模板：<span className="font-medium">{selected?.title}</span>
        </p>
        <p className="text-2xs text-ink-3 mt-1">
          创建后将进入编辑器，可继续调整内容、主题、颜色。
        </p>
      </Modal>
    </div>
  )
}
