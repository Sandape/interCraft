/**
 * VersionDiffView — renders a block-level diff between two resume versions
 * (spec 027 US7 FR-049/050).
 *
 * Accepts the `VersionDiff` payload from the backend endpoint or a locally
 * computed diff. Each block row shows (green add, red remove, yellow modify)
 * and modified blocks can be expanded to show line-level changes.
 */

import { useState } from 'react'
import { ChevronDown, ChevronRight, Plus, Minus, Pencil } from 'lucide-react'
import { Modal } from '@/components/ui/Modal'
import { Button } from '@/components/ui/Button'
import { Badge } from '@/components/ui/Badge'
import type { VersionDiff, BlockDiff, BranchDiff } from '../version-diff/block-diff'

interface VersionDiffViewProps {
  open: boolean
  onClose: () => void
  diff: VersionDiff | null
  loading?: boolean
}

const OP_COLORS: Record<string, { bg: string; border: string; label: string; dot: string }> = {
  added: { bg: 'bg-green-50 dark:bg-green-900/15', border: 'border-green-300 dark:border-green-700', label: '新增', dot: 'bg-green-500' },
  removed: { bg: 'bg-red-50 dark:bg-red-900/15', border: 'border-red-300 dark:border-red-700', label: '删除', dot: 'bg-red-500' },
  modified: { bg: 'bg-yellow-50 dark:bg-yellow-900/15', border: 'border-yellow-300 dark:border-yellow-700', label: '修改', dot: 'bg-yellow-500' },
  unchanged: { bg: '', border: 'border-surface-border dark:border-dark-surface-border', label: '未变', dot: 'bg-ink-muted' },
}

function LineEntry({ kind, text }: { kind: string; text: string }) {
  const cls =
    kind === 'added'
      ? 'bg-green-100 dark:bg-green-900/25 text-green-800 dark:text-green-200'
      : kind === 'removed'
        ? 'bg-red-100 dark:bg-red-900/25 text-red-800 dark:text-red-200 line-through'
        : 'text-ink-2'
  return (
    <pre className={`px-2 py-0.5 text-xs leading-5 ${cls}`}>
      {kind === 'added' ? '+ ' : kind === 'removed' ? '- ' : '  '}
      {text || ' '}
    </pre>
  )
}

function BlockDiffRow({ block }: { block: BlockDiff }) {
  const [expanded, setExpanded] = useState(false)
  const colors = OP_COLORS[block.op] ?? OP_COLORS.unchanged

  return (
    <div className={`rounded border ${colors.border} ${colors.bg} overflow-hidden`}>
      <button
        type="button"
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center gap-2 px-3 py-2 text-left hover:opacity-80"
      >
        <span className={`w-2 h-2 rounded-full flex-shrink-0 ${colors.dot}`} />
        <Badge variant={block.op === 'removed' ? 'danger' : block.op === 'added' ? 'success' : 'default'}>
          {block.type}
        </Badge>
        <span className="text-sm font-medium text-ink-1 truncate">{block.title ?? '（无标题）'}</span>
        {block.lineDiff && (
          <span className="text-2xs text-ink-3 ml-auto">
            <span className="inline-flex items-center gap-1">
              {expanded ? <ChevronDown className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />}
              {block.lineDiff.filter((l) => l.kind !== 'unchanged').length} 处变更
            </span>
          </span>
        )}
        {!block.lineDiff && block.op !== 'unchanged' && (
          <span className="text-xs text-ink-3 ml-auto">{colors.label}</span>
        )}
      </button>
      {expanded && block.lineDiff && (
        <div className="border-t border-inherit max-h-64 overflow-y-auto">
          {block.lineDiff.map((entry, idx) => (
            <LineEntry key={idx} kind={entry.kind} text={entry.text} />
          ))}
        </div>
      )}
    </div>
  )
}

function BranchDiffSummary({ branchDiff, oldNo, newNo }: { branchDiff: BranchDiff; oldNo: number; newNo: number }) {
  const changed = Object.entries(branchDiff).filter(([, v]) => v !== null)
  if (changed.length === 0) return null
  return (
    <div className="mb-4 p-3 rounded border border-surface-border dark:border-dark-surface-border bg-surface-muted dark:bg-dark-surface-muted">
      <div className="text-xs font-semibold text-ink-2 mb-1.5">分支属性变更 (v{oldNo} → v{newNo})</div>
      <ul className="space-y-1">
        {changed.map(([key, val]) => (
          <li key={key} className="text-xs text-ink-3">
            <span className="font-medium text-ink-2">{key}</span>: {val}
          </li>
        ))}
      </ul>
    </div>
  )
}

export default function VersionDiffView({ open, onClose, diff, loading }: VersionDiffViewProps) {
  const summary = diff?.summary

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="版本对比"
      description={diff ? `v${diff.oldVersionNo} → v${diff.newVersionNo}` : undefined}
      size="lg"
      footer={
        <Button variant="ghost" onClick={onClose}>
          关闭
        </Button>
      }
    >
      {loading ? (
        <p className="text-sm text-ink-3 py-8 text-center">对比中…</p>
      ) : !diff ? (
        <p className="text-sm text-ink-3 py-8 text-center">请选择两个版本进行对比</p>
      ) : (
        <div className="space-y-3">
          {/* Summary bar */}
          {summary && (
            <div className="flex gap-3 text-xs text-ink-2 mb-4">
              <span className="flex items-center gap-1">
                <span className="w-2 h-2 rounded-full bg-green-500" /> 新增 {summary.added}
              </span>
              <span className="flex items-center gap-1">
                <span className="w-2 h-2 rounded-full bg-red-500" /> 删除 {summary.removed}
              </span>
              <span className="flex items-center gap-1">
                <span className="w-2 h-2 rounded-full bg-yellow-500" /> 修改 {summary.modified}
              </span>
              <span className="flex items-center gap-1">
                <span className="w-2 h-2 rounded-full bg-ink-muted" /> 未变 {summary.unchanged}
              </span>
            </div>
          )}

          <BranchDiffSummary branchDiff={diff.branchDiff} oldNo={diff.oldVersionNo} newNo={diff.newVersionNo} />

          {/* Block diff list */}
          {diff.blocks.length === 0 ? (
            <p className="text-sm text-ink-3 py-4 text-center">两个版本完全相同</p>
          ) : (
            <div className="space-y-1.5 max-h-[60vh] overflow-y-auto">
              {diff.blocks.map((block, idx) => (
                <BlockDiffRow key={`${block.key}-${idx}`} block={block} />
              ))}
            </div>
          )}
        </div>
      )}
    </Modal>
  )
}

export { BlockDiffRow, LineEntry }