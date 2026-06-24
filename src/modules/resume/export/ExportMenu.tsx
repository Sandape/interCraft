import { useState } from 'react'
import { Download, FileText, FileImage, Loader2, Check, X } from 'lucide-react'
import { cn } from '@/lib/utils'
import { downloadMarkdown, downloadBlob } from '@/modules/resume/converter/markdown-export'
import { exportResume, type ExportFormat } from '@/api/export'
import { blocksToMarkdown } from '@/modules/resume/converter/markdown-converter'
import { renderMarkdown } from '@/modules/resume/renderer'
import { fetchBranchAvatarBlob } from '@/modules/resume/api/avatar'
import type { AvatarPosition, AvatarShape, ResumeBlock, ResumeBranch } from '@/modules/resume/api/types'

interface ExportMenuProps {
  branch: ResumeBranch
  blocks: ResumeBlock[]
  styleId: string
  markdown?: string
  open: boolean
  onClose: () => void
  className?: string
}

const FORMATS: { format: ExportFormat; label: string; icon: React.ReactNode; desc: string }[] = [
  { format: 'pdf', label: 'PDF 文件', icon: <FileText className="h-3.5 w-3.5" />, desc: 'A4 排版，投递标准格式' },
  { format: 'png', label: '图片 (PNG)', icon: <FileImage className="h-3.5 w-3.5" />, desc: '高清 2x 分辨率' },
  { format: 'jpeg', label: '图片 (JPEG)', icon: <FileImage className="h-3.5 w-3.5" />, desc: '高清 2x 分辨率' },
]

export default function ExportMenu({
  branch,
  blocks,
  styleId,
  markdown: externalMd,
  open,
  onClose,
  className,
}: ExportMenuProps) {
  const [exporting, setExporting] = useState<ExportFormat | 'markdown' | null>(null)
  const [error, setError] = useState<string | null>(null)

  if (!open) return null

  const md = externalMd ?? blocksToMarkdown(
    { name: branch.name, company: branch.company, position: branch.position },
    blocks,
  )

  const hasContent = blocks.length > 0 || (externalMd && externalMd.trim().length > 0)

  async function handleExport(format: ExportFormat | 'markdown') {
    setError(null)
    setExporting(format)

    try {
      if (format === 'markdown') {
        downloadMarkdown(branch, blocks)
      } else {
        // US1: render markdown → HTML via the unified engine before sending.
        // The same renderMarkdown function powers the live preview, so preview
        // and exported PDF share an identical HTML generator (no drift).
        const accentColor = branch.accent_color ?? '#39393a'
        const { html } = renderMarkdown(md, { accentColor })
        // US9: inline the avatar as a base64 data URL so the headless browser
        // does not have to authenticate against /api/v1/.../avatar.
        const exportHtml = await wrapHtmlWithAvatar(html, branch)
        const { blob, filename } = await exportResume({
          html: exportHtml,
          format,
        })
        downloadBlob(blob, filename)
      }
      onClose()
    } catch (err) {
      setError(err instanceof Error ? err.message : '导出失败')
    } finally {
      setExporting(null)
    }
  }

  return (
    <div className="fixed inset-0 z-50" onClick={onClose}>
      <div
        className={cn(
          'absolute right-4 top-12 w-[260px] bg-surface dark:bg-dark-surface border border-surface-border dark:border-dark-surface-border rounded-lg shadow-notion-lg z-50',
          className,
        )}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between px-3 py-2.5 border-b border-surface-border dark:border-dark-surface-border">
          <h3 className="text-xs font-semibold text-ink-1">导出简历</h3>
          <button
            onClick={onClose}
            className="p-1 rounded hover:bg-surface-muted text-ink-3 hover:text-ink-1"
            aria-label="关闭"
          >
            <X className="h-3 w-3" />
          </button>
        </div>

        {!hasContent ? (
          <div className="px-3 py-4 text-center text-2xs text-ink-3">简历内容为空，无法导出</div>
        ) : (
          <div className="py-1">
            {/* Markdown export (client-side, always available) */}
            <button
              onClick={() => handleExport('markdown')}
              data-testid="export-markdown-option"
              disabled={exporting !== null}
              className="w-full text-left px-3 py-2.5 flex items-center gap-2.5 hover:bg-surface-muted dark:hover:bg-dark-surface-muted transition-colors disabled:opacity-50"
            >
              <FileText className="h-3.5 w-3.5 text-ink-2 flex-shrink-0" />
              <div className="flex-1 min-w-0">
                <div className="text-xs text-ink-1">Markdown 文件</div>
                <div className="text-2xs text-ink-3">纯文本，便于版本管理</div>
              </div>
              {exporting === 'markdown' ? (
                <Loader2 className="h-3 w-3 animate-spin text-ink-3" />
              ) : (
                <Download className="h-3 w-3 text-ink-3" />
              )}
            </button>

            <div className="px-3 py-1">
              <div className="border-t border-surface-border dark:border-dark-surface-border" />
            </div>

            {/* PDF/Image export (server-side) */}
            {FORMATS.map((f) => (
              <button
                key={f.format}
                onClick={() => handleExport(f.format)}
                data-testid={`export-${f.format}-option`}
                disabled={exporting !== null}
                className="w-full text-left px-3 py-2.5 flex items-center gap-2.5 hover:bg-surface-muted dark:hover:bg-dark-surface-muted transition-colors disabled:opacity-50"
              >
                <div className="text-ink-2 flex-shrink-0">{f.icon}</div>
                <div className="flex-1 min-w-0">
                  <div className="text-xs text-ink-1">{f.label}</div>
                  <div className="text-2xs text-ink-3">{f.desc}</div>
                </div>
                {exporting === f.format ? (
                  <Loader2 className="h-3 w-3 animate-spin text-ink-3" />
                ) : (
                  <Download className="h-3 w-3 text-ink-3" />
                )}
              </button>
            ))}
          </div>
        )}

        {error && (
          <div
            className="px-3 py-2 border-t border-surface-border dark:border-dark-surface-border text-2xs text-red-500"
            data-testid="export-error-message"
            role="status"
          >
            {error}
          </div>
        )}
      </div>
    </div>
  )
}

/**
 * Inline the branch avatar into the rendered HTML as a base64 data URL so
 * the headless export browser does not need to authenticate. Returns the
 * original HTML untouched when there is no avatar.
 *
 * US9.
 */
async function wrapHtmlWithAvatar(html: string, branch: ResumeBranch): Promise<string> {
  if (!branch.avatar_url) return html
  try {
    const blob = await fetchBranchAvatarBlob(branch.id)
    if (!blob) return html
    const dataUrl = await blobToDataUrl(blob)
    const size = Math.max(50, Math.min(200, branch.avatar_size ?? 100))
    const position: AvatarPosition = branch.avatar_position ?? 'right'
    const shape: AvatarShape = branch.avatar_shape ?? 'circle'
    const radius = shape === 'circle' ? '50%' : shape === 'rounded' ? '8px' : '0'
    const img = `<img src="${dataUrl}" alt="头像" style="width:${size}px;height:${size}px;object-fit:cover;border-radius:${radius};display:block;" />`
    const wrapper = `<div class="rs-avatar rs-avatar-${position}" style="margin:8px 0;text-align:${position === 'left' ? 'left' : position === 'right' ? 'right' : 'center'};">${img}</div>`
    return wrapper + html
  } catch {
    // Best-effort: if avatar embedding fails, export without avatar.
    return html
  }
}

function blobToDataUrl(blob: Blob): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => resolve(reader.result as string)
    reader.onerror = () => reject(reader.error)
    reader.readAsDataURL(blob)
  })
}
