/**
 * ResumeEditor page — loads a branch + its blocks, supports add / edit /
 * delete / reorder, and exposes version controls (save / rollback).
 * Supports two modes: Quick (block cards + preview) and Code (Markdown editor + preview).
 */
import { useEffect, useMemo, useState, useCallback, useRef } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { Plus, Save, History, RotateCcw, Eye, Pencil, RefreshCw, PanelRight, GitCompare } from 'lucide-react'
import { Button } from '@/components/ui/Button'
import { Modal } from '@/components/ui/Modal'
import { Input } from '@/components/ui/Input'
import { Badge } from '@/components/ui/Badge'
import AiOptimizePanel from '@/modules/resume/editor/AiOptimizePanel'
import { useResumeBranch, useResumeBlocks } from '@/hooks/queries/useResumeBranches'
import {
  useCreateBlock,
  useDeleteBlock,
  usePatchBlock,
  useReorderBlocks,
} from '@/hooks/mutations/useBranchMutations'
import { usePatchBranch } from '@/hooks/mutations/useBranchMutations'
import { useResumeVersion, useResumeVersions } from '@/hooks/queries/useResumeVersions'
import { useRollbackVersion, useSaveVersion } from '@/hooks/mutations/useVersionMutations'
import { useResumeUIStore } from '@/modules/resume/stores/useResumeUIStore'
import { timeAgo, cn } from '@/lib/utils'
import type { BlockType, BranchStatus, ResumeBlock, ResumeBranch } from '@/modules/resume/api/types'
import { useLock } from '@/lib/lock/useLock'
import { LockIndicator } from '@/components/lock/LockIndicator'
import { OfflineBanner } from '@/components/lock/OfflineBanner'
import { getResumeRepository } from '@/repositories/types'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { BLOCKS_KEY, BRANCHES_KEY, BRANCH_KEY } from '@/hooks/queries/useResumeBranches'
import { markdownToBlocks, blocksToMarkdown } from '@/modules/resume/converter/markdown-converter'
import { RESUME_STYLES, DEFAULT_STYLE_ID, getStyleById } from '@/modules/resume/styles'
import UnifiedToolbar from '@/modules/resume/editor/UnifiedToolbar'
import { useModeToggle } from '@/modules/resume/editor/useModeToggle'
import { QuickEditor, BLOCK_TYPES } from '@/modules/resume/editor/QuickEditor'
import MarkdownEditor from '@/modules/resume/editor/MarkdownEditor'
import ResumePreview from '@/modules/resume/editor/ResumePreview'
import StyleSelector from '@/modules/resume/editor/StyleSelector'
import EditorSidebar from '@/modules/resume/editor/EditorSidebar'
import ExportMenu from '@/modules/resume/export/ExportMenu'
import AvatarDialog from '@/modules/resume/editor/AvatarDialog'
import VersionDiffView from '@/modules/resume/editor/VersionDiffView'
import { useVersionDiff } from '@/hooks/queries/useVersionDiff'
import { pushHistory } from '@/modules/resume/history/local-history'
import type { HistoryEntry } from '@/modules/resume/history/local-history'
import { savePref, loadPref } from '@/modules/resume/ui-pref/index'
import { loadTheme, applyColor } from '@/modules/resume/themes'

const STATUS_LABEL: Record<BranchStatus, string> = {
  draft: '草稿',
  optimizing: '优化中',
  ready: '就绪',
  submitted: '已投递',
  archived: '归档',
}

