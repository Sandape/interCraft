import { useState, useEffect, useMemo, useCallback } from 'react'
import { GripVertical, ChevronDown, ChevronRight, Trash2 } from 'lucide-react'
import { Card } from '@/components/ui/Card'
import { Badge } from '@/components/ui/Badge'
import { Input, Textarea } from '@/components/ui/Input'
import { DndContext, closestCenter, PointerSensor, useSensor, useSensors, type DragEndEvent } from '@dnd-kit/core'
import { SortableContext, verticalListSortingStrategy, useSortable } from '@dnd-kit/sortable'
import { CSS } from '@dnd-kit/utilities'
import type { ResumeBlock, BlockType } from '@/modules/resume/api/types'

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
  onReorder?: (blockId: string, prevId: string | null, nextId: string | null) => void
  onPatchMeta: (blockId: string, meta: Record<string, unknown> | null) => void
  /**
   * US8 forward-locate: clicking a block header scrolls the preview to the
   * matching rendered block and triggers the 1.5s yellow flash.
   */
  onPreviewLocate?: (blockId: string) => void
  /**
   * US8 reverse-locate: when set, the matching block pulses for 1.5s.
   * Parent auto-clears the value after the duration.
   */
  highlightedBlockId?: string | null
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
  onReorder,
  onPatchMeta,
  onPreviewLocate,
  highlightedBlockId,
  isReadonly = false,
}: QuickEditorProps) {
  const sensors = useSensors(useSensor(PointerSensor, { activationConstraint: { distance: 8 } }))

  const handleDragEnd = useCallback(
    (event: DragEndEvent) => {
      const { active, over } = event
      if (!over || active.id === over.id) return
      const oldIndex = blocks.findIndex((b) => b.id === active.id)
      const newIndex = blocks.findIndex((b) => b.id === over.id)
      if (oldIndex === -1 || newIndex === -1) return
      const moved = blocks[oldIndex]
      if (!moved) return
      const reordered = [...blocks]
      reordered.splice(oldIndex, 1)
      reordered.splice(newIndex, 0, moved)
      const pos = reordered.findIndex((b) => b.id === moved.id)
      const prevBlock = pos > 0 ? reordered[pos - 1] : null
      const nextBlock = pos < reordered.length - 1 ? reordered[pos + 1] : null
      onReorder?.(moved.id, prevBlock?.id ?? null, nextBlock?.id ?? null)
    },
    [blocks, onReorder],
  )

  const content = (
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
          onPreviewLocate={onPreviewLocate ? () => onPreviewLocate(b.id) : undefined}
          highlighted={highlightedBlockId === b.id}
          readOnly={isReadonly}
        />
      ))}
    </div>
  )

  if (!onReorder || isReadonly) return content

  return (
    <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={handleDragEnd}>
      <SortableContext items={blocks.map((b) => b.id)} strategy={verticalListSortingStrategy}>
        {blocks.map((b) => (
          <SortableBlockRow
            key={b.id}
            block={b}
            collapsed={collapsedBlockIds.has(b.id)}
            onToggleCollapse={() => onToggleCollapse(b.id)}
            onAutoSave={(content) => onAutoSave(b.id, content)}
            onDelete={() => onDelete(b.id)}
            onMoveUp={() => onMoveUp(b.id)}
            onMoveDown={() => onMoveDown(b.id)}
            onPatchMeta={(meta) => onPatchMeta(b.id, meta)}
            onPreviewLocate={onPreviewLocate ? () => onPreviewLocate(b.id) : undefined}
            highlighted={highlightedBlockId === b.id}
            readOnly={isReadonly}
          />
        ))}
      </SortableContext>
    </DndContext>
  )
}

function SortableBlockRow(props: {
  block: ResumeBlock
  collapsed: boolean
  onToggleCollapse: () => void
  onAutoSave: (content_md: string) => void
  onDelete: () => void
  onMoveUp: () => void
  onMoveDown: () => void
  onPatchMeta: (meta: Record<string, unknown> | null) => void
  onPreviewLocate?: () => void
  highlighted?: boolean
  readOnly?: boolean
}) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({
    id: props.block.id,
  })
  const style: React.CSSProperties = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.5 : undefined,
  }
  return (
    <div ref={setNodeRef} style={style}>
      <BlockRow
        block={props.block}
        collapsed={props.collapsed}
        onToggleCollapse={props.onToggleCollapse}
        onAutoSave={props.onAutoSave}
        onDelete={props.onDelete}
        onMoveUp={props.onMoveUp}
        onMoveDown={props.onMoveDown}
        onPatchMeta={props.onPatchMeta}
        onPreviewLocate={props.onPreviewLocate}
        highlighted={props.highlighted}
        readOnly={props.readOnly}
        dragHandleProps={{ ...attributes, ...listeners }}
      />
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
  onPreviewLocate,
  highlighted,
  readOnly = false,
  dragHandleProps,
}: {
  block: ResumeBlock
  collapsed: boolean
  onToggleCollapse: () => void
  onAutoSave: (content_md: string) => void
  onDelete: () => void
  onMoveUp: () => void
  onMoveDown: () => void
  onPatchMeta: (meta: Record<string, unknown> | null) => void
  /** US8: clicking the block header scrolls the preview to this block. */
  onPreviewLocate?: () => void
  /** US8 reverse-locate: when true, the card pulses yellow for 1.5s. */
  highlighted?: boolean
  readOnly?: boolean
  dragHandleProps?: Record<string, unknown>
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
    <Card
      padding="md"
      data-testid={`block-${block.id}`}
      className={highlighted ? 'rs-editor-block-flash' : undefined}
    >
      <div className="flex items-center gap-2 mb-2">
        <div
          className={
            onPreviewLocate
              ? 'flex items-center gap-2 flex-1 min-w-0 cursor-pointer rounded -mx-1 px-1 hover:bg-surface-muted/60'
              : 'flex items-center gap-2 flex-1 min-w-0'
          }
          onClick={onPreviewLocate}
          role={onPreviewLocate ? 'button' : undefined}
          tabIndex={onPreviewLocate ? 0 : undefined}
          onKeyDown={
            onPreviewLocate
              ? (e) => {
                  if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault()
                    onPreviewLocate()
                  }
                }
              : undefined
          }
          data-testid={`block-header-${block.id}`}
        >
          <GripVertical
            className="h-3.5 w-3.5 text-ink-muted cursor-grab active:cursor-grabbing"
            {...(dragHandleProps as React.HTMLAttributes<SVGSVGElement>)}
          />
          <button
            onClick={(e) => {
              e.stopPropagation()
              onToggleCollapse()
            }}
            className="text-ink-2 hover:text-ink-1"
            aria-label={collapsed ? '展开' : '折叠'}
          >
            {collapsed ? <ChevronRight className="h-3.5 w-3.5" /> : <ChevronDown className="h-3.5 w-3.5" />}
          </button>
          <Badge variant="default">{typeLabel}</Badge>
          {block.title && <span className="text-sm font-medium text-ink-1 truncate">{block.title}</span>}
        </div>
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
