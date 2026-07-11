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
import { useNavigate, useSearchParams } from 'react-router-dom'
import { useQueryClient } from '@tanstack/react-query'
import {
  Eye,
  EyeOff,
  Loader2,
  Sparkles,
  Copy,
  MoreHorizontal,
  Pencil,
  Trash2,
} from 'lucide-react'
import { Card } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { Badge } from '@/components/ui/Badge'
import { Modal } from '@/components/ui/Modal'
import { Input } from '@/components/ui/Input'
import { timeAgo } from '@/lib/utils'
import {
  duplicateResume,
  deleteResume,
  updateResume,
  type ResumeV2ListItem,
} from '@/modules/resume/v2/api'
import { useResumeV2List } from '@/hooks/queries/useResumeV2List'
import { TemplateGalleryModal } from '@/modules/resume/v2/components/TemplateGalleryModal'
import { DeriveWizard, RootResumeCard, DerivedResumeList } from '@/modules/resume/derive'
import { DEFAULT_V3_THEME_ID, listV3Themes } from '@/modules/resume/themes'
import type { MujiThemeId } from '@/modules/resume/renderer/types'

const RECOMMENDED = listV3Themes()

export default function ResumeList() {
  const navigate = useNavigate()
  const qc = useQueryClient()
  const [searchParams, setSearchParams] = useSearchParams()
  const initialJobId = searchParams.get('job_id') || searchParams.get('source_job_id') || undefined
  const deriveRequested = searchParams.get('derive') === 'true' || Boolean(searchParams.get('source_job_id'))
  const autoOpen = searchParams.get('new') === 'true' && !deriveRequested

  // v2 list query — sole data source for this page.
  const { data: v2Resumes = [], isLoading } = useResumeV2List()

  // Gallery modal state.
  const [galleryOpen, setGalleryOpen] = useState(autoOpen)
  const [galleryTheme, setGalleryTheme] = useState<MujiThemeId>(DEFAULT_V3_THEME_ID)
  const [deriveOpen, setDeriveOpen] = useState(deriveRequested)
  const [createError, setCreateError] = useState<string | null>(null)
  const [menuError, setMenuError] = useState<string | null>(null)
  const [renameTarget, setRenameTarget] = useState<ResumeV2ListItem | null>(null)
  const [renameName, setRenameName] = useState('')
  const [deleteTarget, setDeleteTarget] = useState<ResumeV2ListItem | null>(null)
  const [renaming, setRenaming] = useState(false)

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

  useEffect(() => {
    if (deriveRequested) setDeriveOpen(true)
  }, [deriveRequested])

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
      setDeleteTarget(null)
      setMenuError(null)
    } catch (err) {
      setMenuError(err instanceof Error ? err.message : '删除简历失败，请重试')
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
      setMenuError(err instanceof Error ? err.message : '复制简历失败，请重试')
    } finally {
      setDuplicatingId(null)
    }
  }

  function openGallery(themeId: MujiThemeId = DEFAULT_V3_THEME_ID) {
    setGalleryTheme(themeId)
    setGalleryOpen(true)
  }

  function openDerive() {
    const next = new URLSearchParams(searchParams)
    next.set('derive', 'true')
    setSearchParams(next, { replace: true })
    setDeriveOpen(true)
  }

  function closeDerive() {
    setDeriveOpen(false)
    const next = new URLSearchParams(searchParams)
    next.delete('derive')
    next.delete('job_id')
    next.delete('source_job_id')
    if (deriveRequested) next.delete('new')
    setSearchParams(next, { replace: true })
  }

  function openRename(resume: ResumeV2ListItem) {
    setRenameTarget(resume)
    setRenameName(resume.name)
    setMenuError(null)
  }

  async function handleRename() {
    if (!renameTarget || !renameName.trim() || renaming) return
    setRenaming(true)
    try {
      await updateResume(renameTarget.id, { name: renameName.trim() }, renameTarget.version)
      await qc.invalidateQueries({ queryKey: ['resumes', 'v2', 'list'] })
      setRenameTarget(null)
      setMenuError(null)
    } catch (error) {
      setMenuError(error instanceof Error ? error.message : '重命名失败，请重试')
    } finally {
      setRenaming(false)
    }
  }

  return (
    <div className="px-4 py-5 sm:px-6 lg:px-8 lg:py-6 max-w-7xl mx-auto" data-testid="resume-list-page">
      <div className="flex flex-col items-stretch gap-4 mb-6 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-ink-1 tracking-tight">简历中心</h1>
          <p className="text-sm text-ink-3 mt-1">
            根简历沉淀素材 · 一键派生岗位定向简历 · 严格页数导出
          </p>
        </div>
        <div className="grid grid-cols-2 gap-2 sm:flex sm:items-center">
          <Button
            variant="secondary"
            onClick={openDerive}
            data-testid="one-click-derive-button"
          >
            一键派生
          </Button>
          <Button
            variant="primary"
            leftIcon={<Sparkles className="h-3.5 w-3.5" />}
            onClick={() => openGallery()}
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
                onClick={() => openGallery()}
                data-testid="empty-state-cta"
              >
                创建你的第一份简历
              </Button>
            </div>
          </div>

          {/* Recommended templates quick-pick */}
          <div className="mt-4 pt-4 border-t border-surface-border dark:border-dark-surface-border">
            <div className="text-2xs text-ink-3 mb-3">或选择一个编辑器主题开始</div>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
              {RECOMMENDED.map((t) => (
                <button
                  key={t.id}
                  type="button"
                  data-testid={`recommended-theme-${t.id}`}
                  onClick={() => openGallery(t.id as MujiThemeId)}
                  className="group rounded-md border border-surface-border dark:border-dark-surface-border p-2 hover:border-brand-500 dark:hover:border-brand-400 transition-colors"
                >
                  <div
                    className="h-20 rounded flex items-center justify-center text-white text-xs font-medium"
                    style={{ background: t.defaultColor }}
                  >
                    {t.name}
                  </div>
                  <div className="text-2xs text-ink-2 mt-1.5 group-hover:text-brand-600 transition-colors">
                    {t.name}
                  </div>
                </button>
              ))}
            </div>
          </div>
        </Card>
      ) : standardResumes.length > 0 ? (
        <section className="mb-6" data-testid="independent-resume-section">
          <div className="mb-3">
            <h2 className="text-lg font-semibold text-ink-1">独立简历</h2>
            <p className="mt-0.5 text-xs text-ink-3">不绑定具体岗位，可作为独立版本长期维护</p>
          </div>
          <div className="grid grid-cols-1 gap-3 md:grid-cols-2 lg:grid-cols-3" data-testid="resume-list-grid">
          {standardResumes.map((r) => (
            <IndependentResumeCard
              key={r.id}
              resume={r}
              duplicating={duplicatingId === r.id}
              onOpen={() => navigate(`/resume/${r.id}`)}
              onRename={() => openRename(r)}
              onDuplicate={() => void handleDuplicate(r.id)}
              onDelete={() => setDeleteTarget(r)}
            />
          ))}
          </div>
        </section>
      ) : null}

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
            onDelete={(rid) => {
              const target = derivedResumes.find((resume) => resume.id === rid)
              if (target) setDeleteTarget(target)
            }}
            duplicatingId={duplicatingId}
            deletingId={deletingId}
          />
        </section>
      )}

      <TemplateGalleryModal
        open={galleryOpen}
        initialThemeId={galleryTheme}
        onClose={closeGallery}
        onCreated={(input) => {
          void handleCreated(input)
        }}
      />
      <DeriveWizard open={deriveOpen} onClose={closeDerive} initialJobId={initialJobId} />
      {(createError || menuError) && (
        <p className="mt-2 text-xs text-red-500" data-testid="v2-create-error">
          {createError || menuError}
        </p>
      )}

      <Modal
        open={Boolean(renameTarget)}
        onClose={() => !renaming && setRenameTarget(null)}
        title="重命名简历"
        footer={
          <>
            <Button variant="ghost" onClick={() => setRenameTarget(null)} disabled={renaming}>取消</Button>
            <Button variant="primary" onClick={() => void handleRename()} loading={renaming} disabled={!renameName.trim()}>保存</Button>
          </>
        }
      >
        <label className="block text-xs font-medium text-ink-2 mb-1" htmlFor="resume-rename-input">简历名称</label>
        <Input id="resume-rename-input" value={renameName} onChange={(event) => setRenameName(event.target.value)} maxLength={64} autoFocus />
      </Modal>

      <Modal
        open={Boolean(deleteTarget)}
        onClose={() => !deletingId && setDeleteTarget(null)}
        title="删除简历"
        description={`确定删除“${deleteTarget?.name || ''}”吗？此操作无法撤销。`}
        footer={
          <>
            <Button variant="ghost" onClick={() => setDeleteTarget(null)} disabled={Boolean(deletingId)}>取消</Button>
            <Button variant="danger" onClick={() => deleteTarget && void handleDelete(deleteTarget.id)} loading={Boolean(deletingId)}>确认删除</Button>
          </>
        }
      >
        <p className="text-sm text-ink-2">简历内容及相关分享链接将一并失效。</p>
      </Modal>
    </div>
  )
}