export default function ResumeEditor() {
  const { branchId } = useParams<{ branchId: string }>()
  const navigate = useNavigate()
  const qc = useQueryClient()
  const { data: branch } = useResumeBranch(branchId ?? null)
  const { data: blocks = [], isLoading } = useResumeBlocks(branchId ?? null)
  const { data: versions = [] } = useResumeVersions(branchId ?? null)
  const createBlock = useCreateBlock(branchId ?? '')
  const deleteBlock = useDeleteBlock(branchId ?? '')
  const patchBlock = usePatchBlock(branchId ?? '')
  const patchBranch = usePatchBranch()
  const reorder = useReorderBlocks(branchId ?? '')
  const saveVersion = useSaveVersion(branchId ?? '')
  const rollbackVersion = useRollbackVersion(branchId ?? '')

  const collapsedBlockIds = useResumeUIStore((s) => s.collapsedBlockIds)
  const toggleCollapse = useResumeUIStore((s) => s.toggleCollapse)

  const lock = useLock('resume_branch', branchId ?? null)

  // Save version modal
  const [saveOpen, setSaveOpen] = useState(false)
  const [label, setLabel] = useState('')

  // Version drawer
  const [versionDrawerOpen, setVersionDrawerOpen] = useState(false)
  const [rollbackTarget, setRollbackTarget] = useState<number | null>(null)

  // Version detail viewer
  const [viewVersionNo, setViewVersionNo] = useState<number | null>(null)
  const { data: versionDetail } = useResumeVersion(branchId ?? null, viewVersionNo)

  // US7 version diff
  const [diffSelected, setDiffSelected] = useState<number[]>([])
  const [diffOpen, setDiffOpen] = useState(false)
  const { data: versionDiff, isFetching: diffLoading } = useVersionDiff(
    branchId ?? null,
    diffSelected.length === 2 ? Math.min(...diffSelected) : null,
    diffSelected.length === 2 ? Math.max(...diffSelected) : null,
  )

  // Add block modal
  const [addBlockOpen, setAddBlockOpen] = useState(false)
  const [newBlockType, setNewBlockType] = useState<BlockType>('custom')
  const [newBlockTitle, setNewBlockTitle] = useState('')

  // Edit branch modal
  const [editBranchOpen, setEditBranchOpen] = useState(false)
  const [editName, setEditName] = useState('')
  const [editCompany, setEditCompany] = useState('')
  const [editPosition, setEditPosition] = useState('')
  const [editStatus, setEditStatus] = useState<BranchStatus>('draft')

  const refreshFromParent = useMutation({
    mutationFn: () => getResumeRepository().refreshFromParent(branchId!),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: BLOCKS_KEY(branchId!) })
      qc.invalidateQueries({ queryKey: BRANCH_KEY(branchId!) })
      qc.invalidateQueries({ queryKey: BRANCHES_KEY })
    },
  })
  const [refreshConfirmOpen, setRefreshConfirmOpen] = useState(false)

  // US8 — bidirectional locator state. forward: editor → preview; reverse: preview → editor.
  const [scrollToBlockId, setScrollToBlockId] = useState<string | null>(null)
  const [editorHighlightedBlockId, setEditorHighlightedBlockId] = useState<string | null>(null)

  // Auto-clear editor highlight 1.5s after reverse-locate.
  useEffect(() => {
    if (!editorHighlightedBlockId) return
    const t = window.setTimeout(() => setEditorHighlightedBlockId(null), 1500)
    return () => window.clearTimeout(t)
  }, [editorHighlightedBlockId])

  // Reverse-locate: scroll editor list to the block the user clicked in the preview.
  useEffect(() => {
    if (!editorHighlightedBlockId) return
    const el = document.querySelector<HTMLElement>(
      `[data-testid="block-${editorHighlightedBlockId}"]`,
    )
    el?.scrollIntoView({ behavior: 'smooth', block: 'center' })
  }, [editorHighlightedBlockId])

  // Style selection state — default from branch or system default
  const [styleSelectorOpen, setStyleSelectorOpen] = useState(false)
  const [exportMenuOpen, setExportMenuOpen] = useState(false)
  const [avatarDialogOpen, setAvatarDialogOpen] = useState(false)

  // Sidebar drawer
  const [sidebarOpen, setSidebarOpen] = useState(false)

  // Locator interactions are suspended while any modal/drawer is open so
  // click-to-locate never reaches through to a hidden preview.
  const locatorSuspended =
    saveOpen ||
    versionDrawerOpen ||
    viewVersionNo !== null ||
    rollbackTarget !== null ||
    addBlockOpen ||
    editBranchOpen ||
    avatarDialogOpen ||
    styleSelectorOpen ||
    exportMenuOpen ||
    sidebarOpen ||
    diffOpen ||
    refreshConfirmOpen

  // Split pane state
  const [splitRatio, setSplitRatio] = useState(50)
  const splitContainerRef = useRef<HTMLDivElement>(null)
  const dragging = useRef(false)

  const handleSplitDrag = useCallback(() => {
    dragging.current = true
    document.body.style.cursor = 'col-resize'
    document.body.style.userSelect = 'none'

    const handleMouseMove = (e: MouseEvent) => {
      if (!dragging.current || !splitContainerRef.current) return
      const rect = splitContainerRef.current.getBoundingClientRect()
      const x = e.clientX - rect.left
      const pct = Math.max(20, Math.min(80, (x / rect.width) * 100))
      setSplitRatio(pct)
    }

    const handleMouseUp = () => {
      dragging.current = false
      document.body.style.cursor = ''
      document.body.style.userSelect = ''
      document.removeEventListener('mousemove', handleMouseMove)
      document.removeEventListener('mouseup', handleMouseUp)
      // Persist split ratio when drag finishes — read from the splitRatioRef.
      if (branchId) {
        savePref(branchId, { splitRatio: splitRatioRef.current })
      }
    }

    document.addEventListener('mousemove', handleMouseMove)
    document.addEventListener('mouseup', handleMouseUp)
  }, [branchId])

  // Ref tracking latest splitRatio for the drag-end persistence callback.
  const splitRatioRef = useRef(splitRatio)
  useEffect(() => { splitRatioRef.current = splitRatio }, [splitRatio])

  const styleId =
    branch?.style_preference && getStyleById(branch.style_preference)
      ? branch.style_preference
      : DEFAULT_STYLE_ID

  function handleStyleSelect(newStyleId: string) {
    if (!branch) return
    patchBranch.mutate({
      id: branch.id,
      input: { style_preference: newStyleId },
    })
  }

  // Load theme + apply accent color when branch changes (spec 027 US3)
  useEffect(() => {
    if (!branch) return
    const themeId = branch.theme_id ?? 'default'
    const accent = branch.accent_color ?? '#39393a'
    void loadTheme(themeId)
      .then(() => applyColor(accent))
      .catch((err) => console.error('Failed to load theme:', err))
  }, [branch?.id, branch?.theme_id, branch?.accent_color])

  // US7 FR-054/055: restore UI prefs (mode + splitRatio) on mount.
  useEffect(() => {
    if (!branchId) return
    const prefs = loadPref(branchId)
    if (prefs.mode && prefs.mode !== mode) {
      setMode(prefs.mode)
    }
    if (typeof prefs.splitRatio === 'number') {
      setSplitRatio(prefs.splitRatio)
    }
    // Restore scroll position after tick (FR-056).
    const rafId = requestAnimationFrame(() => {
      if (typeof prefs.scrollPos === 'number') {
        const container = document.querySelector<HTMLElement>('.resume-preview-container')
        if (container) container.scrollTop = prefs.scrollPos
      }
    })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [branchId])

  // Mode toggle: Quick ↔ Code
  const { mode, setMode, markdownContent, setMarkdownContent, switchToCode, switchToQuick } =
    useModeToggle({
      branch,
      blocks,
      onBlocksChange: useCallback(
        (newBlocks: ResumeBlock[]) => {
          // Persist each changed block
          newBlocks.forEach((b, i) => {
            const existing = blocks[i]
            if (
              !existing ||
              existing.content_md !== b.content_md ||
              existing.type !== b.type ||
              existing.title !== b.title
            ) {
              patchBlock.mutate({
                id: b.id,
                input: {
                  type: b.type,
                  title: b.title,
                  content_md: b.content_md,
                  meta: b.meta,
                },
              })
            }
          })
        },
        [blocks, patchBlock],
      ),
    })

  // Preview markdown: from code editor in code mode, or generated from blocks in quick mode
  const previewMarkdown = useMemo(() => {
    if (mode === 'code') return markdownContent
    if (!branch) return ''
    return blocksToMarkdown(
      { name: branch.name, company: branch.company, position: branch.position },
      blocks,
    )
  }, [mode, markdownContent, branch, blocks])

  function moveBlock(blockId: string, direction: -1 | 1) {
    const idx = blocks.findIndex((b) => b.id === blockId)
    if (idx < 0) return
    const targetIdx = idx + direction
    if (targetIdx < 0 || targetIdx >= blocks.length) return
    const prev = targetIdx > 0 ? blocks[targetIdx - 1].id : null
    const next = blocks[targetIdx + 1]?.id ?? null
    reorder.mutate({ id: blockId, input: { prev_id: prev, next_id: next } })
  }

  function onSaveVersion() {
    if (!label.trim()) return
    saveVersion.mutate(
      { label: label.trim() },
      {
        onSuccess: () => {
          setLabel('')
          setSaveOpen(false)
        },
      },
    )
  }

  function onRollback() {
    if (rollbackTarget == null) return
    rollbackVersion.mutate(
      { versionNo: rollbackTarget },
      {
        onSuccess: (res) => {
          setRollbackTarget(null)
          navigate(`/resume/${res.new_branch_id}`)
        },
      },
    )
  }

  function onAddBlock() {
    createBlock.mutate(
      { type: newBlockType, title: newBlockTitle || null, content_md: '' },
      {
        onSuccess: () => {
          setAddBlockOpen(false)
          setNewBlockTitle('')
          setNewBlockType('custom')
        },
      },
    )
  }

  function openEditBranch() {
    if (!branch) return
    setEditName(branch.name)
    setEditCompany(branch.company ?? '')
    setEditPosition(branch.position ?? '')
    setEditStatus(branch.status)
    setEditBranchOpen(true)
  }

  function onSaveBranch() {
    if (!branch || !editName.trim()) return
    patchBranch.mutate(
      {
        id: branch.id,
        input: {
          name: editName.trim(),
          company: editCompany.trim() || null,
          position: editPosition.trim() || null,
          status: editStatus,
        },
      },
      { onSuccess: () => setEditBranchOpen(false) },
    )
  }

  function autoSave(id: string, content_md: string) {
    patchBlock.mutate({ id, input: { content_md } })
  }

  // US7 FR-056: save scroll position of the preview container on scroll (debounced 500ms).
  useEffect(() => {
    if (!branchId) return
    const container = document.querySelector<HTMLElement>('.resume-preview-container')
    if (!container) return
    let t: ReturnType<typeof setTimeout>
    const handler = () => {
      clearTimeout(t)
      t = setTimeout(() => {
        savePref(branchId, { scrollPos: container.scrollTop })
      }, 500)
    }
    container.addEventListener('scroll', handler, { passive: true })
    return () => {
      clearTimeout(t)
      container.removeEventListener('scroll', handler)
    }
  }, [branchId])

  // US7 FR-051: push to local history 2s after edit idle (debounce).
  useEffect(() => {
    if (!branchId || !branch) return
    const t = setTimeout(() => {
      pushHistory(branchId, {
        markdown: previewMarkdown,
        themeId: branch.theme_id ?? 'default',
        accentColor: branch.accent_color ?? '#39393a',
        timestamp: Date.now(),
      })
    }, 2000)
    return () => clearTimeout(t)
  }, [branchId, branch, previewMarkdown])

  // Code mode auto-save: parse markdown and persist changed blocks
  function handleCodeAutoSave(md: string) {
    const parsed = markdownToBlocks(md)
    parsed.forEach((pb, i) => {
      const existing = blocks[i]
      if (
        !existing ||
        existing.content_md !== pb.content_md ||
        existing.type !== pb.type ||
        existing.title !== pb.title
      ) {
        patchBlock.mutate({
          id: existing?.id ?? `new-${i}`,
          input: {
            type: pb.type,
            title: pb.title,
            content_md: pb.content_md,
            meta: pb.meta as Record<string, unknown> | null,
          },
        })
      }
    })
  }

  // US7 FR-053: restore from local history entry (content, theme, colour).
  const handleRestoreHistory = useCallback((entry: HistoryEntry) => {
    if (!branchId || !branch) return

    const parsed = markdownToBlocks(entry.markdown)

    // Patch existing blocks by index, create any new ones beyond current count.
    parsed.forEach((pb, i) => {
      const existing = blocks[i]
      if (existing) {
        if (
          existing.content_md !== pb.content_md ||
          existing.type !== pb.type ||
          existing.title !== pb.title
        ) {
          patchBlock.mutate({
            id: existing.id,
            input: {
              type: pb.type,
              title: pb.title,
              content_md: pb.content_md,
              meta: pb.meta as Record<string, unknown> | null,
            },
          })
        }
      } else {
        createBlock.mutate({
          type: pb.type,
          title: pb.title || null,
          content_md: pb.content_md,
        })
      }
    })

    // Delete excess blocks that no longer exist in the restored state.
    if (parsed.length < blocks.length) {
      for (let i = parsed.length; i < blocks.length; i++) {
        deleteBlock.mutate(blocks[i].id)
      }
    }

    // Set markdown content for code mode, and switch to quick.
    setMarkdownContent(entry.markdown)
    setMode('quick')

    // Restore theme + accent colour (FR-053).
    void loadTheme(entry.themeId).then(() => applyColor(entry.accentColor))
    if (entry.themeId !== branch.theme_id || entry.accentColor !== branch.accent_color) {
      patchBranch.mutate({
        id: branch.id,
        input: { theme_id: entry.themeId, accent_color: entry.accentColor },
      })
    }
  }, [branchId, branch, blocks, patchBlock, createBlock, deleteBlock, patchBranch, setMarkdownContent, setMode])

  if (isLoading) {
    return <div className="p-8 text-sm text-ink-3">加载中…</div>
  }
  if (!branch) {
    return <div className="p-8 text-sm text-ink-3">未找到该简历</div>
  }

  const isReadonly = lock.status === 'readonly'

  return (
    <div className="h-screen flex flex-col">
      <UnifiedToolbar
        branchName={branch.name}
        branchId={branch.id}
        mode={mode}
        onModeChange={(newMode) => {
          if (newMode === 'code' && mode === 'quick') {
            switchToCode()
          } else if (newMode === 'quick' && mode === 'code') {
            switchToQuick()
          }
          // Persist mode preference (FR-054).
          if (branchId) savePref(branchId, { mode: newMode })
        }}
        versionCount={versions.length}
        onSaveVersion={() => setSaveOpen(true)}
        onOpenVersions={() => setVersionDrawerOpen(true)}
        onStyleSelect={() => setStyleSelectorOpen(true)}
        onExport={() => setExportMenuOpen(true)}
        onToggleSidebar={() => setSidebarOpen(true)}
        onOpenAvatar={() => setAvatarDialogOpen(true)}
        hasAvatar={Boolean(branch.avatar_url)}
        themeId={branch.theme_id ?? 'default'}
        onThemeSelect={(themeId) => {
          patchBranch.mutate({ id: branch.id, input: { theme_id: themeId } })
        }}
        accentColor={branch.accent_color ?? '#39393a'}
        onAccentColorChange={(hex) => {
          patchBranch.mutate({ id: branch.id, input: { accent_color: hex } })
        }}
        lockStatus={
          <LockIndicator
            status={lock.status}
            holder={lock.holder}
            onRelease={lock.release}
          />
        }
      />

      {/* Branch meta bar (edit pencil, company, status) */}
      <div className="px-4 py-1.5 border-b border-surface-border dark:border-dark-surface-border flex items-center gap-3 text-xs text-ink-3">
        {branch.is_main && (
          <Badge variant="brand">主简历</Badge>
        )}
        {branch.parent_id && !branch.is_main && (
          <Badge variant="default">派生分支</Badge>
        )}
        {!branch.parent_id && !branch.is_main && (
          <Badge variant="default">独立分支</Badge>
        )}
        {branch.company && <span>{branch.company}</span>}
        {branch.position && <span>{branch.position}</span>}
        <Badge variant={branch.status === 'ready' ? 'success' : branch.status === 'optimizing' ? 'warning' : branch.status === 'submitted' ? 'brand' : 'default'}>
          {STATUS_LABEL[branch.status]}
        </Badge>
        {branch.last_edited_at && <span>最后编辑 {timeAgo(branch.last_edited_at)}</span>}
        <button
          onClick={openEditBranch}
          className="p-0.5 rounded hover:bg-surface-muted text-ink-3 hover:text-ink-1"
          aria-label="编辑分支属性"
        >
          <Pencil className="h-3 w-3" />
        </button>
        <div className="flex-1" />
        {branch.parent_id && (
          <Button
            variant="ghost"
            size="sm"
            leftIcon={<RefreshCw className="h-3 w-3" />}
            onClick={() => setRefreshConfirmOpen(true)}
            disabled={refreshFromParent.isPending}
          >
            {refreshFromParent.isPending ? '同步中…' : '同步父级'}
          </Button>
        )}
      </div>

      {/* Editor area with sidebar */}
      <div className="flex-1 min-h-0 flex relative">
        {/* Main split pane */}
        <div ref={splitContainerRef} className="flex-1 min-w-0 flex">
          {/* Left: Editor */}
          <div className="min-h-0 overflow-y-auto" style={{ width: `${splitRatio}%` }}>
            {mode === 'quick' ? (
              <div className="px-6 py-4">
                <QuickEditor
                  blocks={blocks}
                  collapsedBlockIds={collapsedBlockIds}
                  onToggleCollapse={(id) => {
                    toggleCollapse(id)
                    patchBlock.mutate({ id, input: { collapsed: !collapsedBlockIds.has(id) } })
                  }}
                  onAutoSave={autoSave}
                  onDelete={(id) => deleteBlock.mutate(id)}
                  onMoveUp={(id) => moveBlock(id, -1)}
                  onMoveDown={(id) => moveBlock(id, 1)}
                  onReorder={(id, prevId, nextId) => reorder.mutate({ id, input: { prev_id: prevId, next_id: nextId } })}
                  onPatchMeta={(id, meta) => patchBlock.mutate({ id, input: { meta } })}
                  onPreviewLocate={setScrollToBlockId}
                  highlightedBlockId={editorHighlightedBlockId}
                  isReadonly={isReadonly}
                />
                {!isReadonly && (
                  <Button
                    variant="secondary"
                    leftIcon={<Plus className="h-3.5 w-3.5" />}
                    className="mt-4"
                    disabled={createBlock.isPending}
                    onClick={() => setAddBlockOpen(true)}
                    data-testid="add-block"
                  >
                    {createBlock.isPending ? '创建中…' : '添加模块'}
                  </Button>
                )}
              </div>
            ) : (
              <MarkdownEditor
                value={markdownContent}
                onChange={setMarkdownContent}
                readOnly={isReadonly}
                onAutoSave={handleCodeAutoSave}
                onSaveVersion={() => setSaveOpen(true)}
              />
            )}
          </div>

          {/* Drag handle */}
          <div
            onMouseDown={handleSplitDrag}
            className="w-2 cursor-col-resize bg-surface-border dark:bg-dark-surface-border hover:bg-brand-500/30 transition-colors flex-shrink-0"
            data-testid="split-handle"
          />

          {/* Right: Resume Preview */}
          <div className="overflow-hidden flex-1" style={{ width: `${100 - splitRatio}%` }}>
            <ResumePreview
              markdown={previewMarkdown}
              styleId={styleId}
              accentColor={branch.accent_color ?? '#39393a'}
              avatarUrl={branch.avatar_url ?? null}
              avatarSize={branch.avatar_size ?? null}
              avatarPosition={branch.avatar_position ?? null}
              avatarShape={branch.avatar_shape ?? null}
              blocks={mode === 'quick' ? blocks : undefined}
              scrollToBlockId={scrollToBlockId}
              onScrollToBlockHandled={() => setScrollToBlockId(null)}
              onBlockClick={setEditorHighlightedBlockId}
              locatorSuspended={locatorSuspended}
            />
          </div>
        </div>

        {/* Sidebar drawer backdrop */}
        {sidebarOpen && (
          <div className="fixed inset-0 z-20 bg-black/20" onClick={() => setSidebarOpen(false)} />
        )}
        {/* Sidebar drawer (slides from right, overlays preview) */}
        <div
          className={cn(
            'absolute top-0 right-0 h-full w-[340px] z-30 bg-surface dark:bg-dark-surface border-l border-surface-border dark:border-dark-surface-border overflow-y-auto transition-transform duration-200 shadow-lg',
            sidebarOpen ? 'translate-x-0' : 'translate-x-full',
          )}
        >
          <div className="flex items-center justify-between px-3 py-2 border-b border-surface-border dark:border-dark-surface-border">
            <span className="text-xs font-semibold text-ink-2">信息面板</span>
            <button
              onClick={() => setSidebarOpen(false)}
              className="p-0.5 rounded hover:bg-surface-muted text-ink-3 hover:text-ink-1"
              aria-label="关闭面板"
            >
              <PanelRight className="h-3.5 w-3.5" />
            </button>
          </div>
          <EditorSidebar
            branch={branch}
            versions={versions}
            styleId={styleId}
            onStyleSelect={handleStyleSelect}
            onVersionSelect={(versionNo) => {
              setVersionDrawerOpen(false)
              setViewVersionNo(versionNo)
            }}
            onRollback={() => {
              if (versions.length > 0) {
                const latest = [...versions].reverse()[0]
                setRollbackTarget(latest.version_no)
              }
            }}
            onSaveVersion={() => setSaveOpen(true)}
            onRestoreHistory={handleRestoreHistory}
          />
        </div>
      </div>

      {/* ---- Modals (shared across modes) ---- */}

      {/* Add block type selector modal */}
      <Modal
        open={addBlockOpen}
        onClose={() => setAddBlockOpen(false)}
        title="添加模块"
        size="sm"
        footer={
          <>
            <Button variant="ghost" onClick={() => setAddBlockOpen(false)}>
              取消
            </Button>
            <Button
              variant="primary"
              disabled={createBlock.isPending}
              onClick={onAddBlock}
            >
              {createBlock.isPending ? '创建中…' : '创建'}
            </Button>
          </>
        }
      >
        <div className="space-y-3">
          <div>
            <label className="block text-xs font-medium text-ink-2 mb-1.5">类型</label>
            <div className="grid grid-cols-2 gap-1.5">
              {BLOCK_TYPES.map((t) => (
                <button
                  key={t.value}
                  onClick={() => setNewBlockType(t.value)}
                  className={cn(
                    'px-2 py-1.5 text-xs rounded border text-left transition-colors',
                    newBlockType === t.value
                      ? 'border-brand-500 bg-brand-50 dark:bg-brand-500/10 text-brand-700 dark:text-brand-300'
                      : 'border-surface-border dark:border-dark-surface-border text-ink-2 hover:border-ink-3',
                  )}
                >
                  {t.label}
                </button>
              ))}
            </div>
          </div>
          <div>
            <label className="block text-xs font-medium text-ink-2 mb-1.5">标题（可选）</label>
            <Input
              value={newBlockTitle}
              onChange={(e) => setNewBlockTitle(e.target.value)}
              placeholder="模块标题"
            />
          </div>
        </div>
      </Modal>

      {/* Save version modal */}
      <Modal
        open={saveOpen}
        onClose={() => setSaveOpen(false)}
        title="保存版本快照"
        description="会创建一个完整快照，未来可一键回滚"
        size="sm"
        footer={
          <>
            <Button variant="ghost" onClick={() => setSaveOpen(false)}>
              取消
            </Button>
            <Button
              variant="primary"
              disabled={!label.trim() || saveVersion.isPending}
              onClick={onSaveVersion}
              data-testid="save-version-confirm"
            >
              {saveVersion.isPending ? '保存中…' : '保存'}
            </Button>
          </>
        }
      >
        <Input
          value={label}
          onChange={(e) => setLabel(e.target.value)}
          placeholder="例如：加入字节经验"
          maxLength={64}
          data-testid="version-label"
          autoFocus
        />
      </Modal>

      {/* Version history drawer */}
      <Modal
        open={versionDrawerOpen}
        onClose={() => setVersionDrawerOpen(false)}
        title="版本历史"
        description="点击「回滚」会基于该版本创建新分支（不破坏当前分支）"
        size="md"
        footer={
          <Button variant="ghost" onClick={() => setVersionDrawerOpen(false)}>
            关闭
          </Button>
        }
      >
        {versions.length === 0 ? (
          <p className="text-sm text-ink-3 py-4 text-center">还没有历史版本</p>
        ) : (
          <>
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs text-ink-3">
                {diffSelected.length > 0 ? `已选 ${diffSelected.length}/2 个版本` : '勾选两个版本可对比差异'}
              </span>
              {diffSelected.length === 2 && (
                <Button
                  size="sm"
                  variant="primary"
                  leftIcon={<GitCompare className="h-3 w-3" />}
                  onClick={() => {
                    setDiffOpen(true)
                    setVersionDrawerOpen(false)
                  }}
                  data-testid="diff-compare"
                >
                  对比选择
                </Button>
              )}
              {diffSelected.length > 0 && diffSelected.length !== 2 && (
                <Button
                  size="sm"
                  variant="ghost"
                  onClick={() => setDiffSelected([])}
                >
                  清除
                </Button>
              )}
            </div>
            <ul className="divide-y divide-surface-border dark:divide-dark-surface-border">
              {[...versions].reverse().map((v) => (
                <li key={v.id} className="py-3 flex items-center justify-between gap-3" data-testid={`version-${v.version_no}`}>
                  <div className="min-w-0 flex-1 flex items-center gap-3">
                    <input
                      type="checkbox"
                      className="rounded border-surface-border dark:border-dark-surface-border text-brand-500 focus:ring-brand-500 h-4 w-4"
                      checked={diffSelected.includes(v.version_no)}
                      onChange={() => {
                        setDiffSelected((prev) =>
                          prev.includes(v.version_no)
                            ? prev.filter((n) => n !== v.version_no)
                            : prev.length < 2
                              ? [...prev, v.version_no]
                              : prev, // max 2
                        )
                      }}
                      data-testid={`diff-chk-${v.version_no}`}
                    />
                    <div>
                      <div className="text-sm font-medium text-ink-1">
                        v{v.version_no} {v.label ? `· ${v.label}` : '· 未命名'}
                      </div>
                      <div className="text-2xs text-ink-3 mt-0.5">
                        {v.author_type === 'ai' ? 'AI 自动' : '手动'} · {timeAgo(v.created_at)} · {v.is_full_snapshot ? '完整快照' : '差异补丁'}
                      </div>
                    </div>
                  </div>
                  <div className="flex items-center gap-1 flex-shrink-0">
                    <Button
                      size="sm"
                      variant="ghost"
                      leftIcon={<Eye className="h-3 w-3" />}
                      onClick={() => setViewVersionNo(v.version_no)}
                      data-testid={`view-${v.version_no}`}
                    >
                      查看
                    </Button>
                    <Button
                      size="sm"
                      variant="secondary"
                      leftIcon={<RotateCcw className="h-3 w-3" />}
                      onClick={() => {
                        setVersionDrawerOpen(false)
                        setRollbackTarget(v.version_no)
                      }}
                      data-testid={`rollback-${v.version_no}`}
                    >
                      回滚
                    </Button>
                  </div>
                </li>
              ))}
            </ul>
          </>
        )}
      </Modal>

      {/* Version detail viewer modal */}
      <Modal
        open={viewVersionNo !== null}
        onClose={() => setViewVersionNo(null)}
        title={`版本详情 v${viewVersionNo}`}
        size="md"
        footer={
          <Button variant="ghost" onClick={() => setViewVersionNo(null)}>
            关闭
          </Button>
        }
      >
        {versionDetail ? (
          <div className="space-y-3">
            <div className="text-sm text-ink-2">
              <strong>{versionDetail.label ?? '未命名'}</strong>
              <span className="text-ink-3 ml-2">
                {versionDetail.author_type === 'ai' ? 'AI 自动保存' : '手动保存'} · {timeAgo(versionDetail.created_at)}
              </span>
            </div>
            {versionDetail.snapshot.branch && (
              <div className="text-xs text-ink-3 p-2 rounded bg-surface-muted dark:bg-dark-surface-muted">
                <p><strong>分支：</strong>{versionDetail.snapshot.branch.name}</p>
                {versionDetail.snapshot.branch.company && <p>公司：{versionDetail.snapshot.branch.company}</p>}
                {versionDetail.snapshot.branch.position && <p>职位：{versionDetail.snapshot.branch.position}</p>}
                <p>状态：{versionDetail.snapshot.branch.status}</p>
              </div>
            )}
            <div className="text-xs font-medium text-ink-2">
              快照模块 ({versionDetail.snapshot.blocks.length})
            </div>
            <ul className="space-y-1.5 max-h-64 overflow-y-auto">
              {versionDetail.snapshot.blocks.map((sb) => (
                <li key={sb.id} className="text-xs p-2 rounded border border-surface-border dark:border-dark-surface-border">
                  <div className="flex items-center gap-1.5 mb-0.5">
                    <Badge variant="default">{sb.type}</Badge>
                    {sb.title && <span className="font-medium text-ink-1">{sb.title}</span>}
                  </div>
                  <p className="text-ink-3 line-clamp-2 whitespace-pre-wrap">{sb.content_md}</p>
                </li>
              ))}
            </ul>
          </div>
        ) : (
          <p className="text-sm text-ink-3 py-4 text-center">加载中…</p>
        )}
      </Modal>

      {/* US7 Version diff modal */}
      <VersionDiffView
        open={diffOpen}
        onClose={() => {
          setDiffOpen(false)
          setDiffSelected([])
        }}
        diff={versionDiff ?? null}
        loading={diffLoading}
      />

      {/* Rollback confirmation modal */}
      <Modal
        open={rollbackTarget !== null}
        onClose={() => setRollbackTarget(null)}
        title="确认回滚"
        description={`将基于 v${rollbackTarget} 创建一个新分支，原分支内容不变`}
        size="sm"
        footer={
          <>
            <Button variant="ghost" onClick={() => setRollbackTarget(null)}>
              取消
            </Button>
            <Button
              variant="primary"
              disabled={rollbackVersion.isPending}
              onClick={onRollback}
              data-testid="rollback-confirm"
            >
              {rollbackVersion.isPending ? '回滚中…' : '确认回滚'}
            </Button>
          </>
        }
      >
        <p className="text-sm text-ink-2">新分支名称：回滚 v{rollbackTarget}</p>
      </Modal>

      {/* Refresh from parent confirm dialog (US6 FR-044) */}
      <Modal
        open={refreshConfirmOpen}
        onClose={() => setRefreshConfirmOpen(false)}
        title="确认同步父级"
        description="此操作将覆盖当前分支的所有本地修改，是否继续？"
        size="sm"
        footer={
          <>
            <Button variant="ghost" onClick={() => setRefreshConfirmOpen(false)}>
              取消
            </Button>
            <Button
              variant="primary"
              disabled={refreshFromParent.isPending}
              onClick={() => {
                setRefreshConfirmOpen(false)
                refreshFromParent.mutate()
              }}
              data-testid="refresh-parent-confirm"
            >
              {refreshFromParent.isPending ? '同步中…' : '确认同步'}
            </Button>
          </>
        }
      >
        <p className="text-sm text-ink-2">
          当前分支的所有本地修改将被父分支的最新内容覆盖。此操作不可撤销。
        </p>
      </Modal>

      {/* Edit branch modal */}
      <Modal
        open={editBranchOpen}
        onClose={() => setEditBranchOpen(false)}
        title="编辑分支属性"
        size="md"
        footer={
          <>
            <Button variant="ghost" onClick={() => setEditBranchOpen(false)}>
              取消
            </Button>
            <Button
              variant="primary"
              disabled={!editName.trim() || patchBranch.isPending}
              onClick={onSaveBranch}
            >
              {patchBranch.isPending ? '保存中…' : '保存'}
            </Button>
          </>
        }
      >
        <div className="space-y-3">
          <div>
            <label className="block text-xs font-medium text-ink-2 mb-1.5">名称</label>
            <Input value={editName} onChange={(e) => setEditName(e.target.value)} autoFocus />
          </div>
          <div>
            <label className="block text-xs font-medium text-ink-2 mb-1.5">公司</label>
            <Input value={editCompany} onChange={(e) => setEditCompany(e.target.value)} placeholder="（可选）" />
          </div>
          <div>
            <label className="block text-xs font-medium text-ink-2 mb-1.5">职位</label>
            <Input value={editPosition} onChange={(e) => setEditPosition(e.target.value)} placeholder="（可选）" />
          </div>
          <div>
            <label className="block text-xs font-medium text-ink-2 mb-1.5">状态</label>
            <select
              className="w-full h-9 px-3 text-sm rounded-md border border-surface-border dark:border-dark-surface-border bg-surface dark:bg-dark-surface text-ink-1"
              value={editStatus}
              onChange={(e) => setEditStatus(e.target.value as BranchStatus)}
            >
              {Object.entries(STATUS_LABEL).map(([k, v]) => (
                <option key={k} value={k}>{v}</option>
              ))}
            </select>
          </div>
        </div>
      </Modal>

      <OfflineBanner />

      {/* Phase 5 M16: AI Optimize button in branch meta bar */}
      {branch.id && (
        <div className="absolute top-0 right-0 mt-1 mr-2">
          <AiOptimizePanel
            branchId={branch.id}
            onOptimized={() => {
              qc.invalidateQueries({ queryKey: BLOCKS_KEY(branchId!) })
              qc.invalidateQueries({ queryKey: BRANCH_KEY(branchId!) })
            }}
          />
        </div>
      )}

      {/* Style selector popover (for small screens without sidebar) */}
      <StyleSelector
        selectedStyleId={styleId}
        onSelect={handleStyleSelect}
        open={styleSelectorOpen}
        onClose={() => setStyleSelectorOpen(false)}
      />

      {/* Export menu popover */}
      <ExportMenu
        branch={branch}
        blocks={blocks}
        styleId={styleId}
        markdown={mode === 'code' ? markdownContent : undefined}
        open={exportMenuOpen}
        onClose={() => setExportMenuOpen(false)}
      />

      {/* Avatar dialog (spec 027 US9) */}
      <AvatarDialog
        open={avatarDialogOpen}
        onClose={() => setAvatarDialogOpen(false)}
        branch={branch}
        onSave={(patch) => {
          patchBranch.mutate({ id: branch.id, input: patch })
        }}
      />
    </div>
  )
}
