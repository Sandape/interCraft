import { useEffect, useState } from 'react'
import { Check, Loader2 } from 'lucide-react'
import { Modal } from '@/components/ui/Modal'
import { Button } from '@/components/ui/Button'
import { createResume, type ResumeV2Create } from '@/modules/resume/v2/api'
import { fireToast } from '@/modules/resume/v2/editor/center/toast'
import { DEFAULT_V3_THEME_ID, listV3Themes } from '@/modules/resume/themes'
import type { MujiThemeId } from '@/modules/resume/renderer/types'

export interface TemplateGalleryModalProps {
  open: boolean
  initialThemeId?: MujiThemeId
  onClose: () => void
  onCreated: (input: { id: string; name: string; slug: string }) => void
}

const THEME_DESCRIPTIONS: Record<MujiThemeId, string> = {
  'muji-default-autumn': '深色标题栏与居中章节标题，层级清晰稳重',
  'muji-minimal-color': '轻量分隔线与克制强调色，适合信息密集内容',
  'muji-flat-atmospheric': '强调色标题带与大气章节结构，视觉识别更强',
}

function slugify(name: string): string {
  const ascii = name
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .slice(0, 64)
  return ascii || `resume-${Date.now()}`
}

export function TemplateGalleryModal({ open, initialThemeId, onClose, onCreated }: TemplateGalleryModalProps) {
  const themes = listV3Themes()
  const [selected, setSelected] = useState<MujiThemeId>(DEFAULT_V3_THEME_ID)
  const [name, setName] = useState('')
  const [submitting, setSubmitting] = useState(false)

  useEffect(() => {
    if (!open) return
    setSelected(initialThemeId ?? DEFAULT_V3_THEME_ID)
    setName('')
    setSubmitting(false)
  }, [initialThemeId, open])

  async function handleConfirm() {
    if (submitting) return
    const finalName = name.trim() || '未命名简历'
    const payload: ResumeV2Create = {
      name: finalName,
      slug: slugify(finalName),
      template: 'onyx',
      theme_id: selected,
      from_sample: false,
    }
    setSubmitting(true)
    try {
      const resume = await createResume(payload)
      onCreated({ id: resume.id, name: resume.name, slug: resume.slug })
    } catch (error) {
      const message = error instanceof Error ? error.message : '创建简历失败'
      fireToast(`创建简历失败: ${message}`, 'error')
      setSubmitting(false)
    }
  }

  return (
    <Modal
      open={open}
      onClose={() => !submitting && onClose()}
      title="选择主题创建简历"
      description="与编辑器中的三个主题保持一致，创建后仍可随时切换。"
      size="lg"
      footer={
        <>
          <Button variant="ghost" onClick={onClose} disabled={submitting} data-testid="template-gallery-cancel">
            取消
          </Button>
          <Button
            variant="primary"
            onClick={() => void handleConfirm()}
            disabled={submitting}
            leftIcon={submitting ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : undefined}
            data-testid="template-gallery-confirm"
          >
            {submitting ? '创建中…' : '使用此主题创建'}
          </Button>
        </>
      }
    >
      <div className="space-y-5">
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-3" data-testid="template-gallery-grid">
          {themes.map((theme) => {
            const themeId = theme.id as MujiThemeId
            const isSelected = selected === themeId
            return (
              <button
                key={theme.id}
                type="button"
                data-testid={`resume-theme-${theme.id}`}
                aria-pressed={isSelected}
                onClick={() => setSelected(themeId)}
                className={`group rounded-lg border p-3 text-left transition-colors focus:outline-none focus:ring-2 focus:ring-brand-500/35 ${
                  isSelected
                    ? 'border-brand-500 bg-brand-50/60 dark:bg-brand-500/10'
                    : 'border-surface-border hover:border-brand-300 dark:border-dark-surface-border'
                }`}
              >
                <ThemePreview pattern={theme.renderPattern} color={theme.defaultColor} />
                <div className="mt-3 flex items-start justify-between gap-2">
                  <div>
                    <div className="text-sm font-medium text-ink-1">{theme.name}</div>
                    <p className="mt-1 text-xs leading-5 text-ink-3">{THEME_DESCRIPTIONS[themeId]}</p>
                  </div>
                  {isSelected && (
                    <span className="mt-0.5 flex h-5 w-5 flex-none items-center justify-center rounded-full bg-brand-600 text-white" aria-label="已选择">
                      <Check className="h-3 w-3" />
                    </span>
                  )}
                </div>
              </button>
            )
          })}
        </div>

        <div className="space-y-1.5">
          <label htmlFor="template-gallery-name" className="text-xs font-medium text-ink-2">
            简历名称
          </label>
          <input
            id="template-gallery-name"
            type="text"
            value={name}
            onChange={(event) => setName(event.target.value)}
            placeholder="未命名简历"
            maxLength={64}
            data-testid="template-gallery-name"
            className="h-10 w-full rounded-md border border-surface-border bg-surface-muted px-3 text-sm text-ink-1 placeholder:text-ink-muted focus:outline-none focus:ring-2 focus:ring-brand-500/30 dark:border-dark-surface-border dark:bg-dark-surface-muted"
          />
        </div>
      </div>
    </Modal>
  )
}

function ThemePreview({
  pattern,
  color,
}: {
  pattern?: 'dark-header-centered-section' | 'minimal-line' | 'accent-band'
  color: string
}) {
  return (
    <div className="aspect-[4/3] overflow-hidden rounded-md border border-black/5 bg-white p-3 shadow-sm" aria-hidden="true">
      <div
        className={`h-5 rounded-sm ${pattern === 'minimal-line' ? 'bg-transparent' : ''}`}
        style={pattern === 'minimal-line' ? undefined : { backgroundColor: color }}
      >
        {pattern === 'minimal-line' && <div className="h-1 w-1/2 rounded-full" style={{ backgroundColor: color }} />}
      </div>
      <div className="mt-3 space-y-2">
        <div className="h-1.5 w-2/3 rounded-full bg-slate-800" />
        <div className="h-1 w-full rounded-full bg-slate-200" />
        <div className="h-1 w-5/6 rounded-full bg-slate-200" />
        <div
          className={`mt-2 h-2 w-1/2 ${pattern === 'accent-band' ? 'rounded-sm' : 'border-b'}`}
          style={pattern === 'accent-band' ? { backgroundColor: color } : { borderColor: color }}
        />
        <div className="h-1 w-full rounded-full bg-slate-200" />
      </div>
    </div>
  )
}
