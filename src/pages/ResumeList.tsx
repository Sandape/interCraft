/**
 * ResumeList — single entry point for v2 resumes (036 Phase A.2).
 *
 * The page is the sole resume surface:
 *   - The Topbar's "+ 新建简历" button navigates to /resume?new=true
 *     which auto-opens the Template Gallery modal.
 *   - The user picks a template (or the blank option); on confirm we
 *     call `createResume({ name, slug, template })` and navigate into
 *     `/resume/{newId}` (the v2 structured editor at ResumeEditorV2).
 *   - 3 recommended templates are shown as quick-pick thumbnails on the
 *     empty state (036 US5 T041).
 *
 * v1 resume_branches tables were retired; no v1 fallback is rendered.
 */
import { useEffect, useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { useQueryClient } from '@tanstack/react-query'
import {
  Eye,
  EyeOff,
  Loader2,
  Pencil,
  Sparkles,
  Copy,
} from 'lucide-react'
import { Card } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { Badge } from '@/components/ui/Badge'
import { timeAgo } from '@/lib/utils'
import {
  duplicateResume,
  deleteResume,
  type ResumeV2ListItem,
} from '@/modules/resume/v2/api'
import { useResumeV2List } from '@/hooks/queries/useResumeV2List'
import { TemplateGalleryModal } from '@/modules/resume/v2/components/TemplateGalleryModal'
import { DeriveWizard, RootResumeCard, DerivedResumeList } from '@/modules/resume/derive'

interface RecommendedTemplate {
  id: 'pikachu' | 'onyx' | 'bronzor'
  label: string
  accent: string
}

const RECOMMENDED: RecommendedTemplate[] = [
  { id: 'pikachu', label: 'Pikachu', accent: '#ffc837' },
  { id: 'onyx', label: 'Onyx', accent: '#0084d1' },
  { id: 'bronzor', label: 'Bronzor', accent: '#78350f' },
]

export default function ResumeList() {
  const navigate = useNavigate()
  const qc = useQueryClient()
  const [searchParams, setSearchParams] = useSearchParams()
  const autoOpen = searchParams.get('new') === 'true'

  // v2 list query — sole data source for this page.
  const { data: v2Resumes = [], isLoading } = useResumeV2List()

  // Gallery modal state.
  const [galleryOpen, setGalleryOpen] = useState(autoOpen)
  const [deriveOpen, setDeriveOpen] = useState(false)
  const [createError, setCreateError] = useState<string | null>(null)

  // Duplicate state.
  const [duplicatingId, setDuplicatingId] = useState<string | null>(null)
  const [deletingId, setDeletingId] = useState<string | null>(null)

  const standardResumes = v2Resumes.filter(
    (r) => (r.resume_kind || 'standard') === 'standard',
  )
  const derivedResumes = v2Resumes.filter(
    (r) => (r.resume_kind || 'standard') === 'derived',
  )

  // Auto-open when Topbar routes here with ?new=true (036 US4 T056).
  useEffect(() => {
    if (autoOpen) setGalleryOpen(true)
  }, [autoOpen])

  function closeGallery() {
    setGalleryOpen(false)
    setCreateError(null)
    const next = new URLSearchParams(searchParams)
    next.delete('new')
    setSearchParams(next, { replace: true })
  }

  function handleCreated(input: { id: string; name: string; slug: string }) {
    // TemplateGalleryModal already POSTed /api/v1/v2/resumes; here we just
    // invalidate the list cache and navigate to the new editor.
    setCreateError(null)
    void qc.invalidateQueries({ queryKey: ['resumes', 'v2', 'list'] })
    closeGallery()
    navigate(`/resume/${input.id}`)
  }

  async function handleDelete(id: string) {
    if (deletingId) return
    setDeletingId(id)
    try {
      await deleteResume(id)
      await qc.invalidateQueries({ queryKey: ['resumes', 'v2', 'list'] })
    } catch (err) {
      // eslint-disable-next-line no-console
      console.error('Delete failed:', err)
    } finally {
      setDeletingId(null)
    }
  }

  async function handleDuplicate(id: string) {
    if (duplicatingId) return
    setDuplicatingId(id)
    try {
      const copy = await duplicateResume(id)
      await qc.invalidateQueries({ queryKey: ['resumes', 'v2', 'list'] })
      navigate(`/resume/${copy.id}`)
    } catch (err) {
      // eslint-disable-next-line no-console
      console.error('Duplicate failed:', err)
    } finally {
      setDuplicatingId(null)
    }
  }

  return (
    <div className="px-8 py-6 max-w-7xl mx-auto" data-testid="resume-list-page">
      <div className="flex items-start justify-between gap-4 mb-6">
        <div>
          <h1 className="text-2xl font-semibold text-ink-1 tracking-tight">简历中心</h1>
          <p className="text-sm text-ink-3 mt-1">
            根简历沉淀素材 · 一键派生岗位定向简历 · 严格页数导出
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="secondary"
            onClick={() => setDeriveOpen(true)}
            data-testid="one-click-derive-button"
          >
            一键派生
          </Button>
          <Button
            variant="primary"
            leftIcon={<Sparkles className="h-3.5 w-3.5" />}
            onClick={() => setGalleryOpen(true)}
            data-testid="new-resume-button"
          >
            新建简历
          </Button>
        </div>
      </div>

      <div className="mb-6">
        <RootResumeCard
          standardResumes={standardResumes.map((r) => ({ id: r.id, name: r.name }))}
        />
      </div>

      {derivedResumes.length > 0 && (
        <section className="mb-6" data-testid="derived-resume-section">
          <h2 className="text-lg font-semibold text-ink-1 mb-3">派生简历</h2>
          <DerivedResumeList
            items={derivedResumes.map((r) => ({
              id: r.id,
              name: r.name,
              job_id: r.job_id,
              target_page_count: r.target_page_count,
              actual_page_count: r.actual_page_count,
              updated_at: r.updated_at,
            }))}
            onOpen={(rid) => navigate(`/resume/${rid}`)}
            onDuplicate={(rid) => void handleDuplicate(rid)}
            onDelete={(rid) => void handleDelete(rid)}
            duplicatingId={duplicatingId}
            deletingId={deletingId}
          />
        </section>
      )}

      {isLoading ? (
        <div
          className="flex items-center gap-2 text-sm text-ink-3"
          data-testid="resume-list-loading"
        >
          <Loader2 className="h-4 w-4 animate-spin" /> 加载中…
        </div>
      ) : v2Resumes.length === 0 ? (
        <Card padding="lg" data-testid="resume-list-empty">
          <div className="text-center mb-5">
            <Sparkles className="h-8 w-8 text-ink-muted mx-auto" />
            <p className="mt-3 text-sm text-ink-2">还没有简历</p>
            <p className="text-2xs text-ink-3 mt-1">从模板开始，几分钟即可生成专业简历</p>
            <div className="mt-4 flex justify-center">
              <Button
                variant="primary"
                leftIcon={<Sparkles className="h-3.5 w-3.5" />}
                onClick={() => setGalleryOpen(true)}
                data-testid="empty-state-cta"
              >
                创建你的第一份简历
              </Button>
            </div>
          </div>

          {/* Recommended templates quick-pick */}
          <div className="mt-4 pt-4 border-t border-surface-border dark:border-dark-surface-border">
            <div className="text-2xs text-ink-3 mb-3">或挑一个推荐模板开始</div>
            <div className="grid grid-cols-3 gap-3">
              {RECOMMENDED.map((t) => (
                <button
                  key={t.id}
                  type="button"
                  data-testid={`recommended-template-${t.id}`}
                  onClick={() => {
                    setGalleryOpen(true)
                  }}
                  className="group rounded-md border border-surface-border dark:border-dark-surface-border p-2 hover:border-brand-500 dark:hover:border-brand-400 transition-colors"
                >
                  <div
                    className="h-20 rounded flex items-center justify-center text-white text-xs font-medium"
                    style={{ background: t.accent }}
                  >
                    {t.label}
                  </div>
                  <div className="text-2xs text-ink-2 mt-1.5 group-hover:text-brand-600 transition-colors">
                    {t.label}
                  </div>
                </button>
              ))}
            </div>
          </div>
        </Card>
      ) : standardResumes.length > 0 ? (
        <div
          className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3"
          data-testid="resume-list-grid"
        >
          {standardResumes.map((r) => (
            <Link
              key={r.id}
              to={`/resume/${r.id}`}
              className="group"
              data-testid="v2-resume-card"
              data-resume-id={r.id}
            >
              <Card hover padding="md" className="h-full">
                <div className="flex items-start gap-3 mb-3">
                  <div className="h-8 w-8 rounded-md flex items-center justify-center flex-shrink-0 bg-brand-50 dark:bg-brand-500/15 text-brand-600">
                    <Sparkles className="h-3.5 w-3.5" />
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="text-sm font-semibold text-ink-1 truncate group-hover:text-brand-600 transition-colors">
                      {r.name}
                    </div>
                    <div className="text-2xs text-ink-3 mt-0.5 truncate">/{r.slug}</div>
                  </div>
                  {r.is_public ? (
                    <Badge variant="success" className="text-2xs">
                      <Eye className="h-2.5 w-2.5 mr-0.5" />公开
                    </Badge>
                  ) : (
                    <Badge variant="default" className="text-2xs">
                      <EyeOff className="h-2.5 w-2.5 mr-0.5" />私有
                    </Badge>
                  )}
                </div>
                <div className="flex items-center justify-between text-2xs text-ink-3 pt-3 border-t border-surface-border dark:border-dark-surface-border">
                  <span>v{r.version}</span>
                  <span>{r.updated_at ? timeAgo(r.updated_at) : '刚刚创建'}</span>
                </div>
                <div className="flex items-center gap-1 mt-3" onClick={(e) => e.preventDefault()}>
                  <button
                    type="button"
                    onClick={(e) => {
                      e.preventDefault()
                      e.stopPropagation()
                      navigate(`/resume/${r.id}`)
                    }}
                    className="inline-flex items-center gap-1 px-2 h-6 rounded text-2xs bg-brand-50 dark:bg-brand-500/15 text-brand-700 dark:text-brand-300 hover:bg-brand-100 dark:hover:bg-brand-500/25"
                    data-testid="resume-card-open"
                  >
                    <Pencil className="h-2.5 w-2.5" /> 打开
                  </button>
                  <button
                    type="button"
                    onClick={(e) => {
                      e.preventDefault()
                      e.stopPropagation()
                      void handleDuplicate(r.id)
                    }}
                    disabled={duplicatingId === r.id}
                    className="inline-flex items-center gap-1 px-2 h-6 rounded text-2xs bg-surface-muted dark:bg-dark-surface-muted text-ink-2 dark:text-dark-ink-secondary hover:bg-surface dark:hover:bg-dark-surface disabled:opacity-50"
                    data-testid="resume-card-duplicate"
                  >
                    {duplicatingId === r.id ? (
                      <Loader2 className="h-2.5 w-2.5 animate-spin" />
                    ) : (
                      <Copy className="h-2.5 w-2.5" />
                    )}
                    复制
                  </button>
                </div>
              </Card>
            </Link>
          ))}
        </div>
      ) : null}

      <TemplateGalleryModal
        open={galleryOpen}
        onClose={closeGallery}
        onCreated={(input) => {
          void handleCreated(input)
        }}
      />
      <DeriveWizard open={deriveOpen} onClose={() => setDeriveOpen(false)} />
      {createError && (
        <p className="mt-2 text-xs text-red-500" data-testid="v2-create-error">
          {createError}
        </p>
      )}
    </div>
  )
}
