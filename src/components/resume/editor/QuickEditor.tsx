import { useState, useEffect, useMemo } from 'react'
import { GripVertical, ChevronDown, ChevronRight, Trash2 } from 'lucide-react'
import { Card } from '@/components/ui/Card'
import { Badge } from '@/components/ui/Badge'
import { Input, Textarea } from '@/components/ui/Input'
import type { ResumeBlock, BlockType } from '@/api/types'

const BLOCK_TYPES: { value: BlockType; label: string }[] = [
  { value: 'heading', label: '标题' },
  { value: 'summary', label: '简介' },
  { value: 'experience', label: '经历' },
  { value: 'project', label: '项目' },
  { value: 'skill', label: '技能' },
  { value: 'education', label: '教育' },
  { value: 'custom', label: '自定义' },
]

export interface QuickEditorProps {
  blocks: ResumeBlock[]
  collapsedBlockIds: Set<string>
  onToggleCollapse: (blockId: string) => void
  onAutoSave: (blockId: string, content: string) => void
  onDelete: (blockId: string) => void
  onMoveUp: (blockId: string) => void
  onMoveDown: (blockId: string) => void
  onPatchMeta: (blockId: string, meta: Record<string, unknown> | null) => void
  isReadonly?: boolean
}

export function QuickEditor({
  blocks,
  collapsedBlockIds,
  onToggleCollapse,
  onAutoSave,
  onDelete,
  onMoveUp,
  onMoveDown,
  onPatchMeta,
  isReadonly = false,
}: QuickEditorProps) {
  return (
    <div className="space-y-3">
      {blocks.map((b) => (
        <BlockRow
          key={b.id}
          block={b}
          collapsed={collapsedBlockIds.has(b.id)}
          onToggleCollapse={() => onToggleCollapse(b.id)}
          onAutoSave={(content) => onAutoSave(b.id, content)}
          onDelete={() => onDelete(b.id)}
          onMoveUp={() => onMoveUp(b.id)}
          onMoveDown={() => onMoveDown(b.id)}
          onPatchMeta={(meta) => onPatchMeta(b.id, meta)}
          readOnly={isReadonly}
        />
      ))}
    </div>
  )
}

export function BlockRow({
  block,
  collapsed,
  onToggleCollapse,
  onAutoSave,
  onDelete,
  onMoveUp,
  onMoveDown,
  onPatchMeta,
  readOnly = false,
}: {
  block: ResumeBlock
  collapsed: boolean
  onToggleCollapse: () => void
  onAutoSave: (content_md: string) => void
  onDelete: () => void
  onMoveUp: () => void
  onMoveDown: () => void
  onPatchMeta: (meta: Record<string, unknown> | null) => void
  readOnly?: boolean
}) {
  const [value, setValue] = useState(block.content_md)

  useEffect(() => {
    setValue(block.content_md)
  }, [block.content_md])

  useEffect(() => {
    if (readOnly || value === block.content_md) return
    const t = setTimeout(() => onAutoSave(value), 1500)
    return () => clearTimeout(t)
  }, [value, block.content_md, onAutoSave, readOnly])

  const typeLabel = useMemo(
    () => BLOCK_TYPES.find((t) => t.value === block.type)?.label ?? block.type,
    [block.type],
  )

  return (
    <Card padding="md" data-testid={`block-${block.id}`}>
      <div className="flex items-center gap-2 mb-2">
        <GripVertical className="h-3.5 w-3.5 text-ink-muted" />
        <button
          onClick={onToggleCollapse}
          className="text-ink-2 hover:text-ink-1"
          aria-label={collapsed ? '展开' : '折叠'}
        >
          {collapsed ? <ChevronRight className="h-3.5 w-3.5" /> : <ChevronDown className="h-3.5 w-3.5" />}
        </button>
        <Badge variant="default">{typeLabel}</Badge>
        {block.title && <span className="text-sm font-medium text-ink-1 truncate">{block.title}</span>}
        <div className="flex-1" />
        {!readOnly && (
          <>
            <button
              onClick={onMoveUp}
              className="text-2xs text-ink-3 hover:text-ink-1 px-1.5 py-0.5 rounded hover:bg-surface-muted"
              aria-label="上移"
            >
              ↑
            </button>
            <button
              onClick={onMoveDown}
              className="text-2xs text-ink-3 hover:text-ink-1 px-1.5 py-0.5 rounded hover:bg-surface-muted"
              aria-label="下移"
            >
              ↓
            </button>
          </>
        )}
        {!readOnly && (
          <button
            onClick={onDelete}
            className="text-ink-3 hover:text-red-500 p-1 rounded hover:bg-red-50 dark:hover:bg-red-900/20"
            aria-label="删除"
          >
            <Trash2 className="h-3.5 w-3.5" />
          </button>
        )}
      </div>

      {/* Meta fields for experience blocks */}
      {block.type === 'experience' && !collapsed && (
        <div className="grid grid-cols-2 gap-2 mb-2">
          <Input
            size="sm"
            placeholder="公司名称"
            value={(block.meta as Record<string, string> | null)?.company ?? ''}
            onChange={(e) => {
              const current = (block.meta as Record<string, string> | null) ?? {}
              onPatchMeta({ ...current, company: e.target.value })
            }}
            readOnly={readOnly}
          />
          <Input
            size="sm"
            placeholder="角色"
            value={(block.meta as Record<string, string> | null)?.role ?? ''}
            onChange={(e) => {
              const current = (block.meta as Record<string, string> | null) ?? {}
              onPatchMeta({ ...current, role: e.target.value })
            }}
            readOnly={readOnly}
          />
        </div>
      )}

      {!collapsed && (
        <Textarea
          value={value}
          onChange={(e) => setValue(e.target.value)}
          rows={5}
          placeholder="支持 Markdown，1.5s 自动保存"
          data-testid={`block-content-${block.id}`}
          readOnly={readOnly}
        />
      )}
    </Card>
  )
}

export { BLOCK_TYPES }