function IndependentResumeCard({
  resume,
  duplicating,
  onOpen,
  onRename,
  onDuplicate,
  onDelete,
}: {
  resume: ResumeV2ListItem
  duplicating: boolean
  onOpen: () => void
  onRename: () => void
  onDuplicate: () => void
  onDelete: () => void
}) {
  const [menuOpen, setMenuOpen] = useState(false)
  const stop = (event: React.MouseEvent) => event.stopPropagation()
  return (
    <div
      role="link"
      tabIndex={0}
      onClick={onOpen}
      onKeyDown={(event) => {
        if (event.key === 'Enter' || event.key === ' ') {
          event.preventDefault()
          onOpen()
        }
      }}
      className="group cursor-pointer rounded-lg focus:outline-none focus:ring-2 focus:ring-brand-500/35"
      data-testid="v2-resume-card"
      data-resume-id={resume.id}
      aria-label={`打开${resume.name}`}
    >
      <Card hover padding="md" className="h-full">
        <div className="flex items-start gap-3 mb-3">
          <div className="h-8 w-8 rounded-md flex items-center justify-center flex-shrink-0 bg-brand-50 dark:bg-brand-500/15 text-brand-600">
            <Sparkles className="h-3.5 w-3.5" />
          </div>
          <div className="min-w-0 flex-1">
            <div className="text-sm font-semibold text-ink-1 truncate group-hover:text-brand-600 transition-colors">{resume.name}</div>
            <div className="text-2xs text-ink-3 mt-0.5 truncate">/{resume.slug}</div>
          </div>
          {resume.is_public ? (
            <Badge variant="success" className="text-2xs"><Eye className="h-2.5 w-2.5 mr-0.5" />公开</Badge>
          ) : (
            <Badge variant="default" className="text-2xs"><EyeOff className="h-2.5 w-2.5 mr-0.5" />私有</Badge>
          )}
          <div className="relative" onClick={stop}>
            <button
              type="button"
              onClick={() => setMenuOpen((open) => !open)}
              aria-label={`${resume.name}的更多操作`}
              aria-expanded={menuOpen}
              aria-haspopup="menu"
              className="flex h-8 w-8 items-center justify-center rounded-md text-ink-3 hover:bg-surface-muted hover:text-ink-1 dark:hover:bg-dark-surface-muted"
            >
              <MoreHorizontal className="h-4 w-4" />
            </button>
            {menuOpen && (
              <div role="menu" className="absolute right-0 top-9 z-20 w-32 rounded-md border border-surface-border bg-surface p-1 shadow-notion-md dark:border-dark-surface-border dark:bg-dark-surface">
                <CardMenuItem icon={<Pencil className="h-3.5 w-3.5" />} label="重命名" onClick={() => { setMenuOpen(false); onRename() }} />
                <CardMenuItem icon={duplicating ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Copy className="h-3.5 w-3.5" />} label="复制" disabled={duplicating} onClick={() => { setMenuOpen(false); onDuplicate() }} />
                <CardMenuItem icon={<Trash2 className="h-3.5 w-3.5" />} label="删除" danger onClick={() => { setMenuOpen(false); onDelete() }} />
              </div>
            )}
          </div>
        </div>
        <div className="flex items-center justify-between text-2xs text-ink-3 pt-3 border-t border-surface-border dark:border-dark-surface-border">
          <span>v{resume.version}</span>
          <span>{resume.updated_at ? timeAgo(resume.updated_at) : '刚刚创建'}</span>
        </div>
      </Card>
    </div>
  )
}

function CardMenuItem({ icon, label, onClick, danger, disabled }: { icon: React.ReactNode; label: string; onClick: () => void; danger?: boolean; disabled?: boolean }) {
  return (
    <button
      type="button"
      role="menuitem"
      onClick={onClick}
      disabled={disabled}
      className={`flex min-h-9 w-full items-center gap-2 rounded px-2 text-left text-xs disabled:opacity-50 ${danger ? 'text-red-600 hover:bg-red-50 dark:hover:bg-red-500/10' : 'text-ink-2 hover:bg-surface-muted dark:hover:bg-dark-surface-muted'}`}
    >
      {icon}{label}
    </button>
  )
}
