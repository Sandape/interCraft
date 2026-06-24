import { useMemo, useState } from 'react'
import { Sparkles, History, RotateCcw, Eye, HardDrive } from 'lucide-react'
import { Button } from '@/components/ui/Button'
import { Badge } from '@/components/ui/Badge'
import { cn, timeAgo } from '@/lib/utils'
import type { ResumeBranch, ResumeVersionSummary } from '@/modules/resume/api/types'
import { RESUME_STYLES, getStyleById } from '@/modules/resume/styles'
import { getHistory, type HistoryEntry } from '@/modules/resume/history/local-history'

// ── Style thumbnail mini ──────────────────────────────────

function StyleThumbMini({ styleId, active }: { styleId: string; active: boolean }) {
  const borderColor = active ? 'border-accent-400' : 'border-ink-200 dark:border-ink-700'

  if (styleId === 'modern-two-column') {
    return (
      <div className={cn('w-7 h-9 rounded-xs border bg-white dark:bg-ink-800 shrink-0 p-0.5', borderColor)}>
        <div className="flex gap-0.5 h-full">
          <div className="w-[30%] bg-ink-100 dark:bg-ink-600 rounded-xs" />
          <div className="flex-1 space-y-0.5">
            <div className="h-0.5 w-full bg-ink-200 dark:bg-ink-500 rounded-xs" />
            <div className="h-0.5 w-3/4 bg-ink-200 dark:bg-ink-500 rounded-xs" />
            <div className="h-0.5 w-1/2 bg-ink-200 dark:bg-ink-500 rounded-xs" />
          </div>
        </div>
      </div>
    )
  }
  if (styleId === 'editorial') {
    return (
      <div className={cn('w-7 h-9 rounded-xs border bg-white dark:bg-ink-800 shrink-0 p-0.5', borderColor)}>
        <div className="space-y-0.5">
          <div className="h-0.5 w-2/3 bg-ink-300 dark:bg-ink-500 rounded-xs" />
          <div className="h-px bg-ink-200 dark:bg-ink-600 my-0.5" />
          <div className="h-0.5 w-full bg-ink-200 dark:bg-ink-500 rounded-xs" />
          <div className="h-0.5 w-2/3 bg-ink-200 dark:bg-ink-500 rounded-xs" />
        </div>
      </div>
    )
  }
  // default: single column layouts (classic, compact)
  return (
    <div className={cn('w-7 h-9 rounded-xs border bg-white dark:bg-ink-800 shrink-0 p-0.5', borderColor)}>
      <div className="space-y-0.5">
        <div className="h-0.5 w-3/4 bg-ink-300 dark:bg-ink-500 rounded-xs mx-auto" />
        <div className="h-0.5 w-1/3 bg-ink-200 dark:bg-ink-600 rounded-xs mx-auto" />
        <div className="h-px bg-ink-200 dark:bg-ink-600 my-0.5" />
        <div className="h-0.5 w-2/3 bg-ink-200 dark:bg-ink-600 rounded-xs" />
        <div className="h-0.5 w-full bg-ink-200 dark:bg-ink-600 rounded-xs" />
        <div className="h-0.5 w-1/2 bg-ink-200 dark:bg-ink-600 rounded-xs" />
      </div>
    </div>
  )
}

// ── EditorSidebar ─────────────────────────────────────────

interface EditorSidebarProps {
  branch: ResumeBranch
  versions: ResumeVersionSummary[]
  activeVersionId?: string
  styleId: string
  onStyleSelect: (styleId: string) => void
  onVersionSelect: (versionNo: number) => void
  onRollback: () => void
  onSaveVersion: () => void
  onRestoreHistory?: (entry: HistoryEntry) => void
  className?: string
}

