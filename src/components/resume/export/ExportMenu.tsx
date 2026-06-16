import { useState } from 'react'
import { Download, FileText, FileImage, Loader2, Check, X } from 'lucide-react'
import { cn } from '@/lib/utils'
import { downloadMarkdown, downloadBlob } from '@/lib/export/markdown-export'
import { exportResume, type ExportFormat } from '@/api/export'
import { blocksToMarkdown } from '@/lib/markdown-converter'
import type { ResumeBlock, ResumeBranch } from '@/api/types'

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
        const { blob, filename } = await exportResume({
          markdown: md,
          style_id: styleId,
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