export default function EditorSidebar({
  branch,
  versions,
  styleId,
  onStyleSelect,
  onVersionSelect,
  onRollback,
  onSaveVersion,
  onRestoreHistory,
  className,
}: EditorSidebarProps) {
  const aiVersionCount = versions.filter((v) => v.trigger === 'ai').length

  // US7 FR-053: read local history entries for this branch.
  const [localHistory, setLocalHistory] = useState<HistoryEntry[]>(() =>
    getHistory(branch.id),
  )

  return (
    <aside
      className={cn(
        'border-l border-surface-border dark:border-dark-surface-border bg-surface-subtle/40 dark:bg-dark-surface/40 overflow-y-auto',
        className,
      )}
    >
      {/* ── AI 优化摘要 ── */}
      <div className="px-4 py-4 border-b border-surface-border dark:border-dark-surface-border">
        <div className="flex items-center gap-2 mb-3">
          <div className="w-5 h-5 rounded-md bg-gradient-to-br from-brand-400 to-brand-600 flex items-center justify-center">
            <Sparkles className="h-2.5 w-2.5 text-white" />
          </div>
          <h4 className="text-xs font-semibold text-ink-1">AI 优化摘要</h4>
        </div>

        {aiVersionCount === 0 ? (
          <p className="text-2xs text-ink-3 py-2">
            暂无 AI 优化记录。在编辑器中点击「AI 优化」开始。
          </p>
        ) : (
          <div className="space-y-2">
            <div className="flex items-baseline gap-1">
              <span className="text-xs font-semibold font-mono tabular-nums text-ink-1">
                {aiVersionCount}
              </span>
              <span className="text-2xs text-ink-3">次 AI 优化</span>
            </div>
            {branch.match_score != null && (
              <div className="mt-3">
                <div className="flex items-center justify-between text-2xs text-ink-3 mb-1">
                  <span>匹配度</span>
                  <span className="font-mono tabular-nums text-ink-1 font-medium">
                    {branch.match_score}
                  </span>
                </div>
                <div className="h-1.5 bg-surface-muted dark:bg-dark-surface-muted rounded-full overflow-hidden">
                  <div
                    className="h-full bg-gradient-to-r from-brand-400 to-brand-600 rounded-full transition-all"
                    style={{ width: `${Math.max(0, Math.min(100, branch.match_score))}%` }}
                  />
                </div>
              </div>
            )}
          </div>
        )}
      </div>

      {/* ── 目标 JD ── */}
      {branch.company && (
        <div className="px-4 py-4 border-b border-surface-border dark:border-dark-surface-border">
          <h4 className="text-2xs tracking-[0.12em] uppercase text-ink-3 font-medium mb-2">
            目标 JD
          </h4>
          <pre className="text-2xs font-mono leading-relaxed text-ink-3 whitespace-pre-wrap bg-surface-muted dark:bg-dark-surface-muted rounded p-2.5 max-h-[160px] overflow-y-auto">
            {branch.company ? `目标企业：${branch.company}` : '未关联 JD'}
            {branch.position ? `\n目标职位：${branch.position}` : ''}
            {`\n状态：${
              branch.status === 'ready' ? '就绪' :
              branch.status === 'optimizing' ? '优化中' :
              branch.status === 'draft' ? '草稿' :
              branch.status === 'submitted' ? '已投递' : '归档'
            }`}
          </pre>
        </div>
      )}

      {/* ── 模板选择 ── */}
      <div className="px-4 py-4 border-b border-surface-border dark:border-dark-surface-border">
        <div className="mb-2.5">
          <h4 className="text-xs font-semibold text-ink-1">模板</h4>
          <p className="text-2xs text-ink-3 mt-0.5">切换样式实时预览</p>
        </div>
        <div className="grid grid-cols-2 gap-1.5">
          {RESUME_STYLES.map((style) => {
            const isActive = style.id === styleId
            return (
              <button
                key={style.id}
                onClick={() => onStyleSelect(style.id)}
                className={cn(
                  'text-left p-2 rounded-md border transition-all',
                  isActive
                    ? 'border-brand-400 bg-brand-50/50 dark:bg-brand-500/10'
                    : 'border-surface-border dark:border-dark-surface-border hover:border-ink-300 dark:hover:border-dark-ink-muted',
                )}
              >
                <div className="flex items-center gap-1.5 mb-1">
                  <StyleThumbMini styleId={style.id} active={isActive} />
                  <span className="text-2xs font-medium text-ink-1">{style.labelZh}</span>
                </div>
                <div className="text-2xs text-ink-3 leading-snug">{style.description}</div>
              </button>
            )
          })}
        </div>
      </div>

      {/* ── 版本历史 ── */}
      <div className="px-4 py-4">
        <div className="flex items-center justify-between mb-2">
          <div className="flex items-center gap-1.5">
            <History className="h-3 w-3 text-ink-3" />
            <h4 className="text-xs font-semibold text-ink-1">版本历史</h4>
          </div>
          <Badge variant="default">{versions.length}</Badge>
        </div>

        {versions.length > 0 ? (
          <ul className="space-y-0.5">
            {[...versions].reverse().slice(0, 5).map((v) => (
              <li key={v.id}>
                <button
                  onClick={() => onVersionSelect(v.version_no)}
                  className="w-full text-left px-2.5 py-2 rounded-md transition-colors hover:bg-surface-muted dark:hover:bg-dark-surface-muted group"
                >
                  <div className="flex items-center gap-1.5">
                    <span
                      className={cn(
                        'w-1.5 h-1.5 rounded-full shrink-0',
                        v.trigger === 'ai' ? 'bg-brand-500' : 'bg-ink-300 dark:bg-ink-600',
                      )}
                    />
                    <span className="text-xs font-medium text-ink-1 truncate flex-1">
                      v{v.version_no} {v.label ? `· ${v.label}` : '· 未命名'}
                    </span>
                  </div>
                  <div className="text-2xs text-ink-3 mt-0.5 pl-3 tabular-nums">
                    {timeAgo(v.created_at)}
                  </div>
                </button>
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-2xs text-ink-3 py-2 text-center">暂无历史版本</p>
        )}

        <div className="mt-2 space-y-1">
          <button
            onClick={onSaveVersion}
            className="w-full text-2xs text-ink-3 hover:text-ink-1 flex items-center justify-center gap-1 py-1.5 rounded border border-dashed border-surface-border dark:border-dark-surface-border hover:border-ink-300 dark:hover:border-dark-ink-muted"
          >
            + 保存当前版本
          </button>
          <button
            onClick={onRollback}
            className="w-full text-2xs text-ink-3 hover:text-ink-1 flex items-center justify-center gap-1 py-1.5 rounded border border-dashed border-surface-border dark:border-dark-surface-border hover:border-ink-300 dark:hover:border-dark-ink-muted"
          >
            <RotateCcw className="h-2.5 w-2.5" />
            回滚到上一版本
          </button>
        </div>
      </div>

      {/* ── 本地编辑历史 (US7 FR-051~053) ── */}
      <div className="px-4 py-4 border-t border-surface-border dark:border-dark-surface-border">
        <div className="flex items-center justify-between mb-2">
          <div className="flex items-center gap-1.5">
            <HardDrive className="h-3 w-3 text-ink-3" />
            <h4 className="text-xs font-semibold text-ink-1">本地历史</h4>
          </div>
          {localHistory.length > 0 && (
            <Badge variant="default">{localHistory.length}</Badge>
          )}
        </div>

        {localHistory.length === 0 ? (
          <p className="text-2xs text-ink-3 py-2 text-center">编辑内容后自动保存</p>
        ) : (
          <ul className="space-y-0.5">
            {localHistory.slice(0, 8).map((entry, idx) => (
              <li key={entry.timestamp}>
                <button
                  onClick={() => onRestoreHistory?.(entry)}
                  className="w-full text-left px-2.5 py-2 rounded-md transition-colors hover:bg-surface-muted dark:hover:bg-dark-surface-muted group"
                >
                  <div className="flex items-center gap-1.5">
                    <span className="w-1.5 h-1.5 rounded-full shrink-0 bg-ink-300 dark:bg-ink-600" />
                    <span className="text-xs text-ink-1 truncate flex-1">
                      {new Date(entry.timestamp).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })}
                    </span>
                  </div>
                  <div className="text-2xs text-ink-3 mt-0.5 pl-3 truncate">
                    {entry.markdown.slice(0, 40)}{entry.markdown.length > 40 ? '…' : ''}
                  </div>
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
    </aside>
  )
}
